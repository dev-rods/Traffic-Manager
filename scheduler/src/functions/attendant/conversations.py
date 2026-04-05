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

        # Query RECEIVED (INBOUND) and SENT (OUTBOUND) with date range to avoid
        # STATUS_UPDATE items that have corrupted timestamps (year 58228 from ms→s bug).
        # Using BETWEEN with year range ensures we only get valid timestamps.
        all_items = []
        for prefix in ("RECEIVED#", "SENT#", "QUEUED#"):
            response = table.query(
                IndexName="clinicId-statusTimestamp-index",
                KeyConditionExpression=(
                    Key("clinicId").eq(clinic_id) &
                    Key("statusTimestamp").between(f"{prefix}2020", f"{prefix}2030")
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
            raw_phone = item.get("phone", "")

            # Skip WhatsApp group/list IDs
            if "@" in raw_phone or not raw_phone:
                continue

            # Normalize phone to digits only for consistent dedup
            phone = "".join(c for c in raw_phone if c.isdigit())
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

        # Enrich with patient names from PostgreSQL
        if conversations:
            from src.services.db.postgres import PostgresService
            try:
                db = PostgresService()
                phones_list = list(conversations.keys())
                placeholders = ",".join(["%s"] * len(phones_list))
                patients = db.execute_query(
                    f"SELECT phone, name FROM scheduler.patients WHERE clinic_id = %s AND phone IN ({placeholders})",
                    (clinic_id, *phones_list),
                )
                name_map = {p["phone"]: p["name"] for p in patients if p.get("name")}
                for phone, conv in conversations.items():
                    if phone in name_map:
                        conv["sender_name"] = name_map[phone]
            except Exception as e:
                logger.warning(f"[Conversations] Could not enrich names: {e}")

        return http_response(200, {
            "status": "OK",
            "conversations": list(conversations.values()),
            "total": len(conversations),
        })

    except Exception as e:
        logger.error(f"[Conversations] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
