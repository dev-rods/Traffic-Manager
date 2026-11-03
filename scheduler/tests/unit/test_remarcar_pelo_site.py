# -*- coding: utf-8 -*-
"""Remarcar pelo site (PRD 035): mesmo registro, nova data, nenhum CANCELLED.

E a grade oferecida para remarcar não pode ser ocupada pelo próprio
agendamento, senão mover 10:00 para 10:30 no mesmo dia colide consigo mesmo.
"""
import json
import os
import unittest
from datetime import datetime
from unittest import mock

import pytz

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.public_booking import reschedule_appointment as mod
from src.services.availability_engine import AvailabilityEngine

CLINIC = "clinica-1"
APPT = "11111111-1111-1111-1111-111111111111"
AGORA = datetime(2026, 10, 20, 10, 0, tzinfo=pytz.utc)


def evento(body):
    return {
        "headers": {"x-api-key": "k"},
        "pathParameters": {"clinicId": CLINIC, "appointmentId": APPT},
        "body": json.dumps(body),
    }


def corpo(r):
    return json.loads(r["body"])


BODY = {"phone": "5511999990000", "token": "t", "date": "2026-10-22", "time": "14:00"}


class _Base(unittest.TestCase):

    def setUp(self):
        self.db = mock.MagicMock()
        self.db.execute_query.side_effect = self.query
        self.service = mock.MagicMock()
        self.service.reschedule_appointment.return_value = {
            "id": APPT, "appointment_date": "2026-10-22", "status": "CONFIRMED"}
        self.dono = True
        patches = [
            mock.patch.object(mod, "require_booking_intake_api_key", return_value=("k", None)),
            mock.patch.object(mod, "verify_token", return_value=True),
            mock.patch.object(mod, "PostgresService", return_value=self.db),
            mock.patch.object(mod.AppointmentService, "completo", return_value=self.service),
            mock.patch.object(mod.relogio, "agora_na_clinica",
                              return_value=AGORA.astimezone(pytz.timezone("America/Sao_Paulo"))),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)

    def query(self, sql, params=None):
        if "FROM scheduler.clinics" in sql:
            return [{"timezone": "America/Sao_Paulo"}]
        if "FROM scheduler.appointments a" in sql:
            return [{"id": APPT}] if self.dono else []
        return []

    def chama(self, body=BODY):
        return mod.handler(evento(body), None)


class TestRemarcar(_Base):

    def test_sucesso_mantem_o_id_e_chama_o_reschedule_em_lugar(self):
        r = self.chama()
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(corpo(r)["appointment"]["id"], APPT)
        self.service.reschedule_appointment.assert_called_once_with(APPT, "2026-10-22", "14:00")
        self.service.cancel_appointment.assert_not_called()
        self.service.create_appointment.assert_not_called()

    def test_hora_com_segundos_e_aceita(self):
        self.chama({**BODY, "time": "14:00:00"})
        self.service.reschedule_appointment.assert_called_once_with(APPT, "2026-10-22", "14:00")

    def test_agendamento_de_outro_telefone_e_404(self):
        self.dono = False
        self.assertEqual(self.chama()["statusCode"], 404)
        self.service.reschedule_appointment.assert_not_called()

    def test_token_invalido_e_401(self):
        with mock.patch.object(mod, "verify_token", return_value=False):
            self.assertEqual(self.chama()["statusCode"], 401)
        self.service.reschedule_appointment.assert_not_called()

    def test_data_ilegivel_e_400(self):
        for body in ({**BODY, "date": "22/10/2026"}, {**BODY, "time": "2pm"}, {k: v for k, v in BODY.items() if k != "date"}):
            with self.subTest(body=body):
                self.assertEqual(self.chama(body)["statusCode"], 400)
        self.service.reschedule_appointment.assert_not_called()

    def test_horario_passado_e_400(self):
        self.assertEqual(self.chama({**BODY, "date": "2026-10-19"})["statusCode"], 400)
        self.service.reschedule_appointment.assert_not_called()

    def test_conflito_e_409_com_mensagem_para_a_pessoa(self):
        from src.services.appointment_service import ConflictError, OptimisticLockError
        for erro in (ConflictError("x"), OptimisticLockError("y")):
            with self.subTest(erro=type(erro).__name__):
                self.service.reschedule_appointment.side_effect = erro
                r = self.chama()
                self.assertEqual(r["statusCode"], 409)
                self.assertEqual(corpo(r)["message"], mod.MENSAGEM_CONFLITO)

    def test_sem_phone_ou_token_e_400(self):
        self.assertEqual(self.chama({"date": "2026-10-22", "time": "14:00"})["statusCode"], 400)


class TestGradeIgnoraOProprioAgendamento(unittest.TestCase):

    def _db(self):
        db = mock.MagicMock()
        db.execute_query.return_value = []
        return db

    def test_com_id_a_consulta_de_ocupacao_exclui_o_registro(self):
        db = self._db()
        engine = AvailabilityEngine(db, ignorar_agendamento=APPT)
        engine._janelas_das_regras(CLINIC, "2026-10-22", [], 0)
        sql, params = db.execute_query.call_args[0]
        self.assertIn("AND id <> %s::uuid", sql)
        self.assertEqual(params[-1], APPT)

    def test_sem_id_a_consulta_e_a_de_sempre(self):
        db = self._db()
        AvailabilityEngine(db)._janelas_das_regras(CLINIC, "2026-10-22", [], 0)
        sql, params = db.execute_query.call_args[0]
        self.assertNotIn("id <>", sql)
        self.assertEqual(params, (CLINIC, "2026-10-22"))

    def test_o_endpoint_publico_repassa_o_parametro(self):
        from src.functions.public_booking import availability as av
        capturado = {}

        class EngineEspiao:
            def __init__(self, db, ignorar_agendamento=None):
                capturado["ignorar"] = ignorar_agendamento

        db = mock.MagicMock()
        db.execute_query.return_value = [{"timezone": "America/Sao_Paulo", "max_future_dates": 5}]
        with mock.patch.object(av, "require_booking_intake_api_key", return_value=("k", None)), \
             mock.patch.object(av, "PostgresService", return_value=db), \
             mock.patch.object(av, "AvailabilityEngine", EngineEspiao), \
             mock.patch.object(av.janela_do_site, "dias_oferecidos", return_value={}):
            r = av.handler({
                "headers": {"x-api-key": "k"},
                "pathParameters": {"clinicId": CLINIC},
                "queryStringParameters": {"totalDuration": "30", "excludeAppointmentId": APPT},
            }, None)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(capturado["ignorar"], APPT)


class TestListagemTrazOCarrinho(unittest.TestCase):

    def test_my_appointments_devolve_service_ids_e_pares(self):
        from src.services.appointment_service import AppointmentService
        db = mock.MagicMock()
        db.execute_query.return_value = []
        AppointmentService(db).get_active_appointments_by_phone(CLINIC, "5511999990000")
        sql = db.execute_query.call_args[0][0]
        self.assertIn("AS service_ids", sql)
        self.assertIn("AS service_area_pairs", sql)
        self.assertIn("'serviceId', asa.service_id", sql)


if __name__ == "__main__":
    unittest.main()
