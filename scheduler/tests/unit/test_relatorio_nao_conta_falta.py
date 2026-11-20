# -*- coding: utf-8 -*-
"""Falta e cancelamento ficam fora de dinheiro e de "agendamentos" (PRD 054).

Até 20/11/2026 relatório e dashboard somavam receita com `status != 'CANCELLED'`:
falta não é cancelado, então 48 faltas da Essência (R$ 9.809) entravam na
receita de outubro/novembro. Este guarda varre os dois handlers procurando o
padrão que deixou a falta entrar, e prova que acha.
"""
import os
import re
import unittest

SRC = os.path.join(os.path.dirname(__file__), "..", "..", "src")
RELATORIOS = [os.path.join("functions", "clinic", "reports.py"),
              os.path.join("functions", "clinic", "dashboard.py"),
              os.path.join("functions", "clinic", "agenda_summary.py")]

# Soma ou contagem na mesma linha de "diferente de cancelado": o filtro que
# deixa NO_SHOW passar.
SO_TIRA_CANCELADO = re.compile(r"(SUM\(|COUNT\(\*\) FILTER)[^\n]*!= 'CANCELLED'")


def _fonte(rel):
    with open(os.path.join(SRC, rel), encoding="utf-8") as f:
        return f.read()


class TestGuarda(unittest.TestCase):
    def test_nenhum_relatorio_soma_com_diferente_de_cancelado(self):
        culpados = {rel: SO_TIRA_CANCELADO.findall(_fonte(rel)) for rel in RELATORIOS}
        self.assertEqual({k: v for k, v in culpados.items() if v}, {})

    def test_a_guarda_enxerga_o_padrao_antigo(self):
        """Prova positiva: e o trecho que estava em reports.py ate 20/11/2026."""
        antigo = "COALESCE(SUM(final_price_cents) FILTER (WHERE status != 'CANCELLED'), 0) as net_revenue_cents"
        self.assertTrue(SO_TIRA_CANCELADO.search(antigo))
        self.assertTrue(SO_TIRA_CANCELADO.search("COUNT(*) FILTER (WHERE status != 'CANCELLED') as total"))

    def test_relatorio_e_dashboard_usam_a_regra_unica(self):
        from src.services.reagendamento import ativos
        for rel in RELATORIOS[:2]:
            with self.subTest(rel):
                self.assertIn("ativos(", _fonte(rel))
        self.assertEqual(ativos(), "status NOT IN ('CANCELLED', 'NO_SHOW')")


if __name__ == "__main__":
    unittest.main()
