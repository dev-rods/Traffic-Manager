import logging
import os
from typing import Dict

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("MESSAGE_EVENTS_TABLE", "")

# Delivery status ordering — later entries supersede earlier ones. Used both to
# collapse the QUEUED → SENT transition on the OUTBOUND record and to promote
# the OUTBOUND status when a STATUS_UPDATE (RECEIVED/READ/PLAYED) exists.
_STATUS_ORDER = {
    "FAILED": 0,
    "QUEUED": 1,
    "SENT": 2,
    "RECEIVED": 3,
    "READ_BY_ME": 4,
    "READ": 4,
    "PLAYED": 5,
}


def _rank(status: str) -> int:
    return _STATUS_ORDER.get(status, -1)


def handler(event, context):
    """
    GET /clinics/{clinicId}/conversations/{phone}/messages?limit=50

    Retorna as mensagens de uma conversa (clinic + phone). Para cada OUTBOUND,
    o campo `status` reflete o estado mais avançado conhecido:
    QUEUED → SENT → RECEIVED → READ → PLAYED. Isso permite o frontend renderizar
    ticks estilo WhatsApp por mensagem sem precisar de nova roundtrip.
    """
    _, auth_error = require_api_key(event)
    if auth_error:
        return auth_error

    clinic_id = extract_path_param(event, "clinicId")
    phone = extract_path_param(event, "phone")
    limit = int(extract_query_param(event, "limit") or "50")

    if not clinic_id or not phone:
        return http_response(400, {"status": "ERROR", "message": "clinicId e phone obrigatórios"})

    clean_phone = "".join(c for c in phone if c.isdigit())

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)

        response = table.query(
            KeyConditionExpression=Key("pk").eq(f"CLINIC#{clinic_id}#PHONE#{clean_phone}"),
            ScanIndexForward=True,
            Limit=limit,
        )

        items = response.get("Items", [])

        # First pass: for each messageId, find the highest-rank status seen across
        # OUTBOUND (QUEUED/SENT/FAILED) and STATUS_UPDATE (SENT/RECEIVED/READ/PLAYED) rows.
        best_status: Dict[str, str] = {}
        for item in items:
            mid = item.get("messageId", "")
            if not mid:
                continue
            status = item.get("status", "")
            if _rank(status) > _rank(best_status.get(mid, "")):
                best_status[mid] = status

        # Second pass: emit one message per messageId using the OUTBOUND/INBOUND record
        # as the source of content/direction/timestamp, then override status with the
        # highest-rank one collected above.
        seen: Dict[str, dict] = {}
        for item in items:
            direction = item.get("direction", "")
            if direction == "STATUS_UPDATE":
                continue

            mid = item.get("messageId", "")
            msg = {
                "id": mid,
                "direction": direction,
                "content": item.get("content", ""),
                "message_type": item.get("messageType", "text"),
                "status": best_status.get(mid, item.get("status", "")),
                "created_at": item.get("createdAt", ""),
                "sender_name": item.get("senderName", ""),
            }

            # Multiple OUTBOUND rows can share a messageId (QUEUED then SENT). Keep the
            # earliest createdAt so the bubble timestamp matches when the send started,
            # not when the confirmation landed.
            existing = seen.get(mid)
            if existing is None or msg["created_at"] < existing["created_at"]:
                seen[mid] = msg

        messages = list(seen.values())
        messages.sort(key=lambda m: m["created_at"])

        return http_response(200, {
            "status": "OK",
            "messages": messages,
            "total": len(messages),
        })

    except Exception as e:
        logger.error(f"[Messages] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
