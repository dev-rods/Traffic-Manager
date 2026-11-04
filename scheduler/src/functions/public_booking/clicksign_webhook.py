# -*- coding: utf-8 -*-
"""POST /public/clicksign/webhook - eventos de assinatura da ClickSign (PRD 036).

A ClickSign assina o CORPO CRU com HMAC SHA-256 do segredo configurado no
webhook e manda em `Content-Hmac: sha256=<hex>` (a documentação cita também
`x-clicksign-signature`; lemos os dois). Diferente do Asaas, que compara um
token fixo. Sem segredo configurado, recusa tudo: um webhook aberto deixaria
qualquer um marcar termo como assinado.

O HMAC é sobre o corpo como chegou, nunca sobre o JSON re-serializado.

Responde 200 assim que o evento é processado e gravado. Erro de
processamento devolve 500 para a ClickSign reenviar.
"""
import base64
import hashlib
import hmac
import json
import logging
import os

from src.providers.signature_provider import provedor_ativo
from src.services import consentimento
from src.services.db.postgres import PostgresService
from src.utils.http import http_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

HEADERS_DE_ASSINATURA = ("content-hmac", "x-clicksign-signature")


def _assinatura(event) -> str:
    headers = event.get("headers") or {}
    for chave, valor in headers.items():
        if str(chave).lower() in HEADERS_DE_ASSINATURA and valor:
            valor = str(valor).strip()
            return valor[7:] if valor.lower().startswith("sha256=") else valor
    return ""


def _corpo_cru(event) -> bytes:
    corpo = event.get("body") or ""
    if event.get("isBase64Encoded"):
        return base64.b64decode(corpo)
    return corpo.encode("utf-8") if isinstance(corpo, str) else bytes(corpo)


def assinatura_confere(segredo: str, corpo: bytes, recebida: str) -> bool:
    if not segredo or not recebida:
        return False
    esperado = hmac.new(segredo.encode("utf-8"), corpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, recebida.lower())


def handler(event, context):
    corpo = _corpo_cru(event)
    if not assinatura_confere(os.environ.get("CLICKSIGN_WEBHOOK_SECRET", ""), corpo, _assinatura(event)):
        logger.warning("[ClicksignWebhook] assinatura ausente ou inválida")
        return http_response(401, {"status": "ERROR", "message": "Não autorizado"})

    try:
        evento = json.loads(corpo.decode("utf-8") or "{}")
    except (ValueError, UnicodeDecodeError):
        return http_response(400, {"status": "ERROR", "message": "Corpo inválido"})
    if not isinstance(evento, dict):
        return http_response(400, {"status": "ERROR", "message": "Corpo inválido"})

    event_id = consentimento.event_id_de(evento)
    try:
        resultado = consentimento.aplica_evento(PostgresService(), provedor_ativo(), evento, event_id)
        logger.info("[ClicksignWebhook] {}: {}".format(event_id, resultado))
        return http_response(200, {"status": "SUCCESS", "result": resultado})
    except Exception as e:
        logger.error("[ClicksignWebhook] falha em {}: {}".format(event_id, e), exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
