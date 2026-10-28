# -*- coding: utf-8 -*-
"""O link de "Meus agendamentos": so existe com dominio proprio da clinica."""
import unittest

from src.services.autoatendimento import link_de_autoatendimento


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
