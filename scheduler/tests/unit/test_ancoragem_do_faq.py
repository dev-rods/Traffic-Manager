# -*- coding: utf-8 -*-
"""A fala do modelo só traz fatos que estão no item do FAQ (PRD 064)."""
import unittest

from src.services import ancoragem_do_faq as anc

INTERVALO = {"question_key": "SESSION_INTERVAL", "question_label": "Qual o intervalo entre as sessões?",
             "answer": "O intervalo entre as sessões é de aproximadamente 30 dias, podendo variar conforme as datas de cada mês."}
PREPARO = {"question_key": "PREPARATION", "question_label": "Precisa de cuidados antes ou depois?",
           "answer": "Raspe os pelos com lâmina no dia anterior. Evite sol por 5 dias antes e depois. Use protetor solar FPS 30 ou mais. Suspenda ácidos na semana anterior."}
VIRILHA = {"question_key": "BIKINI_TYPES", "question_label": "Qual a diferença entre virilha simples, cavada e completa?",
           "answer": "Simples: só os pelos para fora do biquíni. Cavada: quase toda a virilha, deixando uma faixa central. Completa: toda a região. O perianal é à parte."}


class TestFatos(unittest.TestCase):
    def test_numeros_com_unidade_e_termos(self):
        f = anc.fatos("Evite sol por 5 dias, use FPS 30 e suspenda o ácido retinoico. Roacutan precisa de 6 meses.")
        self.assertIn("5dias", f)
        self.assertIn("30", f)
        self.assertIn("roacutan", f)
        self.assertIn("6meses", f)
        self.assertIn("acido", f)

    def test_digito_solto_de_conversa_nao_e_fato(self):
        self.assertEqual(anc.fatos("Temos 3 opções de virilha, qual você prefere?"), set())


class TestConfere(unittest.TestCase):
    def test_resposta_com_as_palavras_do_item_esta_ancorada(self):
        self.assertEqual(anc.confere("O intervalo é de aproximadamente 30 dias 😊 Quer que eu veja as datas?", [INTERVALO]), [])

    def test_prazo_inventado_e_pego(self):
        faltam = anc.confere("O intervalo é de 45 dias e você precisa de 10 sessões.", [INTERVALO])
        self.assertIn("45dias", faltam)
        self.assertIn("10sessoes", faltam)

    def test_produto_fora_do_item_e_pego(self):
        self.assertEqual(anc.confere("Raspe no dia anterior e evite sol por 5 dias. Pode usar Roacutan normalmente.", [PREPARO]), ["roacutan"])

    def test_numero_do_item_com_outra_unidade_passa(self):
        """'30' está no item ('FPS 30'); 'por 30 dias' na fala não é invenção de número."""
        self.assertEqual(anc.confere("Use protetor FPS 30 por 30 dias.", [PREPARO]), [])

    def test_resumo_dos_tipos_de_virilha_passa(self):
        fala = ("O valor depende do tipo: simples (só o que fica para fora do biquíni), cavada (quase toda, "
                "deixando uma faixa central) ou completa (toda a região). Qual delas você quer?")
        self.assertEqual(anc.confere(fala, [VIRILHA]), [])

    def test_horario_e_data_sao_agenda_nao_fato_do_faq(self):
        self.assertEqual(anc.confere("O intervalo é de aproximadamente 30 dias. Para o dia 21 tenho 16:25.", [INTERVALO]), [])

    def test_numero_vindo_de_outra_tool_passa_pelo_respaldo(self):
        self.assertEqual(anc.confere("Dói pouco. A sessão dura 45 min e custa R$ 120.", [PREPARO],
                                     respaldo='{"total_minutes": 45, "price_display": "R$ 120,00"}'), [])
        self.assertEqual(anc.confere("A sessão dura 45 min.", [PREPARO], respaldo="{}"), ["45min"])

    def test_sem_fala_ou_sem_item_nada_a_conferir(self):
        self.assertEqual(anc.confere("", [INTERVALO]), [])
        self.assertEqual(anc.confere("qualquer coisa com 99 dias", []), [])
