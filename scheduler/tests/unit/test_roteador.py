"""Que consulta a pergunta do cliente exige antes de qualquer resposta.

As frases dos testes foram TIRADAS DAS CONVERSAS REAIS da Essência - 180
mensagens de clientes no MessageEvents. Inventar frases aqui reproduziria o
erro do dia: eu escrevi um payload que supus e o teste passou sem provar nada.
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")
os.environ.setdefault("MESSAGE_EVENTS_TABLE", "test-events")

from src.services.roteador import (
    AGENDAMENTO_PROPRIO,
    DISPONIBILIDADE,
    PRECO,
    intencoes,
    tools_obrigatorias,
)


class TestAgendamentoProprio(unittest.TestCase):
    """Perguntas sobre a agenda da própria pessoa - o caso que gerou o bug."""

    def test_frases_reais(self):
        for frase in [
            "A minha sessão está confirmada?",
            "Quando é minha próxima sessão?",
            "Estou confuso, achei que tinha ligado para cancelar essa sessão",
            "Remarcar sessão",
            "Cancelar sessão",
            "Me confirma as informações do meu próximo agendamento?",
        ]:
            with self.subTest(frase=frase):
                self.assertIn(AGENDAMENTO_PROPRIO, intencoes(frase))


class TestPreco(unittest.TestCase):
    def test_frases_reais(self):
        for frase in [
            "Você pode me passar a tabela de preços?",
            "Quanto esta o botox?",
            "Gostaria de saber os valores da depilação a laser",
            "Qual o valor da sessão avulsa?",
        ]:
            with self.subTest(frase=frase):
                self.assertIn(PRECO, intencoes(frase))


class TestDisponibilidade(unittest.TestCase):
    def test_frases_reais(self):
        for frase in [
            "Bom dia! Gostaria de marcar horário para depilação a laser",
            "Eu queria saber quais vão ser as datas disponíveis desse mês de setembro",
            "as 20:30 vc tem que dia disponível pra depilação?",
            "Agendar sessão",
            "oi! gostaria de marcar pro dia 29",
        ]:
            with self.subTest(frase=frase):
                self.assertIn(DISPONIBILIDADE, intencoes(frase))


class TestConversaComum(unittest.TestCase):
    """Não pode disparar consulta à toa: cada pré-carga custa latência."""

    def test_frases_reais_sem_intencao(self):
        for frase in [
            "Oi, tudo bem?",
            "Obrigada!",
            "Faz sentido, muito obrigado",
            "Bom dia",
            "Eu não consigo depilar com lamina antes da sessão",
        ]:
            with self.subTest(frase=frase):
                self.assertEqual(intencoes(frase), set())

    def test_vazio(self):
        self.assertEqual(intencoes(""), set())
        self.assertEqual(intencoes(None), set())


class TestMultiplasIntencoes(unittest.TestCase):
    def test_pergunta_combinada(self):
        frase = "Quanto custa e quais datas tem disponível?"
        achadas = intencoes(frase)
        self.assertIn(PRECO, achadas)
        self.assertIn(DISPONIBILIDADE, achadas)


class TestToolsObrigatorias(unittest.TestCase):
    def test_agendamento_exige_lookup(self):
        self.assertIn("lookup_appointments", tools_obrigatorias({AGENDAMENTO_PROPRIO}))

    def test_preco_exige_catalogo(self):
        tools = tools_obrigatorias({PRECO})
        self.assertTrue({"list_services", "list_areas"} & set(tools))

    def test_disponibilidade_pre_carrega_o_catalogo_e_nao_a_agenda(self):
        """check_availability passou a exigir as áreas escolhidas.

        A pré-carga chama as tools com argumento vazio. Pré-carregá-la agora
        devolveria os dias de uma sessão de 15 minutos - o piso - entregues ao
        modelo como dado consultado. A agenda de verdade o agente consulta
        depois, com as áreas em mãos.
        """
        tools = tools_obrigatorias({DISPONIBILIDADE})

        self.assertNotIn("check_availability", tools)
        self.assertIn("list_areas", tools)

    def test_sem_intencao_nao_exige_nada(self):
        self.assertEqual(tools_obrigatorias(set()), [])
