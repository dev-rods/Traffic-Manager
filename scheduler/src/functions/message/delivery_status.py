import os
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import parse_body, http_response, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DELIVERED_STATUSES = ("RECEIVED", "READ", "READ_BY_ME", "PLAYED")
# How far past the batch's earliest send we bother to look for confirmations.
# WhatsApp typically confirms delivery within seconds; a wide window costs us
# nothing on hot batches and covers slow deliveries on cold ones.
LOOKAHEAD_MINUTES = 30


def handler(event, context):
    """
    POST /messages/delivery-status

    Body:
    {
      "clinicId": "...",
      "sends": [
        { "providerMessageId": "<whatsapp id>", "sentAtIso": "2026-07-24T01:14:36Z" },
        ...
      ]
    }

    Consulta o GSI clinicId-statusTimestamp-index de forma direcionada: para cada
    status "entregue" (RECEIVED/READ/PLAYED/READ_BY_ME) faz uma Query com
    BETWEEN no range key statusTimestamp = "<STATUS>#<ISO_TS>", limitando o
    escaneamento à janela entre o menor sentAt e sentAt + 30 min. Assim escapamos
    de escanear a clínica inteira.
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Body vazio"})

        clinic_id = body.get("clinicId")
        sends = body.get("sends") or []

        if not clinic_id or not isinstance(sends, list) or not sends:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatórios: clinicId, sends (array não vazio)",
            })

        normalized: List[Dict[str, str]] = []
        for s in sends:
            pmid = (s or {}).get("providerMessageId") or ""
            sent_at = (s or {}).get("sentAtIso") or ""
            if pmid and sent_at:
                normalized.append({"providerMessageId": pmid, "sentAtIso": sent_at})

        if not normalized:
            return http_response(200, {"status": "SUCCESS", "results": []})

        target_pmids: Set[str] = {s["providerMessageId"] for s in normalized}
        # The frontend sends ISO with milliseconds (Date.toISOString), but STATUS_UPDATE
        # rows store second-precision (e.g. "RECEIVED#2026-07-24T12:23:25Z"). Truncate
        # to seconds so the lexicographic range on statusTimestamp matches cleanly.
        min_sent_at = _truncate_ms(min(s["sentAtIso"] for s in normalized))
        upper_bound = _iso_plus(min_sent_at, minutes=LOOKAHEAD_MINUTES)

        table = _get_table()
        delivered_pmids: Set[str] = set()

        for status in DELIVERED_STATUSES:
            low = f"{status}#{min_sent_at}"
            high = f"{status}#{upper_bound}"
            resp = table.query(
                IndexName="clinicId-statusTimestamp-index",
                KeyConditionExpression=Key("clinicId").eq(clinic_id)
                & Key("statusTimestamp").between(low, high),
                ProjectionExpression="messageId, direction",
            )
            for item in resp.get("Items", []):
                if item.get("direction") != "STATUS_UPDATE":
                    continue
                mid = item.get("messageId")
                if mid in target_pmids:
                    delivered_pmids.add(mid)
            # Note: the query above doesn't paginate — the [sentAt, sentAt+30min]
            # window per status will realistically fit in a single 1MB page even
            # for busy clinics. If a clinic ever hits that limit, add pagination.

        results = []
        for s in normalized:
            pmid = s["providerMessageId"]
            results.append({
                "providerMessageId": pmid,
                "delivery": "delivered" if pmid in delivered_pmids else "pending",
            })

        return http_response(200, {"status": "SUCCESS", "results": results})

    except Exception as e:
        logger.error(f"[delivery_status] erro: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})


def _truncate_ms(iso_ts: str) -> str:
    """Strip fractional seconds so 2026-07-24T12:23:19.731Z becomes 2026-07-24T12:23:19Z."""
    if "." in iso_ts:
        head, _, tail = iso_ts.partition(".")
        # tail is like "731Z" — keep only the trailing zone marker if present
        return head + ("Z" if tail.endswith("Z") else "")
    return iso_ts


def _iso_plus(iso_ts: str, minutes: int) -> str:
    dt = datetime.strptime(_truncate_ms(iso_ts), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    dt += timedelta(minutes=minutes)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


_table: Optional[Any] = None


def _get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(os.environ["MESSAGE_EVENTS_TABLE"])
    return _table
