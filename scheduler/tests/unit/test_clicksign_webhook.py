# -*- coding: utf-8 -*-
"""Webhook da ClickSign (PRD 036): HMAC do corpo cru, parse, idempotência e rota."""
import hashlib
import hmac
import json
import os
import unittest
from unittest import mock

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.functions.public_booking import clicksign_webhook

SEGREDO = "segredo-de-teste"
CORPO = json.dumps({"event": {"name": "auto_close", "occurred_at": "2026-11-04T12:00:00Z"},
                    "document": {"key": "doc-1"}})


def hmac_de(corpo: str, segredo: str = SEGREDO) -> str:
    return hmac.new(segredo.encode(), corpo.encode("utf-8"), hashlib.sha256).hexdigest()


def evento(corpo=CORPO, assinatura=None, header="Content-Hmac", base64=False):
    headers = {}
    if assinatura is not None:
        headers[header] = assinatura
    ev = {"httpMethod": "POST", "resource": "/public/clicksign/webhook", "headers": headers, "body": corpo}
    if base64:
        import base64 as b64
        ev["body"] = b64.b64encode(corpo.encode("utf-8")).decode("ascii")
        ev["isBase64Encoded"] = True
    return ev


class Base(unittest.TestCase):
    def setUp(self):
        p = mock.patch.dict(os.environ, {"CLICKSIGN_WEBHOOK_SECRET": SEGREDO})
        p.start()
        self.addCleanup(p.stop)
        self.aplica = mock.patch("src.services.consentimento.aplica_evento", return_value="SIGNED")
        self.aplica_mock = self.aplica.start()
        self.addCleanup(self.aplica.stop)
        for alvo in ("src.functions.public_booking.clicksign_webhook.PostgresService",
                     "src.functions.public_booking.clicksign_webhook.provedor_ativo"):
            p = mock.patch(alvo)
            p.start()
            self.addCleanup(p.stop)


class TestAssinatura(Base):
    def test_hmac_certo_com_prefixo_processa(self):
        r = clicksign_webhook.handler(evento(assinatura="sha256=" + hmac_de(CORPO)), None)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(json.loads(r["body"])["result"], "SIGNED")
        args = self.aplica_mock.call_args[0]
        self.assertEqual(args[2]["event"]["name"], "auto_close")
        self.assertEqual(args[3], "auto_close:doc-1:2026-11-04T12:00:00Z")

    def test_hmac_sem_prefixo_e_no_outro_header(self):
        r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO), header="x-clicksign-signature"), None)
        self.assertEqual(r["statusCode"], 200)

    def test_header_em_qualquer_caixa(self):
        r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO), header="content-hmac"), None)
        self.assertEqual(r["statusCode"], 200)

    def test_corpo_em_base64_e_verificado_depois_de_decodificar(self):
        r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO), base64=True), None)
        self.assertEqual(r["statusCode"], 200)

    def test_hmac_errado_e_401(self):
        r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO, "outro")), None)
        self.assertEqual(r["statusCode"], 401)
        self.aplica_mock.assert_not_called()

    def test_hmac_ausente_e_401(self):
        self.assertEqual(clicksign_webhook.handler(evento(), None)["statusCode"], 401)

    def test_hmac_de_outro_corpo_e_401(self):
        outro = CORPO.replace("doc-1", "doc-2")
        self.assertEqual(clicksign_webhook.handler(evento(outro, assinatura=hmac_de(CORPO)), None)["statusCode"], 401)

    def test_segredo_vazio_recusa_tudo(self):
        with mock.patch.dict(os.environ, {"CLICKSIGN_WEBHOOK_SECRET": ""}):
            r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO, "")), None)
        self.assertEqual(r["statusCode"], 401)

    def test_corpo_invalido_e_400(self):
        corpo = "nao é json"
        r = clicksign_webhook.handler(evento(corpo, assinatura=hmac_de(corpo)), None)
        self.assertEqual(r["statusCode"], 400)
        corpo = "[1, 2]"
        r = clicksign_webhook.handler(evento(corpo, assinatura=hmac_de(corpo)), None)
        self.assertEqual(r["statusCode"], 400)

    def test_falha_no_processamento_e_500_para_reenvio(self):
        self.aplica_mock.side_effect = RuntimeError("banco fora")
        r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO)), None)
        self.assertEqual(r["statusCode"], 500)

    def test_repetido_responde_200(self):
        self.aplica_mock.return_value = "repetido"
        r = clicksign_webhook.handler(evento(assinatura=hmac_de(CORPO)), None)
        self.assertEqual(r["statusCode"], 200)
        self.assertEqual(json.loads(r["body"])["result"], "repetido")


class TestRota(unittest.TestCase):
    def test_router_e_interface(self):
        from src.functions.public_booking.router import ROUTES
        self.assertIs(ROUTES[("POST", "public/clicksign/webhook")], clicksign_webhook.handler)
        raiz = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(os.path.join(raiz, "sls", "functions", "public_booking", "interface.yml"), encoding="utf-8") as f:
            yml = f.read()
        self.assertIn("path: public/clicksign/webhook", yml)
        self.assertIn("s3:PutObject", yml)
        with open(os.path.join(raiz, "serverless.yml"), encoding="utf-8") as f:
            sls = f.read()
        for chave in ("CLICKSIGN_API_KEY", "CLICKSIGN_WEBHOOK_SECRET", "CLICKSIGN_TCLE_TEMPLATE_KEY",
                      "TCLE_VERSION", "CLICKSIGN_BASE_URL", "DOCUMENTOS_BUCKET",
                      "sls/resources/s3/documentos-bucket.yml", "sls/functions/consent/interface.yml"):
            self.assertIn(chave, sls)


if __name__ == "__main__":
    unittest.main()
