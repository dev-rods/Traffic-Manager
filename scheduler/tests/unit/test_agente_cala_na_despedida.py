# -*- coding: utf-8 -*-
"""O agente cala na despedida repetida e cumprimenta pelo relógio (PRD 064).

Caso de 24/11/2026 (Nobre): "Muito obrigada" -> "Por nada! Até o dia 03/12"
-> "Até 🙂" -> "Até lá!". Duas defesas: a guarda determinística antes do
modelo (eventos recentes) e, se ela não pegar, a declaração do próprio modelo
em `sem_consulta_necessaria(motivo="despedida")` com resposta vazia, que
deixa de virar handoff.
"""
import os
import time
import unittest
from datetime import datetime
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import conversation_agent as modulo
from tests.unit.dublagem_agente import (
    CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo, usa_tool,
)


def evento(direction, content, ha_segundos=60):
    quando = time.gmtime(time.time() - ha_segundos)
    return {"direction": direction, "content": content,
            "sk": f"MSG#{time.strftime('%Y-%m-%dT%H:%M:%S', quando)}Z#x"}


class TestGuardaAntesDoModelo(unittest.TestCase):

    def test_ate_depois_do_ate_do_bot_nao_chama_o_modelo(self):
        anthropic = AnthropicRoteiro([texto_do_modelo("Até lá! 💛")])
        agente = monta_agente(anthropic=anthropic)
        agente._eventos_recentes = lambda c, p: [
            evento("INBOUND", "Muito obrigada 😊", 120),
            evento("OUTBOUND", "Por nada! Até o dia 03/12 💛", 60),
        ]
        saida = agente.process_message(CLINIC, mensagem("Até 🙂"))
        self.assertEqual(saida, [])
        self.assertEqual(anthropic.chamadas, 0)

    def test_pergunta_depois_da_despedida_e_atendida(self):
        anthropic = AnthropicRoteiro([usa_tool("sem_consulta_necessaria", {"motivo": "pergunta"}),
                                      texto_do_modelo("Sim, pode raspar no dia.")])
        agente = monta_agente(anthropic=anthropic)
        agente._eventos_recentes = lambda c, p: [evento("OUTBOUND", "Até lá! 💛", 60)]
        saida = agente.process_message(CLINIC, mensagem("obrigada! e eu raspo no dia?"))
        self.assertEqual(len(saida), 1)
        self.assertIn("raspar", saida[0].content)


class TestModeloDeclaraDespedida(unittest.TestCase):

    def test_sem_consulta_despedida_e_resposta_vazia_nao_vira_handoff(self):
        anthropic = AnthropicRoteiro([
            usa_tool("sem_consulta_necessaria", {"motivo": "despedida, nada a consultar"}),
            {"content": [], "stop_reason": "end_turn"},
        ])
        agente = monta_agente(anthropic=anthropic)
        saida = agente.process_message(CLINIC, mensagem("Até 🙂"))
        self.assertEqual(saida, [])
        self.assertEqual(anthropic.chamadas, 2)
        self.assertEqual(anthropic.correcoes, [])
        # Historico gravado continua valido: nao termina em turno de usuario solto.
        hist = agente.sessao_salva.get("agent_history") or []
        self.assertTrue(not hist or hist[-1]["role"] != "user")

    def test_sem_consulta_por_outro_motivo_e_vazio_continua_sendo_falha(self):
        anthropic = AnthropicRoteiro([
            usa_tool("sem_consulta_necessaria", {"motivo": "paciente mandou o nome"}),
            {"content": [], "stop_reason": "end_turn"},
            texto_do_modelo("Perfeito, anotei. Qual o seu CPF?"),
        ])
        agente = monta_agente(anthropic=anthropic)
        saida = agente.process_message(CLINIC, mensagem("Maria Teste"))
        self.assertEqual(len(saida), 1)
        # Pediu a versao curta (terceira chamada) em vez de aceitar o vazio.
        self.assertEqual(anthropic.chamadas, 3)


class TestSaudacaoPeloRelogio(unittest.TestCase):

    def _agente_as(self, hora, texto):
        anthropic = AnthropicRoteiro([usa_tool("sem_consulta_necessaria", {"motivo": "saudacao"}),
                                      texto_do_modelo(texto)])
        agente = monta_agente(anthropic=anthropic)
        agora = datetime(2026, 11, 25, hora, 10)
        return agente, anthropic, mock.patch.object(modulo._relogio, "agora_na_clinica", return_value=agora)

    def test_boa_noite_copiada_vira_bom_dia(self):
        agente, _, relogio = self._agente_as(8, "Olá, boa noite! Aqui é da clínica. Quais áreas você quer tratar?")
        with relogio:
            saida = agente.process_message(CLINIC, mensagem("Olá, boa noite"))
        self.assertIn("bom dia", saida[0].content)
        self.assertNotIn("boa noite", saida[0].content)

    def test_calendario_traz_a_hora_e_o_periodo(self):
        agente, anthropic, relogio = self._agente_as(15, "Boa tarde! Quais áreas?")
        with relogio:
            agente.process_message(CLINIC, mensagem("oi"))
        turno = anthropic.conversas[0][-1]["content"]
        self.assertIn("Agora: 15:10, tarde.", turno)

    def test_regra_da_saudacao_e_da_despedida_no_prompt(self):
        # Os blocos sao anexados em _build_system_prompt (prefixo cacheado);
        # o dublê troca essa funcao, entao a verificacao e pela fonte.
        import inspect
        fonte = inspect.getsource(modulo.ConversationAgent._build_system_prompt)
        self.assertIn("DESPEDIDA", fonte)
        self.assertIn("Cumprimente pelo período de AGORA", fonte)
