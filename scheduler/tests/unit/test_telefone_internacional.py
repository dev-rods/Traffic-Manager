# -*- coding: utf-8 -*-
"""Telefone de fora do Brasil não ganha `55` (PRD 033).

A Isadora fala pelo WhatsApp `31617223202` (Holanda). `normalize_phone` prefixava
55 em tudo que não começasse por 55, o cadastro virou `5531617223202`, e o site
recusava o número dela por não ser brasileiro. Ela agendou com o número da mãe e
nasceu um segundo cadastro (01/11/2026).
"""
import unittest

from src.utils.phone import (
    format_phone_display,
    formas_do_numero,
    is_valid_br_phone,
    is_valid_phone,
    normalize_phone,
    variantes_do_numero,
)


class TestNormalizeInternacional(unittest.TestCase):
    def test_holanda_como_o_zapi_entrega(self):
        self.assertEqual(normalize_phone("31617223202"), "31617223202")

    def test_holanda_como_a_pessoa_digita(self):
        self.assertEqual(normalize_phone("+31 6 1722 3202"), "31617223202")

    def test_alemanha(self):
        self.assertEqual(normalize_phone("491735425685"), "491735425685")
        self.assertEqual(normalize_phone("+49 173 5425685"), "491735425685")

    def test_brasil_nao_muda(self):
        for entrada in ("11999990000", "(11) 99999-0000", "+55 11 99999-0000",
                        "5511999990000", "011999990000"):
            with self.subTest(entrada=entrada):
                self.assertEqual(normalize_phone(entrada), "5511999990000")

    def test_fixo_brasileiro(self):
        self.assertEqual(normalize_phone("1133334444"), "551133334444")

    def test_sem_o_nono_digito_como_o_whatsapp_guarda(self):
        """`553591328559` (DDD 35, 8 dígitos) é a Paula: entra e sai igual."""
        self.assertEqual(normalize_phone("553591328559"), "553591328559")

    def test_ddd_valido_mas_nao_celular_nao_e_brasil(self):
        """31 é DDD de Minas, mas 617223202 não começa por 9: é a Holanda."""
        self.assertEqual(normalize_phone("31617223202"), "31617223202")

    def test_vazio(self):
        self.assertEqual(normalize_phone(""), "")
        self.assertEqual(normalize_phone(None), "")


class TestValidacao(unittest.TestCase):
    def test_internacional_precisa_do_mais(self):
        self.assertTrue(is_valid_phone("+31 617223202"))
        self.assertTrue(is_valid_phone("+49 173 5425685"))
        self.assertFalse(is_valid_br_phone("+31 617223202"))

    def test_brasileiro_continua_valendo(self):
        self.assertTrue(is_valid_phone("(11) 99999-0000"))
        self.assertTrue(is_valid_phone("+55 11 99999-0000"))
        self.assertTrue(is_valid_phone("1133334444"))

    def test_lixo(self):
        self.assertFalse(is_valid_phone("12345"))
        self.assertFalse(is_valid_phone("+1"))
        self.assertFalse(is_valid_phone(""))
        self.assertFalse(is_valid_phone("11899990000"))  # celular sem o 9


class TestVariantesInternacional(unittest.TestCase):
    def test_estrangeiro_tem_uma_forma_so(self):
        self.assertEqual(variantes_do_numero("491735425685"), {"491735425685"})
        self.assertEqual(formas_do_numero("+31 617223202"), ["31617223202"])

    def test_paula(self):
        """As duas grafias da Paula casam entre si."""
        self.assertEqual(formas_do_numero("553591328559"),
                         ["553591328559", "5535991328559"])
        self.assertEqual(formas_do_numero("5535991328559"),
                         ["553591328559", "5535991328559"])


class TestDisplay(unittest.TestCase):
    def test_brasil(self):
        self.assertEqual(format_phone_display("5511999990000"), "(11) 99999-0000")
        self.assertEqual(format_phone_display("553591328559"), "(35) 9132-8559")

    def test_fora(self):
        self.assertEqual(format_phone_display("31617223202"), "+31617223202")


if __name__ == "__main__":
    unittest.main()
