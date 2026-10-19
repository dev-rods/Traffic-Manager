# -*- coding: utf-8 -*-
"""A politica de desconto que o agente aplica, fixada ANTES de sair do agente.

O calculo morava dentro do `ToolExecutor._calcula_desconto`, e o site publico
de agendamento nao o chamava: o mesmo carrinho custava menos pelo WhatsApp do
que pelo site. A conta foi extraida para `politica_de_desconto.decide`, que os
dois passam a chamar.

Extracao que muda preco e o pior tipo de regressao - ninguem percebe ate a
paciente reclamar no caixa. Por isso a tabela abaixo roda contra os DOIS
caminhos: o agente (como sempre rodou) e a funcao nova. Se um dia divergirem,
o teste diz qual caso.
"""
import os
import unittest
from decimal import Decimal
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor
from src.services import politica_de_desconto as politica

CLINIC = "clinica-teste-0001"
FONE = "5511999990000"
PRECO_POR_AREA = 20000

REGRAS_PADRAO = {
    "first_session_discount_pct": 50,
    "tier_2_min_areas": 2, "tier_2_max_areas": 3, "tier_2_discount_pct": 10,
    "tier_3_min_areas": 4, "tier_3_discount_pct": 20,
}
# Primeira sessao MENOR que a faixa 3: vence a faixa, porque a regra e "o
# maior desconto aplicavel", nao "primeira sessao primeiro".
REGRAS_FAIXA_VENCE = dict(REGRAS_PADRAO, first_session_discount_pct=10)


def pares(n):
    return [{"service_id": "s1", "area_id": f"a{i}"} for i in range(n)]


# (nome, regras, primeira_visita, personalizado, qtd_areas, pct, razao, is_first)
CASOS = (
    ("sem_regra", None, True, None, 2, 0, None, False),
    ("primeira_sessao", REGRAS_PADRAO, True, None, 1, 50, "first_session", True),
    ("faixa_2", REGRAS_PADRAO, False, None, 2, 10, "tier_2", False),
    ("faixa_3", REGRAS_PADRAO, False, None, 4, 20, "tier_3", False),
    ("primeira_vence_faixa", REGRAS_PADRAO, True, None, 4, 50, "first_session", True),
    ("faixa_vence_primeira", REGRAS_FAIXA_VENCE, True, None, 4, 20, "tier_3", True),
    ("nada_se_aplica", REGRAS_PADRAO, False, None, 1, 0, None, False),
    ("personalizado", REGRAS_PADRAO, True, Decimal("30"), 1, Decimal("30"), "personalizado", False),
    ("personalizado_zero", REGRAS_PADRAO, True, Decimal("0"), 4, Decimal("0"), "personalizado", False),
    ("personalizado_fracionado", REGRAS_PADRAO, False, Decimal("12.5"), 2, Decimal("12.5"), "personalizado", False),
    # 100% combinado e parceria: a mesma razao que o painel grava no
    # agendamento, para a agenda pintar igual.
    ("parceria", REGRAS_PADRAO, True, Decimal("100"), 1, Decimal("100"), "partnership", False),
)


def db_fake(regras, personalizado):
    db = mock.MagicMock()

    def consulta(sql, params=None):
        if "custom_discount_pct" in sql:
            return [{"custom_discount_pct": personalizado}]
        if "discount_rules" in sql:
            return [regras] if regras else []
        if "service_areas sa" in sql and "price_cents" in sql:
            return [{"price_cents": PRECO_POR_AREA}]
        return []

    db.execute_query.side_effect = consulta
    return db


def pelo_agente(regras, primeira, personalizado, qtd):
    ex = object.__new__(ToolExecutor)
    ex.db = db_fake(regras, personalizado)
    with mock.patch("src.services.ai_tools.e_primeira_visita", return_value=primeira):
        return ex._calcula_desconto({"service_area_pairs": pares(qtd)}, CLINIC, FONE, {})


