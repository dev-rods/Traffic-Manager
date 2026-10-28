# -*- coding: utf-8 -*-
"""O que mandamos ao Asaas (API v3), com o HTTP mockado.

O que se confere aqui é o contrato que a documentação impõe: débito vira
cobrança de cartão (a fatura oferece débito), dinheiro vira `UNDEFINED`, Pix
busca o "copia e cola", cliente é reaproveitado pelo CPF, valor vai em reais.
"""
import os
import unittest
from datetime import date
from unittest import mock

from src.providers import payment_provider
from src.providers.asaas_provider import AsaasProvider
from src.providers.payment_provider import (
    CANCELADO, ErroDoProvedor, PAGO, PENDENTE, Pagador, PagamentoIndisponivel,
)

PAGADOR = Pagador(nome="Ana Souza", cpf="52998224725", telefone="5511999990000")


def resposta(status=200, json=None):
    r = mock.MagicMock()
    r.status_code = status
    r.content = b"x" if json is not None else b""
    r.json.return_value = json or {}
    r.text = str(json)
    return r


class TestCobranca(unittest.TestCase):
    def setUp(self):
        self.chamadas = []
        self.cliente_existe = True
        p = mock.patch("src.providers.asaas_provider.requests.request", side_effect=self.http)
        p.start()
        self.addCleanup(p.stop)
        self.asaas = AsaasProvider("chave", "https://api-sandbox.asaas.com/")

    def http(self, metodo, url, headers=None, timeout=None, **kw):
        caminho = url.split("/v3", 1)[1]
        self.chamadas.append((metodo, caminho, kw))
        self.assertEqual(headers["access_token"], "chave")
        if metodo == "GET" and caminho == "/customers":
            return resposta(json={"data": [{"id": "cus_1"}] if self.cliente_existe else []})
        if metodo == "POST" and caminho == "/customers":
            return resposta(json={"id": "cus_novo"})
        if metodo == "POST" and caminho == "/payments":
            return resposta(json={"id": "pay_1", "status": "PENDING", "invoiceUrl": "https://asaas/i/pay_1"})
        if metodo == "GET" and caminho == "/payments/pay_1/pixQrCode":
            return resposta(json={"payload": "000201", "encodedImage": "..."})
        if metodo == "GET" and caminho == "/payments/pay_1":
            return resposta(json={"status": "RECEIVED"})
        return resposta(json={})

    def cria(self, metodo):
        return self.asaas.cria_cobranca(PAGADOR, metodo, 22550, date(2026, 10, 20), "Sessão", "ref-1")

    def corpo_da_cobranca(self):
        return next(kw["json"] for m, c, kw in self.chamadas if m == "POST" and c == "/payments")

    def test_pix(self):
        c = self.cria("PIX")
        self.assertEqual((c.id, c.status, c.pix_payload), ("pay_1", PENDENTE, "000201"))
        corpo = self.corpo_da_cobranca()
        self.assertEqual(corpo, {"customer": "cus_1", "billingType": "PIX", "value": 225.5,
                                 "dueDate": "2026-10-20", "description": "Sessão", "externalReference": "ref-1"})

    def test_credito_e_debito_viram_cartao_com_fatura(self):
        for metodo in ("CREDIT_CARD", "DEBIT_CARD"):
            with self.subTest(metodo=metodo):
                self.chamadas.clear()
                c = self.cria(metodo)
                self.assertEqual(self.corpo_da_cobranca()["billingType"], "CREDIT_CARD")
                self.assertEqual(c.invoice_url, "https://asaas/i/pay_1")
                self.assertIsNone(c.pix_payload)

    def test_dinheiro_e_indefinido(self):
        self.cria("CASH")
        self.assertEqual(self.corpo_da_cobranca()["billingType"], "UNDEFINED")

    def test_cliente_novo_sem_notificacao_do_asaas(self):
        self.cliente_existe = False
        self.cria("PIX")
        novo = next(kw["json"] for m, c, kw in self.chamadas if m == "POST" and c == "/customers")
        self.assertEqual(novo["cpfCnpj"], "52998224725")
        self.assertTrue(novo["notificationDisabled"])
        self.assertEqual(self.corpo_da_cobranca()["customer"], "cus_novo")

    def test_status_cancela_e_dinheiro(self):
        self.assertEqual(self.asaas.consulta_status("pay_1"), PAGO)
        self.asaas.cancela("pay_1")
        self.asaas.recebe_em_dinheiro("pay_1", 22550, date(2026, 10, 20))
        self.assertIn(("DELETE", "/payments/pay_1", {}), self.chamadas)
        dinheiro = next(kw["json"] for m, c, kw in self.chamadas if c == "/payments/pay_1/receiveInCash")
        self.assertEqual(dinheiro, {"paymentDate": "2026-10-20", "value": 225.5, "notifyCustomer": False})

    def test_erro_vira_erro_do_provedor(self):
        with mock.patch("src.providers.asaas_provider.requests.request",
                        return_value=resposta(400, {"errors": [{"description": "CPF inválido"}]})):
            with self.assertRaises(ErroDoProvedor):
                self.cria("PIX")


