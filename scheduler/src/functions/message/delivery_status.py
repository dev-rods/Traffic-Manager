import os
import logging
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.utils.http import parse_body, http_response, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DELIVERED_STATUSES = {"RECEIVED", "READ", "READ_BY_ME", "PLAYED"}


def handler(event, context):
    """
    POST /messages/delivery-status

    Body:
    {
      "clinicId": "...",
      "sends": [
        { "providerMessageId": "<whatsapp id>", "sentAtIso": "2026-07-23T14:00:00Z" },
        ...
      ]
    }

    Retorna, para cada envio, o estado de entrega deduzido dos webhooks de status
    do WhatsApp (RECEIVED/READ/PLAYED). Consulta o GSI clinicId-statusTimestamp-index
    para pegar todos os STATUS_UPDATEs da clínica a partir do menor sentAt, então
    faz o casamento em memória por providerMessageId.
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

        # Normalize + validate
        normalized: List[Dict[str, str]] = []
        for s in sends:
            pmid = (s or {}).get("providerMessageId") or ""
            sent_at = (s or {}).get("sentAtIso") or ""
            if pmid and sent_at:
                normalized.append({"providerMessageId": pmid, "sentAtIso": sent_at})

        if not normalized:
            return http_response(200, {"status": "SUCCESS", "results": []})

        min_sent_at = min(s["sentAtIso"] for s in normalized)

        # Query GSI clinicId-statusTimestamp-index for status updates since the earliest send.
        # statusTimestamp format is "<STATUS>#<ISO_TS>" — we can't range-query it directly for
        # timestamps across statuses, so we do a query by clinic and filter in code.
        table = _get_table()
        latest_status_by_pmid: Dict[str, Dict[str, str]] = {}

        query_kwargs: Dict[str, Any] = {
            "IndexName": "clinicId-statusTimestamp-index",
            "KeyConditionExpression": Key("clinicId").eq(clinic_id),
        }

        target_pmids = {s["providerMessageId"] for s in normalized}
        pending = set(target_pmids)

        while True:
            resp = table.query(**query_kwargs)
            for item in resp.get("Items", []):
                if item.get("direction") != "STATUS_UPDATE":
                    continue
                pmid = item.get("messageId")
                if pmid not in target_pmids:
                    continue
                created_at = item.get("createdAt", "")
                if created_at < min_sent_at:
                    continue
                status = item.get("status", "")
                cur = latest_status_by_pmid.get(pmid)
                if cur is None or created_at > cur["at"]:
                    latest_status_by_pmid[pmid] = {"status": status, "at": created_at}
                if status in DELIVERED_STATUSES:
                    pending.discard(pmid)
            last_key = resp.get("LastEvaluatedKey")
            if not last_key:
                break
            # Short-circuit: if every target is already confirmed delivered, stop paging
            if not pending:
                break
            query_kwargs["ExclusiveStartKey"] = last_key

        results = []
        for s in normalized:
            pmid = s["providerMessageId"]
            latest = latest_status_by_pmid.get(pmid)
            if latest and latest["status"] in DELIVERED_STATUSES:
                delivery = "delivered"
            elif latest:
                delivery = "sent_only"  # z-api enfileirou/aceitou, mas WhatsApp não confirmou entrega
            else:
                delivery = "pending"    # nenhum webhook chegou ainda desde o envio
            results.append({
                "providerMessageId": pmid,
                "delivery": delivery,
                "lastStatus": latest["status"] if latest else None,
                "lastStatusAt": latest["at"] if latest else None,
            })

        return http_response(200, {"status": "SUCCESS", "results": results})

    except Exception as e:
        logger.error(f"[delivery_status] erro: {e}")
        return http_response(500, {"status": "ERROR", "message": str(e)})


_table: Optional[Any] = None


def _get_table():
    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        _table = dynamodb.Table(os.environ["MESSAGE_EVENTS_TABLE"])
    return _table
