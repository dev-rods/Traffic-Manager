# -*- coding: utf-8 -*-
"""Conta principal e conta reserva da Anthropic (PRD 068).

A reserva só entra quando a principal é RECUSADA (saldo, teto de gasto, chave
inválida). Falha passageira é retentada na própria principal: passar para a
reserva por um 429 comum ou um 500 só gastaria a outra conta.
"""
import io
import json
import os
import unittest
from contextlib import redirect_stdout
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services import anthropic_service
from src.services.anthropic_service import (
    AnthropicError,
    AnthropicService,
    e_recusa_da_conta,
)

PRINCIPAL = "chave-principal-de-teste"
RESERVA = "chave-reserva-de-teste"


def erro(status, tipo, mensagem, codigo=None):
    corpo = {"type": "error", "error": {"type": tipo, "message": mensagem}}
    if codigo:
        corpo["error"]["details"] = {"error_code": codigo}
    return status, corpo


SEM_SALDO = erro(400, "invalid_request_error",
                 "Your credit balance is too low to access the Anthropic API. "
                 "Please go to Plans & Billing to upgrade or purchase credits.")
LIMITE_DA_ORGANIZACAO = erro(400, "invalid_request_error",
                             "You have reached your specified workspace spend limit.")
CHAVE_INVALIDA = erro(401, "authentication_error", "invalid x-api-key")
COBRANCA = erro(402, "billing_error", "Billing error")
SEM_PERMISSAO = erro(403, "permission_error", "Permission denied")
TETO_MENSAL = erro(429, "rate_limit_error", "You have reached your API usage limits: ...",
                   "enforced_spend_limit_reached")
LIMITE_DE_TAXA = erro(429, "rate_limit_error", "Number of request tokens has exceeded your rate limit")
PEDIDO_MAL_FORMADO = erro(400, "invalid_request_error", "messages: field required")
INTERNO = erro(500, "api_error", "Internal server error")
SOBRECARGA = erro(529, "overloaded_error", "Overloaded")


def resposta(status, corpo=None):
    r = mock.Mock()
    r.status_code = status
    r.headers = {}
    r.json.return_value = corpo if corpo is not None else {
        "content": [{"type": "text", "text": "ok"}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 10, "output_tokens": 2},
    }
    r.text = json.dumps(r.json.return_value)
    return r


def ok():
    return resposta(200)


def de(vetor):
    return resposta(*vetor)


class TestClassificacaoDaRecusa(unittest.TestCase):
    def test_recusas_da_conta(self):
        for vetor in (SEM_SALDO, LIMITE_DA_ORGANIZACAO, CHAVE_INVALIDA, COBRANCA,
                      SEM_PERMISSAO, TETO_MENSAL):
            with self.subTest(vetor=vetor):
                self.assertTrue(e_recusa_da_conta(*vetor))

    def test_nao_sao_recusa(self):
        for vetor in (LIMITE_DE_TAXA, PEDIDO_MAL_FORMADO, INTERNO, SOBRECARGA):
            with self.subTest(vetor=vetor):
                self.assertFalse(e_recusa_da_conta(*vetor))

    def test_corpo_vazio_so_vale_pelo_status(self):
        self.assertTrue(e_recusa_da_conta(401, {}))
        self.assertFalse(e_recusa_da_conta(400, None))


class BaseDasContas(unittest.TestCase):
    reserva = RESERVA

    def setUp(self):
        env = {"ANTHROPIC_API_KEY": PRINCIPAL, "STAGE": "teste"}
        if self.reserva:
            env["ANTHROPIC_API_KEY_RESERVA"] = self.reserva
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        if not self.reserva:
            os.environ.pop("ANTHROPIC_API_KEY_RESERVA", None)
        self.addCleanup(patcher.stop)
        anthropic_service._recusada_ate.clear()
        self.addCleanup(anthropic_service._recusada_ate.clear)
        mock.patch("src.services.anthropic_service.time.sleep").start()
        self.addCleanup(mock.patch.stopall)
        self.servico = AnthropicService()

    def chama(self, respostas):
        """Chama o serviço e devolve (resultado ou exceção, chaves usadas, métricas, logs)."""
        saida = io.StringIO()
        with mock.patch("requests.post", side_effect=respostas) as post, \
                redirect_stdout(saida), \
                self.assertLogs("src.services", level="INFO") as logs:
            try:
                resultado = self.servico.create_message(
                    system="s", messages=[{"role": "user", "content": "oi"}], max_tokens=8)
            except AnthropicError as e:
                resultado = e
            # Garante ao menos uma linha para o assertLogs não falhar sozinho.
            anthropic_service.logger.info("fim do teste")
        chaves = [c.kwargs["headers"]["x-api-key"] for c in post.call_args_list]
        metricas = [json.loads(l) for l in saida.getvalue().splitlines() if l.startswith("{")]
        nomes = [m["_aws"]["CloudWatchMetrics"][0]["Metrics"][0]["Name"] for m in metricas]
        return resultado, chaves, nomes, metricas, "\n".join(logs.output)


