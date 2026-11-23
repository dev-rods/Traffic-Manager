# -*- coding: utf-8 -*-
"""O bot nunca marca duas sessões no mesmo mês (PRD 056).

Até 21/11/2026 `book_appointment` aceitava `segunda_sessao=true` quando a
pessoa pedia duas "com todas as letras". Saiu: no mesmo mês a tool recusa
sempre e manda remarcar. Em outro mês (PRD 060, 23/11/2026) a tool PERGUNTA
"remarcar ou mais uma?" e só cria com `mais_uma=true` depois de ter
perguntado nesta conversa. Só um ADMIN, pelo painel, mantém duas. A guarda do
serviço cobre o caso em que o ctx não traz a sessão (só a mais próxima, ou
nenhuma).
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor, _mesmo_mes
from src.services.appointment_service import OutraSessaoFutura, SessaoNoMesmoMes

CLINIC = "clinica-teste-0001"
PHONE = "5511999990000"
AREAS = [{"id": "a1", "name": "Axilas"}]
PEDIDO = {"date": "2026-11-19", "time": "15:25", "full_name": "Fulana",
          "service_area_pairs": [{"service_id": "s1", "area_id": "a1"}]}
MESMO_MES = {"id": "ap-18", "data": "2026-11-18", "hora": "14:50", "areas": "Axilas, Buço"}
OUTRO_MES = {"id": "ap-12", "data": "2026-12-02", "hora": "10:00", "areas": "Axilas"}


def ctx(paciente, session=None):
    return {"turnos": [{"role": "user", "content": "quero fazer axilas"}],
            "paciente": paciente, "session": {} if session is None else session}


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
        """O ctx não traz a sessão (cadastro sem a projeção) e o serviço
        enxerga a de novembro."""
        ex = executor()
        ex.appointment_service.create_appointment.side_effect = SessaoNoMesmoMes(
            {"id": "ap-legado", "appointment_date": "2026-11-05", "start_time": "09:00:00", "areas_display": "Buço"})
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            r = ex._tool_book_appointment(dict(PEDIDO), CLINIC, PHONE,
                                          ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": None}))
        self.assertEqual(r["error"], "ja_tem_sessao_marcada")
        self.assertEqual(r["sessao"], {"appointment_id": "ap-legado", "date": "2026-11-05",
                                       "time": "09:00", "areas": "Buço"})


class TestOutroMesPergunta(unittest.TestCase):
    """Sessão futura em outro mês: a tool devolve a pergunta (PRD 060)."""

    def _chama(self, ex, args, session, futuro=OUTRO_MES):
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=10):
            return ex._tool_book_appointment(dict(args), CLINIC, PHONE,
                                             ctx({"encontrado": True, "nome": "Fulana", "agendamento_futuro": futuro},
                                                 session=session))

    def test_sem_mais_uma_pergunta_e_grava_na_sessao(self):
        ex = executor()
        session = {}
        r = self._chama(ex, PEDIDO, session)
        self.assertEqual(r["error"], "ja_tem_sessao_futura")
        self.assertEqual(r["sessao"], {"appointment_id": "ap-12", "date": "2026-12-02", "time": "10:00", "areas": "Axilas"})
        self.assertIn("PERGUNTE", r["o_que_fazer"])
        self.assertIn("alterar_agendamento com appointment_id=ap-12", r["o_que_fazer"])
        self.assertIn("mais_uma=true", r["o_que_fazer"])
        self.assertEqual(session["pergunta_mais_uma"], "ap-12")
        ex.appointment_service.create_appointment.assert_not_called()

    def test_mais_uma_sem_pergunta_feita_pergunta_de_novo(self):
        """O modelo não decide por ela: sem a pergunta na sessão, mais_uma é ignorado."""
        ex = executor()
        session = {}
        r = self._chama(ex, dict(PEDIDO, mais_uma=True), session)
        self.assertEqual(r["error"], "ja_tem_sessao_futura")
        self.assertEqual(session["pergunta_mais_uma"], "ap-12")
        ex.appointment_service.create_appointment.assert_not_called()

    def test_mais_uma_de_outra_sessao_nao_vale(self):
        ex = executor()
        r = self._chama(ex, dict(PEDIDO, mais_uma=True), {"pergunta_mais_uma": "ap-velha"})
        self.assertEqual(r["error"], "ja_tem_sessao_futura")
        ex.appointment_service.create_appointment.assert_not_called()

    def test_mais_uma_depois_da_pergunta_cria_e_avisa_que_a_anterior_continua(self):
        ex = executor()
        r = self._chama(ex, dict(PEDIDO, mais_uma=True), {"pergunta_mais_uma": "ap-12"})
        self.assertTrue(r["success"])
        self.assertEqual(r["sessao_anterior_mantida"], {"date": "2026-12-02", "time": "10:00"})
        self.assertIs(ex.appointment_service.create_appointment.call_args.kwargs["mais_uma"], True)

    def test_sem_sessao_futura_cria_e_o_servico_recebe_false(self):
        ex = executor()
        r = self._chama(ex, PEDIDO, {}, futuro=None)
        self.assertTrue(r["success"])
        self.assertNotIn("sessao_anterior_mantida", r)
        self.assertIs(ex.appointment_service.create_appointment.call_args.kwargs["mais_uma"], False)

    def test_a_definicao_anuncia_mais_uma_como_opcional(self):
        from src.services.ai_tools import get_tool_definitions
        book = next(t for t in get_tool_definitions(format="anthropic") if t["name"] == "book_appointment")
        self.assertEqual(book["input_schema"]["properties"]["mais_uma"]["type"], "boolean")
        self.assertNotIn("mais_uma", book["input_schema"]["required"])

    def test_guarda_do_servico_vira_a_mesma_pergunta(self):
        """O ctx não trouxe a sessão futura e o serviço a enxergou."""
        ex = executor()
        ex.appointment_service.create_appointment.side_effect = OutraSessaoFutura(
            {"id": "ap-dez", "appointment_date": "2026-12-10", "start_time": "09:00:00", "areas_display": "Virilha"})
        session = {}
        r = self._chama(ex, PEDIDO, session, futuro=None)
        self.assertEqual(r["error"], "ja_tem_sessao_futura")
        self.assertEqual(r["sessao"], {"appointment_id": "ap-dez", "date": "2026-12-10", "time": "09:00", "areas": "Virilha"})
        self.assertEqual(session["pergunta_mais_uma"], "ap-dez")

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
