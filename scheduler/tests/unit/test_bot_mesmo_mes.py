# -*- coding: utf-8 -*-
"""O bot nunca marca duas sessões no mesmo mês (PRD 056).

Até 21/11/2026 `book_appointment` aceitava `segunda_sessao=true` quando a
pessoa pedia duas "com todas as letras". Saiu: no mesmo mês a tool recusa
sempre e manda remarcar; em outro mês cria e avisa que a anterior continua.
Só um ADMIN, pelo painel, mantém duas. A guarda do serviço cobre o caso em
que o ctx não traz a sessão do mês (ele traz só a mais próxima).
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor, _mesmo_mes
from src.services.appointment_service import SessaoNoMesmoMes

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"
AREAS = [{"id": "a1", "name": "Axilas"}]
PEDIDO = {"date": "2026-11-19", "time": "15:25", "full_name": "Fulana",
          "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}
MESMO_MES = {"id": "ap-18", "data": "2026-11-18", "hora": "14:50", "areas": "Axilas, Buço"}
OUTRO_MES = {"id": "ap-12", "data": "2026-12-02", "hora": "10:00", "areas": "Axilas"}


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
    ex.appointment_service.create_appointment.return_value = {"id": "ap-novo", "status": "CONFIRMED"}
    ex.availability_engine = mock.MagicMock()
    ex._troca_por_combos = lambda args, clinic_id: []
    return ex


class TestMesmoMes(unittest.TestCase):
    def test_comparacao_por_ano_mes(self):
        self.assertTrue(_mesmo_mes("2026-11-18", "2026-11-30"))
        self.assertFalse(_mesmo_mes("2026-11-30", "2026-12-01"))
        self.assertFalse(_mesmo_mes("2025-11-18", "2026-11-18"))
        self.assertFalse(_mesmo_mes(None, "2026-11-18"))
        self.assertFalse(_mesmo_mes("", ""))


class TestRecusaNoMesmoMes(unittest.TestCase):
    def test_recusa_e_manda_remarcar(self):
        ex = executor()
        r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                      ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": MESMO_MES}))
        self.assertEqual(r["error"], "ja_tem_sessao_marcada")
        self.assertEqual(r["sessao"]["appointment_id"], "ap-18")
        self.assertIn("alterar_agendamento", r["o_que_fazer"])
        self.assertIn("cancelada e remarcada", r["o_que_fazer"])
        self.assertNotIn("segunda_sessao", r["o_que_fazer"])
        ex.appointment_service.create_appointment.assert_not_called()

    def test_nao_ha_saida_nem_com_segunda_sessao(self):
        """O argumento antigo chegando de um modelo que o decorou: ignorado."""
        ex = executor()
        r = ex._tool_book_appointment(dict(PEDIDO, segunda_sessao=True), CLINIC, PHONE,
                                      ctx({"encontrado": True, "agendamento_futuro": MESMO_MES}))
        self.assertEqual(r["error"], "ja_tem_sessao_marcada")
        ex.appointment_service.create_appointment.assert_not_called()

    def test_a_definicao_nao_anuncia_mais_o_argumento(self):
        from src.services.ai_tools import get_tool_definitions
        book = next(t for t in get_tool_definitions(format="anthropic") if t["name"] == "book_appointment")
        self.assertNotIn("segunda_sessao", book["input_schema"]["properties"])

    def test_guarda_do_servico_vira_o_mesmo_recado(self):
        """O ctx traz só a sessão mais próxima (dezembro); a de novembro é
        legado que só o serviço enxerga."""
        ex = executor()
        ex.appointment_service.create_appointment.side_effect = SessaoNoMesmoMes(
            {"id": "ap-legado", "appointment_date": "2026-11-05", "start_time": "09:00:00", "areas_display": "Buço"})
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                          ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": OUTRO_MES}))
        self.assertEqual(r["error"], "ja_tem_sessao_marcada")
        self.assertEqual(r["sessao"], {"appointment_id": "ap-legado", "date": "2026-11-05",
                                       "time": "09:00", "areas": "Buço"})


class TestOutroMesPassa(unittest.TestCase):
    def test_cria_e_avisa_que_a_anterior_continua(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                          ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": OUTRO_MES}))
        self.assertTrue(r["success"])
        self.assertEqual(r["sessao_anterior_mantida"], {"date": "2026-12-02", "time": "10:00"})
        ex.appointment_service.create_appointment.assert_called_once()

    def test_sem_sessao_futura_nao_avisa_nada(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                          ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": None}))
        self.assertTrue(r["success"])
        self.assertNotIn("sessao_anterior_mantida", r)

    def test_lead_nova_agenda_como_antes(self):
        ex = executor()
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE, ctx({"encontrado": False}))
        self.assertTrue(r["success"])


class TestAlterarParaMesOcupado(unittest.TestCase):
    def test_remarca_barrada_vira_recado(self):
        ex = executor()
        ex._agendamento_confirmado = lambda a, c: {
            "id": "ap-12", "appointment_date": "2026-12-02", "start_time": "10:00:00",
            "areas_display": "Axilas", "total_duration_minutes": 10, "final_price_cents": 6500}
        ex.appointment_service.remarca.side_effect = SessaoNoMesmoMes(
            {"id": "ap-18", "appointment_date": "2026-11-18", "start_time": "14:50:00", "areas_display": "Axilas, Buço"})
        r = ex._tool_alterar_agendamento({"appointment_id": "ap-12", "new_date": "2026-11-25", "new_time": "16:00"},
                                         CLINIC, PHONE, ctx({"encontrado": True, "agendamento_futuro": OUTRO_MES}))
        self.assertEqual(r["error"], "ja_tem_sessao_nesse_mes")
        self.assertEqual(r["sessao"]["appointment_id"], "ap-18")
        self.assertIn("outro mês", r["o_que_fazer"])


if __name__ == "__main__":
    unittest.main()
