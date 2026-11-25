# -*- coding: utf-8 -*-
"""Na retomada, a última pergunta da pessoa vem primeiro (PRD 064)."""
import time
import unittest

from src.services import pergunta_em_aberto as pa
from tests.unit.dublagem_agente import CLINIC, AnthropicRoteiro, mensagem, monta_agente, texto_do_modelo, usa_tool


def evento(direction, content, ha_segundos=600):
    quando = time.gmtime(time.time() - ha_segundos)
    return {"direction": direction, "content": content,
            "sk": f"MSG#{time.strftime('%Y-%m-%dT%H:%M:%S', quando)}Z#x"}


class TestUltimaPergunta(unittest.TestCase):
    def test_pergunta_com_interrogacao(self):
        ev = [evento("INBOUND", "Ola"), evento("INBOUND", "Tudo bem?"), evento("INBOUND", "Quanto é a depilação na virilha? Obrigada")]
        self.assertEqual(pa.ultima_pergunta(ev), "Quanto é a depilação na virilha? Obrigada")

    def test_pergunta_sem_interrogacao(self):
        self.assertEqual(pa.ultima_pergunta([evento("INBOUND", "quanto fica axila e buço")]), "quanto fica axila e buço")

    def test_informacao_depois_da_pergunta_ainda_conta(self):
        ev = [evento("INBOUND", "tem horário sábado?"), evento("INBOUND", "axilas e virilha")]
        self.assertEqual(pa.ultima_pergunta(ev), "tem horário sábado?")

    def test_bot_respondeu_depois_entao_nada_em_aberto(self):
        ev = [evento("INBOUND", "quanto é?"), evento("OUTBOUND", "Depende das áreas.")]
        self.assertIsNone(pa.ultima_pergunta(ev))

    def test_fecho_social_nao_e_pergunta(self):
        self.assertIsNone(pa.ultima_pergunta([evento("INBOUND", "obrigada!")]))
        self.assertIsNone(pa.ultima_pergunta([evento("INBOUND", "Tudo bem?")]))


class TestRespondeu(unittest.TestCase):
    def test_fala_do_assunto(self):
        self.assertTrue(pa.respondeu("O valor da virilha depende do tipo: simples, cavada ou completa.",
                                     "Quanto é a depilação na virilha?"))

    def test_preco_respondido_com_numero(self):
        self.assertTrue(pa.respondeu("Sai por R$ 120.", "quanto custa?"))

    def test_mudou_de_assunto(self):
        self.assertFalse(pa.respondeu("Oi! Aqui é da clínica. Quais áreas você gostaria de tratar?",
                                      "Quanto é a depilação na virilha?"))

    def test_sem_pergunta_sempre_ok(self):
        self.assertTrue(pa.respondeu("qualquer coisa", None))


class TestLimpaMeta(unittest.TestCase):
    def test_tira_o_bastidor(self):
        self.assertEqual(pa.limpa_meta("peço desculpas, vou reformular. temos três opções de virilha."),
                         "Temos três opções de virilha.")
        self.assertEqual(pa.limpa_meta("Reformulando: a virilha simples sai por R$ 70."), "A virilha simples sai por R$ 70.")

    def test_nao_mexe_no_resto(self):
        self.assertEqual(pa.limpa_meta("Desculpe a demora! A virilha sai por R$ 70."), "Desculpe a demora! A virilha sai por R$ 70.")
        self.assertEqual(pa.limpa_meta(""), "")


class TestNoAgente(unittest.TestCase):
    def _agente(self, roteiro):
        anthropic = AnthropicRoteiro(roteiro)
        agente = monta_agente(anthropic=anthropic)
        agente._eventos_recentes = lambda c, p, limit=6: [
            evento("INBOUND", "Ola"), evento("INBOUND", "Quanto é a depilação na virilha? Obrigada")]
        return agente, anthropic

    def test_retomada_leva_a_pergunta_no_turno_e_no_fim_do_system(self):
        agente, anthropic = self._agente([texto_do_modelo("Olá! O valor da virilha depende do tipo. Qual você quer?")])
        agente.process_message(CLINIC, mensagem("__RETOMAR_CONVERSA__"))
        turno = anthropic.conversas[0][-1]["content"]
        self.assertIn("PERGUNTA EM ABERTO", turno)
        self.assertIn("Quanto é a depilação na virilha?", turno)
        self.assertTrue(anthropic.prompts[0].rstrip().endswith("para depois."))

    def test_resposta_fora_da_pergunta_e_reescrita_uma_vez(self):
        agente, anthropic = self._agente([
            texto_do_modelo("Olá! Aqui é da clínica. Quais áreas você gostaria de tratar?"),
            texto_do_modelo("Olá! O valor da virilha depende do tipo (simples, cavada ou completa). Qual você prefere?"),
        ])
        saida = agente.process_message(CLINIC, mensagem("__RETOMAR_CONVERSA__"))
        self.assertEqual(anthropic.chamadas, 2)
        self.assertIn("virilha", saida[0].content.lower())
        self.assertTrue(any("Responda primeiro" in c for c in anthropic.correcoes) or anthropic.chamadas == 2)

    def test_mensagem_comum_nao_ganha_o_bloco(self):
        agente, anthropic = self._agente([usa_tool("sem_consulta_necessaria", {"motivo": "x"}), texto_do_modelo("Oi!")])
        agente.process_message(CLINIC, mensagem("oi"))
        self.assertNotIn("PERGUNTA EM ABERTO", anthropic.conversas[0][-1]["content"])
        self.assertNotIn("A PERGUNTA VEM PRIMEIRO", anthropic.prompts[0])
