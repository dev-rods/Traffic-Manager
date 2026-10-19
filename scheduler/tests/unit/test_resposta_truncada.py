# -*- coding: utf-8 -*-
"""Resposta cortada pelo teto de saida, ou vazia, nunca vira silencio.

Em 17/10/2026, na Essencia, a rodada que ia apresentar os horarios de duas
areas gerou exatamente 1024 tokens (o teto de entao). A API cortou no meio do
bloco de present_options e devolveu conteudo vazio com stop_reason=max_tokens.
O agente tratou o vazio como resposta final: zero mensagens, zero log. A
paciente ficou dois dias sem resposta, ate alguem responder pelo celular.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import atendimento as at
from src.services.bot_policy import MOTIVO_ESGOTOU
from src.services.conversation_agent import MAX_TOKENS_DE_SAIDA, PEDIDO_DE_VERSAO_CURTA
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo, usa_tool,
)


def cortada_no_meio_da_tool():
    """O que a API devolve quando o teto cai dentro de um tool_use: nada."""
    return {"content": [], "stop_reason": "max_tokens"}


def texto_cortado(t):
    return {"content": [{"type": "text", "text": t}], "stop_reason": "max_tokens"}


class TestRespostaTruncada(unittest.TestCase):

    def test_vazia_pede_versao_curta_e_responde(self):
        anthropic = AnthropicRoteiro([
            usa_tool("check_availability"),
            cortada_no_meio_da_tool(),
            texto_do_modelo("Encontrei três opções de horário. Qual período prefere?"),
        ])
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={"available_slots": ["10:00"]})
        saida = agente.process_message(CLINIC, mensagem("sim, por favor"))

        self.assertEqual(len(saida), 1)
        self.assertIn("três opções", saida[0].content)
        self.assertEqual(anthropic.chamadas, 3)
        # O pedido de versao curta foi anexado ao turno do usuario (conteudo
        # vazio nao pode virar turno de assistente).
        ultima = anthropic.conversas[-1][-1]
        self.assertEqual(ultima["role"], "user")
        self.assertIn(PEDIDO_DE_VERSAO_CURTA, str(ultima["content"]))

    def test_texto_cortado_tambem_e_refeito(self):
        anthropic = AnthropicRoteiro([
            texto_cortado("Claro! As opções que encontrei para você são: primeiro a de"),
            texto_do_modelo("Encontrei uma opção de manhã. Fica bom?"),
        ])
        agente = monta_agente(anthropic=anthropic)
        saida = agente.process_message(CLINIC, mensagem("oi"))

        self.assertEqual(len(saida), 1)
        self.assertNotIn("primeiro a de", saida[0].content, "o texto pela metade nao sai")
        self.assertIn("opção de manhã", saida[0].content)
        self.assertEqual(anthropic.correcoes, [PEDIDO_DE_VERSAO_CURTA])

    def test_cortada_com_ferramenta_inteira_segue_normal(self):
        """stop_reason=max_tokens mas o tool_use veio completo: executa."""
        anthropic = AnthropicRoteiro([
            {"content": [{"type": "tool_use", "id": "t1", "name": "check_availability", "input": {}}],
             "stop_reason": "max_tokens"},
            texto_do_modelo("Encontrei horários. Quer que eu reserve?"),
        ])
        agente = monta_agente(anthropic=anthropic, resultado_da_tool={"available_slots": ["10:00"]})
        saida = agente.process_message(CLINIC, mensagem("quais horários?"))

        # A pre-carga (identificar_paciente, list_areas) vem antes; o que importa
        # e a ferramenta do turno ter rodado.
        self.assertIn("check_availability", agente.tool_executor.chamadas)
        self.assertEqual(len(saida), 1)
        self.assertEqual(anthropic.correcoes, [])

    def test_vazia_duas_vezes_avisa_e_entrega_a_uma_pessoa(self):
        anthropic = AnthropicRoteiro([cortada_no_meio_da_tool(), cortada_no_meio_da_tool()])
        agente = monta_agente(anthropic=anthropic)
        agente.db = mock.MagicMock()
        agente.db.execute_query.return_value = [{"id": "tarefa-1"}]
        saida = agente.process_message(CLINIC, mensagem("oi"))

        self.assertEqual(len(saida), 1, "silencio nunca")
        self.assertIn("especialista", saida[0].content)
        sessao = agente.sessao_salva
        self.assertEqual(at.estado(sessao), at.HUMAN_ACTIVE)
        self.assertEqual(sessao[at.CAMPO]["handoff_reason"], MOTIVO_ESGOTOU)
        self.assertIsNotNone(sessao[at.CAMPO].get("pending_intent"), "a fila ve a pendencia")

    def test_o_teto_de_saida_subiu(self):
        """1024 nao cabia uma present_options com os horarios de tres dias."""
        self.assertGreaterEqual(MAX_TOKENS_DE_SAIDA, 2048)
        visto = []
        anthropic = AnthropicRoteiro([texto_do_modelo("oi")])
        original = anthropic.create_message

        def create_message(system, messages, tools, max_tokens, tool_choice=None):
            visto.append(max_tokens)
            return original(system, messages, tools, max_tokens, tool_choice)

        anthropic.create_message = create_message
        monta_agente(anthropic=anthropic).process_message(CLINIC, mensagem("oi"))
        self.assertEqual(visto, [MAX_TOKENS_DE_SAIDA])


if __name__ == "__main__":
    unittest.main()
