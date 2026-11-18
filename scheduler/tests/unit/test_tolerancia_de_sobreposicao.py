# -*- coding: utf-8 -*-
"""Edição pelo painel tolera até 15 min de sobreposição (PRD 049).

Uma regra, um lugar: `AppointmentService._conflitos` mede, por vizinha, quanto
a janela nova a invade (LEAST dos fins - GREATEST dos inícios) e só acusa
quando passa de `tolerancia_minutos`. Com 0 é a regra de sempre; só o handler
do painel passa 15. O banco falso abaixo APLICA o SQL do helper sobre uma
agenda fixa, para o teste conferir a regra e não o texto.
"""
import inspect
import os
import re
import unittest
from datetime import date
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "t")

from src.functions.appointment import update as handler_mod
from src.services.appointment_service import AppointmentService, ConflictError
from src.utils.acesso import ADMIN, Identidade

CLINIC = "c"
DIA = "2026-11-25"
APPT = "11111111-1111-1111-1111-111111111111"
_ADMIN = Identidade(papel=ADMIN, chave_mestra=True)


def _min(hhmm):
    h, m = hhmm.split(":")[:2]
    return int(h) * 60 + int(m)


class Agenda:
    """Vizinhas do dia: 12:40-13:00 (20 min) e 13:30-13:45 (15 min).
    Executa a mesma conta do SQL do helper, lendo os parâmetros."""

    VIZINHAS = [("viz-a", "12:40", "13:00"), ("viz-b", "13:30", "13:45")]

    def __init__(self):
        self.sqls = []

    def execute_query(self, sql, params=None):
        self.sqls.append((sql, params))
        assert "LEAST(end_time" in sql and "GREATEST(start_time" in sql
        assert "start_time >= " not in sql, "a terceira cláusula redundante voltou"
        params = list(params)
        excluir = None
        if "id != %s::uuid" in sql:
            excluir = params.pop(2)
        _, _, fim, inicio, fim2, inicio2, tolerancia = params
        assert (fim, inicio) == (fim2, inicio2)
        achados = []
        for vid, vi, vf in self.VIZINHAS:
            if vid == excluir:
                continue
            if not (_min(vi) < _min(fim) and _min(vf) > _min(inicio)):
                continue
            sobreposicao = min(_min(vf), _min(fim)) - max(_min(vi), _min(inicio))
            if sobreposicao > int(tolerancia):
                achados.append({"id": vid})
        return achados


class TestHelper(unittest.TestCase):
    def setUp(self):
        self.db = Agenda()
        self.svc = AppointmentService(self.db)

    def conflitos(self, inicio, fim, tolerancia=0, excluir=None):
        return [r["id"] for r in self.svc._conflitos(CLINIC, DIA, inicio, fim,
                                                      excluir_id=excluir, tolerancia_minutos=tolerancia)]

    def test_sem_tolerancia_e_a_regra_de_sempre(self):
        self.assertEqual(self.conflitos("12:30", "12:45"), ["viz-a"])
        self.assertEqual(self.conflitos("12:30", "12:40"), [], "encostar não conflita")
        self.assertEqual(self.conflitos("13:00", "13:30"), [], "entre as duas, encostando nas duas")

    def test_quinze_minutos_passam_dezesseis_nao(self):
        self.assertEqual(self.conflitos("12:30", "12:55", 15), [])
        self.assertEqual(self.conflitos("12:30", "12:56", 15), ["viz-a"])

    def test_invadir_pela_frente_tambem_vale(self):
        # Começa dentro da vizinha anterior: 12:50-13:20 invade viz-a em 10.
        self.assertEqual(self.conflitos("12:50", "13:20", 15), [])
        self.assertEqual(self.conflitos("12:44", "13:20", 15), ["viz-a"])

    def test_vizinha_curta_inteira_dentro_da_invasao(self):
        # viz-b tem 15 min: engolida inteira, a sobreposição é 15 e passa.
        self.assertEqual(self.conflitos("13:20", "13:50", 15), [])
        # viz-a tem 20: engolida inteira passa de 15.
        self.assertEqual(self.conflitos("12:30", "13:10", 15), ["viz-a"])

    def test_duas_vizinhas_medidas_separadamente(self):
        # 12:50-13:40: invade viz-a em 10 e viz-b em 10. Cada uma dentro do limite.
        self.assertEqual(self.conflitos("12:50", "13:40", 15), [])
        self.assertEqual(self.conflitos("12:50", "13:40", 5), ["viz-a", "viz-b"])

    def test_exclui_a_propria_sessao(self):
        self.assertEqual(self.conflitos("12:40", "13:00", 0, excluir="viz-a"), [])

    def test_parametros_na_ordem_que_os_fakes_antigos_leem(self):
        self.svc._conflitos(CLINIC, DIA, "12:30", "12:45", excluir_id=APPT, tolerancia_minutos=15)
        _, params = self.db.sqls[-1]
        self.assertEqual(params[:5], (CLINIC, DIA, APPT, "12:45", "12:30"))
        self.assertEqual(params[-1], 15)


