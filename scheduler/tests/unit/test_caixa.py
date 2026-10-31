# -*- coding: utf-8 -*-
"""O caixa do painel (PRD 026, fase 2).

O que importa conferir: previsto pela data da sessão, recebido pela data em
que o dinheiro entrou (no fuso da clínica), pendência só até hoje, e quem
pode o quê - o resumo é do admin, a baixa em dinheiro é da recepção.
"""
import json
import os
import unittest
import uuid
from datetime import date, datetime, time, timezone
from unittest import mock

import pytz

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import caixa

CLINIC = "clinica-teste-0001"
SP = pytz.timezone("America/Sao_Paulo")
AGORA = SP.localize(datetime(2026, 10, 20, 15, 0))


class Db:
    def __init__(self):
        self.consultas = []

    def execute_query(self, sql, params=None):
        self.consultas.append((sql, params))
        if "SELECT timezone" in sql:
            return [{"timezone": "America/Sao_Paulo"}]
        if "GROUP BY appointment_date" in sql:
            return [
                {"dia": date(2026, 10, 19), "sessoes": 2, "previsto": 30000},
                {"dia": date(2026, 10, 20), "sessoes": 1, "previsto": 13500},
            ]
        if "GROUP BY 1, method" in sql:
            return [
                {"dia": date(2026, 10, 19), "method": "PIX", "quantidade": 1, "recebido": 13500},
                {"dia": date(2026, 10, 19), "method": "CASH", "quantidade": 1, "recebido": 16500},
                {"dia": date(2026, 10, 20), "method": "CREDIT_CARD", "quantidade": 1, "recebido": 9500},
            ]
        if "vivo.status IS NULL" in sql:
            return [{"id": uuid.UUID(int=1), "appointment_date": date(2026, 10, 20), "start_time": time(9, 0),
                     "final_price_cents": 13500, "checked_in_at": None, "nome": "Rodrigo",
                     "payment_id": uuid.UUID(int=2), "method": "CASH", "payment_status": "AWAITING_CASH"}]
        if "ORDER BY pay.paid_at" in sql:
            return [{"id": uuid.UUID(int=3), "method": "PIX", "amount_cents": 13500,
                     "paid_at": datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc), "provider": "simulado",
                     "appointment_date": date(2026, 10, 19), "start_time": time(10, 0), "nome": "Ana"}]
        raise AssertionError(sql)


class TestResumo(unittest.TestCase):
    def setUp(self):
        p = mock.patch("src.services.relogio.agora_na_clinica", return_value=AGORA)
        p.start()
        self.addCleanup(p.stop)

    def test_totais_por_dia_e_por_metodo(self):
        r = caixa.resumo(Db(), CLINIC, "2026-10-19", "2026-10-25")
        t = r["totals"]
        self.assertEqual((t["expectedCents"], t["receivedCents"]), (43500, 39500))
        self.assertEqual(t["byMethod"]["CASH"], {"count": 1, "cents": 16500})
        self.assertEqual((t["pendingCents"], t["pendingCount"]), (13500, 1))
        self.assertEqual([d["date"] for d in r["days"]], ["2026-10-19", "2026-10-20"])
        self.assertEqual(r["days"][0]["byMethod"]["PIX"], 13500)
        self.assertEqual(r["pending"][0]["paymentStatus"], "AWAITING_CASH")
        self.assertTrue(r["payments"][0]["simulated"])

    def test_recebido_e_pela_data_do_pagamento_no_fuso_da_clinica(self):
        db = Db()
        caixa.resumo(db, CLINIC, "2026-10-19", "2026-10-25")
        sql, params = next(c for c in db.consultas if "GROUP BY 1, method" in c[0])
        self.assertIn("paid_at AT TIME ZONE %s", sql)
        self.assertEqual(params[0], "America/Sao_Paulo")

    def test_pendencia_vai_so_ate_hoje(self):
        db = Db()
        caixa.resumo(db, CLINIC, "2026-10-19", "2026-10-25")
        _, params = next(c for c in db.consultas if "vivo.status IS NULL" in c[0])
        self.assertEqual(params[2], date(2026, 10, 20))

    def test_periodo_todo_no_futuro_nao_tem_pendencia(self):
        db = Db()
        r = caixa.resumo(db, CLINIC, "2026-10-21", "2026-10-25")
        self.assertEqual(r["pending"], [])
        self.assertFalse(any("vivo.status IS NULL" in c[0] for c in db.consultas))

    def test_periodo_invalido(self):
        for de, ate in (("2026-10-25", "2026-10-19"), ("19/10/2026", "2026-10-20"),
                        ("2026-01-01", "2026-12-31"), (None, "2026-10-20")):
            with self.subTest(de=de, ate=ate), self.assertRaises(caixa.PeriodoInvalido):
                caixa.resumo(Db(), CLINIC, de, ate)


