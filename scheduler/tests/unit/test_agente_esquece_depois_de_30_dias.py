# -*- coding: utf-8 -*-
"""PRD 022: quem volta depois de 30 dias de silêncio é conversa nova.

Apagar a sessão não bastaria: o agente reconstrói o histórico dos eventos.
Os dois caminhos têm que respeitar a mesma janela, e o item vencido ainda
pode estar no banco (o DynamoDB apaga com até 48 h de atraso).
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import retencao
from src.services.conversation_agent import ConversationAgent
from tests.unit.dublagem_agente import CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo

AGORA = 1_800_000_000
DIA = 86400
HISTORICO = [{"role": "user", "content": "quero axilas"}, {"role": "assistant", "content": "Tenho quarta"}] * 3


class TabelaComItem:
    def __init__(self, item):
        self.item = item

    def get_item(self, Key):
        return {"Item": self.item}


def item_de(dias_atras, session):
    return {"pk": f"CLINIC#{CLINIC}", "sk": "PHONE#5511999990000", "session": session,
            "updatedAt": retencao.iso(AGORA - dias_atras * DIA)}


class TestCargaDaSessao(unittest.TestCase):
    """`_load_session` de verdade, com a tabela dublada."""

    def _carrega(self, dias_atras):
        agente = monta_agente()
        agente.sessions_table = TabelaComItem(item_de(dias_atras, {
            "agent_history": HISTORICO, "bot_enabled": True, "lead_id": "l1",
            "campanha": {"modo": "X"}, "recusas_de_area": {"a": 1},
        }))
        with mock.patch("src.services.retencao.time.time", return_value=AGORA):
            return ConversationAgent._load_session(agente, CLINIC, "5511999990000")

    def test_29_dias_lembra_tudo(self):
        s = self._carrega(29)
        self.assertEqual(len(s["agent_history"]), 6)
        self.assertIn("campanha", s)

    def test_31_dias_e_conversa_nova_mas_a_pessoa_continua_sendo_quem_e(self):
        s = self._carrega(31)
        self.assertNotIn("agent_history", s)
        self.assertNotIn("campanha", s)
        self.assertNotIn("recusas_de_area", s)
        self.assertTrue(s["bot_enabled"], "a elegibilidade nao e conversa")
        self.assertEqual(s["lead_id"], "l1")


class TestReconstrucaoRespeitaAJanela(unittest.TestCase):
    def test_eventos_sao_pedidos_desde_o_inicio_da_memoria(self):
        agente = monta_agente(anthropic=AnthropicRoteiro([texto_do_modelo("Oi!")]))
        tracker = mock.MagicMock()
        tracker.get_conversation_messages.return_value = []
        agente.message_tracker = tracker
        with mock.patch("src.services.retencao.time.time", return_value=AGORA):
            agente.rebuild_history_from_events(CLINIC, "5511999990000")
        _, kwargs = tracker.get_conversation_messages.call_args
        self.assertEqual(kwargs["desde"], AGORA - 30 * DIA)

    def test_sessao_vazia_sem_eventos_recentes_fala_do_zero(self):
        """Com a sessão vencida e os eventos fora da janela, o modelo recebe
        só a mensagem nova."""
        anthropic = AnthropicRoteiro([texto_do_modelo("Oi! Como posso ajudar?")])
        vistas = {}
        original = anthropic.create_message

        def create_message(system, messages, tools, max_tokens, tool_choice=None):
            vistas["messages"] = messages
            return original(system, messages, tools, max_tokens, tool_choice)
        anthropic.create_message = create_message
        agente = monta_agente(anthropic=anthropic)
        tracker = mock.MagicMock()
        tracker.get_conversation_messages.return_value = []  # nada nos ultimos 30 dias
        agente.message_tracker = tracker
        agente.process_message(CLINIC, mensagem("oi, voltei"))
        turnos_de_usuario = [m for m in vistas["messages"] if m["role"] == "user"]
        self.assertEqual(len(turnos_de_usuario), 1)
        self.assertIn("oi, voltei", str(turnos_de_usuario[0]["content"]))


if __name__ == "__main__":
    unittest.main()
