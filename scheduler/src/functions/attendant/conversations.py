import logging
import os
from collections import OrderedDict

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("MESSAGE_EVENTS_TABLE", "")


def handler(event, context):
    """
    GET /clinics/{clinicId}/conversations?limit=20

    Lists recent conversations grouped by phone, with last message preview.
    Uses the clinicId-statusTimestamp GSI on MessageEvents table.
    """
    _, auth_error = require_api_key(event)
    if auth_error:
        return auth_error

    clinic_id = extract_path_param(event, "clinicId")
    limit = int(extract_query_param(event, "limit") or "20")

    if not clinic_id:
        return http_response(400, {"status": "ERROR", "message": "clinicId obrigatório"})

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)

        # Query RECEIVED messages (INBOUND) and SENT messages (OUTBOUND) separately,
        # then merge. We can't query both prefixes at once with DynamoDB key conditions.
        # STATUS_UPDATE items have corrupted timestamps (year 58228) so we must avoid them.
        all_items = []
        for prefix in ("RECEIVED#", "SENT#"):
            response = table.query(
                IndexName="clinicId-statusTimestamp-index",
                KeyConditionExpression=(
                    Key("clinicId").eq(clinic_id) &
                    Key("statusTimestamp").begins_with(prefix)
                ),
                ScanIndexForward=False,
                Limit=300,
            )
            all_items.extend(response.get("Items", []))

        # Sort all items by createdAt descending
        all_items.sort(key=lambda x: x.get("createdAt", ""), reverse=True)

        # Group by phone, keep only latest message per phone
        conversations = OrderedDict()
        for item in all_items:
            phone = item.get("phone", "")
            direction = item.get("direction", "")

            if direction == "STATUS_UPDATE":
                continue

            if phone not in conversations:
                conversations[phone] = {
                    "phone": phone,
                    "last_message": item.get("content", "")[:100],
                    "last_direction": direction,
                    "last_message_at": item.get("createdAt", ""),
                    "sender_name": item.get("senderName", ""),
                }

            if len(conversations) >= limit:
                break

        return http_response(200, {
            "status": "OK",
            "conversations": list(conversations.values()),
            "total": len(conversations),
        })

    except Exception as e:
        logger.error(f"[Conversations] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
