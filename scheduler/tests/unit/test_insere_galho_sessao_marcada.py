# -*- coding: utf-8 -*-
"""O script que põe o galho 2b no prompt do banco é idempotente e não adivinha."""
import unittest

from src.scripts.insere_galho_sessao_marcada import (
    ANCORA_AUSENTE,
    APLICADO,
    JA_APLICADO,
    TITULO,
    aplica,
)

PROMPT = ("═══ COMO CONDUZIR A CONVERSA ═══\n\n1. PRIMEIRO CONTATO\n   ...\n\n"
          "2. DÚVIDA\n   ...\n\n3. ÁREAS\n   Chame list_areas.\n\n4. DATA E HORÁRIO\n")


class TestAplica(unittest.TestCase):
    def test_insere_antes_de_areas_e_nao_toca_no_resto(self):
        novo, status = aplica(PROMPT)
        self.assertEqual(status, APLICADO)
        self.assertLess(novo.index(TITULO), novo.index("3. ÁREAS"))
        self.assertGreater(novo.index(TITULO), novo.index("2. DÚVIDA"))
        self.assertIn("alterar_agendamento", novo)
        self.assertTrue(novo.endswith("4. DATA E HORÁRIO\n"))
        self.assertIn("1. PRIMEIRO CONTATO", novo)

    def test_segunda_rodada_nao_repete(self):
        novo, _ = aplica(PROMPT)
        de_novo, status = aplica(novo)
        self.assertEqual(status, JA_APLICADO)
        self.assertEqual(de_novo, novo)
        self.assertEqual(novo.count(TITULO), 1)

    def test_sem_ancora_recusa_em_vez_de_adivinhar(self):
        mesmo, status = aplica("Prompt editado à mão, sem a etapa de áreas.")
        self.assertEqual(status, ANCORA_AUSENTE)
        self.assertNotIn(TITULO, mesmo)


if __name__ == "__main__":
    unittest.main()
