# -*- coding: utf-8 -*-
"""A tool que EDITA a sessão que existe (PRD 045).

Até 09/11/2026 o modelo só tinha `reschedule_appointment` (data e hora). Para
trocar áreas, o único caminho era `book_appointment`: linha nova, a antiga de
pé. Esta tool reutiliza o que o painel já usa, na mesma ordem: áreas antes
(mudam a duração), conflito só contra a data final.
"""
import os
import unittest
from datetime import date, time
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor
from src.services.appointment_service import ConflictError

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"
AID = "99d73dc3-a7aa-4b85-b149-7dbca186f45a"

AREAS = [{"id": "a1", "name": "Axilas"}, {"id": "a2", "name": "1/2 Perna"}]
# A trava de areas le a transcricao: ela pediu "so a axila" em voz alta.
CTX = {
    "turnos": [{"role": "user", "content": "gostaria de remarcar para fazer somente a axila"}],
    "paciente": {"encontrado": True,
                 "agendamento_futuro": {"id": AID, "data": "2026-11-06", "hora": "13:50",
                                        "areas": "Axilas, 1/2 Perna"}},
}
SO_AXILA = [{"service_id": "s1", "area_id": "a1"}]


class Db:
    def __init__(self):
        self.areas = "Axilas, 1/2 Perna"

    def execute_query(self, sql, params=()):
        if "FROM scheduler.areas" in sql:
            return AREAS
        if "FROM scheduler.appointments a" in sql and "areas_display" in sql:
            return [{"id": AID, "appointment_date": date(2026, 11, 6),
                     "start_time": time(13, 50), "end_time": time(14, 5),
                     "total_duration_minutes": 15, "final_price_cents": 9500,
                     "areas_display": self.areas}]
        return []


def executor(db=None):
    ex = object.__new__(ToolExecutor)
    ex.db = db or Db()
    ex.appointment_service = mock.MagicMock()
    ex.availability_engine = mock.MagicMock()
    return ex


def _sem_combos(ex):
    ex._troca_por_combos = lambda args, clinic_id: []
    return ex


class TestSoAreas(unittest.TestCase):
    def test_edita_a_linha_e_mantem_o_horario(self):
        """O caso da Nobre: tirar a 1/2 perna, mesmo dia, mesma hora."""
        ex = _sem_combos(executor())
        ex.db.areas = "Axilas"  # o que o banco devolve depois da edicao
        r = ex._tool_alterar_agendamento(
            {"appointment_id": AID, "service_area_pairs": SO_AXILA}, CLINIC, PHONE, dict(CTX))

        self.assertTrue(r["success"])
        self.assertTrue(r["horario_mantido"])
        self.assertEqual((r["date"], r["time"]), ("2026-11-06", "13:50"))
        self.assertEqual(r["areas"], "Axilas")
        ex.appointment_service.update_appointment_services.assert_called_once_with(
            AID, "s1", [{"serviceId": "s1", "areaId": "a1"}], verificar_conflito=True)
        ex.appointment_service.reschedule_appointment.assert_not_called()
        ex.appointment_service.create_appointment.assert_not_called()

    def test_nao_cabe_vira_resposta_e_nao_erro(self):
        ex = _sem_combos(executor())
        ex.appointment_service.update_appointment_services.side_effect = ConflictError("x")
        r = ex._tool_alterar_agendamento(
            {"appointment_id": AID, "service_area_pairs": SO_AXILA}, CLINIC, PHONE, dict(CTX))
        self.assertEqual(r["error"], "nao_cabe")
        self.assertIn("MESMO dia", r["o_que_fazer"])
        self.assertIn("13:50", r["o_que_fazer"])
        ex.appointment_service.reschedule_appointment.assert_not_called()

    def test_area_nao_conversada_e_barrada_como_no_book(self):
        ex = _sem_combos(executor())
        ctx = dict(CTX, turnos=[{"role": "user", "content": "oi"}])
        r = ex._tool_alterar_agendamento(
            {"appointment_id": AID, "service_area_pairs": SO_AXILA}, CLINIC, PHONE, ctx)
        self.assertIn("error", r)
        ex.appointment_service.update_appointment_services.assert_not_called()


