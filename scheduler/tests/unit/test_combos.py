# -*- coding: utf-8 -*-
"""Duas áreas que o cadastro vende juntas viram o combo, e o combo é mais barato.

06/10/2026, Aline: "virilha completa" e "perianal" em linhas separadas. O bot
somou R$ 175 + R$ 95; o cadastro tem "Virilha Completa + ânus" por R$ 195. A
clínica corrigiu à mão duas horas depois.
"""
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.combos import aplica, combos_do_catalogo
from tests.unit.catalogo_real import AREAS

S = "svc-laser"
# Preços reais da Essência (centavos), 06/10/2026.
PRECOS = {
    "Virilha Completa": 17500, "Perianal/ânus": 9500, "Virilha Completa + ânus": 19500,
    "Peitoral": 15500, "Abdômen": 15500, "Peitoral + abdômen": 23500,
    "Axilas": 9500, "Mão ou Pé + Dedos": 7000, "Perna Completa": 24500,
    "Ombros": 11500, "Costas total + ombros": 23500,
}


def preco_de(service_id, area_id):
    return PRECOS.get(area_id)


def par(nome):
    return {"service_id": S, "area_id": nome}


class TestOQueECombo(unittest.TestCase):
    def test_os_dois_combos_reais(self):
        combos = combos_do_catalogo(AREAS)
        self.assertEqual(combos, {
            "Virilha Completa + ânus": ["Virilha Completa", "Perianal/ânus"],
            "Peitoral + abdômen": ["Peitoral", "Abdômen"],
        })

    def test_mais_nao_e_combo_quando_um_lado_nao_existe(self):
        """'Costas total' e 'Barba Comp.' não são vendidas sozinhas."""
        combos = combos_do_catalogo(AREAS)
        self.assertNotIn("Costas total + ombros", combos)
        self.assertNotIn("Barba Comp. + Pescoço", combos)
        self.assertNotIn("Mão ou Pé + Dedos", combos)


class TestOCasoDaAline(unittest.TestCase):
    PARES = [par("Axilas"), par("Virilha Completa"), par("Perianal/ânus"),
             par("Mão ou Pé + Dedos"), par("Perna Completa")]

    def test_vira_o_combo_e_diz_quanto_economizou(self):
        novos, trocas = aplica(self.PARES, AREAS, preco_de)
        self.assertEqual([p["area_id"] for p in novos],
                         ["Axilas", "Virilha Completa + ânus", "Mão ou Pé + Dedos", "Perna Completa"])
        self.assertEqual(trocas, [{
            "de": ["Virilha Completa", "Perianal/ânus"],
            "para": "Virilha Completa + ânus",
            "economia_cents": 7500,
        }])

    def test_nao_muda_os_pares_originais(self):
        antes = [dict(p) for p in self.PARES]
        aplica(self.PARES, AREAS, preco_de)
        self.assertEqual(self.PARES, antes)


class TestQuandoNaoTroca(unittest.TestCase):
    def test_so_uma_das_partes(self):
        novos, trocas = aplica([par("Axilas"), par("Virilha Completa")], AREAS, preco_de)
        self.assertEqual(trocas, [])
        self.assertEqual(len(novos), 2)

    def test_combo_mais_caro_que_a_soma_nao_e_aplicado(self):
        """Combo mais caro seria a clínica cobrando a mais - não é decisão do bot."""
        caro = dict(PRECOS, **{"Virilha Completa + ânus": 30000})
        novos, trocas = aplica([par("Virilha Completa"), par("Perianal/ânus")], AREAS, lambda s, a: caro.get(a))
        self.assertEqual(trocas, [])

    def test_combo_com_preco_igual_a_soma_e_aplicado(self):
        igual = dict(PRECOS, **{"Virilha Completa + ânus": 27000})
        _, trocas = aplica([par("Virilha Completa"), par("Perianal/ânus")], AREAS, lambda s, a: igual.get(a))
        self.assertEqual(len(trocas), 1)

    def test_sem_preco_nao_troca(self):
        _, trocas = aplica([par("Virilha Completa"), par("Perianal/ânus")], AREAS, lambda s, a: None)
        self.assertEqual(trocas, [])

    def test_servicos_diferentes_nao_se_combinam(self):
        pares = [{"service_id": "a", "area_id": "Virilha Completa"},
                 {"service_id": "b", "area_id": "Perianal/ânus"}]
        _, trocas = aplica(pares, AREAS, preco_de)
        self.assertEqual(trocas, [])

    def test_dois_combos_na_mesma_chamada(self):
        pares = [par("Peitoral"), par("Virilha Completa"), par("Abdômen"), par("Perianal/ânus")]
        novos, trocas = aplica(pares, AREAS, preco_de)
        self.assertEqual(sorted(p["area_id"] for p in novos),
                         ["Peitoral + abdômen", "Virilha Completa + ânus"])
        self.assertEqual(len(trocas), 2)


