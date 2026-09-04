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
    DURACAO,
    PRECO,
    exige_consulta,
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

    def test_nenhuma_tool_precarregada_exige_argumento(self):
        """A pré-carga chama as tools com argumento vazio.

        check_availability e calculate_duration dependem das áreas escolhidas,
        que só existem na conversa - pré-carregá-las devolveria o piso de 15
        minutos como se fosse a duração real, que é mentira com cara de dado
        consultado.
        """
        sem_argumento = {"lookup_appointments", "list_services", "list_areas"}

        for nome in (AGENDAMENTO_PROPRIO, PRECO, DISPONIBILIDADE, DURACAO):
            for tool in tools_obrigatorias({nome}):
                with self.subTest(intencao=nome, tool=tool):
                    self.assertIn(tool, sem_argumento)


class TestDuracao(unittest.TestCase):
    """"Quanto tempo dura?" não casava com nada, e o agente respondia de
    memória - a pergunta é comum e a resposta é derivada."""

    def test_a_frase_que_falhou_em_producao(self):
        self.assertIn(DURACAO, intencoes("Quanto tempo dura mesmo a sessão para essas áreas?"))

    def test_variantes_reais(self):
        for frase in ["qual a duração da sessão?", "quanto tempo demora",
                      "quantos minutos leva", "quanto tempo dura",
                      "quanto duram as sessões"]:
            with self.subTest(frase=frase):
                self.assertIn(DURACAO, intencoes(frase))

    def test_nao_dispara_em_conversa_comum(self):
        for frase in ["oi, tudo bem?", "quanto custa a virilha", "obrigado!"]:
            with self.subTest(frase=frase):
                self.assertNotIn(DURACAO, intencoes(frase))


class TestConsultaEhOPadrao(unittest.TestCase):
    """`exige_consulta` inverteu o desenho: consultar é o default.

    Antes o tool_choice era forçado só quando o regex reconhecia o assunto, e a
    lista de assuntos factuais não tem fim - "E horários à tarde?" não casava
    com nada e o bot listou dez horários inventados. Agora a lista curta é a de
    conversa fiada.
    """

    def test_a_frase_que_escapou_do_regex(self):
        self.assertTrue(exige_consulta("E horários à tarde?"))

    def test_duvidas_de_faq_exigem_consulta(self):
        """Antes iam direto para a memória: o FAQ inteiro estava no prompt."""
        for frase in ["dói muito?", "quantas sessões preciso?",
                      "posso fazer bronzeada?", "pode parcelar?",
                      "vocês atendem sábado?"]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))

    def test_frase_afirmativa_sobre_assunto_factual_exige_consulta(self):
        for frase in ["quero agendar", "buço e axilas", "pode ser 14h"]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))

    def test_escolha_de_area_exige_consulta(self):
        """O caso que a heurística de maiúscula quebrava - e o mais caro."""
        for frase in ["Buço Completo", "Axilas", "Perna Completa", "Virilha Cavada"]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))

    def test_escolha_de_data_exige_consulta(self):
        for frase in ["23/09", "15/10"]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))


class TestExcecoesDeConversaFiada(unittest.TestCase):
    """A lista curta: um conjunto fechado, casado contra a mensagem inteira."""

    def test_social(self):
        for frase in ["oi", "bom dia", "tudo bem?", "obrigado!", "valeu",
                      "tchau", "sim", "ok", "perfeito", "beleza", "entendi"]:
            with self.subTest(frase=frase):
                self.assertFalse(exige_consulta(frase))

    def test_social_emendado(self):
        """"oi, tudo bem?" são duas expressões sociais, não uma pergunta."""
        for frase in ["oi, tudo bem?", "bom dia, tudo bem?", "obrigado, valeu!"]:
            with self.subTest(frase=frase):
                self.assertFalse(exige_consulta(frase))

    def test_social_mais_pergunta_exige_consulta(self):
        """Basta um pedaço não ser conversa fiada."""
        self.assertTrue(exige_consulta("oi, quanto custa?"))

    def test_nao_adivinha_dado_de_cadastro_pelo_formato(self):
        """Quem declara que não precisa consultar é o modelo, não o regex.

        Reconhecer cadastro pelo formato errava dos dois lados: "Buço Completo"
        tem cara de nome próprio e "23/09" tem cara de data de nascimento.
        """
        for frase in ["André Felipe", "andre felipe", "1999", "12/05/1990",
                      "andre@gmail.com", "123.456.789-00"]:
            with self.subTest(frase=frase):
                self.assertTrue(exige_consulta(frase))

    def test_maiuscula_nao_muda_a_classificacao(self):
        """O cliente escreve como quiser; o formato não carrega a intenção."""
        self.assertEqual(exige_consulta("André Felipe"), exige_consulta("andre felipe"))
        self.assertEqual(exige_consulta("AXILAS"), exige_consulta("axilas"))

    def test_vazio_nao_consulta(self):
        self.assertFalse(exige_consulta(""))
        self.assertFalse(exige_consulta(None))
