# -*- coding: utf-8 -*-
"""A MESMA tabela existe em frontend/src/lib/desconto.test.ts.

O preco com desconto e calculado nas duas linguagens: a tela precisa mostrar o
total antes de salvar. Divergindo, a atendente combina um valor com a paciente
e o sistema cobra outro - e quem descobre e a paciente, no caixa.

A regra e TRUNCAR, nao arredondar, porque era o que a divisao inteira ja fazia
com percentual inteiro. Trocar por arredondamento mudaria precos antigos.
"""
import io
import os
import re
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


CASOS_EM_CENTAVOS = (
    (19500, 2000, 17500),
    (1, 1, 0),
    (20000, 20000, 0),
    (0, 0, 0),
)


class TestContratoEmCentavos(unittest.TestCase):
    """PRD 050: desconto em reais e subtracao exata, nos dois lados."""

    def test_tabela_de_referencia(self):
        for total, cents, esperado in CASOS_EM_CENTAVOS:
            with self.subTest(total=total, cents=cents):
                self.assertEqual(aplica(total, None, cents=cents), esperado)


class TestBordas(unittest.TestCase):
    def test_sem_percentual_nao_desconta(self):
        self.assertEqual(aplica(20000, None), 20000)

    def test_percentual_ilegivel_nao_desconta(self):
        """Errar para o lado de cobrar o cheio: desconto fantasma sai do bolso
        da clinica e ninguem confere."""
        self.assertEqual(aplica(20000, "abc"), 20000)

    def test_total_zerado(self):
        self.assertEqual(aplica(0, 50), 0)


class TestRazoesConhecidasDoFrontend(unittest.TestCase):
    """PRD 053: toda razao que o backend grava em `discount_reason` tem rotulo
    em `rotuloDaRazao` (frontend/src/lib/desconto.ts). Sem isto, uma razao nova
    apareceria crua no popover e no Hoje ("tier_4"), e ninguem veria no teste."""

    FRONT = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                         "frontend", "src", "lib", "desconto.ts")

    def test_toda_razao_do_backend_tem_rotulo_no_painel(self):
        from src.services.desconto_personalizado import RAZAO, RAZAO_PARCERIA
        from src.services.politica_de_desconto import RAZAO_NENHUM, RAZOES_DA_POLITICA

        with io.open(self.FRONT, encoding="utf-8") as f:
            fonte = f.read()
        bloco = fonte.split("const ROTULOS", 1)[1].split("}", 1)[0]
        rotuladas = set(re.findall(r"^\s*(\w+):", bloco, re.M))

        esperadas = set(RAZOES_DA_POLITICA) | {RAZAO, RAZAO_PARCERIA, RAZAO_NENHUM, "custom"}
        self.assertTrue(esperadas <= rotuladas, esperadas - rotuladas)


if __name__ == "__main__":
    unittest.main()
