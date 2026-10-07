# -*- coding: utf-8 -*-
"""A ambiguidade de área é barrada pela tool, não pedida no prompt.

Mesma lição de confirmacao_de_areas: com modelo, instrução é pedido. Aqui o
custo do erro é maior porque nada parece errado na conversa - a paciente pediu
"virilha completa", o bot marcou "Virilha Completa", e só na sala se descobre
que ela queria com ânus (outra duração, outro preço).
"""
import os
import unittest

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.ai_tools import ToolExecutor

AREAS = [
    {"id": "a-virilha", "name": "Virilha Completa"},
    {"id": "a-axilas", "name": "Axilas"},
]

FAQ = [
    {"question_label": "Como me preparar?", "answer": "Raspe com lâmina na véspera."},
]


class BancoFake:
    """Devolve áreas para a consulta de áreas, nada no resto."""

    def __init__(self):
        self.consultas = []

    def execute_query(self, sql, params=None):
        self.consultas.append(sql)
        if "FROM scheduler.areas" in sql:
            return AREAS
        if "faq_items" in sql:
            return FAQ
        return []


def ctx(*turnos):
    return {
        "clinic_id": "c1",
        "phone": "5511999999999",
        "turnos": [{"role": r, "content": c} for r, c in turnos],
    }


PARES = {"service_area_pairs": [{"service_id": "s1", "area_id": "a-virilha"}]}


class TestATravaSegura(unittest.TestCase):
    def setUp(self):
        self.executor = ToolExecutor(BancoFake(), availability_engine=None,
                                     appointment_service=None)

    def test_book_appointment_recusa_virilha_sem_a_pergunta(self):
        r = self.executor.execute("book_appointment", PARES, ctx(("user", "quero virilha completa")))
        self.assertEqual(r["error"], "areas_ambiguas")
        self.assertIn("ânus", r["o_que_fazer"].lower())

    def test_get_time_slots_tambem_recusa(self):
        r = self.executor.execute("get_time_slots", PARES, ctx(("user", "virilha completa")))
        self.assertEqual(r["error"], "areas_ambiguas")

    def test_calculate_discount_tambem_recusa(self):
        r = self.executor.execute("calculate_discount", PARES, ctx(("user", "virilha completa")))
        self.assertEqual(r["error"], "areas_ambiguas")

    def test_depois_da_pergunta_respondida_deixa_seguir(self):
        r = self.executor.execute("get_time_slots", PARES, ctx(
            ("user", "quero virilha completa"),
            ("assistant", "Quer incluir a região do ânus (perianal)?"),
            ("user", "não, só a virilha"),
        ))
        self.assertNotEqual(r.get("error"), "areas_ambiguas")

    def test_area_sem_ambiguidade_nao_e_afetada(self):
        r = self.executor.execute("get_time_slots", {
            "service_area_pairs": [{"service_id": "s1", "area_id": "a-axilas"}],
        }, ctx(("user", "quero axilas")))
        self.assertNotEqual(r.get("error"), "areas_ambiguas")


if __name__ == "__main__":
    unittest.main()