class TestRotas(unittest.TestCase):
    modulo = "src.functions.caixa.router"

    def chama(self, metodo, proxy, query=None):
        from src.functions.caixa.router import handler
        r = handler({"httpMethod": metodo, "pathParameters": {"clinicId": CLINIC, "proxy": proxy},
                     "queryStringParameters": query, "headers": {}, "body": None}, None)
        return r["statusCode"], json.loads(r["body"])

    def test_resumo_so_admin(self):
        from src.utils.http import http_response
        with mock.patch(f"{self.modulo}.require_api_key", return_value=(None, http_response(403, {}))):
            self.assertEqual(self.chama("GET", "resumo", {"date_from": "2026-10-19", "date_to": "2026-10-19"})[0], 403)

    def test_resumo(self):
        with mock.patch(f"{self.modulo}.require_api_key", return_value=("k", None)), \
                mock.patch(f"{self.modulo}.PostgresService", return_value=Db()), \
                mock.patch("src.services.relogio.agora_na_clinica", return_value=AGORA):
            s, b = self.chama("GET", "resumo", {"date_from": "2026-10-19", "date_to": "2026-10-20"})
        self.assertEqual((s, b["totals"]["receivedCents"]), (200, 39500))

    def test_resumo_periodo_invalido(self):
        with mock.patch(f"{self.modulo}.require_api_key", return_value=("k", None)), \
                mock.patch(f"{self.modulo}.PostgresService", return_value=Db()):
            self.assertEqual(self.chama("GET", "resumo", {"date_from": "x", "date_to": "y"})[0], 400)

    def test_baixa_em_dinheiro_e_da_recepcao(self):
        pid = str(uuid.uuid4())
        recepcao = mock.Mock(mostra_valores=False)
        with mock.patch(f"{self.modulo}.require_acesso", return_value=(recepcao, None)) as acesso, \
                mock.patch(f"{self.modulo}.PostgresService"), \
                mock.patch(f"{self.modulo}.provedor_ativo"), \
                mock.patch("src.services.checkin.marca_recebido_em_dinheiro",
                           return_value={"id": pid, "status": "PAID", "amountCents": 15000}) as baixa:
            s, b = self.chama("POST", f"pagamentos/{pid}/dinheiro")
        self.assertEqual((s, b["payment"]["status"]), (200, "PAID"))
        self.assertNotIn("amountCents", b["payment"])
        self.assertEqual(acesso.call_args[0][1], "agenda.escrever")
        self.assertEqual(baixa.call_args[0][2:], (CLINIC, pid))

    def test_baixa_de_pagamento_que_nao_aguarda_dinheiro(self):
        from src.services.checkin import CheckinInvalido
        with mock.patch(f"{self.modulo}.require_acesso", return_value=(object(), None)), \
                mock.patch(f"{self.modulo}.PostgresService"), mock.patch(f"{self.modulo}.provedor_ativo"), \
                mock.patch("src.services.checkin.marca_recebido_em_dinheiro", side_effect=CheckinInvalido("x")):
            self.assertEqual(self.chama("POST", f"pagamentos/{uuid.uuid4()}/dinheiro")[0], 409)

    def test_rota_desconhecida(self):
        self.assertEqual(self.chama("DELETE", "resumo")[0], 404)
        self.assertEqual(self.chama("POST", "pagamentos/x/dinheiro")[0], 404)

    def test_interface(self):
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(raiz, "sls", "functions", "caixa", "interface.yml"), encoding="utf-8") as f:
            self.assertIn("path: clinics/{clinicId}/caixa/{proxy+}", f.read())
        with open(os.path.join(raiz, "serverless.yml"), encoding="utf-8") as f:
            self.assertIn("sls/functions/caixa/interface.yml", f.read())


if __name__ == "__main__":
    unittest.main()
