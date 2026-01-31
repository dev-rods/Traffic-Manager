import uuid
import logging
from datetime import datetime

from src.services.db.postgres import PostgresService
from src.services.reminder_service import ReminderService
from src.services.template_service import TemplateService
from src.services.message_tracker import MessageTracker
from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Cron handler (EventBridge rate(15 minutes)).
    Processes pending reminders and sends WhatsApp messages.
    """
    trace_id = str(uuid.uuid4())[:8]
    logger.info(f"[traceId: {trace_id}] [ReminderProcessor] Iniciando processamento de lembretes")

    reminder_service = ReminderService()
    tracker = MessageTracker()
    db = PostgresService()
    template_service = TemplateService(db)

    now_iso = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    reminders = reminder_service.get_pending_reminders(now_iso)

    sent = 0
    failed = 0
    processed = len(reminders)

    # Cache clinics to avoid repeated DB lookups
    clinic_cache = {}

    for reminder in reminders:
        reminder_id = reminder.get("reminderId", "")
        clinic_id = reminder.get("clinicId", "")
        phone = reminder.get("phoneNumber", "")
        patient_name = reminder.get("patientName", "")
        appointment_time = reminder.get("appointmentTime", "")
        pk = reminder.get("pk", "")
        sk = reminder.get("sk", "")

        try:
            # Fetch clinic (cached)
            if clinic_id not in clinic_cache:
                clinics = db.execute_query(
                    "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                    (clinic_id,),
                )
                clinic_cache[clinic_id] = clinics[0] if clinics else None

            clinic = clinic_cache[clinic_id]
            if not clinic:
                logger.warning(f"[traceId: {trace_id}] Clinica {clinic_id} nao encontrada, pulando lembrete {reminder_id}")
                reminder_service.mark_failed(reminder_id, pk, sk, "Clinica nao encontrada")
                failed += 1
                continue

            # Render reminder message
            clinic_name = clinic.get("name", "")
            content = template_service.get_and_render(
                clinic_id,
                "REMINDER_24H",
                {"time": appointment_time, "clinic_name": clinic_name, "patient_name": patient_name},
            )

            # Send via provider
            provider = get_provider(clinic)
            msg_id = str(uuid.uuid4())
            conversation_id = f"{clinic_id}#{phone}"

            tracker.track_outbound(
                clinic_id=clinic_id,
                phone=phone,
                message_id=msg_id,
                conversation_id=conversation_id,
                message_type="TEXT",
                content=content,
                status="QUEUED",
                metadata={"reminderType": "REMINDER_24H", "reminderId": reminder_id},
            )

            response = provider.send_text(phone, content)

            if response.success:
                tracker.track_outbound(
                    clinic_id=clinic_id,
                    phone=phone,
                    message_id=msg_id,
                    conversation_id=conversation_id,
                    message_type="TEXT",
                    content=content,
                    status="SENT",
                    provider_message_id=response.provider_message_id,
                    provider_response=response.raw_response,
                )
                reminder_service.mark_sent(reminder_id, pk, sk)
                sent += 1
                logger.info(f"[traceId: {trace_id}] Lembrete {reminder_id} enviado para {phone}")
            else:
                tracker.track_outbound(
                    clinic_id=clinic_id,
                    phone=phone,
                    message_id=msg_id,
                    conversation_id=conversation_id,
                    message_type="TEXT",
                    content=content,
                    status="FAILED",
                    metadata={"error": response.error},
                )
                reminder_service.mark_failed(reminder_id, pk, sk, response.error or "Erro desconhecido")
                failed += 1
                logger.error(f"[traceId: {trace_id}] Falha ao enviar lembrete {reminder_id}: {response.error}")

        except Exception as e:
            logger.error(f"[traceId: {trace_id}] Erro ao processar lembrete {reminder_id}: {e}")
            reminder_service.mark_failed(reminder_id, pk, sk, str(e))
            failed += 1

    logger.info(
        f"[traceId: {trace_id}] [ReminderProcessor] Processamento concluido: "
        f"{processed} processados, {sent} enviados, {failed} falhas"
    )

    return {"processed": processed, "sent": sent, "failed": failed}
