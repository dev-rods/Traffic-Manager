import logging
import os

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("MESSAGE_EVENTS_TABLE", "")


def handler(event, context):
    """
    GET /clinics/{clinicId}/conversations/{phone}/messages?limit=50

    Returns messages for a specific conversation (clinic + phone).
    """
    _, auth_error = require_api_key(event)
    if auth_error:
        return auth_error

    clinic_id = extract_path_param(event, "clinicId")
    phone = extract_path_param(event, "phone")
    limit = int(extract_query_param(event, "limit") or "50")

    if not clinic_id or not phone:
        return http_response(400, {"status": "ERROR", "message": "clinicId e phone obrigatórios"})

    # Normalize phone to digits only
    clean_phone = "".join(c for c in phone if c.isdigit())

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)

        response = table.query(
            KeyConditionExpression=Key("pk").eq(f"CLINIC#{clinic_id}#PHONE#{clean_phone}"),
            ScanIndexForward=True,
            Limit=limit,
        )

        # Deduplicate by messageId — outbound messages create both QUEUED and SENT entries.
        # Keep the latest entry per messageId (SENT supersedes QUEUED).
        seen = {}
        for item in response.get("Items", []):
            direction = item.get("direction", "")
            if direction == "STATUS_UPDATE":
                continue

            msg_id = item.get("messageId", "")
            msg = {
                "id": msg_id,
                "direction": direction,
                "content": item.get("content", ""),
                "message_type": item.get("messageType", "text"),
                "status": item.get("status", ""),
                "created_at": item.get("createdAt", ""),
                "sender_name": item.get("senderName", ""),
            }

            if msg_id in seen:
                # Keep the entry with the "better" status (SENT > QUEUED > FAILED)
                existing = seen[msg_id]
                if msg["status"] in ("SENT", "RECEIVED") or existing["status"] == "QUEUED":
                    seen[msg_id] = msg
            else:
                seen[msg_id] = msg

        # Preserve chronological order from the original query
        messages = list(seen.values())

        return http_response(200, {
            "status": "OK",
            "messages": messages,
            "total": len(messages),
        })

    except Exception as e:
        logger.error(f"[Messages] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
