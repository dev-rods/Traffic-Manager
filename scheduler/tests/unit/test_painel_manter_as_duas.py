# -*- coding: utf-8 -*-
"""Pelo painel, a única exceção à regra de uma sessão por mês é "manter as
duas", e é de ADMIN com motivo (PRD 056). STAFF leva 403; ADMIN sem motivo,
400. O 409 do conflito traz a sessão existente, com o nome, para o aviso.
"""
import json
import unittest
from unittest import mock

from src.services.appointment_service import OutraSessaoFutura, SessaoNoMesmoMes
from src.services.mesmo_mes import OTHER_MONTH_APPOINTMENT, excecao_das_duas, resposta_409
from src.utils.acesso import ADMIN, STAFF, Identidade

_ADMIN = Identidade(papel=ADMIN, chave_mestra=True, nome="Dra. Clara")
_STAFF = Identidade(papel=STAFF, user_id="u1", clinic_id="c", nome="Recepção")

CLINIC = "clinicaessenciaestetica-9668a4"
EXISTENTE = {"id": "x1", "appointment_date": "2026-11-25", "start_time": "14:00:00",
             "areas_display": "Axilas", "patient_name": "Ana"}
BASE = {"clinicId": CLINIC, "phone": "5511970522647", "serviceId": "s1",
        "date": "2026-11-28", "time": "10:00", "fullName": "Ana"}


def _duble(servico):
    classe = mock.MagicMock()
    classe.completo.return_value = servico
    classe.return_value = servico
    return classe


def _corpo(r):
    return json.loads(r["body"])


class TestExcecao(unittest.TestCase):
    def test_sem_o_campo_nada_muda(self):
        self.assertEqual(excecao_das_duas(_STAFF, {}), (False, None))
        self.assertEqual(excecao_das_duas(_ADMIN, {"manterAsDuas": "true"}), (False, None))

    def test_staff_403(self):
        duas, erro = excecao_das_duas(_STAFF, {"manterAsDuas": True, "motivoDasDuas": "x"})
        self.assertFalse(duas)
        self.assertEqual(erro["statusCode"], 403)

    def test_admin_sem_motivo_400(self):
        duas, erro = excecao_das_duas(_ADMIN, {"manterAsDuas": True, "motivoDasDuas": "  "})
        self.assertFalse(duas)
        self.assertEqual(erro["statusCode"], 400)

    def test_admin_com_motivo_passa(self):
        self.assertEqual(excecao_das_duas(_ADMIN, {"manterAsDuas": True, "motivoDasDuas": "pele"}), (True, None))

    def test_409_leva_a_sessao_e_o_nome(self):
        r = resposta_409(EXISTENTE)
        self.assertEqual(r["statusCode"], 409)
        self.assertEqual(_corpo(r)["code"], "SAME_MONTH_APPOINTMENT")
        self.assertEqual(_corpo(r)["existing"], {"id": "x1", "date": "2026-11-25", "time": "14:00",
                                                 "areas": "Axilas", "patientName": "Ana"})


