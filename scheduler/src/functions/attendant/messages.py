import logging
import os
from typing import Dict, List, Set

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("MESSAGE_EVENTS_TABLE", "")

# Delivery status ordering — higher rank supersedes lower.
_STATUS_ORDER = {
    "FAILED": 0,
    "QUEUED": 1,
    "SENT": 2,
    "RECEIVED": 3,
    "READ_BY_ME": 4,
    "READ": 4,
    "PLAYED": 5,
}
DELIVERED_STATUSES = ("RECEIVED", "READ", "READ_BY_ME", "PLAYED")


def _rank(status: str) -> int:
    return _STATUS_ORDER.get(status, -1)


def handler(event, context):
    """
    GET /clinics/{clinicId}/conversations/{phone}/messages?limit=50

    Returns messages for a specific conversation. Each OUTBOUND is augmented with
    the highest-rank delivery status observed for it — the STATUS_UPDATE rows for
    delivery confirmations are indexed under a *different* pk (WhatsApp @lid, not
    the patient's real phone), so we look them up via the clinicId GSI keyed by
    the providerMessageId we stored on the OUTBOUND row.
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

        # First pass: collapse QUEUED/SENT rows per messageId (they share the same pk)
        # and collect providerMessageIds so we can look up delivery updates via the GSI.
        by_msgid: Dict[str, dict] = {}
        provider_ids: Set[str] = set()
        earliest_iso = ""
        for item in items:
            direction = item.get("direction", "")
            if direction != "OUTBOUND" and direction != "INBOUND":
                continue
            mid = item.get("messageId", "")
            if not mid:
                continue

            msg = {
                "id": mid,
                "direction": direction,
                "content": item.get("content", ""),
                "message_type": item.get("messageType", "text"),
                "status": item.get("status", ""),
                "provider_message_id": item.get("providerMessageId", ""),
                "created_at": item.get("createdAt", ""),
                "sender_name": item.get("senderName", ""),
            }

            existing = by_msgid.get(mid)
            if existing is None:
                by_msgid[mid] = msg
            else:
                # Keep earliest createdAt but promote status/providerMessageId to whichever row has them.
                if msg["created_at"] and (not existing["created_at"] or msg["created_at"] < existing["created_at"]):
                    existing["created_at"] = msg["created_at"]
                if _rank(msg["status"]) > _rank(existing["status"]):
                    existing["status"] = msg["status"]
                if not existing["provider_message_id"] and msg["provider_message_id"]:
                    existing["provider_message_id"] = msg["provider_message_id"]

            if direction == "OUTBOUND":
                pmid = msg["provider_message_id"]
                if pmid:
                    provider_ids.add(pmid)
                if not earliest_iso or (msg["created_at"] and msg["created_at"] < earliest_iso):
                    earliest_iso = msg["created_at"]

        # Second pass: look up delivery STATUS_UPDATE rows for the OUTBOUND providerMessageIds
        # in this conversation via the GSI. One query per delivered status, each bounded
        # by (earliest OUTBOUND createdAt, "Z") — a narrow enough range in practice.
        best_by_pmid: Dict[str, str] = {}
        if provider_ids and earliest_iso:
            for status in DELIVERED_STATUSES:
                low = f"{status}#{earliest_iso}"
                high = f"{status}#9999-12-31T23:59:59Z"
                pmids_left = set(provider_ids) - {p for p, s in best_by_pmid.items() if _rank(s) >= _rank(status)}
                if not pmids_left:
                    continue
                resp = table.query(
                    IndexName="clinicId-statusTimestamp-index",
                    KeyConditionExpression=Key("clinicId").eq(clinic_id)
                    & Key("statusTimestamp").between(low, high),
                    ProjectionExpression="messageId, direction, #s",
                    ExpressionAttributeNames={"#s": "status"},
                )
                for row in resp.get("Items", []):
                    if row.get("direction") != "STATUS_UPDATE":
                        continue
                    row_mid = row.get("messageId", "")
                    if row_mid not in provider_ids:
                        continue
                    row_status = row.get("status", "")
                    if _rank(row_status) > _rank(best_by_pmid.get(row_mid, "")):
                        best_by_pmid[row_mid] = row_status
            # Apply the highest-rank delivery status back onto each OUTBOUND message.
            for msg in by_msgid.values():
                pmid = msg.pop("provider_message_id", "")
                if msg["direction"] == "OUTBOUND" and pmid in best_by_pmid:
                    if _rank(best_by_pmid[pmid]) > _rank(msg["status"]):
                        msg["status"] = best_by_pmid[pmid]

        # Strip the internal helper field from INBOUND items too (they never had a providerMessageId)
        for msg in by_msgid.values():
            msg.pop("provider_message_id", None)

        messages: List[dict] = list(by_msgid.values())
        messages.sort(key=lambda m: m["created_at"])

        return http_response(200, {
            "status": "OK",
            "messages": messages,
            "total": len(messages),
        })

    except Exception as e:
        logger.error(f"[Messages] Error: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