class TestSoDataHora(unittest.TestCase):
    def test_move_sem_tocar_nas_areas(self):
        ex = _sem_combos(executor())
        r = ex._tool_alterar_agendamento(
            {"appointment_id": AID, "new_date": "2026-11-19", "new_time": "15:25"},
            CLINIC, PHONE, dict(CTX))
        self.assertTrue(r["success"])
        self.assertFalse(r["horario_mantido"])
        ex.appointment_service.reschedule_appointment.assert_called_once_with(AID, "2026-11-19", "15:25")
        ex.appointment_service.update_appointment_services.assert_not_called()

    def test_so_a_hora_mantem_a_data(self):
        ex = _sem_combos(executor())
        ex._tool_alterar_agendamento({"appointment_id": AID, "new_time": "14:05"}, CLINIC, PHONE, dict(CTX))
        ex.appointment_service.reschedule_appointment.assert_called_once_with(AID, "2026-11-06", "14:05")

    def test_mesma_data_e_hora_nao_remarca(self):
        """O modelo repete o horario atual: nada a mover, nada gravado."""
        ex = _sem_combos(executor())
        r = ex._tool_alterar_agendamento(
            {"appointment_id": AID, "new_date": "2026-11-06", "new_time": "13:50"}, CLINIC, PHONE, dict(CTX))
        self.assertTrue(r["success"])
        self.assertTrue(r["horario_mantido"])
        ex.appointment_service.reschedule_appointment.assert_not_called()


class TestOsDois(unittest.TestCase):
    def test_areas_sem_conferir_conflito_depois_remarca(self):
        """A ordem do painel: a data ainda e a antiga quando as areas entram."""
        ex = _sem_combos(executor())
        ordem = []
        ex.appointment_service.update_appointment_services.side_effect = (
            lambda *a, **k: ordem.append(("areas", k.get("verificar_conflito"))))
        ex.appointment_service.reschedule_appointment.side_effect = (
            lambda *a: ordem.append(("remarca", a[1:])))
        r = ex._tool_alterar_agendamento(
            {"appointment_id": AID, "service_area_pairs": SO_AXILA,
             "new_date": "2026-11-19", "new_time": "15:25"}, CLINIC, PHONE, dict(CTX))
        self.assertTrue(r["success"])
        self.assertEqual(ordem, [("areas", False), ("remarca", ("2026-11-19", "15:25"))])


class TestContrato(unittest.TestCase):
    def test_nada_a_alterar(self):
        ex = executor()
        r = ex._tool_alterar_agendamento({"appointment_id": AID}, CLINIC, PHONE, dict(CTX))
        self.assertEqual(r["error"], "nada_a_alterar")

    def test_agendamento_que_nao_existe(self):
        class Vazio(Db):
            def execute_query(self, sql, params=()):
                return AREAS if "FROM scheduler.areas" in sql else []
        ex = _sem_combos(executor(Vazio()))
        r = ex._tool_alterar_agendamento({"appointment_id": "nao-existe", "new_time": "14:05"},
                                         CLINIC, PHONE, dict(CTX))
        self.assertEqual(r["error"], "agendamento_nao_encontrado")
        ex.appointment_service.reschedule_appointment.assert_not_called()

    def test_a_tool_antiga_nao_existe_mais(self):
        """Uma tool so (decisao §7.2 A): o nome antigo nao e mais chamavel."""
        from src.services.ai_tools import get_tool_definitions
        nomes = {t["name"] for t in get_tool_definitions(format="anthropic")}
        self.assertIn("alterar_agendamento", nomes)
        self.assertNotIn("reschedule_appointment", nomes)
        self.assertEqual(executor().execute("reschedule_appointment", {}, {"clinic_id": CLINIC}),
                         {"error": "Unknown tool: reschedule_appointment"})


if __name__ == "__main__":
    unittest.main()
