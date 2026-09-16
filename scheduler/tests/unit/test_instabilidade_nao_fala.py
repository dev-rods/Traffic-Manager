# -*- coding: utf-8 -*-
"""Instabilidade nossa não vira mensagem para a paciente.

Em 14 e 15/09/2026, com a conta da Anthropic sem saldo, quem escrevia recebia
"Desculpe, estou com dificuldades no momento. Tente novamente em instantes." —
inclusive a paciente 5511974247671, às 11:37. Duas horas depois, uma atendente
respondeu à mão.

Regra do André, 15/09/2026: essa mensagem nunca chega ao cliente. O bot cala e a
conversa vira uma pessoa esperando resposta — que é o que a clínica já sabe
tratar. Calar sem entregar a conversa seria pior do que a mensagem ruim, então o
teste cobre as duas metades: silêncio E pausa.
"""
import os
import time
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.anthropic_service import AnthropicError
from src.services.bot_policy import (
    CAMPO_DE_PAUSA,
    PAUSA_HANDOFF,
    PAUSA_INSTABILIDADE,
    entrega_por_instabilidade,
    esta_pausado,
)
from tests.unit.dublagem_agente import CLINIC, PHONE, mensagem, monta_agente


class AnthropicQuebrado:
    """A API fora do ar, como em 14/09: 400 de saldo insuficiente."""

    def __init__(self):
        self.chamadas = 0

    def create_message(self, system, messages, tools, max_tokens, tool_choice=None):
        self.chamadas += 1
        raise AnthropicError(
            'Anthropic API error 400: {"type":"error","error":{"type":'
            '"invalid_request_error","message":"Your credit balance is too low"}}'
        )


class TestOAgenteCala(unittest.TestCase):
    def test_nao_sai_mensagem_nenhuma(self):
        """O caso da 5511974247671: ela não pode receber nada."""
        agente = monta_agente(AnthropicQuebrado())
        saida = agente.process_message(CLINIC, mensagem("quero agendar axilas"))
        self.assertEqual(saida, [])

    def test_a_conversa_vai_para_uma_pessoa(self):
        """Calar sem entregar deixaria a paciente sem resposta e sem ninguém sabendo."""
        agente = monta_agente(AnthropicQuebrado())
        agente.process_message(CLINIC, mensagem("quero agendar axilas"))
        sessao = agente.sessao_salva
        self.assertEqual(sessao[CAMPO_DE_PAUSA], PAUSA_INSTABILIDADE)
        self.assertEqual(sessao["state"], "HUMAN_HANDOFF")
        self.assertTrue(esta_pausado(sessao))

    def test_a_mensagem_dela_nao_se_perde(self):
        """O histórico é salvo: quando alguém retomar, o contexto está lá."""
        agente = monta_agente(AnthropicQuebrado())
        agente.process_message(CLINIC, mensagem("quero agendar axilas"))
        historico = agente.sessao_salva.get("agent_history") or []
        self.assertIn(
            "quero agendar axilas",
            " ".join(str(t.get("content")) for t in historico),
        )


class TestOMotivoEProprio(unittest.TestCase):
    """Falha do sistema não é o bot pedindo ajuda - e só separadas dá para medir."""

    def test_nao_se_confunde_com_handoff(self):
        self.assertNotEqual(PAUSA_INSTABILIDADE, PAUSA_HANDOFF)

    def test_marca_a_sessao_e_pausa(self):
        agora = int(time.time())
        sessao = entrega_por_instabilidade({}, agora=agora)
        self.assertEqual(sessao[CAMPO_DE_PAUSA], PAUSA_INSTABILIDADE)
        self.assertEqual(sessao["attendant_active_until"], agora + 24 * 60 * 60)
        self.assertTrue(esta_pausado(sessao))

    def test_vence_como_qualquer_atendimento(self):
        """Não é pausa permanente: passadas 24h sem ninguém, o bot volta."""
        velha = entrega_por_instabilidade({}, agora=int(time.time()) - 25 * 60 * 60)
        self.assertFalse(esta_pausado(velha))

    def test_nao_perde_o_que_a_sessao_ja_tinha(self):
        sessao = entrega_por_instabilidade({"agent_history": [{"role": "user"}]})
        self.assertEqual(len(sessao["agent_history"]), 1)


class TestOFluxoDeterministico(unittest.TestCase):
    """A clínica sem agente tinha a mesma mensagem, com outras palavras."""

    def _engine(self):
        from src.services.conversation_engine import ConversationEngine

        engine = object.__new__(ConversationEngine)
        # db=None faz o handler de estado estourar de verdade dentro do
        # `_on_enter` - é a falha que o except real captura.
        engine.db = None
        engine.template_service = None
        engine.appointment_service = None
        engine.availability_engine = None
        return engine

    def test_on_enter_que_falha_entrega_e_cala(self):
        from src.services.conversation_engine import ConversationEngine, ConversationState

        engine = self._engine()
        sessao = {"state": ConversationState.PRICE_TABLE.value}

        _, _, override = engine._on_enter(
            ConversationState.PRICE_TABLE, CLINIC, PHONE, sessao
        )

        # Nada de texto de erro para a paciente...
        self.assertIsNone(override)
        # ...e a conversa foi entregue a uma pessoa.
        self.assertTrue(sessao["_falha_de_sistema"])
        self.assertEqual(sessao[CAMPO_DE_PAUSA], PAUSA_INSTABILIDADE)
        self.assertTrue(esta_pausado(sessao))
        self.assertIsNotNone(ConversationEngine)


if __name__ == "__main__":
    unittest.main()
