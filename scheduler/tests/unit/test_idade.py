# -*- coding: utf-8 -*-
"""A idade é medida na data da SESSÃO, e a conta é uma só.

Quem faz 18 entre a conversa e a sessão chega maior de idade na cadeira; quem
completa 18 no dia seguinte ainda é menor quando o laser liga. Medir "hoje"
erraria os dois casos, e são justamente os casos em que a regra do responsável
legal decide alguma coisa.
"""
import unittest
from datetime import date, datetime

from src.services.idade import (
    dias_para_a_maioridade,
    e_menor_de_idade,
    em_anos,
    em_dias,
    para_data,
)


class TestParaData(unittest.TestCase):
    def test_iso(self):
        self.assertEqual(para_data("2008-11-05"), date(2008, 11, 5))

    def test_formato_brasileiro(self):
        self.assertEqual(para_data("05/11/2008"), date(2008, 11, 5))
        self.assertEqual(para_data("5-11-2008"), date(2008, 11, 5))

    def test_date_e_datetime_passam_direto(self):
        self.assertEqual(para_data(date(2008, 11, 5)), date(2008, 11, 5))
        self.assertEqual(para_data(datetime(2008, 11, 5, 14, 30)), date(2008, 11, 5))

    def test_o_que_nao_e_data(self):
        for valor in ("", None, "ontem", "11/2008", "2008", "30/02/2008", "abc"):
            with self.subTest(valor=valor):
                self.assertIsNone(para_data(valor))


class TestEmDias(unittest.TestCase):
    def test_conta_os_dias_ate_a_sessao(self):
        self.assertEqual(em_dias("2008-11-05", "2008-11-06"), 1)
        self.assertEqual(em_dias("2008-11-05", "2026-09-23"), 6531)

    def test_conta_o_bissexto(self):
        self.assertEqual(em_dias("2024-02-28", "2024-03-01"), 2)

    def test_nascimento_depois_da_sessao_da_negativo(self):
        """Não é erro da função: é data digitada trocada, e quem chama decide."""
        self.assertEqual(em_dias("2026-09-23", "2026-09-20"), -3)

    def test_sem_data_nao_inventa(self):
        self.assertIsNone(em_dias(None, "2026-09-23"))
        self.assertIsNone(em_dias("2008-11-05", None))


class TestEmAnos(unittest.TestCase):
    def test_aniversario_no_dia_ja_conta(self):
        """Fez 18 no dia da sessão: chega maior de idade."""
        self.assertEqual(em_anos("2008-09-23", "2026-09-23"), 18)

    def test_vespera_do_aniversario_ainda_nao(self):
        self.assertEqual(em_anos("2008-09-24", "2026-09-23"), 17)

    def test_nascido_em_29_de_fevereiro(self):
        self.assertEqual(em_anos("2008-02-29", "2026-02-28"), 17)
        self.assertEqual(em_anos("2008-02-29", "2026-03-01"), 18)


class TestMenorDeIdade(unittest.TestCase):
    def test_o_caso_que_a_regra_existe_para_pegar(self):
        """17 na conversa, 18 na sessão: não precisa de responsável."""
        self.assertTrue(e_menor_de_idade("2008-09-20", "2026-09-19"))
        self.assertFalse(e_menor_de_idade("2008-09-20", "2026-09-23"))

    def test_menor_continua_menor(self):
        self.assertTrue(e_menor_de_idade("2010-01-01", "2026-09-23"))

    def test_sem_data_devolve_none_e_nao_false(self):
        """None é 'não sei'. Quem trata como 'não' manda menor sem aviso."""
        self.assertIsNone(e_menor_de_idade(None, "2026-09-23"))
        self.assertIsNone(e_menor_de_idade("", "2026-09-23"))


class TestDiasParaAMaioridade(unittest.TestCase):
    def test_quantos_dias_faltam(self):
        self.assertEqual(dias_para_a_maioridade("2008-09-30", "2026-09-23"), 7)

    def test_ja_maior_da_zero_ou_negativo(self):
        self.assertEqual(dias_para_a_maioridade("2008-09-23", "2026-09-23"), 0)
        self.assertLess(dias_para_a_maioridade("1994-05-11", "2026-09-23"), 0)

    def test_nascido_em_29_de_fevereiro_faz_18_em_primeiro_de_marco(self):
        self.assertEqual(dias_para_a_maioridade("2008-02-29", "2026-02-28"), 1)


if __name__ == "__main__":
    unittest.main()
