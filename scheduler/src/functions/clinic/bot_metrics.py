import logging
import os
from datetime import datetime, timedelta
from collections import defaultdict

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MESSAGE_EVENTS_TABLE = os.environ.get("MESSAGE_EVENTS_TABLE", "")


def handler(event, context):
    """
    GET /clinics/{clinicId}/bot-metrics?period=today|week|month
    """
    _, auth_error = require_api_key(event)
    if auth_error:
        return auth_error

    clinic_id = extract_path_param(event, "clinicId")
    period = extract_query_param(event, "period") or "today"

    if not clinic_id:
        return http_response(400, {"status": "ERROR", "message": "clinicId obrigatório"})

    now = datetime.utcnow()
    if period == "week":
        start = (now - timedelta(days=7)).isoformat() + "Z"
    elif period == "month":
        start = (now - timedelta(days=30)).isoformat() + "Z"
    else:
        start = now.strftime("%Y-%m-%dT00:00:00Z")

    try:
        # 1. Query MessageEvents for the period
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(MESSAGE_EVENTS_TABLE)

        # Query RECEIVED (INBOUND) and SENT/QUEUED (OUTBOUND) with date range to avoid
        # STATUS_UPDATE items that have corrupted timestamps (year 58228 from ms→s bug)
        items = []
        for prefix in ("RECEIVED#", "SENT#", "QUEUED#"):
            response = table.query(
                IndexName="clinicId-statusTimestamp-index",
                KeyConditionExpression=(
                    Key("clinicId").eq(clinic_id) &
                    Key("statusTimestamp").between(f"{prefix}{start[:10]}", f"{prefix}2030")
                ),
                ScanIndexForward=True,
                Limit=5000,
            )
            items.extend(response.get("Items", []))

        # Count unique conversations and messages
        inbound_phones = set()
        outbound_count = 0
        handoff_phones = set()
        daily_counts = defaultdict(int)

        for item in items:
            direction = item.get("direction", "")
            phone = item.get("phone", "")
            created = item.get("createdAt", "")
            state = item.get("conversationState", "")

            if direction == "INBOUND":
                inbound_phones.add(phone)
                if created:
                    day = created[:10]
                    daily_counts[day] += 1
            elif direction == "OUTBOUND":
                outbound_count += 1

            if state in ("HUMAN_HANDOFF", "HUMAN_ATTENDANT_ACTIVE"):
                handoff_phones.add(phone)

        # 2. Query leads for conversion rate
        db = PostgresService()
        leads_result = db.execute_query(
            """
            SELECT
                COUNT(*) as total_leads,
                COUNT(*) FILTER (WHERE booked = TRUE) as booked_leads
            FROM scheduler.leads
            WHERE clinic_id = %s AND created_at >= %s
            """,
            (clinic_id, start),
        )

        total_leads = leads_result[0]["total_leads"] if leads_result else 0
        booked_leads = leads_result[0]["booked_leads"] if leads_result else 0
        conversion_rate = round((booked_leads / total_leads * 100), 1) if total_leads > 0 else 0

        return http_response(200, {
            "status": "OK",
            "metrics": {
                "total_conversations": len(inbound_phones),
                "messages_sent": outbound_count,
                "conversion_rate": conversion_rate,
                "total_leads": total_leads,
                "booked_leads": booked_leads,
                "handoff_count": len(handoff_phones),
                "daily_conversations": dict(daily_counts),
            },
            "period": period,
        })

    except Exception as e:
        logger.error(f"[BotMetrics] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
