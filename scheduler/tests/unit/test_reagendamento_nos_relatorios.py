# -*- coding: utf-8 -*-
"""Reagendado sai de "cancelamentos" em todo relatório (PRD 035).

A regra mora em `reagendamento.py`. Estes testes conferem que cada relatório
a usa: o SQL que chega ao banco filtra cancelado por `rescheduled_to_id IS
NULL` e conta reagendado à parte; e a resposta carrega o campo novo.
"""
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("SCHEDULER_API_KEY", "chave-de-teste")

from src.functions.clinic import agenda_summary, dashboard, reports
from src.services.reagendamento import E_CANCELADO_DE_VERDADE, E_REAGENDADO

EVENTO = {
    "headers": {"x-api-key": "chave-de-teste"},
    "pathParameters": {"clinicId": "clinica-1"},
    "queryStringParameters": None,
}


def _db(resposta_por_sql):
    """Roteia `execute_query` pelo conteúdo do SQL; o resto responde vazio."""
    db = mock.MagicMock()

    def execute_query(sql, params=None):
        for trecho, linhas in resposta_por_sql.items():
            if trecho in sql:
                return linhas
        return []

    db.execute_query.side_effect = execute_query
    return db


def _sqls(db):
    return [c[0][0] for c in db.execute_query.call_args_list]


def _corpo(resposta):
    return json.loads(resposta["body"])


class TestDashboard(unittest.TestCase):

    def chama(self):
        db = _db({
            "total_appointments": [{
                "total_appointments": 10, "confirmed_appointments": 7,
                "cancelled_appointments": 1, "rescheduled_appointments": 2,
                "net_revenue_cents": 0, "gross_revenue_cents": 0,
                "total_discount_cents": 0, "pending_appointments": 0}],
        })
        with mock.patch.object(dashboard, "PostgresService", return_value=db), \
             mock.patch.object(dashboard, "require_api_key", return_value=("k", None)):
            resposta = dashboard.handler(EVENTO, None)
        return db, _corpo(resposta)

    def test_resumo_separa_cancelado_de_reagendado(self):
        db, corpo = self.chama()
        resumo = corpo["summary"]
        self.assertEqual(resumo["cancelled_appointments"], 1)
        self.assertEqual(resumo["rescheduled_appointments"], 2)
        # Taxa sobre cancelados de verdade: 1/10, nao 3/10.
        self.assertEqual(resumo["cancellation_rate"], 10)

    def test_o_sql_usa_a_regra_unica(self):
        db, _ = self.chama()
        sql = next(s for s in _sqls(db) if "total_appointments" in s)
        self.assertIn(E_CANCELADO_DE_VERDADE.format(a="appointments"), sql)
        self.assertIn(E_REAGENDADO.format(a="appointments"), sql)
        self.assertNotIn("FILTER (WHERE status = 'CANCELLED')", sql)

    def test_lista_do_dia_traz_o_destino(self):
        db, _ = self.chama()
        sql = next(s for s in _sqls(db) if "patient_db_name" in s)
        self.assertIn("rt.appointment_date as rescheduled_to_date", sql)
        self.assertIn("LEFT JOIN scheduler.appointments rt ON rt.id = a.rescheduled_to_id", sql)


class TestReports(unittest.TestCase):

    def test_resumo_separa_cancelado_de_reagendado(self):
        db = _db({
            "cancelled_appointments": [{
                "total_appointments": 20, "confirmed_appointments": 18,
                "cancelled_appointments": 2, "rescheduled_appointments": 5,
                "gross_revenue_cents": 0, "net_revenue_cents": 0, "total_discount_cents": 0}],
            "FROM scheduler.patients": [{"count": 0}],
        })
        with mock.patch.object(reports, "PostgresService", return_value=db), \
             mock.patch.object(reports, "require_api_key", return_value=("k", None)):
            corpo = _corpo(reports.handler(EVENTO, None))

        self.assertEqual(corpo["summary"]["cancelled_appointments"], 2)
        self.assertEqual(corpo["summary"]["rescheduled_appointments"], 5)
        self.assertEqual(corpo["summary"]["cancellation_rate"], 10)
        sql = next(s for s in _sqls(db) if "cancelled_appointments" in s)
        self.assertIn(E_CANCELADO_DE_VERDADE.format(a="appointments"), sql)
        self.assertIn(E_REAGENDADO.format(a="appointments"), sql)


class TestAgendaSummary(unittest.TestCase):

    def chama(self, linhas):
        db = _db({"perdido_cents": linhas})
        with mock.patch.object(agenda_summary, "PostgresService", return_value=db), \
             mock.patch.object(agenda_summary, "require_api_key", return_value=("k", None)):
            corpo = _corpo(agenda_summary.handler(EVENTO, None))
        return db, corpo

    def test_reagendado_conta_a_parte_e_nao_e_perda(self):
        from datetime import date
        db, corpo = self.chama([{
            "dia": date(2026, 10, 21), "confirmados": 3, "cancelados": 1, "reagendados": 2,
            "pacientes": 3, "bruto_cents": 30000, "liquido_cents": 27000,
            "minutos": 90, "perdido_cents": 9000}])

        dia = corpo["days"][0]
        self.assertEqual(dia["cancelled"], 1)
        self.assertEqual(dia["rescheduled"], 2)
        self.assertEqual(dia["lost_cents"], 9000)
        self.assertEqual(corpo["total"]["rescheduled"], 2)

        sql = _sqls(db)[0]
        self.assertIn(f"FILTER (WHERE {E_CANCELADO_DE_VERDADE.format(a='ap')})", sql)
        self.assertIn(f"FILTER (WHERE {E_REAGENDADO.format(a='ap')})", sql)
        # A perda em reais so conta cancelamento de verdade.
        self.assertIn(
            f"SUM(ap.final_price_cents) FILTER (WHERE {E_CANCELADO_DE_VERDADE.format(a='ap')})", sql)
        self.assertNotIn("WHERE ap.status = 'CANCELLED')", sql)

    def test_cadeia_de_tres_conta_dois_reagendados_e_um_desfecho(self):
        """Cada elo intermediário é CANCELLED com vínculo; o último é o
        desfecho. O banco agrupa por registro, então a contagem é direta."""
        from datetime import date
        _, corpo = self.chama([
            {"dia": date(2026, 10, 21), "confirmados": 0, "cancelados": 0, "reagendados": 1,
             "pacientes": 0, "bruto_cents": 0, "liquido_cents": 0, "minutos": 0, "perdido_cents": 0},
            {"dia": date(2026, 10, 22), "confirmados": 0, "cancelados": 0, "reagendados": 1,
             "pacientes": 0, "bruto_cents": 0, "liquido_cents": 0, "minutos": 0, "perdido_cents": 0},
            {"dia": date(2026, 10, 27), "confirmados": 1, "cancelados": 0, "reagendados": 0,
             "pacientes": 1, "bruto_cents": 10000, "liquido_cents": 10000, "minutos": 30, "perdido_cents": 0},
        ])
        self.assertEqual(corpo["total"]["rescheduled"], 2)
        self.assertEqual(corpo["total"]["cancelled"], 0)
        self.assertEqual(corpo["total"]["confirmed"], 1)
        self.assertEqual(corpo["total"]["lost_cents"], 0)


if __name__ == "__main__":
    unittest.main()
