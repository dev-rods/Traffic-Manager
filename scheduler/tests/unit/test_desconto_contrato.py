# -*- coding: utf-8 -*-
"""A MESMA tabela existe em frontend/src/lib/desconto.test.ts.

O preco com desconto e calculado nas duas linguagens: a tela precisa mostrar o
total antes de salvar. Divergindo, a atendente combina um valor com a paciente
e o sistema cobra outro - e quem descobre e a paciente, no caixa.

A regra e TRUNCAR, nao arredondar, porque era o que a divisao inteira ja fazia
com percentual inteiro. Trocar por arredondamento mudaria precos antigos.
"""
import unittest
from decimal import Decimal

from src.services.desconto_personalizado import aplica

CASOS = (
    (20000, "0", 20000),
    (20000, "10", 18000),
    (20000, "12.5", 17500),
    (20000, "33.33", 13334),
    (20000, "100", 0),
    (19999, "10", 17999),
    (9500, "7.77", 8761),
    (1, "50", 0),
    (0, "50", 0),
)


class TestContratoComOFrontend(unittest.TestCase):
    def test_tabela_de_referencia(self):
        for total, pct, esperado in CASOS:
            with self.subTest(total=total, pct=pct):
                self.assertEqual(aplica(total, Decimal(pct)), esperado)


class TestCompatibilidadeComOInteiro(unittest.TestCase):
    """O comportamento antigo nao pode mudar: eram 5 divisoes inteiras
    espalhadas pelo backend, e a conta nova substituiu todas."""

    def test_identico_a_divisao_inteira_em_todo_percentual_cheio(self):
        for total in (1, 9999, 12345, 19999, 20000, 100000):
            for pct in range(0, 101):
                with self.subTest(total=total, pct=pct):
                    self.assertEqual(aplica(total, pct), total * (100 - pct) // 100)


class TestBordas(unittest.TestCase):
    def test_sem_percentual_nao_desconta(self):
        self.assertEqual(aplica(20000, None), 20000)

    def test_percentual_ilegivel_nao_desconta(self):
        """Errar para o lado de cobrar o cheio: desconto fantasma sai do bolso
        da clinica e ninguem confere."""
        self.assertEqual(aplica(20000, "abc"), 20000)

    def test_total_zerado(self):
        self.assertEqual(aplica(0, 50), 0)


if __name__ == "__main__":
    unittest.main()
