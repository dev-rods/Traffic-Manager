# -*- coding: utf-8 -*-
"""O link de "Meus agendamentos": so existe com dominio proprio da clinica."""
import unittest

from src.services.autoatendimento import link_citado, link_de_autoatendimento, link_de_meus_agendamentos


class TestLinkDeMeusAgendamentos(unittest.TestCase):
    """PRD 060: o link que abre "Meus agendamentos" direto, para remarcar e cancelar."""

    def test_com_dominio_leva_o_parametro(self):
        self.assertEqual(link_de_meus_agendamentos({"custom_domain": "agendar.nobrelaser.com.br"}),
                         "https://agendar.nobrelaser.com.br/?meus=1")

    def test_sem_dominio_e_none(self):
        self.assertIsNone(link_de_meus_agendamentos({"custom_domain": None}))
        self.assertIsNone(link_de_meus_agendamentos({}))
        self.assertIsNone(link_de_meus_agendamentos(None))

    def test_o_texto_com_o_link_de_meus_continua_contando_como_link_enviado(self):
        clinic = {"custom_domain": "agendar.x.com.br"}
        self.assertTrue(link_citado(f"remarque por aqui: {link_de_meus_agendamentos(clinic)}",
                                    link_de_autoatendimento(clinic)))


class TestLink(unittest.TestCase):
    def test_com_dominio(self):
        self.assertEqual(link_de_autoatendimento({"custom_domain": "agendar.nobrelaser.com.br"}),
                         "https://agendar.nobrelaser.com.br/")

    def test_sem_dominio_e_none(self):
        self.assertIsNone(link_de_autoatendimento({"custom_domain": None}))
        self.assertIsNone(link_de_autoatendimento({"custom_domain": "  "}))
        self.assertIsNone(link_de_autoatendimento({}))
        self.assertIsNone(link_de_autoatendimento(None))

    def test_nao_duplica_esquema(self):
        self.assertEqual(link_de_autoatendimento({"custom_domain": "https://x.com"}), "https://x.com/")
        self.assertEqual(link_de_autoatendimento({"custom_domain": "x.com/"}), "https://x.com/")


if __name__ == "__main__":
    unittest.main()
