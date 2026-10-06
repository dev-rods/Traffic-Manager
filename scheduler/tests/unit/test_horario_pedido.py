# -*- coding: utf-8 -*-
"""Quem pede um horário exato recebe a resposta exata.

O caso real, 06/10/2026 às 12:21: a Olivia pediu 21/10 às 17:45 com seis
áreas (35 min). A tarde do dia 21 tinha 16:00-16:25 e 18:25-18:35 ocupados,
então 16:25-18:25 estava livre e 17:45-18:20 cabia. A grade de sugestões
anda de 35 em 35 a partir de 16:25 (16:25, 17:00, 17:35) e 17:45 nunca
aparece. O bot disse que não tinha.

A grade continua sendo grade. O que entra é a pergunta certa: "cabe às
17:45?", respondida contra as janelas livres.
"""
import os
import unittest
from datetime import time
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor, _normaliza_hora
from src.services.availability_engine import AvailabilityEngine

CLINIC = "clinicaessenciaestetica-9668a4"
DIA = "2026-10-21"
DURACAO = 35


def motor_do_dia_21():
    """O dia 21/10 como estava às 12:21 de 06/10, só a tarde."""
    db = mock.MagicMock()

    def query(sql, params=None):
        if "buffer_minutes" in sql:
            return [{"buffer_minutes": 0}]
        if "availability_rules" in sql:
            return [{"start_time": time(7, 30), "end_time": time(20, 30), "rule_date": DIA}]
        if "availability_exceptions" in sql:
            return []
        if "FROM scheduler.appointments" in sql:
            return [
                {"start_time": time(16, 0), "end_time": time(16, 25)},
                {"start_time": time(18, 25), "end_time": time(18, 35)},
                {"start_time": time(19, 0), "end_time": time(19, 10)},
                {"start_time": time(20, 5), "end_time": time(20, 20)},
            ]
        return []

    db.execute_query.side_effect = query
    return AvailabilityEngine(db)


class TestAGradeNaoEAAgenda(unittest.TestCase):
    def test_a_grade_do_dia_21_pula_as_17h45(self):
        """O comportamento de antes, documentado: 17:45 cabia e não estava na grade."""
        grade = motor_do_dia_21().get_available_slots_multi(CLINIC, DIA, DURACAO)
        self.assertIn("17:35", grade)
        self.assertNotIn("17:45", grade)

    def test_mas_17h45_cabe(self):
        self.assertTrue(motor_do_dia_21().cabe_no_horario(CLINIC, DIA, DURACAO, "17:45"))

    def test_17h55_nao_cabe_porque_invade_as_18h25(self):
        self.assertFalse(motor_do_dia_21().cabe_no_horario(CLINIC, DIA, DURACAO, "17:55"))

    def test_17h50_e_o_ultimo_que_cabe(self):
        self.assertTrue(motor_do_dia_21().cabe_no_horario(CLINIC, DIA, DURACAO, "17:50"))

    def test_em_cima_de_agendamento_nao_cabe(self):
        self.assertFalse(motor_do_dia_21().cabe_no_horario(CLINIC, DIA, DURACAO, "16:10"))

    def test_fora_da_regra_nao_cabe(self):
        self.assertFalse(motor_do_dia_21().cabe_no_horario(CLINIC, DIA, DURACAO, "07:00"))
        self.assertFalse(motor_do_dia_21().cabe_no_horario(CLINIC, DIA, DURACAO, "20:00"))

    def test_hora_ilegivel_e_erro_falham_fechado(self):
        motor = motor_do_dia_21()
        self.assertFalse(motor.cabe_no_horario(CLINIC, DIA, DURACAO, "meio-dia"))
        motor.db.execute_query.side_effect = RuntimeError("down")
        self.assertFalse(motor.cabe_no_horario(CLINIC, DIA, DURACAO, "17:45"))

    def test_buffer_conta(self):
        """Com buffer de 10, 17:45+35 = 18:20 invade o buffer das 18:25."""
        motor = motor_do_dia_21()
        original = motor.db.execute_query.side_effect
        motor.db.execute_query.side_effect = lambda sql, params=None: (
            [{"buffer_minutes": 10}] if "buffer_minutes" in sql else original(sql, params))
        self.assertFalse(motor.cabe_no_horario(CLINIC, DIA, DURACAO, "17:45"))
        self.assertTrue(motor.cabe_no_horario(CLINIC, DIA, DURACAO, "17:35"))

    def test_a_grade_continua_igual(self):
        """A refatoração não muda a lista de sugestões."""
        grade = motor_do_dia_21().get_available_slots_multi(CLINIC, DIA, DURACAO)
        self.assertEqual(grade[-3:], ["17:00", "17:35", "19:10"])


class TestNormalizaHora(unittest.TestCase):
    def test_formatos_que_a_pessoa_escreve(self):
        for entrada, esperado in [("17:45", "17:45"), ("17h45", "17:45"), ("17:45h", "17:45"),
                                  ("17h", "17:00"), (" 9:05 ", "09:05"), ("17H45", "17:45")]:
            with self.subTest(entrada=entrada):
                self.assertEqual(_normaliza_hora(entrada), esperado)

    def test_lixo(self):
        for ruim in (None, "", "tarde", "25:00", "17:60", "amanhã"):
            with self.subTest(ruim=ruim):
                self.assertIsNone(_normaliza_hora(ruim))


class TestATool(unittest.TestCase):
    def _executor(self):
        ex = object.__new__(ToolExecutor)
        ex.db = mock.MagicMock()
        ex.db.execute_query.side_effect = lambda sql, params=None: (
            [{"id": "a1", "name": "Axilas"}] if "FROM scheduler.areas" in sql else mock.MagicMock())
        ex.availability_engine = motor_do_dia_21()
        ex.appointment_service = mock.MagicMock()
        return ex

    def _chama(self, ex, **args):
        base = {"date": DIA, "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}
        base.update(args)
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=DURACAO):
            return ex._tool_get_time_slots(base, CLINIC, "5511983583024",
                                           {"turnos": [{"role": "user", "content": "quero axilas"}]})

    def test_sem_pedido_nada_muda(self):
        r = self._chama(self._executor())
        self.assertNotIn("horario_pedido", r)
        self.assertNotIn("17:45", r["available_slots"])

    def test_o_caso_da_olivia(self):
        r = self._chama(self._executor(), horario_pedido="17:45h")
        self.assertEqual(r["horario_pedido"], "17:45")
        self.assertTrue(r["horario_pedido_disponivel"])
        # Entra na lista: a proveniência respalda "17:45" na resposta.
        self.assertIn("17:45", r["available_slots"])
        self.assertEqual(r["available_slots"], sorted(r["available_slots"]))

    def test_pedido_que_nao_cabe(self):
        r = self._chama(self._executor(), horario_pedido="17:55")
        self.assertFalse(r["horario_pedido_disponivel"])
        self.assertNotIn("17:55", r["available_slots"])

    def test_pedido_ilegivel_e_ignorado(self):
        r = self._chama(self._executor(), horario_pedido="de tarde")
        self.assertNotIn("horario_pedido", r)


if __name__ == "__main__":
    unittest.main()