class TestCriarPeloPainel(unittest.TestCase):
    def chama(self, corpo, identidade=_ADMIN, servico=None):
        from src.functions.appointment import create as modulo
        evento = {"pathParameters": {"clinicId": CLINIC}, "headers": {"x-api-key": "k"}, "body": json.dumps(corpo)}
        service = servico or mock.MagicMock()
        if servico is None:
            service.create_appointment.return_value = {"id": "ap1"}
        with mock.patch.object(modulo, "require_acesso", return_value=(identidade, None)), \
             mock.patch.object(modulo, "PostgresService"), \
             mock.patch.object(modulo, "AppointmentService", _duble(service)), \
             mock.patch.object(modulo, "_serialize_row", side_effect=lambda r: r):
            return modulo.handler(evento, None), service

    def test_conflito_vira_409_com_a_existente(self):
        service = mock.MagicMock()
        service.create_appointment.side_effect = SessaoNoMesmoMes(EXISTENTE)
        r, _ = self.chama(dict(BASE), servico=service)
        self.assertEqual(r["statusCode"], 409)
        self.assertEqual(_corpo(r)["existing"]["patientName"], "Ana")

    def test_substituir_passa_ao_servico_com_o_autor(self):
        r, service = self.chama(dict(BASE, substituir=True))
        self.assertEqual(r["statusCode"], 201)
        kw = service.create_appointment.call_args.kwargs
        self.assertIs(kw["substituir_mesmo_mes"], True)
        self.assertIs(kw["permitir_duas"], False)
        self.assertEqual(kw["autor"], "Dra. Clara")

    def test_staff_nao_mantem_as_duas(self):
        r, service = self.chama(dict(BASE, manterAsDuas=True, motivoDasDuas="x"), identidade=_STAFF)
        self.assertEqual(r["statusCode"], 403)
        service.create_appointment.assert_not_called()

    def test_admin_sem_motivo_400(self):
        r, service = self.chama(dict(BASE, manterAsDuas=True))
        self.assertEqual(r["statusCode"], 400)
        service.create_appointment.assert_not_called()

    def test_admin_com_motivo_passa_permitir_duas(self):
        r, service = self.chama(dict(BASE, manterAsDuas=True, motivoDasDuas="duas áreas separadas"))
        self.assertEqual(r["statusCode"], 201)
        kw = service.create_appointment.call_args.kwargs
        self.assertIs(kw["permitir_duas"], True)
        self.assertEqual(kw["motivo_das_duas"], "duas áreas separadas")


    # -- Sessao futura em OUTRO mes (PRD 060) --------------------------------

    def test_outro_mes_vira_409_proprio_com_a_existente(self):
        service = mock.MagicMock()
        service.create_appointment.side_effect = OutraSessaoFutura(dict(EXISTENTE, appointment_date="2026-12-10"))
        r, _ = self.chama(dict(BASE), servico=service)
        self.assertEqual(r["statusCode"], 409)
        self.assertEqual(_corpo(r)["code"], OTHER_MONTH_APPOINTMENT)
        self.assertEqual(_corpo(r)["existing"]["date"], "2026-12-10")
        self.assertEqual(_corpo(r)["existing"]["patientName"], "Ana")
        self.assertIn("outro mês", _corpo(r)["message"])

    def test_remarcar_existente_e_mais_uma_chegam_ao_servico_sem_admin(self):
        # STAFF da propria clinica: a 060 nao pede ADMIN nem motivo.
        recepcao = Identidade(papel=STAFF, user_id="u1", clinic_id=CLINIC, nome="Recepção")
        r, service = self.chama(dict(BASE, remarcarExistente=True), identidade=recepcao)
        self.assertEqual(r["statusCode"], 201)
        kw = service.create_appointment.call_args.kwargs
        self.assertIs(kw["remarcar_a_existente"], True)
        self.assertIs(kw["mais_uma"], False)
        r, service = self.chama(dict(BASE, maisUma=True), identidade=recepcao)
        self.assertEqual(r["statusCode"], 201)
        kw = service.create_appointment.call_args.kwargs
        self.assertIs(kw["mais_uma"], True)
        self.assertIs(kw["remarcar_a_existente"], False)
        self.assertIs(kw["permitir_duas"], False)

    def test_as_flags_so_valem_como_true_literal(self):
        r, service = self.chama(dict(BASE, remarcarExistente="true", maisUma=1))
        kw = service.create_appointment.call_args.kwargs
        self.assertIs(kw["remarcar_a_existente"], False)
        self.assertIs(kw["mais_uma"], False)


class TestMoverPeloPainel(unittest.TestCase):
    def chama(self, corpo, identidade=_ADMIN):
        from src.functions.appointment import update as modulo
        evento = {"pathParameters": {"appointmentId": "ap1"}, "headers": {"x-api-key": "k"}, "body": json.dumps(corpo)}
        db = mock.MagicMock()
        db.execute_query.return_value = [{"appointment_date": "2026-12-02", "start_time": "10:00:00"}]
        service = mock.MagicMock()
        service.remarca.return_value = {"antigo": {"id": "ap1", "outcome": "CANCELLED"}, "novo": {"id": "ap2"}}
        with mock.patch.object(modulo, "require_acesso", return_value=(identidade, None)), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "pode_tocar_agendamento", return_value=True), \
             mock.patch.object(modulo, "dentro_da_janela", return_value=True), \
             mock.patch.object(modulo, "AppointmentService", _duble(service)), \
             mock.patch.object(modulo, "_serialize_row", side_effect=lambda r: r):
            return modulo.handler(evento, None), service

    def test_substituir_chega_ao_remarca(self):
        r, service = self.chama({"date": "2026-11-28", "time": "10:00", "substituir": True})
        self.assertEqual(r["statusCode"], 200)
        kw = service.remarca.call_args.kwargs
        self.assertIs(kw["substituir_mesmo_mes"], True)
        self.assertIs(kw["permitir_duas"], False)

    def test_staff_nao_mantem_as_duas_ao_mover(self):
        r, service = self.chama({"date": "2026-11-28", "manterAsDuas": True, "motivoDasDuas": "x"}, identidade=_STAFF)
        self.assertEqual(r["statusCode"], 403)
        service.remarca.assert_not_called()

    def test_conflito_ao_mover_vira_409(self):
        from src.functions.appointment import update as modulo
        evento = {"pathParameters": {"appointmentId": "ap1"}, "headers": {"x-api-key": "k"},
                  "body": json.dumps({"date": "2026-11-28", "time": "10:00"})}
        db = mock.MagicMock()
        db.execute_query.return_value = [{"appointment_date": "2026-12-02", "start_time": "10:00:00"}]
        service = mock.MagicMock()
        service.remarca.side_effect = SessaoNoMesmoMes(EXISTENTE)
        with mock.patch.object(modulo, "require_acesso", return_value=(_ADMIN, None)), \
             mock.patch.object(modulo, "PostgresService", return_value=db), \
             mock.patch.object(modulo, "pode_tocar_agendamento", return_value=True), \
             mock.patch.object(modulo, "dentro_da_janela", return_value=True), \
             mock.patch.object(modulo, "AppointmentService", _duble(service)):
            r = modulo.handler(evento, None)
        self.assertEqual(r["statusCode"], 409)
        self.assertEqual(_corpo(r)["code"], "SAME_MONTH_APPOINTMENT")


if __name__ == "__main__":
    unittest.main()
