# -*- coding: utf-8 -*-
"""book_appointment para quem JÁ TEM sessão só com a pessoa tendo dito que
quer duas (PRD 045).

O "Confirmo?" da Essência em 09/11/2026 ia inserir uma segunda linha com a
primeira ainda CONFIRMED. A tool explica e o modelo refaz - o mesmo padrão
de `full_name_obrigatorio`.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"
AREAS = [{"id": "a1", "name": "Axilas"}]
PEDIDO = {"date": "2026-11-19", "time": "15:25",
          "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}
FUTURO = {"id": "ap-18", "data": "2026-11-18", "hora": "14:50", "areas": "Axilas, Buço"}


def ctx(paciente):
    return {"turnos": [{"role": "user", "content": "quero fazer axilas"}],
            "paciente": paciente}


def executor():
    db = mock.MagicMock()
    db.execute_write.return_value = 1
    db.execute_query.side_effect = lambda sql, params=None: (
        AREAS if "FROM scheduler.areas" in sql else mock.MagicMock())
    ex = object.__new__(ToolExecutor)
    ex.db = db
    ex.appointment_service = mock.MagicMock()
    ex.appointment_service.create_appointment.return_value = {"id": "ap-novo"}
    ex.availability_engine = mock.MagicMock()
    ex._troca_por_combos = lambda args, clinic_id: []
    return ex


class TestRecusa(unittest.TestCase):
    def test_com_sessao_futura_nao_cria_e_explica(self):
        ex = executor()
        r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                      ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": FUTURO}))
        self.assertEqual(r["error"], "ja_tem_sessao_marcada")
        self.assertEqual(r["sessao"]["appointment_id"], "ap-18")
        self.assertEqual(r["sessao"]["areas"], "Axilas, Buço")
        self.assertIn("alterar_agendamento", r["o_que_fazer"])
        self.assertIn("segunda_sessao=true", r["o_que_fazer"])
        ex.appointment_service.create_appointment.assert_not_called()

    def test_segunda_sessao_explicita_segue(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_book_appointment(dict(PEDIDO, segunda_sessao=True, full_name="Fulana"),
                                          CLINIC, PHONE,
                                          ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": FUTURO}))
        self.assertNotEqual(r.get("error"), "ja_tem_sessao_marcada")
        ex.appointment_service.create_appointment.assert_called_once()

    def test_segunda_sessao_tem_de_ser_true_de_verdade(self):
        """"true" como string ou 1 nao conta: o registro no rastro e booleano."""
        ex = executor()
        for valor in ("true", 1, "sim"):
            r = ex._tool_book_appointment(dict(PEDIDO, segunda_sessao=valor), CLINIC, PHONE,
                                          ctx({"encontrado": True, "agendamento_futuro": FUTURO}))
            self.assertEqual(r.get("error"), "ja_tem_sessao_marcada", valor)
        ex.appointment_service.create_appointment.assert_not_called()


class TestNaoMudaQuemNaoTemSessao(unittest.TestCase):
    def test_lead_nova_agenda_como_antes(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            ex._tool_book_appointment(dict(PEDIDO, full_name="Fulana"), CLINIC, PHONE,
                                      ctx({"encontrado": False}))
        ex.appointment_service.create_appointment.assert_called_once()

    def test_paciente_sem_proxima_agenda_como_antes(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                      ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": None}))
        ex.appointment_service.create_appointment.assert_called_once()

    def test_a_definicao_anuncia_o_argumento(self):
        from src.services.ai_tools import get_tool_definitions
        book = next(t for t in get_tool_definitions(format="anthropic") if t["name"] == "book_appointment")
        self.assertIn("segunda_sessao", book["input_schema"]["properties"])


if __name__ == "__main__":
    unittest.main()
