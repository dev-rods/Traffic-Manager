# -*- coding: utf-8 -*-
"""Estorno de pagamento de sessão cancelada (PRD 028, M7).

No primeiro teste gravado, o caixa contava como "Recebido" o dinheiro de
sessões que depois foram canceladas, sem aviso. O estorno é decisão humana
(pode virar crédito para outra sessão), mas só vale para sessão cancelada, e
dinheiro em espécie não passa pelo Asaas.
"""
import json
import os
import unittest
import uuid
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import checkin

CLINIC = "clinica-teste-0001"
PAG = "bbbbbbbb-0000-0000-0000-000000000001"


class Db:
    def __init__(self, status="PAID", metodo="PIX", sessao="CANCELLED", provider="asaas"):
        self.row = {"id": PAG, "clinic_id": CLINIC, "appointment_id": "a1", "method": metodo,
                    "amount_cents": 13500, "status": status, "provider": provider,
                    "provider_payment_id": "pay_1", "appointment_status": sessao, "paid_at": None}
        self.marcado = None

    def execute_query(self, sql, params=None):
        assert "appointment_status" in sql
        return [dict(self.row)] if params[0] == PAG and params[1] == CLINIC else []

    def execute_write(self, sql, params=None):
        assert "UPDATE scheduler.appointment_payments SET status" in sql
        self.marcado = params[0]
        return 1


class Provedor:
    nome = "asaas"

    def __init__(self, aguarda=False):
        self.estornados = []
        self.aguarda = aguarda

    def estorna(self, cobranca_id):
        self.estornados.append(cobranca_id)
        return self.aguarda


class TestEstorno(unittest.TestCase):
    def test_pix_de_sessao_cancelada_estorna_no_asaas(self):
        db, prov = Db(), Provedor()
        r = checkin.estorna(db, prov, CLINIC, PAG)
        self.assertEqual((r["status"], db.marcado, prov.estornados), ("REFUNDED", "REFUNDED", ["pay_1"]))

    def test_dinheiro_nao_passa_pelo_asaas(self):
        db, prov = Db(metodo="CASH"), Provedor()
        self.assertEqual(checkin.estorna(db, prov, CLINIC, PAG)["status"], "REFUNDED")
        self.assertEqual(prov.estornados, [])

    def test_sessao_que_ainda_vai_acontecer_nao_estorna(self):
        db, prov = Db(sessao="CONFIRMED"), Provedor()
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.estorna(db, prov, CLINIC, PAG)
        self.assertEqual((prov.estornados, db.marcado), ([], None))

    def test_so_pagamento_confirmado(self):
        with self.assertRaises(checkin.CheckinInvalido):
            checkin.estorna(Db(status="PENDING"), Provedor(), CLINIC, PAG)

    def test_estornado_de_novo_nao_chama_o_asaas(self):
        db, prov = Db(status="REFUNDED"), Provedor()
        self.assertEqual(checkin.estorna(db, prov, CLINIC, PAG)["status"], "REFUNDED")
        self.assertEqual(prov.estornados, [])

    def test_de_outra_clinica_ou_id_invalido(self):
        for cid, pid in (("outra", PAG), (CLINIC, "x")):
            with self.subTest(cid=cid, pid=pid), self.assertRaises(checkin.NaoEncontrado):
                checkin.estorna(Db(), Provedor(), cid, pid)


class TestRotaDeEstorno(unittest.TestCase):
    modulo = "src.functions.caixa.router"

    def chama(self):
        from src.functions.caixa.router import handler
        r = handler({"httpMethod": "POST", "pathParameters": {"clinicId": CLINIC, "proxy": f"pagamentos/{PAG}/estorno"},
                     "headers": {}, "body": None}, None)
        return r["statusCode"], json.loads(r["body"])

    def test_so_admin(self):
        from src.utils.http import http_response
        with mock.patch(f"{self.modulo}.require_api_key", return_value=(None, http_response(403, {}))):
            self.assertEqual(self.chama()[0], 403)

    def test_estorna(self):
        with mock.patch(f"{self.modulo}.require_api_key", return_value=("k", None)), \
                mock.patch(f"{self.modulo}.PostgresService"), mock.patch(f"{self.modulo}.provedor_ativo"), \
                mock.patch("src.services.checkin.estorna", return_value={"id": PAG, "status": "REFUNDED"}) as e:
            s, b = self.chama()
        self.assertEqual((s, b["payment"]["status"]), (200, "REFUNDED"))
        self.assertEqual(e.call_args[0][2:], (CLINIC, PAG))

    def test_sessao_nao_cancelada_vira_409(self):
        with mock.patch(f"{self.modulo}.require_api_key", return_value=("k", None)), \
                mock.patch(f"{self.modulo}.PostgresService"), mock.patch(f"{self.modulo}.provedor_ativo"), \
                mock.patch("src.services.checkin.estorna", side_effect=checkin.CheckinInvalido("x")):
            self.assertEqual(self.chama()[0], 409)


class TestAutorizacao(unittest.TestCase):
    def test_asaas_pedindo_autorizacao_o_painel_fica_sabendo(self):
        r = checkin.estorna(Db(), Provedor(aguarda=True), CLINIC, PAG)
        self.assertEqual((r["status"], r["refundNeedsAuthorization"]), ("REFUNDED", True))

    def test_dinheiro_nunca_pede_autorizacao(self):
        r = checkin.estorna(Db(metodo="CASH"), Provedor(aguarda=True), CLINIC, PAG)
        self.assertFalse(r["refundNeedsAuthorization"])


class TestAsaasEstorna(unittest.TestCase):
    def test_chama_refund(self):
        from src.providers.asaas_provider import AsaasProvider
        chamadas = []
        resp = mock.MagicMock(status_code=200, content=b"{}")
        resp.json.return_value = {}
        with mock.patch("src.providers.asaas_provider.requests.request",
                        side_effect=lambda m, u, **k: chamadas.append((m, u)) or resp):
            self.assertFalse(AsaasProvider("k", "https://api-sandbox.asaas.com").estorna("pay_1"))
        self.assertEqual(chamadas, [("POST", "https://api-sandbox.asaas.com/v3/payments/pay_1/refund")])

    def test_acao_critica_pendente(self):
        # Resposta real do sandbox (28/10/2026) com a proteção de eventos críticos ligada.
        from src.providers.asaas_provider import AsaasProvider
        resp = mock.MagicMock(status_code=200, content=b"{}")
        resp.json.return_value = {"id": "pay_1", "status": "RECEIVED", "refunds": [
            {"status": "AWAITING_CRITICAL_ACTION_AUTHORIZATION", "value": 135.0}]}
        with mock.patch("src.providers.asaas_provider.requests.request", return_value=resp):
            self.assertTrue(AsaasProvider("k", "https://api-sandbox.asaas.com").estorna("pay_1"))


if __name__ == "__main__":
    unittest.main()
