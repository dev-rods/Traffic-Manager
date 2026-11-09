# -*- coding: utf-8 -*-
"""A regra: a mensagem pede data sem oferecer nenhuma? (PRD 044)

Os casos marcados como reais saíram da varredura de todas as mensagens de saída
de produção em 09/11/2026 - os dois defeitos e, principalmente, os legítimos,
que são a maioria e não podem casar.
"""
import unittest

from src.services.pergunta_de_data import (
    oferece_nenhuma_data,
    oferece_ver_as_datas,
    pede_data_sem_consulta,
)


class TestPedeDataSemConsulta(unittest.TestCase):
    def test_o_caso_da_nobre_09_11(self):
        """Real: fechou o valor e perguntou a data sem ter chamado a tool."""
        self.assertTrue(pede_data_sem_consulta(
            "Fechado! Então ficaria: virilha completa, perianal e axilas.\n\n"
            "Total: De R$ 280,00 por R$ 238,00 (15% de desconto)\n\n"
            "Agora me diz: qual data fica melhor pra você?"))

    def test_o_caso_da_essencia_19_10(self):
        """Real: a resposta da pessoa foi "Já te respondi"."""
        self.assertTrue(pede_data_sem_consulta("Qual data fica melhor para você?"))

    def test_variacoes_da_mesma_pergunta(self):
        for texto in ("Que dia fica melhor para você?",
                      "Qual dia você prefere?",
                      "Quando você prefere?",
                      "Qual seria a melhor data para você?",
                      "Qual data você consegue vir?"):
            with self.subTest(texto):
                self.assertTrue(pede_data_sem_consulta(texto))


class TestNaoBarraPerguntaLegitima(unittest.TestCase):
    """O que salva estas é a ordem: elas OFERECEM datas antes de perguntar."""

    def test_lista_de_datas_e_depois_a_pergunta(self):
        self.assertFalse(pede_data_sem_consulta(
            "Temos estas datas disponíveis:\n1. Qui, 03/12\n2. Qui, 10/12\n\n"
            "Qual data fica melhor?"))

    def test_datas_em_texto_corrido(self):
        """Real, Essência 20/10 - correta e tem de passar intacta."""
        self.assertFalse(pede_data_sem_consulta(
            "Nossas próximas datas são 21, 22, 27 e 28 de outubro. Iniciamos às "
            "7h30, e o último horário é às 20h30. Qual dia fica melhor para você?"))

    def test_lista_de_horarios(self):
        self.assertFalse(pede_data_sem_consulta(
            "Horários disponíveis para quinta, 3 de dezembro:\n1. 16:00\n2. 16:20\n"
            "Qual prefere?"))

    def test_a_linha_do_prompt_para_o_primeiro_contato(self):
        """O prompt manda responder isto a quem pergunta data antes das áreas.
        Barrá-la seria brigar com uma regra que está certa."""
        self.assertFalse(pede_data_sem_consulta(
            "Consigo ver as datas pra você agora. Quais áreas você gostaria de tratar?"))

    def test_mensagem_sem_nada_de_data(self):
        self.assertFalse(pede_data_sem_consulta("Quais áreas você gostaria de tratar?"))
        self.assertFalse(pede_data_sem_consulta(""))
        self.assertFalse(pede_data_sem_consulta(None))


class TestOfereceNenhumaData(unittest.TestCase):
    def test_usa_o_extrator_da_proveniencia(self):
        self.assertTrue(oferece_nenhuma_data("qual data fica melhor?"))
        self.assertFalse(oferece_nenhuma_data("dia 03/12 às 16:40"))


class TestOfereceVerAsDatas(unittest.TestCase):
    """Decisão §7.3: isto é medido, não bloqueado - não inventa dia nenhum."""

    def test_reconhece_a_variante_branda(self):
        self.assertTrue(oferece_ver_as_datas("Quer ver as datas disponíveis?"))
        self.assertTrue(oferece_ver_as_datas("Posso consultar a agenda pra você?"))

    def test_nao_confunde_com_a_apresentacao_das_datas(self):
        self.assertFalse(oferece_ver_as_datas("Temos estas datas disponíveis:"))

    def test_nao_e_a_regra_de_bloqueio(self):
        """A variante branda NÃO pode disparar o guarda."""
        self.assertFalse(pede_data_sem_consulta("Quer ver as datas disponíveis?"))


if __name__ == "__main__":
    unittest.main()
