import logging
import os
import time

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("CONVERSATION_SESSIONS_TABLE", "")


def handler(event, context):
    """
    GET /clinics/{clinicId}/conversations/active

    Lists conversation sessions for a clinic, showing which are paused.
    """
    _, auth_error = require_api_key(event)
    if auth_error:
        return auth_error

    clinic_id = extract_path_param(event, "clinicId")

    if not clinic_id:
        return http_response(400, {"status": "ERROR", "message": "clinicId obrigatório"})

    try:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)

        # Query all sessions for this clinic
        response = table.query(
            KeyConditionExpression=Key("pk").eq(f"CLINIC#{clinic_id}"),
        )

        now = int(time.time())
        conversations = []

        for item in response.get("Items", []):
            session = item.get("session", {})
            phone = item.get("phone", "")

            # Skip WhatsApp group/list IDs
            if "@" in phone or not phone:
                continue

            state = session.get("state", "")
            attendant_until = session.get("attendant_active_until")
            handoff_at = session.get("human_handoff_requested_at")
            updated_at = item.get("updatedAt", "")

            # Determine if bot is paused for this conversation
            bot_paused = False
            if state in ("HUMAN_ATTENDANT_ACTIVE", "HUMAN_HANDOFF"):
                if attendant_until and now < attendant_until:
                    bot_paused = True
                elif handoff_at and now < (handoff_at + 86400):
                    bot_paused = True

            conversations.append({
                "phone": phone,
                "state": state,
                "bot_paused": bot_paused,
                "attendant_active_until": attendant_until,
                "updated_at": updated_at,
            })

        # Enrich with patient names from PostgreSQL
        if conversations:
            from src.services.db.postgres import PostgresService
            try:
                db = PostgresService()
                phones_list = [c["phone"] for c in conversations]
                placeholders = ",".join(["%s"] * len(phones_list))
                patients = db.execute_query(
                    f"SELECT phone, name FROM scheduler.patients WHERE clinic_id = %s AND phone IN ({placeholders}) AND deleted_at IS NULL",
                    (clinic_id, *phones_list),
                )
                name_map = {p["phone"]: p["name"] for p in patients if p.get("name")}
                for conv in conversations:
                    conv["name"] = name_map.get(conv["phone"], "")
            except Exception as e:
                logger.warning(f"[ListActive] Could not enrich names: {e}")

        # Sort: paused first, then by updated_at desc
        conversations.sort(key=lambda c: (not c["bot_paused"], c.get("updated_at", "")), reverse=False)

        return http_response(200, {
            "status": "OK",
            "conversations": conversations,
            "total": len(conversations),
        })

    except Exception as e:
        logger.error(f"[ListActive] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
