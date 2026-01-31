import json
import logging

from src.utils.http import parse_body, http_response
from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Webhook handler for WhatsApp message status updates via z-api.

    POST /webhook/whatsapp/status
    Receives z-api MessageStatusCallback payloads.
    Status lifecycle: SENT -> RECEIVED -> READ -> PLAYED
    """
    try:
        body = parse_body(event)
        if not body:
            return http_response(200, {"status": "OK"})

        logger.info(f"[StatusWebhook] Payload recebido: {json.dumps(body)[:500]}")

        # 1. Identify clinic by instanceId
        instance_id = body.get("instanceId", "")
        if not instance_id:
            logger.warning("[StatusWebhook] Payload sem instanceId")
            return http_response(200, {"status": "OK"})

        db = PostgresService()
        clinics = db.execute_query(
            "SELECT clinic_id FROM scheduler.clinics WHERE zapi_instance_id = %s AND active = TRUE",
            (instance_id,),
        )

        if not clinics:
            logger.warning(f"[StatusWebhook] Clinica nao encontrada para instanceId={instance_id}")
            return http_response(200, {"status": "OK"})

        clinic_id = clinics[0]["clinic_id"]

        # 2. Extract status data
        status = body.get("status", "")
        message_ids = body.get("ids", [])
        phone = body.get("phone", "")
        timestamp = body.get("momment", 0)

        if not status or not message_ids:
            logger.warning("[StatusWebhook] Payload sem status ou ids")
            return http_response(200, {"status": "OK"})

        # 3. Track status updates
        tracker = MessageTracker()
        updated_count = 0

        for msg_id in message_ids:
            tracker.update_status(
                clinic_id=clinic_id,
                phone=phone,
                message_id=msg_id,
                new_status=status,
                timestamp=timestamp,
                raw_payload=body,
            )
            updated_count += 1

        logger.info(
            f"[StatusWebhook] Status '{status}' registrado para {updated_count} mensagem(ns) | "
            f"clinic={clinic_id} phone={phone}"
        )

        return http_response(200, {
            "status": "OK",
            "updatedCount": updated_count,
        })

    except Exception as e:
        logger.error(f"[StatusWebhook] Erro interno: {e}")
        # Always return 200 to prevent z-api from retrying
        return http_response(200, {"status": "OK", "error": "internal"})
