# -*- coding: utf-8 -*-
"""O lembrete nao planta a ideia de cancelar. Teste literal, de proposito.

Citar "cancelar" ou "remarcar" no lembrete e gatilho: quem ia comparecer passa
a considerar a saida. O link so vai se a pessoa pedir, pelo bot (PRD 027).
"""
import unittest

from src.services.template_service import DEFAULT_TEMPLATES


class TestTemplateDoLembrete(unittest.TestCase):
    def test_existe_e_o_antigo_saiu(self):
        self.assertIn("LEMBRETE_SESSAO", DEFAULT_TEMPLATES)
        self.assertNotIn("REMINDER_24H", DEFAULT_TEMPLATES)

    def test_nao_cita_cancelar_remarcar_nem_link(self):
        t = DEFAULT_TEMPLATES["LEMBRETE_SESSAO"].lower()
        for proibido in ("cancel", "remarc", "http", "responda ok"):
            self.assertNotIn(proibido, t)

    def test_tem_as_variaveis(self):
        t = DEFAULT_TEMPLATES["LEMBRETE_SESSAO"]
        for v in ("{{nome}}", "{{areas}}", "{{clinic_name}}", "{{dia}}", "{{hora}}"):
            self.assertIn(v, t)


if __name__ == "__main__":
    unittest.main()
