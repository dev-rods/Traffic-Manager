import json
import os
import time
import uuid
import logging

import boto3

from src.utils.http import parse_body, http_response
from src.services.db.postgres import PostgresService
from src.services.template_service import TemplateService
from src.services.conversation_engine import ConversationEngine, ConversationState
from src.services.message_tracker import MessageTracker
from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Webhook handler for incoming WhatsApp messages via z-api.

    POST /webhook/whatsapp
    Receives z-api ReceivedCallback payloads.
    No API key required — authentication via instanceId validation.
    """
    try:
        body = parse_body(event)
        if not body:
            return http_response(200, {"status": "OK"})

        logger.info(f"[Webhook] Payload recebido: {json.dumps(body)[:500]}")

        # 1. Validate callback type
        if body.get("isGroup", False):
            logger.info("[Webhook] Ignorando mensagem de grupo")
            return http_response(200, {"status": "OK"})

        # 2. Identify clinic by instanceId
        instance_id = body.get("instanceId", "")
        if not instance_id:
            logger.warning("[Webhook] Payload sem instanceId")
            return http_response(200, {"status": "OK"})

        # 1b. Handle fromMe (attendant messages)
        if body.get("fromMe", False):
            phone = body.get("phone", "")
            if phone and instance_id:
                content = _extract_text_content(body)
                db = PostgresService()
                clinic_id = _resolve_clinic_id(db, instance_id)
                if clinic_id:
                    if content and content.strip().lower() in ("#encerrar", "#fim"):
                        _deactivate_attendant_mode(clinic_id, phone)
                    else:
                        _activate_attendant_mode(clinic_id, phone)
            logger.info("[Webhook] Mensagem propria processada (fromMe=true)")
            return http_response(200, {"status": "OK"})

        db = PostgresService()
        clinics = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE zapi_instance_id = %s AND active = TRUE",
            (instance_id,),
        )

        if not clinics:
            logger.warning(f"[Webhook] Clinica não encontrada para instanceId={instance_id}")
            return http_response(200, {"status": "OK"})

        clinic = clinics[0]
        clinic_id = clinic["clinic_id"]

        # 3. Setup services
        provider = get_provider(clinic)
        tracker = MessageTracker()
        template_service = TemplateService(db)

        # availability_engine and appointment_service are optional (Phase 8)
        availability_engine = _get_availability_engine(db)
        appointment_service = _get_appointment_service(db)

        engine = ConversationEngine(
            db=db,
            template_service=template_service,
            availability_engine=availability_engine,
            appointment_service=appointment_service,
            provider=provider,
            message_tracker=tracker,
        )

        # 4. Parse incoming message
        incoming = provider.parse_incoming_message(body)
        logger.info(
            f"[Webhook] Mensagem de {incoming.phone} | type={incoming.message_type} | "
            f"content='{incoming.content[:50]}' | clinic={clinic_id}"
        )

        # 5. Track inbound
        conversation_id = f"{clinic_id}#{incoming.phone}"
        tracker.track_inbound(
            clinic_id=clinic_id,
            phone=incoming.phone,
            message_id=incoming.message_id,
            conversation_id=conversation_id,
            incoming_message=incoming,
        )

        # 6. Process through conversation engine
        outgoing_messages = engine.process_message(clinic_id, incoming)

        # 7. Send responses
        for msg in outgoing_messages:
            msg_id = str(uuid.uuid4())

            tracker.track_outbound(
                clinic_id=clinic_id,
                phone=incoming.phone,
                message_id=msg_id,
                conversation_id=conversation_id,
                message_type=msg.message_type.upper(),
                content=msg.content,
                status="QUEUED",
            )

            if msg.message_type == "buttons" and msg.buttons:
                response = provider.send_buttons(incoming.phone, msg.content, msg.buttons)
            elif msg.message_type == "list" and msg.sections:
                button_text = msg.button_text or "Selecione"
                response = provider.send_list(incoming.phone, msg.content, button_text, msg.sections)
            else:
                response = provider.send_text(incoming.phone, msg.content)

            if response.success:
                tracker.track_outbound(
                    clinic_id=clinic_id,
                    phone=incoming.phone,
                    message_id=msg_id,
                    conversation_id=conversation_id,
                    message_type=msg.message_type.upper(),
                    content=msg.content,
                    status="SENT",
                    provider_message_id=response.provider_message_id,
                    provider_response=response.raw_response,
                )
                logger.info(f"[Webhook] Resposta enviada: msgId={msg_id} providerMsgId={response.provider_message_id}")
            else:
                tracker.track_outbound(
                    clinic_id=clinic_id,
                    phone=incoming.phone,
                    message_id=msg_id,
                    conversation_id=conversation_id,
                    message_type=msg.message_type.upper(),
                    content=msg.content,
                    status="FAILED",
                    metadata={"error": response.error},
                )
                logger.error(f"[Webhook] Falha ao enviar resposta: msgId={msg_id} error={response.error}")

        return http_response(200, {"status": "OK", "messagesProcessed": len(outgoing_messages)})

    except Exception as e:
        logger.error(f"[Webhook] Erro interno: {e}")
        # Always return 200 to prevent z-api from retrying
        return http_response(200, {"status": "OK", "error": "internal"})


def _get_availability_engine(db):
    try:
        from src.services.availability_engine import AvailabilityEngine
        return AvailabilityEngine(db)
    except ImportError:
        logger.info("[Webhook] AvailabilityEngine nao disponivel (Phase 8)")
        return None


def _get_appointment_service(db):
    try:
        from src.services.appointment_service import AppointmentService
        from src.services.sheets_sync import SheetsSync
        sheets_sync = SheetsSync(db)
        return AppointmentService(db, sheets_sync=sheets_sync)
    except ImportError:
        logger.info("[Webhook] AppointmentService nao disponivel (Phase 8)")
        return None


ATTENDANT_TTL_SECONDS = 2 * 60 * 60  # 2 hours


def _resolve_clinic_id(db: PostgresService, instance_id: str):
    clinics = db.execute_query(
        "SELECT clinic_id FROM scheduler.clinics WHERE zapi_instance_id = %s AND active = TRUE",
        (instance_id,),
    )
    return clinics[0]["clinic_id"] if clinics else None


def _get_sessions_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(os.environ["CONVERSATION_SESSIONS_TABLE"])


def _load_session(table, clinic_id: str, phone: str) -> dict:
    try:
        response = table.get_item(
            Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
        )
        item = response.get("Item")
        if item:
            return item.get("session", {})
    except Exception as e:
        logger.error(f"[Webhook] Error loading session: {e}")
    return {}


def _save_session(table, clinic_id: str, phone: str, session: dict) -> None:
    try:
        now = int(time.time())
        table.put_item(
            Item={
                "pk": f"CLINIC#{clinic_id}",
                "sk": f"PHONE#{phone}",
                "session": session,
                "clinicId": clinic_id,
                "phone": phone,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
            }
        )
    except Exception as e:
        logger.error(f"[Webhook] Error saving session: {e}")


def _extract_text_content(body: dict) -> str:
    if "text" in body:
        return body["text"].get("message", "")
    return ""


def _activate_attendant_mode(clinic_id: str, phone: str) -> None:
    table = _get_sessions_table()
    session = _load_session(table, clinic_id, phone)
    state = session.get("state", "")

    if state in (ConversationState.HUMAN_HANDOFF.value, ConversationState.HUMAN_ATTENDANT_ACTIVE.value):
        session["state"] = ConversationState.HUMAN_ATTENDANT_ACTIVE.value
        session["attendant_active_until"] = int(time.time()) + ATTENDANT_TTL_SECONDS
        _save_session(table, clinic_id, phone, session)
        logger.info(f"[Webhook] Modo atendente ativado/renovado para {phone} (TTL 2h)")


def _deactivate_attendant_mode(clinic_id: str, phone: str) -> None:
    table = _get_sessions_table()
    session = _load_session(table, clinic_id, phone)
    state = session.get("state", "")

    if state in (ConversationState.HUMAN_HANDOFF.value, ConversationState.HUMAN_ATTENDANT_ACTIVE.value):
        session["state"] = ConversationState.WELCOME.value
        session.pop("attendant_active_until", None)
        session.pop("human_handoff_requested_at", None)
        _save_session(table, clinic_id, phone, session)
        logger.info(f"[Webhook] Modo atendente encerrado para {phone}")