class TestOAgenteContinuaCobrandoOMesmo(unittest.TestCase):
    def test_tabela(self):
        for nome, regras, primeira, pers, qtd, pct, razao, is_first in CASOS:
            with self.subTest(caso=nome):
                r = pelo_agente(regras, primeira, pers, qtd)
                total = PRECO_POR_AREA * qtd
                self.assertEqual(r["discount_pct"], pct)
                self.assertEqual(r["discount_reason"], razao)
                self.assertEqual(r["original_price_cents"], total)
                self.assertEqual(r["discounted_price_cents"], politica.aplica_desconto(total, pct))
                if regras is not None or pers is not None:
                    self.assertEqual(r["is_first_session"], is_first)

    def test_sem_preco_continua_a_consultar(self):
        ex = object.__new__(ToolExecutor)
        ex.db = mock.MagicMock()
        ex.db.execute_query.return_value = []
        r = ex._calcula_desconto({"service_area_pairs": pares(1)}, CLINIC, FONE, {})
        self.assertEqual(r["price_display"], "Valor a consultar")
        self.assertEqual(r["discount_pct"], 0)


class TestADecisaoExtraidaEAMesma(unittest.TestCase):
    def test_tabela(self):
        for nome, regras, primeira, pers, qtd, pct, razao, is_first in CASOS:
            with self.subTest(caso=nome):
                d = politica.decide(
                    db_fake(regras, pers), CLINIC, FONE, qtd,
                    e_primeira=lambda *a, **k: primeira,
                )
                self.assertEqual(d.pct, pct)
                self.assertEqual(d.razao, razao)
                if regras is not None or pers is not None:
                    self.assertEqual(d.is_first, is_first)

    def test_sem_telefone_so_vale_a_faixa(self):
        """Antes de digitar o celular o site so sabe quantas areas ha. Primeira
        sessao e personalizado dependem de QUEM e - sem telefone, nao entram."""
        consultado = mock.MagicMock(return_value=True)
        d = politica.decide(db_fake(REGRAS_PADRAO, Decimal("30")), CLINIC, None, 4,
                            e_primeira=consultado)
        self.assertEqual((d.pct, d.razao, d.is_first), (20, "tier_3", False))
        consultado.assert_not_called()

    def test_sem_telefone_e_uma_area_nao_ha_desconto(self):
        d = politica.decide(db_fake(REGRAS_PADRAO, None), CLINIC, None, 1)
        self.assertEqual((d.pct, d.razao), (0, None))


class TestTextoDoPreco(unittest.TestCase):
    """A linha de valor da confirmacao no WhatsApp. O formato e o que o bot ja
    mandava (`~de~ → por (x% off - motivo)`), para a clinica reconhecer."""

    def test_sem_preco(self):
        self.assertEqual(politica.texto_do_preco(None, None, 0, None, 0), "Consultar")

    def test_sem_desconto(self):
        self.assertEqual(politica.texto_do_preco(15000, 15000, 0, None, 1), "R$ 150,00")

    def test_milhar(self):
        self.assertEqual(politica.texto_do_preco(120000, 120000, 0, None, 1), "R$ 1.200,00")

    def test_primeira_sessao(self):
        self.assertEqual(
            politica.texto_do_preco(20000, 10000, 50, "first_session", 1),
            "~R$ 200,00~ → R$ 100,00 (50% off - primeira sessão)",
        )

    def test_faixa(self):
        self.assertEqual(
            politica.texto_do_preco(40000, 36000, 10, "tier_2", 2),
            "~R$ 400,00~ → R$ 360,00 (10% off - 2 áreas)",
        )

    def test_personalizado_fracionado(self):
        self.assertEqual(
            politica.texto_do_preco(20000, 17500, Decimal("12.50"), "personalizado", 1),
            "~R$ 200,00~ → R$ 175,00 (12,5% off - desconto especial)",
        )

    def test_parceria_e_dita_pelo_nome(self):
        self.assertEqual(
            politica.texto_do_preco(20000, 0, Decimal("100"), "partnership", 1),
            "~R$ 200,00~ → R$ 0,00 (100% off - parceria)",
        )

    def test_personalizado_zero_e_sem_desconto(self):
        self.assertEqual(politica.texto_do_preco(20000, 20000, Decimal("0"), "personalizado", 1),
                         "R$ 200,00")


if __name__ == "__main__":
    unittest.main()
