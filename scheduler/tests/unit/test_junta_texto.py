# -*- coding: utf-8 -*-
"""A bolha com opções não repete a chamada para a lista.

Casos reais de 13 e 16/10/2026 (Essência): o modelo escreveu a mesma
chamada em `present_options.message` e na fala final, e a paciente leu a
pergunta duas vezes na mesma bolha. O padrão legítimo "responde e então
oferece" (test_agente_sabe_a_data) continua saindo inteiro.
"""
import unittest

from src.services.conversation_agent import ConversationAgent

junta = ConversationAgent._junta_texto


class TestDuasChamadasViramUma(unittest.TestCase):

    def test_16_10_turno_2_fica_a_final_com_o_reconhecimento(self):
        r = junta("Qual tipo de virilha você prefere?",
                  "Perfeito, vamos agendar sua sessão! Só preciso saber: qual tipo de virilha "
                  "você prefere - Cavada, Completa, Simples ou 1/2 Virilha?")
        self.assertEqual(r.count("virilha você prefere"), 1)
        self.assertTrue(r.startswith("Perfeito, vamos agendar"))

    def test_16_10_turno_1_duas_perguntas_viram_uma(self):
        r = junta("Temos alguns tipos de virilha. Qual você prefere?",
                  "Qual delas faz mais sentido pra você: Virilha Cavada, Virilha Completa, "
                  "Virilha Simples ou 1/2 Virilha?")
        self.assertEqual(r.count("?"), 1)

    def test_13_10_mesma_frase_com_e_sem_negrito(self):
        r = junta("Perfeito! Para a sessão de Axilas, essas são as próximas datas disponíveis:",
                  "Perfeito! Para a sessão de *Axilas,* essas são as próximas datas disponíveis:")
        self.assertEqual(r, "Perfeito! Para a sessão de *Axilas,* essas são as próximas datas disponíveis:")

    def test_13_10_dois_pontos_duas_vezes_vira_um(self):
        r = junta("Horários disponíveis em 22/10 (tarde):",
                  "Esses são alguns horários de tarde disponíveis em *22/10:*")
        self.assertEqual(r, "Esses são alguns horários de tarde disponíveis em *22/10:*")

    def test_emoji_no_fim_nao_esconde_a_pergunta(self):
        r = junta("Qual área você quer tratar?", "Me conta qual área você gostaria de tratar? 😊")
        self.assertEqual(r.count("?"), 1)


class TestRespondeEEntaoOferece(unittest.TestCase):

    def test_resposta_mais_pergunta_saem_as_duas(self):
        r = junta("Amanhã (05/09) não temos horário.", "Alguma dessas fica boa pra você?")
        self.assertIn("05/09", r)
        self.assertIn("Alguma dessas fica boa pra você?", r)

    def test_pergunta_mais_fechamento_saem_as_duas(self):
        r = junta("Qual data prefere?", "Qualquer dúvida me chama 😊")
        self.assertIn("Qual data prefere?", r)
        self.assertIn("Qualquer dúvida", r)

    def test_uma_so_vazia(self):
        self.assertEqual(junta("", "Qual data?"), "Qual data?")
        self.assertEqual(junta("Qual data?", None), "Qual data?")
