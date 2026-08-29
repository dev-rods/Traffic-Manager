"""Pré-filtro de datas candidatas do AvailabilityEngine.

Cada verificação de dia custa 5 queries ao banco. Varrer os 90 dias do horizonte
custava ~450 idas ao banco e levava mais de 80 segundos numa clínica que atende
em poucas datas fixas por mês — acima do que uma conversa de WhatsApp tolera.
O pré-filtro resolve numa query só quais dias sequer podem ter horário.

Os testes usam um banco falso que registra as queries, para verificar tanto o
resultado quanto a promessa de custo (uma query, não noventa).
"""
import os
import unittest
from datetime import date

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.availability_engine import AvailabilityEngine


class FakeDb:
    def __init__(self, rows):
        self.rows = rows
        self.queries = []

    def execute_query(self, query, params=None):
        self.queries.append((query, params))
        return self.rows


def _engine(rows):
    db = FakeDb(rows)
    return AvailabilityEngine(db), db


class TestDatasFixas(unittest.TestCase):
    def test_devolve_apenas_as_datas_com_regra(self):
        engine, _ = _engine([
            {"day_of_week": None, "rule_date": date(2026, 9, 23)},
            {"day_of_week": None, "rule_date": date(2026, 9, 24)},
            {"day_of_week": None, "rule_date": date(2026, 10, 21)},
        ])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 90)

        self.assertEqual(datas, ["2026-09-23", "2026-09-24", "2026-10-21"])

    def test_uma_unica_query_independente_do_horizonte(self):
        engine, db = _engine([{"day_of_week": None, "rule_date": date(2026, 9, 23)}])

        engine._candidate_dates("clinica-x", date(2026, 9, 1), 90)

        self.assertEqual(len(db.queries), 1)

    def test_ignora_data_fora_do_horizonte(self):
        # o horizonte de 10 dias termina em 11/09; a regra de 23/09 fica de fora
        engine, _ = _engine([{"day_of_week": None, "rule_date": date(2026, 9, 23)}])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 10)

        self.assertEqual(datas, [])

    def test_nao_inclui_o_proprio_dia_de_hoje(self):
        # a busca começa em start+1: agendamento é sempre para frente
        engine, _ = _engine([{"day_of_week": None, "rule_date": date(2026, 9, 1)}])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 30)

        self.assertEqual(datas, [])


class TestRegrasRecorrentes(unittest.TestCase):
    def test_expande_dia_da_semana_no_horizonte(self):
        # day_of_week=3 é quarta-feira (0=domingo no banco)
        engine, _ = _engine([{"day_of_week": 3, "rule_date": None}])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 21)

        self.assertEqual(datas, ["2026-09-02", "2026-09-09", "2026-09-16"])

    def test_combina_recorrente_com_data_fixa(self):
        engine, _ = _engine([
            {"day_of_week": 3, "rule_date": None},
            {"day_of_week": None, "rule_date": date(2026, 9, 5)},
        ])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 10)

        self.assertEqual(datas, ["2026-09-02", "2026-09-05", "2026-09-09"])

    def test_data_fixa_que_cai_em_dia_recorrente_nao_duplica(self):
        engine, _ = _engine([
            {"day_of_week": 3, "rule_date": None},
            {"day_of_week": None, "rule_date": date(2026, 9, 2)},  # também é quarta
        ])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 7)

        self.assertEqual(datas, ["2026-09-02"])


class TestSemRegras(unittest.TestCase):
    def test_clinica_sem_regra_devolve_vazio(self):
        engine, db = _engine([])

        datas = engine._candidate_dates("clinica-x", date(2026, 9, 1), 90)

        self.assertEqual(datas, [])
        self.assertEqual(len(db.queries), 1)


if __name__ == "__main__":
    unittest.main()
