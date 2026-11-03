import logging
import os
import time
from collections import OrderedDict

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("MESSAGE_EVENTS_TABLE", "")


def _get_clinic(clinic_id):
    """Politica de resposta da clinica. Falha vira dict vazio (politica ALL)."""
    try:
        from src.services.db.postgres import PostgresService

        rows = PostgresService().execute_query(
            "SELECT bot_autoreply_policy, bot_pilot_phones, bot_paused "
            "FROM scheduler.clinics WHERE clinic_id = %s",
            (clinic_id,),
        )
        return rows[0] if rows else {}
    except Exception as e:
        logger.warning(f"[Conversations] Não consegui ler a política de {clinic_id}: {e}")
        return {}


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

        # Por que o bot esta calado em cada conversa (PRD 031). A lista vinha
        # so do MessageEvents e nao sabia distinguir "fora da regra" de "com
        # atendente": a recepcao abria uma a uma. Falha aqui nao derruba a
        # lista, so tira o selo.
        if conversations:
            try:
                from src.services import atendimento
                from src.services.sessoes_da_clinica import carrega_sessoes_da_clinica

                clinic = _get_clinic(clinic_id)
                sessoes = carrega_sessoes_da_clinica(clinic_id)
                now = int(time.time())
                for phone, conv in conversations.items():
                    motivo = atendimento.motivo_da_pausa(clinic, sessoes.get(phone), phone, now)
                    conv["pause_reason"] = motivo
                    conv["bot_paused"] = motivo is not None
            except Exception as e:
                logger.warning(f"[Conversations] Sem motivo da pausa: {e}")

        # Enrich with patient names from PostgreSQL
        if conversations:
            from src.services.db.postgres import PostgresService
            try:
                db = PostgresService()
                phones_list = list(conversations.keys())
                placeholders = ",".join(["%s"] * len(phones_list))
                patients = db.execute_query(
                    f"SELECT phone, name FROM scheduler.patients WHERE clinic_id = %s AND phone IN ({placeholders}) AND deleted_at IS NULL",
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