class TestReserva(BaseDasContas):
    def test_principal_atende_sem_tocar_a_reserva(self):
        r, chaves, nomes, _, logs = self.chama([ok()])
        self.assertEqual(r["stop_reason"], "end_turn")
        self.assertEqual(chaves, [PRINCIPAL])
        self.assertEqual(nomes, [])
        self.assertIn("conta=principal", logs)

    def test_recusa_da_principal_vai_para_a_reserva(self):
        r, chaves, nomes, _, logs = self.chama([de(CHAVE_INVALIDA), ok()])
        self.assertEqual(r["stop_reason"], "end_turn")
        self.assertEqual(chaves, [PRINCIPAL, RESERVA])
        self.assertEqual(nomes, ["ChamadaPelaReserva"])
        self.assertIn("conta=reserva", logs)
        self.assertIn("Recusa da conta principal: 401", logs)

    def test_sem_saldo_e_teto_mensal_vao_para_a_reserva_sem_retentar(self):
        for vetor in (SEM_SALDO, TETO_MENSAL, COBRANCA):
            with self.subTest(vetor=vetor[1]["error"]["message"][:30]):
                anthropic_service._recusada_ate.clear()
                _, chaves, _, _, _ = self.chama([de(vetor), ok()])
                self.assertEqual(chaves, [PRINCIPAL, RESERVA])

    def test_memoria_da_recusa_e_volta_depois_de_24h(self):
        self.chama([de(SEM_SALDO), ok()])

        _, chaves, nomes, _, _ = self.chama([ok()])
        self.assertEqual(chaves, [RESERVA], "dentro das 24 h vai direto à reserva")
        self.assertEqual(nomes, ["ChamadaPelaReserva"])

        daqui_a_um_dia = anthropic_service.time.time() + anthropic_service.MEMORIA_DA_RECUSA + 1
        with mock.patch("src.services.anthropic_service.time.time", return_value=daqui_a_um_dia):
            _, chaves, nomes, _, logs = self.chama([ok()])
        self.assertEqual(chaves, [PRINCIPAL])
        self.assertEqual(nomes, [])
        self.assertIn("Conta principal voltou a atender", logs)

    def test_falha_passageira_retenta_na_principal(self):
        for vetor in (LIMITE_DE_TAXA, INTERNO, SOBRECARGA):
            with self.subTest(status=vetor[0]):
                _, chaves, nomes, _, _ = self.chama([de(vetor), ok()])
                self.assertEqual(chaves, [PRINCIPAL, PRINCIPAL])
                self.assertEqual(nomes, [])

    def test_pedido_mal_formado_nao_vai_para_a_reserva(self):
        r, chaves, nomes, _, _ = self.chama([de(PEDIDO_MAL_FORMADO)])
        self.assertIsInstance(r, AnthropicError)
        self.assertEqual(chaves, [PRINCIPAL])
        self.assertEqual(nomes, ["ChamadaFalhou"])

    def test_as_duas_recusadas(self):
        r, chaves, nomes, _, _ = self.chama([de(SEM_SALDO), de(CHAVE_INVALIDA)])
        self.assertIsInstance(r, AnthropicError)
        self.assertEqual(chaves, [PRINCIPAL, RESERVA])
        self.assertEqual(nomes, ["ChamadaFalhou"])

    def test_principal_recusada_e_reserva_fora_ainda_tenta_a_principal(self):
        # A memória põe a principal no fim da fila, não fora dela.
        self.chama([de(SEM_SALDO), ok()])
        _, chaves, _, _, _ = self.chama([de(CHAVE_INVALIDA), ok()])
        self.assertEqual(chaves, [RESERVA, PRINCIPAL])

    def test_chave_nunca_aparece_em_log_nem_em_excecao(self):
        r, _, _, metricas, logs = self.chama([de(SEM_SALDO), de(CHAVE_INVALIDA)])
        for texto in (str(r), logs, json.dumps(metricas)):
            self.assertNotIn(PRINCIPAL, texto)
            self.assertNotIn(RESERVA, texto)

    def test_linha_emf(self):
        _, _, _, metricas, _ = self.chama([de(CHAVE_INVALIDA), ok()])
        (m,) = metricas
        definicao = m["_aws"]["CloudWatchMetrics"][0]
        self.assertEqual(definicao["Namespace"], "ClinicScheduler/Anthropic")
        self.assertEqual(definicao["Dimensions"], [["Stage"]])
        self.assertEqual(m["Stage"], "teste")
        self.assertEqual(m["ChamadaPelaReserva"], 1)
        self.assertIsInstance(m["_aws"]["Timestamp"], int)


class TestSemReserva(BaseDasContas):
    reserva = None

    def test_recusa_sem_reserva_e_o_comportamento_de_hoje(self):
        r, chaves, nomes, _, _ = self.chama([de(SEM_SALDO)])
        self.assertIsInstance(r, AnthropicError)
        self.assertEqual(chaves, [PRINCIPAL])
        self.assertEqual(nomes, ["ChamadaFalhou"])


if __name__ == "__main__":
    unittest.main()
