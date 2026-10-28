# -*- coding: utf-8 -*-
"""POST /public/asaas/webhook - eventos de cobrança do Asaas (PRD 026).

O Asaas manda o `authToken` configurado no webhook no header
`asaas-access-token`; sem ele igual a `ASAAS_WEBHOOK_TOKEN`, 401. Sem o
segredo configurado, recusa tudo: um webhook aberto deixaria qualquer um
marcar sessão como paga.

Responde 200 assim que o evento é gravado. Erro de processamento devolve
500 para o Asaas tentar de novo; depois de 15 falhas seguidas ele pausa a
fila, então o log de erro aqui é o alarme.
"""
import hmac
import json
import logging
import os

from src.providers.payment_provider import provedor_ativo
from src.services import checkin
from src.services.db.postgres import PostgresService
from src.utils.http import http_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _token(event):
    headers = event.get("headers") or {}
    for chave, valor in headers.items():
        if chave.lower() == "asaas-access-token":
            return valor or ""
    return ""


def handler(event, context):
    esperado = os.environ.get("ASAAS_WEBHOOK_TOKEN", "")
    if not esperado or not hmac.compare_digest(_token(event), esperado):
        logger.warning("[AsaasWebhook] token ausente ou inválido")
        return http_response(401, {"status": "ERROR", "message": "Não autorizado"})

    try:
        evento = json.loads(event.get("body") or "{}")
    except ValueError:
        return http_response(400, {"status": "ERROR", "message": "Corpo inválido"})

    try:
        resultado = checkin.aplica_evento(PostgresService(), provedor_ativo(), evento)
        logger.info(f"[AsaasWebhook] {evento.get('event')} {evento.get('id')}: {resultado}")
        return http_response(200, {"status": "SUCCESS", "result": resultado})
    except Exception as e:
        logger.error(f"[AsaasWebhook] falha em {evento.get('event')} {evento.get('id')}: {e}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno"})
