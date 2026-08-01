"""
Scheduled Lambda: uploads offline conversions (real appointments) to Google Ads.

Runs daily. For each clinic mapped to a Google Ads account, finds appointments
tied to a gclid lead that are eligible (CONFIRMED, session already occurred, within
the gclid 90-day window, not yet uploaded) and sends them as ClickConversions.

Recurring by design: every appointment is its own conversion, so the accumulated
return of a returning client flows to Google over time.
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import boto3

from src.services.postgres_service import PostgresService
from src.services.google_ads_client_service import GoogleAdsClientService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")

# Google Ads aceita no máximo 2000 operações por UploadClickConversions
UPLOAD_CHUNK_SIZE = 2000
_SP_TZ = ZoneInfo("America/Sao_Paulo")


def _format_conversion_dt(conv_dt: datetime) -> str:
    """Formata para "YYYY-MM-DD HH:MM:SS+/-HH:MM" no fuso da clínica (BRT).

    conversion_date é TIMESTAMPTZ; o psycopg2 devolve tz-aware (UTC no Supabase).
    Converte para America/Sao_Paulo e usa o offset real, em vez de carimbar
    -03:00 sobre a hora UTC (o que deslocaria toda conversão).
    """
    if conv_dt.tzinfo is None:
        conv_dt = conv_dt.replace(tzinfo=timezone.utc)
    s = conv_dt.astimezone(_SP_TZ).strftime("%Y-%m-%d %H:%M:%S%z")  # ...-0300
    return s[:-2] + ":" + s[-2:]  # insere o ':' no offset -> -03:00


def _get_mapped_clinics(db: PostgresService):
    """Clinics that have a Google Ads account and an offline conversion action configured."""
    return db.execute_query(
        """
        SELECT clinic_id, google_ads_customer_id, offline_conversion_action_id
        FROM scheduler.clinics
        WHERE google_ads_customer_id IS NOT NULL
          AND offline_conversion_action_id IS NOT NULL
        """
    )


def _get_pending_conversions(db: PostgresService, clinic_id: str):
    """Eligible conversions for a clinic (delay anti-cancelamento + janela 90d)."""
    return db.execute_query(
        """
        SELECT lc.id, lc.gclid, lc.value_cents, lc.conversion_date
        FROM scheduler.lead_conversions lc
        JOIN scheduler.appointments a ON a.id = lc.appointment_id
        WHERE lc.clinic_id = %s
          AND lc.uploaded_at IS NULL
          AND a.status = 'CONFIRMED'
          AND a.appointment_date < CURRENT_DATE
          AND lc.conversion_date <= lc.click_date + INTERVAL '90 days'
        ORDER BY lc.conversion_date ASC
        """,
        (clinic_id,),
    )


def _mark_uploaded(db: PostgresService, conversion_ids):
    if not conversion_ids:
        return
    db.execute_write(
        "UPDATE scheduler.lead_conversions SET uploaded_at = NOW() WHERE id = ANY(%s::uuid[])",
        (list(conversion_ids),),
    )


def _record_execution(trace_id: str, summary: dict):
    try:
        table_name = os.environ.get("EXECUTION_HISTORY_TABLE")
        if not table_name:
            return
        dynamodb.Table(table_name).put_item(
            Item={
                "traceId": trace_id,
                "stageTm": "offline_conversion_upload",
                "status": "COMPLETED",
                "timestamp": datetime.utcnow().isoformat(),
                "payload": json.dumps(summary),
            }
        )
    except Exception as e:
        logger.error(f"Falha ao registrar execução: {e}")


def handler(event, context):
    trace_id = str(uuid.uuid4())
    logger.info(f"[traceId: {trace_id}] Iniciando upload de conversões offline")

    db = PostgresService()
    ads_service = GoogleAdsClientService()

    summary = {"clinics": 0, "uploaded": 0, "failed": 0, "details": []}

    clinics = _get_mapped_clinics(db)
    summary["clinics"] = len(clinics)

    for clinic in clinics:
        clinic_id = clinic["clinic_id"]
        customer_id = clinic["google_ads_customer_id"]
        conversion_action_id = clinic["offline_conversion_action_id"]

        pending = _get_pending_conversions(db, clinic_id)
        if not pending:
            continue

        conversions = []
        for row in pending:
            conversions.append({
                "identifier": str(row["id"]),
                "gclid": row["gclid"],
                "conversion_date_time": _format_conversion_dt(row["conversion_date"]),
                "conversion_value": (row["value_cents"] or 0) / 100.0,
            })

        # Envia em lotes de até 2000 (limite do Google) para não estourar o request
        # inteiro num backlog grande — cada lote é marcado assim que confirmado.
        clinic_uploaded = 0
        clinic_failed = 0
        errors = []
        for start in range(0, len(conversions), UPLOAD_CHUNK_SIZE):
            chunk = conversions[start:start + UPLOAD_CHUNK_SIZE]
            result = ads_service.upload_offline_conversions(
                customer_id=customer_id,
                conversion_action_id=conversion_action_id,
                conversions=chunk,
            )
            uploaded_ids = result.get("uploaded_identifiers", [])
            _mark_uploaded(db, uploaded_ids)
            clinic_uploaded += len(uploaded_ids)
            clinic_failed += result.get("failed", 0) if result.get("success") else len(chunk)
            if result.get("error"):
                errors.append(result["error"])

        summary["uploaded"] += clinic_uploaded
        summary["failed"] += clinic_failed
        summary["details"].append({
            "clinicId": clinic_id,
            "pending": len(pending),
            "uploaded": clinic_uploaded,
            "failed": clinic_failed,
            "errors": errors or None,
        })
        logger.info(
            f"[traceId: {trace_id}] Clínica {clinic_id}: {clinic_uploaded}/{len(pending)} enviadas"
        )

    _record_execution(trace_id, summary)
    logger.info(f"[traceId: {trace_id}] Concluído: {json.dumps(summary)}")
    return {"traceId": trace_id, "summary": summary}
