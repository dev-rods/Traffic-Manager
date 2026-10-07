# -*- coding: utf-8 -*-
"""CPF e data de nascimento entram normalizados, venham de onde vierem.

Os dois chegam de três lugares - o bot pelo WhatsApp, o painel e a importação de
histórico - e cada um escreve de um jeito. Guardar como veio faria a busca por
CPF depender de a pessoa ter digitado com ponto ou sem.
"""
import unittest
from datetime import date, timedelta

from src.utils.cadastro import normaliza_cpf, normaliza_data_nascimento


class TestCpf(unittest.TestCase):
    def test_tira_pontuacao(self):
        for entrada in ("079.039.845-19", "07903984519", "079 039 845 19"):
            with self.subTest(entrada=entrada):
                self.assertEqual(normaliza_cpf(entrada), "07903984519")

    def test_vazio_vira_none_e_nao_string_vazia(self):
        """`''` passaria em checagem de preenchimento e esconderia o vazio."""
        for entrada in ("", "   ", None, "---"):
            with self.subTest(entrada=entrada):
                self.assertIsNone(normaliza_cpf(entrada))

    def test_tamanho_errado_e_recusado(self):
        """`False` e None significam coisas diferentes: um é erro, o outro é
        "não informado". O endpoint devolve 400 só para o primeiro."""
        for entrada in ("123", "0790398451", "079039845199"):
            with self.subTest(entrada=entrada):
                self.assertIs(normaliza_cpf(entrada), False)

    def test_digito_verificador_nao_e_validado(self):
        """Decisão consciente: recusar um CPF ditado errado no WhatsApp travaria
        o agendamento por um dado que a recepção corrige depois."""
        self.assertEqual(normaliza_cpf("11111111111"), "11111111111")


class TestDataDeNascimento(unittest.TestCase):
    def test_iso_do_painel(self):
        self.assertEqual(normaliza_data_nascimento("1999-12-29"), "1999-12-29")

    def test_formato_brasileiro_do_whatsapp(self):
        for entrada in ("29/12/1999", "29.12.1999"):
            with self.subTest(entrada=entrada):
                self.assertEqual(normaliza_data_nascimento(entrada), "1999-12-29")

    def test_vazio_vira_none(self):
        for entrada in ("", "  ", None):
            with self.subTest(entrada=entrada):
                self.assertIsNone(normaliza_data_nascimento(entrada))

    def test_texto_que_nao_e_data(self):
        for entrada in ("ontem", "12", "99/99/9999"):
            with self.subTest(entrada=entrada):
                self.assertIs(normaliza_data_nascimento(entrada), False)

    def test_data_futura_e_erro_de_digitacao(self):
        amanha = (date.today() + timedelta(days=1)).isoformat()

        self.assertIs(normaliza_data_nascimento(amanha), False)

    def test_mais_de_120_anos_e_erro_de_digitacao(self):
        """Deixar passar polui o cadastro em silêncio - ninguém revisa uma data
        que o sistema aceitou."""
        self.assertIs(normaliza_data_nascimento("1850-01-01"), False)

    def test_hoje_e_valido(self):
        """Recém-nascida não é caso desta clínica, mas a fronteira tem que ser
        clara: hoje passa, amanhã não."""
        self.assertEqual(normaliza_data_nascimento(date.today().isoformat()),
                         date.today().isoformat())


if __name__ == "__main__":
    unittest.main()
