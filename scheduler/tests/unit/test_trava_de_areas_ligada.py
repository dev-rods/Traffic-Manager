# -*- coding: utf-8 -*-
"""A trava de áreas está LIGADA no fluxo, não só implementada.

Regressão do piloto de 11/09/2026. O André perguntou "quais horários para
24/09?" e o bot respondeu com horários, fechando depois em "Costas total +
ombros, Lombar e Axilas" - R$ 400,50, a um "sim" de agendar. Ele nunca perguntou
as áreas: chamou `list_areas`, pegou a lista inteira e escolheu três.

O prompt já mandava confirmar as áreas antes. Não adiantou.

Uma trava dessas morre de dois jeitos, e os dois são silenciosos:
  1. a transcrição para de chegar ao contexto -> ela não barra mais nada
  2. alguém remove a chamada de uma das tools -> aquela porta reabre
Por isso os testes aqui miram a FIAÇÃO, não a função.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor

CLINIC = "clinicaessenciaestetica-9668a4"
PHONE = "5511970522647"

# As áreas reais da Essência que o bot inventou naquele dia.
AREAS = [
    {"id": "20879906", "name": "Costas total + ombros"},
    {"id": "a-lombar", "name": "Lombar"},
    {"id": "a-axilas", "name": "Axilas"},
    {"id": "a-buco", "name": "Buço"},
]
INVENTADOS = [
    {"service_id": "s1", "area_id": "20879906"},
    {"service_id": "s1", "area_id": "a-lombar"},
    {"service_id": "s1", "area_id": "a-axilas"},
]

# A conversa real, sem nenhuma área citada.
CONVERSA_DO_PILOTO = [
    {"role": "assistant", "content": "Estamos com novas datas: 23/09, 24/09, 29/09."},
    {"role": "user", "content": "Sim, quais horários disponíveis para 24/09?"},
]


def executor():
    ex = object.__new__(ToolExecutor)
    ex.db = mock.MagicMock()
    ex.db.execute_query.side_effect = lambda sql, params=None: (
        AREAS if "FROM scheduler.areas" in sql else mock.MagicMock())
    ex.appointment_service = mock.MagicMock()
    ex.availability_engine = mock.MagicMock()
    return ex


class TestAsTresPortasEstaoFechadas(unittest.TestCase):
    """Uma porta aberta basta: preço errado e agendamento errado saem por ela."""

    def _recusou(self, tool):
        r = executor().execute(
            tool,
            {"date": "2026-09-24", "time": "18:10", "full_name": "André",
             "service_area_pairs": list(INVENTADOS)},
            {"clinic_id": CLINIC, "phone": PHONE, "turnos": list(CONVERSA_DO_PILOTO)},
        )
        return r.get("error") == "areas_nao_confirmadas"

    def test_get_time_slots(self):
        """A porta por onde o defeito entrou: horário calculado sobre área
        inventada sai errado, porque a duração do slot depende das áreas."""
        self.assertTrue(self._recusou("get_time_slots"))

    def test_calculate_discount(self):
        self.assertTrue(self._recusou("calculate_discount"))

    def test_book_appointment(self):
        self.assertTrue(self._recusou("book_appointment"))

    def test_e_o_agendamento_nao_chega_a_ser_criado(self):
        ex = executor()
        ex.execute("book_appointment",
                   {"date": "2026-09-24", "time": "18:10",
                    "service_area_pairs": list(INVENTADOS)},
                   {"clinic_id": CLINIC, "phone": PHONE,
                    "turnos": list(CONVERSA_DO_PILOTO)})

        ex.appointment_service.create_appointment.assert_not_called()


class TestOCaminhoNormalSegue(unittest.TestCase):
    """A trava não pode transformar o bot em inútil."""

    def test_area_pedida_pela_paciente_passa(self):
        turnos = CONVERSA_DO_PILOTO + [{"role": "user", "content": "quero axilas"}]
        r = executor().execute(
            "calculate_discount",
            {"service_area_pairs": [{"service_id": "s1", "area_id": "a-axilas"}]},
            {"clinic_id": CLINIC, "phone": PHONE, "turnos": turnos})

        self.assertNotEqual(r.get("error"), "areas_nao_confirmadas")

    def test_area_proposta_pelo_bot_e_respondida_passa(self):
        """É o fluxo que o André pediu: achou no histórico, perguntou, ela respondeu."""
        turnos = [
            {"role": "assistant", "content": "Da última vez foi Buço. Confirma que é essa?"},
            {"role": "user", "content": "isso"},
        ]
        r = executor().execute(
            "calculate_discount",
            {"service_area_pairs": [{"service_id": "s1", "area_id": "a-buco"}]},
            {"clinic_id": CLINIC, "phone": PHONE, "turnos": turnos})

        self.assertNotEqual(r.get("error"), "areas_nao_confirmadas")

    def test_achar_no_historico_sem_perguntar_nao_passa(self):
        """O pedido do André: mesmo achando no agendamento anterior, pergunta.

        O resultado da tool NÃO conta como ter dito - só o que foi escrito à
        paciente conta.
        """
        turnos = [{"role": "user", "content": "oi"}]
        r = executor().execute(
            "calculate_discount",
            {"service_area_pairs": [{"service_id": "s1", "area_id": "a-buco"}]},
            {"clinic_id": CLINIC, "phone": PHONE, "turnos": turnos})

        self.assertEqual(r.get("error"), "areas_nao_confirmadas")


class TestFalhaFechada(unittest.TestCase):
    def test_sem_transcricao_barra(self):
        """Se a fiação quebrar, a trava tem de FECHAR, não sumir."""
        r = executor().execute(
            "book_appointment",
            {"date": "2026-09-24", "service_area_pairs": list(INVENTADOS)},
            {"clinic_id": CLINIC, "phone": PHONE})

        self.assertEqual(r.get("error"), "areas_nao_confirmadas")

    def test_sem_pares_nao_atrapalha(self):
        """A consulta obrigatória chama tools com argumentos vazios."""
        r = executor().execute("lookup_appointments", {},
                               {"clinic_id": CLINIC, "phone": PHONE})
        self.assertNotEqual(r.get("error"), "areas_nao_confirmadas")


class TestATranscricaoChegaNaTool(unittest.TestCase):
    """O elo entre o agente e a trava - onde ela morreria calada."""

    def test_process_message_manda_os_turnos(self):
        from tests.unit.dublagem_agente import (
            AnthropicRoteiro, mensagem, monta_agente, usa_tool)

        recebidos = {}

        class ExecutorEspiao:
            chamadas = []

            def execute(self, nome, args, context):
                # Por nome: a pre-carga obrigatoria tambem chama o executor, e
                # medir a chamada errada faria o teste falar de outra coisa.
                recebidos[nome] = context
                return {"ok": True}

        agente = monta_agente(
            tool_executor=ExecutorEspiao(),
            anthropic=AnthropicRoteiro([usa_tool("get_time_slots", {"date": "2026-09-24"})]))
        agente.process_message(CLINIC, mensagem("quais horários para 24/09?"))

        self.assertIn("get_time_slots", recebidos, "a tool não foi executada")
        self.assertIn(
            "turnos", recebidos["get_time_slots"],
            "o agente não manda a transcrição; a trava de áreas fica inerte e "
            "o bot volta a poder inventar área")
        self.assertTrue(recebidos["get_time_slots"]["turnos"],
                        "a transcrição chegou vazia")

    def test_os_turnos_trazem_o_que_a_paciente_disse(self):
        from tests.unit.dublagem_agente import (
            AnthropicRoteiro, mensagem, monta_agente, usa_tool)

        recebidos = {}

        class ExecutorEspiao:
            chamadas = []

            def execute(self, nome, args, context):
                # Por nome: a pre-carga obrigatoria tambem chama o executor, e
                # medir a chamada errada faria o teste falar de outra coisa.
                recebidos[nome] = context
                return {"ok": True}

        agente = monta_agente(
            tool_executor=ExecutorEspiao(),
            anthropic=AnthropicRoteiro([usa_tool("get_time_slots", {"date": "2026-09-24"})]))
        agente.process_message(CLINIC, mensagem("quero axilas"))

        texto = " ".join(t["content"] for t in recebidos["get_time_slots"]["turnos"])
        self.assertIn("axilas", texto)


if __name__ == "__main__":
    unittest.main()
