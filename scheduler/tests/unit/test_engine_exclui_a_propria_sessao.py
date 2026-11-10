# -*- coding: utf-8 -*-
"""A agenda vista por quem JÁ TEM sessão não conta a vaga dela (PRD 045).

Em 09/11/2026 o bot respondeu "14:50 não encaixa mais" à paciente que estava
nas 14:50; em 05/11, "13:50 não encaixa só com a axila" a quem estava nas
13:50 e queria TIRAR uma área. Reproduzido contra prod: a vaga cabia assim que
o agendamento dela era excluído. A agenda abaixo é a forma do caso real:
um dia cheio, e ela no meio.
"""
import unittest
from datetime import time
from unittest import mock

from src.services.availability_engine import AvailabilityEngine
from src.services.ai_tools import ToolExecutor

CLINIC = "clinica-teste-0001"
DIA = "2026-11-18"
DELA = "99d73dc3-a7aa-4b85-b149-7dbca186f45a"

# 14:10-14:40 outra pessoa, 14:50-15:20 ELA, 15:30-15:40 outra pessoa.
AGENDA = [
    {"id": "outro-1", "start_time": time(14, 10), "end_time": time(14, 40)},
    {"id": DELA, "start_time": time(14, 50), "end_time": time(15, 20)},
    {"id": "outro-2", "start_time": time(15, 30), "end_time": time(15, 40)},
]


class Db:
    """Responde pelo trecho do SQL. O filtro `id <> %s` é aplicado de verdade:
    é ele que o teste mede."""

    def execute_query(self, sql, params=()):
        if "FROM scheduler.clinics" in sql and "buffer_minutes" in sql:
            return [{"buffer_minutes": 0}]
        if "FROM scheduler.availability_rules" in sql:
            return [{"start_time": time(14, 0), "end_time": time(16, 0), "rule_date": None}]
        if "FROM scheduler.availability_exceptions" in sql:
            return []
        if "FROM scheduler.appointments" in sql:
            linhas = AGENDA
            if "id <> %s" in sql:
                linhas = [a for a in AGENDA if a["id"] != params[-1]]
            return [{"start_time": a["start_time"], "end_time": a["end_time"]} for a in linhas]
        return []


class TestExcluindo(unittest.TestCase):
    def test_sem_excluir_a_vaga_dela_esta_ocupada(self):
        """O defeito, como estava."""
        engine = AvailabilityEngine(Db())
        self.assertFalse(engine.cabe_no_horario(CLINIC, DIA, 30, "14:50"))
        self.assertNotIn("14:50", engine.get_available_slots_multi(CLINIC, DIA, 30))

    def test_excluindo_a_vaga_e_dela(self):
        engine = AvailabilityEngine(Db()).excluindo(DELA)
        self.assertTrue(engine.cabe_no_horario(CLINIC, DIA, 30, "14:50"))
        # Tirar area (menos tempo) cabe; o caso da Nobre.
        self.assertTrue(engine.cabe_no_horario(CLINIC, DIA, 10, "14:50"))
        # Mas a vaga dos outros continua dos outros.
        self.assertFalse(engine.cabe_no_horario(CLINIC, DIA, 30, "14:10"))

    def test_excluindo_nao_muda_o_engine_compartilhado(self):
        original = AvailabilityEngine(Db())
        copia = original.excluindo(DELA)
        self.assertIsNone(original.ignorar_agendamento)
        self.assertEqual(copia.ignorar_agendamento, DELA)
        self.assertIsNot(copia, original)


class TestEngineDoTurno(unittest.TestCase):
    """O executor escolhe a agenda pelo ctx: quem tem sessão, sem ela."""

    def _executor(self):
        ex = object.__new__(ToolExecutor)
        ex.db = Db()
        ex.appointment_service = mock.MagicMock()
        ex.availability_engine = AvailabilityEngine(Db())
        return ex

    def test_com_sessao_futura_a_agenda_exclui_a_sessao(self):
        ex = self._executor()
        ctx = {"paciente": {"encontrado": True,
                            "agendamento_futuro": {"id": DELA, "data": DIA, "hora": "14:50"}}}
        self.assertEqual(ex._engine_de(ctx).ignorar_agendamento, DELA)

    def test_sem_sessao_e_o_engine_de_sempre(self):
        ex = self._executor()
        self.assertIs(ex._engine_de({"paciente": {"encontrado": False}}), ex.availability_engine)
        self.assertIs(ex._engine_de({}), ex.availability_engine)

    def test_get_time_slots_responde_que_o_horario_dela_cabe(self):
        """O caso de ponta a ponta na tool: `[Slots] pediu 14:50 -> cabe`."""
        ex = self._executor()
        ctx = {"paciente": {"encontrado": True,
                            "agendamento_futuro": {"id": DELA, "data": DIA, "hora": "14:50"}},
               "turnos": []}
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=30):
            r = ex._horarios({"date": DIA, "horario_pedido": "14:50"}, CLINIC, "5511", ctx)
        self.assertTrue(r["horario_pedido_disponivel"])
        self.assertIn("14:50", r["available_slots"])


if __name__ == "__main__":
    unittest.main()
