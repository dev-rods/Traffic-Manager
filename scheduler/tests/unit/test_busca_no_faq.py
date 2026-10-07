# -*- coding: utf-8 -*-
"""A busca entrega a resposta que a clínica já escreveu.

O caso de 23/09/2026, tirado do log de produção: a paciente perguntou se podia
fazer a sessão menstruada, o bot traduziu certo para a tool

    get_faq_answer({"question": "Pode fazer a sessão estando menstruada?"})

e a busca devolveu três itens que não tinham nada a ver. O FAQ da Essência tem
"Posso fazer menstruada?" - com a resposta completa, inclusive sobre absorvente.
A paciente repetiu a pergunta e acabou atendida por uma especialista, para algo
que a clínica já respondia por escrito.

Os testes rodam contra o FAQ REAL (faq_real.py), e não contra um inventado.
Conferir regra de busca contra dado imaginário já passou uma vez aqui, em
16/09, e custou cinco perguntas repetidas a uma paciente.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from faq_real import FAQ_ESSENCIA
from src.services.busca_no_faq import PISO, busca, pontua, termos, _peso_dos_termos


def titulos(resultado):
    return [i["question_label"] for i in resultado]


class TestOCasoDaPaciente(unittest.TestCase):
    """23/09/2026, reproduzido com a pergunta exata que saiu no log."""

    PERGUNTA = "Pode fazer a sessão estando menstruada?"

    def test_a_resposta_certa_vem_em_primeiro(self):
        r = busca(self.PERGUNTA, FAQ_ESSENCIA)

        self.assertTrue(r, "a busca não pode voltar vazia: a resposta existe")
        self.assertEqual(r[0]["question_label"], "Posso fazer menstruada?")

    def test_e_os_tres_irrelevantes_de_antes_saem(self):
        """Eram estes que a busca antiga devolvia, por estarem no topo da
        lista e casarem com 'pode', 'fazer' ou 'sessão'."""
        r = titulos(busca(self.PERGUNTA, FAQ_ESSENCIA))

        self.assertNotIn("O resultado é definitivo?", r)
        self.assertNotIn("Posso fazer mais de uma sessão na mesma área no mesmo dia?", r)

    def test_a_resposta_fala_de_absorvente(self):
        """O conteúdo que a paciente precisava e não recebeu."""
        r = busca(self.PERGUNTA, FAQ_ESSENCIA)

        self.assertIn("absorvente", r[0]["answer"].lower())


class TestPerguntasComoAsPacientesEscrevem(unittest.TestCase):
    """Ninguém digita o título do item do FAQ."""

    CASOS = [
        ("tem problema fazer menstruada?", "Posso fazer menstruada?"),
        ("posso ficar no sol depois?", "Posso pegar sol antes ou depois da sessão?"),
        ("doi muito?", "Depilação a Laser dói?"),
        ("quantas sessoes preciso fazer", "Quantas sessões são necessárias?"),
        ("tenho silicone, pode?", "Tenho prótese de silicone, posso fazer?"),
        ("virilha completa pega o anus?", "Virilha completa já inclui o ânus?"),
        ("atende homem?", "Atende homens também?"),
        ("fiz cera semana passada", "Fiz depilação com cera, posso fazer laser?"),
    ]

    def test_cada_uma_acha_o_item_certo(self):
        for pergunta, esperado in self.CASOS:
            with self.subTest(pergunta):
                r = busca(pergunta, FAQ_ESSENCIA)
                self.assertTrue(r, "voltou vazio")
                self.assertEqual(r[0]["question_label"], esperado)

    def test_sem_acento_acha_igual(self):
        """A paciente escreve no celular, com pressa."""
        com = busca("posso fazer menstruada?", FAQ_ESSENCIA)
        sem = busca("posso fazer menstruada", FAQ_ESSENCIA)

        self.assertEqual(titulos(com)[:1], titulos(sem)[:1])
        self.assertEqual(
            titulos(busca("depilacao a laser doi", FAQ_ESSENCIA))[0],
            "Depilação a Laser dói?",
        )


class TestOPisoProtegeODesconhecido(unittest.TestCase):
    """Vazio é uma resposta: faz o bot chamar a especialista."""

    def test_assunto_fora_do_faq_volta_vazio(self):
        for pergunta in (
            "vocês fazem massagem modeladora?",
            "aceitam pagamento em bitcoin?",
            "tem vaga de emprego?",
        ):
            with self.subTest(pergunta):
                self.assertEqual(busca(pergunta, FAQ_ESSENCIA), [])

    def test_so_palavra_comum_nao_e_resposta(self):
        """"Posso fazer?" casava com meio FAQ na busca antiga."""
        self.assertEqual(busca("posso fazer?", FAQ_ESSENCIA), [])

    def test_pergunta_vazia_nao_quebra(self):
        for lixo in ("", "   ", "???", None):
            with self.subTest(repr(lixo)):
                self.assertEqual(busca(lixo, FAQ_ESSENCIA), [])

    def test_faq_vazio_nao_quebra(self):
        self.assertEqual(busca("posso fazer menstruada?", []), [])


class TestComoAPontuacaoDecide(unittest.TestCase):
    def setUp(self):
        self.pesos = _peso_dos_termos(FAQ_ESSENCIA)

    def test_palavra_rara_vale_mais_que_comum(self):
        """É o coração da correção: 'menstruada' aparece em 1 item, 'sessão'
        em muitos. Pesar igual foi o que enterrou a resposta certa."""
        self.assertGreater(self.pesos["menstruada"], self.pesos["sessao"])

    def test_titulo_vale_mais_que_resposta(self):
        item = {
            "question_label": "Posso fazer menstruada?",
            "answer": "Outro assunto qualquer.",
        }
        outro = {
            "question_label": "Outro assunto qualquer.",
            "answer": "Posso fazer menstruada?",
        }

        self.assertGreater(
            pontua("menstruada", item, self.pesos),
            pontua("menstruada", outro, self.pesos),
        )

    def test_palavras_vazias_nao_pontuam(self):
        item = {"question_label": "Posso fazer menstruada?", "answer": ""}

        self.assertEqual(pontua("posso fazer", item, self.pesos), 0.0)

    def test_o_piso_e_alcancavel_por_uma_palavra_rara(self):
        """Se o piso exigisse duas palavras raras, 'menstruada?' sozinha -
        que é como a paciente insistiu - voltaria vazia."""
        item = next(i for i in FAQ_ESSENCIA
                    if i["question_label"] == "Posso fazer menstruada?")

        self.assertGreaterEqual(pontua("menstruada", item, self.pesos), PISO)


class TestNormalizacao(unittest.TestCase):
    def test_pontuacao_nao_gruda_na_palavra(self):
        """A busca antiga procurava literalmente `%menstruada?%`, com a
        interrogação colada - e por isso não casava com o texto da resposta."""
        self.assertEqual(termos("menstruada?"), ["menstruada"])

    def test_acento_sai(self):
        self.assertEqual(termos("sessão"), ["sessao"])

    def test_palavra_curta_sai(self):
        self.assertNotIn("eu", termos("eu quero"))


class TestQuantidade(unittest.TestCase):
    def test_no_maximo_tres(self):
        r = busca("cuidados antes depois sol cera sessão pelos", FAQ_ESSENCIA)

        self.assertLessEqual(len(r), 3)


class TestOsAchadosDaRevisao(unittest.TestCase):
    """Dois defeitos que sobreviveram à primeira versão desta busca.

    Achados relendo o próprio código em 27/09/2026, antes do deploy. Nenhum
    dos dois quebrava um teste - o primeiro passava por sorte de ordenação, e
    o segundo não era testado.
    """

    def test_quantas_pontua_em_vez_de_ser_ignorada(self):
        """"quantas/quanto/quando" estavam na lista de palavras vazias.

        Com elas ignoradas, "quantas sessões preciso fazer" sobrava só com
        "sessão" - que casa com 12 dos 19 itens - e virava um empate triplo
        decidido por `display_order`. O item certo vencia porque está em 4º na
        lista, não porque a busca o achou relevante: bastaria a clínica
        reordenar o FAQ para a resposta mudar.
        """
        self.assertIn("quanta", termos("quantas sessoes"))
        self.assertIn("quando", termos("quando posso voltar"))

    def test_e_a_pergunta_de_quantidade_ganha_sozinha(self):
        pesos = _peso_dos_termos(FAQ_ESSENCIA)
        r = busca("quantas sessoes preciso fazer", FAQ_ESSENCIA)

        self.assertEqual(r[0]["question_label"], "Quantas sessões são necessárias?")
        if len(r) > 1:
            primeiro = pontua("quantas sessoes preciso fazer", r[0], pesos)
            segundo = pontua("quantas sessoes preciso fazer", r[1], pesos)
            self.assertGreater(primeiro, segundo, "empate no topo é decidido por ordem")

    def test_item_muito_mais_fraco_nao_viaja_junto(self):
        """O 3º colocado da pergunta sobre menstruação era "Quantas sessões são
        necessárias?", com 15% da pontuação do 1º - passava só porque "sessão"
        casa.

        Item fraco ao lado da resposta certa é convite para o modelo costurar
        os dois, e foi assim que a paciente recebeu cuidados pré-sessão quando
        perguntou outra coisa.
        """
        r = busca("Pode fazer a sessão estando menstruada?", FAQ_ESSENCIA)

        self.assertNotIn("Quantas sessões são necessárias?", titulos(r))

    def test_mas_o_complementar_de_verdade_continua(self):
        """O corte não pode ser tão apertado que devolva sempre um item só:
        em "posso pegar sol?", o segundo tem 45% e complementa a resposta."""
        r = busca("posso pegar sol?", FAQ_ESSENCIA)

        self.assertEqual(len(r), 2)
        self.assertIn("Pode fazer em pele bronzeada/com sol?", titulos(r))


class TestIntervaloEntreSessoes(unittest.TestCase):
    """06/10/2026: "fiz 29/9, faço 28/10?" foi para especialista porque o FAQ
    não tinha a pergunta - a resposta estava escondida dentro de "Quantas
    sessões?" e de "mais de uma sessão no mesmo dia?". O item novo tem de
    chegar ao modelo para as formas em que ele pergunta à tool."""

    def test_o_item_chega_ao_modelo(self):
        from tests.unit.faq_real import FAQ_ESSENCIA

        for pergunta in (
            "Qual o intervalo recomendado entre sessões de depilação a laser?",
            "Qual o intervalo ideal entre uma sessão de depilação a laser e outra?",
            "intervalo entre sessões",
            "quanto tempo entre uma sessão e outra",
        ):
            with self.subTest(pergunta=pergunta):
                achados = [a["question_label"] for a in busca(pergunta, FAQ_ESSENCIA)]
                self.assertIn("Qual o intervalo entre as sessões?", achados)


class TestPerguntasReaisDeProducao(unittest.TestCase):
    """O que o modelo de fato perguntou à tool em produção (12 dias até
    06/10/2026), com o item que deveria vir em primeiro - ou None quando o
    FAQ não tem a resposta e o certo é voltar vazio.

    Antes da cobertura do título: 24 de 33. Depois: 30. Os três que ainda
    erram estão em `AINDA_ERRAM`, nomeados, para quem for mexer no ranqueador
    saber o que ganha e o que perde.
    """

    INTERVALO = "Qual o intervalo entre as sessões?"
    CASOS = [
        ("Qual o intervalo recomendado entre sessões de depilação a laser?", INTERVALO),
        ("Qual o intervalo ideal entre uma sessão de depilação a laser e outra?", INTERVALO),
        ("intervalo entre sessões", INTERVALO),
        ("quanto tempo entre uma sessão e outra", INTERVALO),
        ("Quantas sessões são necessárias para resultado?", "Quantas sessões são necessárias?"),
        ("Depilação a laser dói? Como funciona o método?", "Depilação a Laser dói?"),
        ("virilha completa inclui região perianal/ânus?", "Virilha completa já inclui o ânus?"),
        ("virilha inclui região do ânus/perianal?", "Virilha completa já inclui o ânus?"),
        ("vocês fazem pacote de sessões?", {"Quantas sessões são necessárias?", None}),
        ("Vocês fazem botox?", None),
        ("Vocês emitem nota fiscal?", None),
        ("Parcela? Formas de pagamento, aceita parcelamento?", None),
        ("atraso para a sessão, posso chegar atrasada", None),
        ("Posso escolher atendimento com uma profissional específica?", None),
        ("Por que o preço das áreas mudou de um mês para outro?", None),
    ]

    # Conhecidos. Não são regressão: já erravam antes da cobertura.
    AINDA_ERRAM = [
        # "raspar" não vira "raspe", e "gilete" só aparece numa resposta.
        ("Precisa raspar/passar gilete antes da sessão?",
         {"Precisa de cuidados antes ou depois?", "A clínica pode auxiliar na raspagem pré-sessão?"}),
        # "antes" e "durante" casam o item de cuidados.
        ("Vocês abrem aos sábados ou apenas durante a semana?", None),
        # "completo" e "inclui" casam o item da virilha.
        ("Rosto completo inclui pescoço?", None),
    ]

    def test_o_primeiro_e_o_certo(self):
        for pergunta, esperado in self.CASOS:
            with self.subTest(pergunta=pergunta):
                r = titulos(busca(pergunta, FAQ_ESSENCIA))
                topo = r[0] if r else None
                if isinstance(esperado, set):
                    self.assertIn(topo, esperado)
                else:
                    self.assertEqual(topo, esperado)

    def test_os_que_ainda_erram_continuam_nomeados(self):
        """Quando um destes passar, ele sai daqui e entra em CASOS."""
        for pergunta, esperado in self.AINDA_ERRAM:
            with self.subTest(pergunta=pergunta):
                r = titulos(busca(pergunta, FAQ_ESSENCIA))
                topo = r[0] if r else None
                acertou = topo in esperado if isinstance(esperado, set) else topo == esperado
                self.assertFalse(acertou, "passou a acertar: mova para CASOS")

if __name__ == "__main__":
    unittest.main()