class TestNasTools(unittest.TestCase):
    """A troca acontece na tool, depois da trava de áreas, e o modelo fica sabendo."""

    def _executor(self):
        from src.services.ai_tools import ToolExecutor

        ex = object.__new__(ToolExecutor)
        db = mock.MagicMock()

        def query(sql, params=None):
            if "FROM scheduler.areas" in sql:
                return AREAS
            if "FROM scheduler.service_areas sa" in sql and "price_cents" in sql:
                return [{"price_cents": PRECOS.get(params[1])}]
            if "discount_rules" in sql:
                return [{"first_session_discount_pct": 0, "tier_2_min_areas": 2, "tier_2_max_areas": 4,
                         "tier_2_discount_pct": 10, "tier_3_min_areas": 5, "tier_3_discount_pct": 15}]
            return []

        db.execute_query.side_effect = query
        ex.db = db
        ex.availability_engine = mock.MagicMock()
        ex.appointment_service = mock.MagicMock()
        return ex

    CTX = {"turnos": [{"role": "user", "content": "axila, virilha completa, perianal, pés e pernas completas"},
                      {"role": "assistant", "content": "a de pés é Mão ou Pé + Dedos e pernas completas é Perna Completa, certo?"},
                      {"role": "user", "content": "Sim"}]}

    def test_calculate_discount_usa_o_combo_e_avisa(self):
        ex = self._executor()
        with mock.patch("src.services.ai_tools.desconto_do_paciente", return_value=None), \
             mock.patch("src.services.ai_tools.e_primeira_visita", return_value=False):
            r = ex._tool_calculate_discount(
                {"service_area_pairs": TestOCasoDaAline.PARES}, "c1", "5519991058272", dict(self.CTX))

        # 95 + 195 + 70 + 245 = 605, quatro areas -> 10%
        self.assertEqual(r["original_price_cents"], 60500)
        self.assertEqual(r["discount_pct"], 10)
        self.assertEqual(r["combos_aplicados"][0]["para"], "Virilha Completa + ânus")
        self.assertIn("Virilha Completa + ânus", r["o_que_dizer"])

    def test_book_appointment_grava_o_combo(self):
        ex = self._executor()
        ex.appointment_service.create_appointment.return_value = {"id": "ap1", "status": "CONFIRMED"}
        with mock.patch("src.services.ai_tools.calcula_duracao", return_value=40), \
             mock.patch("src.services.ai_tools.identificar_paciente", return_value={"encontrado": True, "nome": "Aline"}):
            r = ex._tool_book_appointment(
                {"service_area_pairs": TestOCasoDaAline.PARES, "date": "2026-10-28", "time": "07:30"},
                "c1", "5519991058272", dict(self.CTX))

        self.assertTrue(r.get("success"), r)
        kw = ex.appointment_service.create_appointment.call_args[1]
        self.assertEqual([p["area_id"] for p in kw["service_area_pairs"]],
                         ["Axilas", "Virilha Completa + ânus", "Mão ou Pé + Dedos", "Perna Completa"])
        self.assertEqual(r["combos_aplicados"][0]["economia_cents"], 7500)

    def test_sem_combo_nada_muda_no_resultado(self):
        ex = self._executor()
        with mock.patch("src.services.ai_tools.desconto_do_paciente", return_value=None), \
             mock.patch("src.services.ai_tools.e_primeira_visita", return_value=False):
            r = ex._tool_calculate_discount(
                {"service_area_pairs": [par("Axilas"), par("Perna Completa")]}, "c1", "x",
                {"turnos": [{"role": "user", "content": "axilas e perna completa"}]})
        self.assertNotIn("combos_aplicados", r)


if __name__ == "__main__":
    unittest.main()