class TestSimulaNoSandbox(unittest.TestCase):
    """O botão "Simular pagamento (teste)" do iPad, com o Asaas de verdade em dev."""

    def test_sandbox_confirma_pela_api(self):
        chamadas = []
        with mock.patch("src.providers.asaas_provider.requests.request",
                        side_effect=lambda m, u, **k: chamadas.append((m, u)) or resposta(json={"status": "RECEIVED"})):
            asaas = AsaasProvider("chave", "https://api-sandbox.asaas.com")
            self.assertTrue(asaas.pode_simular)
            asaas.simula("pay_1")
        self.assertEqual(chamadas, [("POST", "https://api-sandbox.asaas.com/v3/sandbox/payment/pay_1/confirm")])

    def test_producao_nunca_simula(self):
        with mock.patch("src.providers.asaas_provider.requests.request") as http:
            asaas = AsaasProvider("chave", "https://api.asaas.com")
            self.assertFalse(asaas.pode_simular)
            with self.assertRaises(ErroDoProvedor):
                asaas.simula("pay_1")
        http.assert_not_called()

    def test_cobranca_de_teste(self):
        from src.providers.payment_provider import cobranca_de_teste
        self.assertTrue(cobranca_de_teste("simulado"))
        with mock.patch.dict(os.environ, {"ASAAS_BASE_URL": "https://api-sandbox.asaas.com"}):
            self.assertTrue(cobranca_de_teste("asaas"))
        with mock.patch.dict(os.environ, {"ASAAS_BASE_URL": "https://api.asaas.com"}):
            self.assertFalse(cobranca_de_teste("asaas"))


class TestStatus(unittest.TestCase):
    def test_mapa(self):
        from src.providers.asaas_provider import status_do_asaas
        self.assertEqual(status_do_asaas("RECEIVED_IN_CASH"), PAGO)
        self.assertEqual(status_do_asaas("DELETED"), CANCELADO)
        self.assertIsNone(status_do_asaas("ALGO_NOVO"))


class TestProvedorAtivo(unittest.TestCase):
    def test_com_chave_e_asaas(self):
        with mock.patch.dict(os.environ, {"ASAAS_API_KEY": "k", "STAGE": "prod"}):
            self.assertEqual(payment_provider.provedor_ativo().nome, "asaas")

    def test_sem_chave_simulado_so_em_dev(self):
        with mock.patch.dict(os.environ, {"ASAAS_API_KEY": "", "STAGE": "dev"}):
            self.assertEqual(payment_provider.provedor_ativo().nome, "simulado")
        with mock.patch.dict(os.environ, {"ASAAS_API_KEY": "", "STAGE": "prod"}):
            with self.assertRaises(PagamentoIndisponivel):
                payment_provider.provedor_ativo()


class TestCpf(unittest.TestCase):
    def test_digitos(self):
        from src.utils.cadastro import cpf_valido
        self.assertTrue(cpf_valido("529.982.247-25"))
        self.assertTrue(cpf_valido("11144477735"))
        for ruim in ("52998224724", "00000000000", "123", "", None):
            with self.subTest(cpf=ruim):
                self.assertFalse(cpf_valido(ruim))


if __name__ == "__main__":
    unittest.main()