class TestPadraoZero(unittest.TestCase):
    """Bot e site chamam os métodos sem a tolerância: o padrão tem de ser 0."""

    def test_metodos_de_edicao_nascem_sem_tolerancia(self):
        for nome in ("reschedule_appointment", "update_appointment_services", "set_manual_duration"):
            parametro = inspect.signature(getattr(AppointmentService, nome)).parameters["tolerancia_minutos"]
            self.assertEqual(parametro.default, 0, nome)

    def test_criacao_nao_tem_tolerancia(self):
        self.assertNotIn("tolerancia_minutos",
                         inspect.signature(AppointmentService.create_appointment).parameters)

    def test_mensagem_cita_o_limite_so_quando_ha_tolerancia(self):
        padrao = "Conflito de horário no novo slot: x"
        self.assertEqual(AppointmentService._mensagem_de_conflito(padrao, 0, DIA, "12:30", "12:56"), padrao)
        com = AppointmentService._mensagem_de_conflito(padrao, 15, DIA, "12:30", "12:56")
        self.assertIn("mais de 15 minutos", com)
        self.assertIn("12:30-12:56", com)


def _duble(servico):
    classe = mock.MagicMock()
    classe.completo.return_value = servico
    classe.return_value = servico
    return classe


def _chama(corpo):
    servico = mock.MagicMock()
    servico.update_appointment_services.return_value = {"manual_duration_descartada": False}
    db = mock.MagicMock()
    db.execute_query.return_value = [
        {"appointment_date": DIA, "start_time": "12:30:00", "original_price_cents": 19500}
    ]
    evento = {"headers": {"x-api-key": "k"},
              "pathParameters": {"clinicId": CLINIC, "appointmentId": APPT}, "body": None}
    with mock.patch.object(handler_mod, "require_acesso", return_value=(_ADMIN, None)), \
         mock.patch.object(handler_mod, "parse_body", return_value=corpo), \
         mock.patch.object(handler_mod, "PostgresService", return_value=db), \
         mock.patch.object(handler_mod, "AppointmentService", _duble(servico)):
        resposta = handler_mod.handler(evento, None)
    return servico, resposta


class TestHandlerDoPainel(unittest.TestCase):
    """Só o painel passa 15, nas três chamadas."""

    def test_areas_duracao_e_remarcacao_levam_quinze(self):
        servico, _ = _chama({"serviceId": "s1", "serviceAreaPairs": [{"serviceId": "s1", "areaId": "a1"}],
                             "date": "2026-11-26", "time": "09:00"})
        self.assertEqual(servico.update_appointment_services.call_args.kwargs["tolerancia_minutos"], 15)
        self.assertEqual(servico.reschedule_appointment.call_args.kwargs["tolerancia_minutos"], 15)

        servico, _ = _chama({"manualDurationMinutes": 20})
        self.assertEqual(servico.set_manual_duration.call_args.kwargs["tolerancia_minutos"], 15)
        self.assertEqual(handler_mod.TOLERANCIA_DO_PAINEL_MIN, 15)

    def test_conflito_acima_do_limite_vira_409_com_a_mensagem(self):
        servico = mock.MagicMock()
        servico.set_manual_duration.side_effect = ConflictError(
            AppointmentService._mensagem_de_conflito("x", 15, DIA, "12:30", "12:56"))
        db = mock.MagicMock()
        evento = {"headers": {"x-api-key": "k"},
                  "pathParameters": {"clinicId": CLINIC, "appointmentId": APPT}, "body": None}
        with mock.patch.object(handler_mod, "require_acesso", return_value=(_ADMIN, None)), \
             mock.patch.object(handler_mod, "parse_body", return_value={"manualDurationMinutes": 26}), \
             mock.patch.object(handler_mod, "PostgresService", return_value=db), \
             mock.patch.object(handler_mod, "AppointmentService", _duble(servico)):
            resposta = handler_mod.handler(evento, None)
        self.assertEqual(resposta["statusCode"], 409)
        self.assertIn("mais de 15 minutos", resposta["body"])


class TestQuemNaoPassaTolerancia(unittest.TestCase):
    """O bot e o site chamam o serviço sem `tolerancia_minutos`."""

    def _fonte(self, rel):
        raiz = os.path.join(os.path.dirname(__file__), "..", "..", "src")
        with open(os.path.join(raiz, rel), encoding="utf-8") as f:
            return f.read()

    def test_bot_e_site_nao_mencionam_tolerancia(self):
        for rel in ("services/ai_tools.py", "functions/public_booking/reschedule_appointment.py",
                    "functions/public_booking/create_appointment.py", "functions/appointment/create.py"):
            self.assertNotIn("tolerancia_minutos", self._fonte(rel), rel)

    def test_so_o_handler_do_painel_passa_a_constante(self):
        raiz = os.path.join(os.path.dirname(__file__), "..", "..", "src")
        usos = []
        for pasta, _, arquivos in os.walk(raiz):
            for nome in arquivos:
                if nome.endswith(".py"):
                    caminho = os.path.join(pasta, nome)
                    with open(caminho, encoding="utf-8") as f:
                        if re.search(r"tolerancia_minutos=(?!0\b)[A-Z_0-9]", f.read()):
                            usos.append(os.path.relpath(caminho, raiz).replace(os.sep, "/"))
        self.assertEqual(usos, ["functions/appointment/update.py"])
