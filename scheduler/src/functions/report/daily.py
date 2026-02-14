import uuid
import logging
from datetime import datetime, timedelta
import pytz

from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker
from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Cron handler (EventBridge cron(0 23 * * ? *) = 23:00 UTC = 20:00 BRT).
    Sends daily report with next day's agenda to each active clinic.
    """
    trace_id = str(uuid.uuid4())[:8]
    logger.info(f"[traceId: {trace_id}] [DailyReport] Iniciando envio de relatorios diarios")

    db = PostgresService()
    tracker = MessageTracker()

    # Fetch all active clinics
    clinics = db.execute_query(
        "SELECT * FROM scheduler.clinics WHERE active = TRUE AND phone IS NOT NULL AND phone != ''"
    )

    reports_sent = 0
    reports_skipped = 0
    reports_failed = 0

    for clinic in clinics:
        clinic_id = clinic["clinic_id"]
        clinic_name = clinic.get("name", "")
        clinic_phone = clinic.get("phone", "")
        timezone_str = clinic.get("timezone", "America/Sao_Paulo")

        try:
            # Calculate tomorrow in clinic's timezone
            try:
                tz = pytz.timezone(timezone_str)
            except Exception:
                tz = pytz.timezone("America/Sao_Paulo")

            now_local = datetime.now(tz)
            tomorrow = (now_local + timedelta(days=1)).strftime("%Y-%m-%d")
            tomorrow_display = (now_local + timedelta(days=1)).strftime("%d/%m/%Y")

            # Fetch tomorrow's appointments
            appointments = db.execute_query(
                """
                SELECT
                    a.start_time, a.areas, a.status,
                    p.name as patient_name, p.phone as patient_phone,
                    s.name as service_name
                FROM scheduler.appointments a
                LEFT JOIN scheduler.patients p ON a.patient_id = p.id
                LEFT JOIN scheduler.services s ON a.service_id = s.id
                WHERE a.clinic_id = %s AND a.appointment_date = %s AND a.status = 'CONFIRMED'
                ORDER BY a.start_time ASC
                """,
                (clinic_id, tomorrow),
            )

            if not appointments:
                reports_skipped += 1
                logger.info(f"[traceId: {trace_id}] Clinica {clinic_id}: sem agendamentos para {tomorrow}, pulando")
                continue

            # Build report message
            lines = [f"Agenda de amanha ({tomorrow_display}):", ""]

            for appt in appointments:
                time_str = str(appt.get("start_time", ""))
                # Handle timedelta from PostgreSQL
                if hasattr(appt.get("start_time"), "total_seconds"):
                    total_secs = int(appt["start_time"].total_seconds())
                    h, m = total_secs // 3600, (total_secs % 3600) // 60
                    time_str = f"{h:02d}:{m:02d}"

                patient = appt.get("patient_name") or appt.get("patient_phone", "")
                service = appt.get("service_name", "")
                areas = appt.get("areas", "")

                parts = [time_str, patient]
                if service:
                    parts.append(service)
                if areas:
                    parts.append(areas)

                lines.append(" - ".join(parts))

            lines.append("")
            lines.append(f"Total: {len(appointments)} sessão(ões) agendada(s)")

            report_content = "\n".join(lines)

            # Send via provider
            provider = get_provider(clinic)
            msg_id = str(uuid.uuid4())
            conversation_id = f"{clinic_id}#REPORT"

            tracker.track_outbound(
                clinic_id=clinic_id,
                phone=clinic_phone,
                message_id=msg_id,
                conversation_id=conversation_id,
                message_type="TEXT",
                content=report_content,
                status="QUEUED",
                metadata={"reportType": "DAILY_AGENDA", "reportDate": tomorrow},
            )

            response = provider.send_text(clinic_phone, report_content)

            if response.success:
                tracker.track_outbound(
                    clinic_id=clinic_id,
                    phone=clinic_phone,
                    message_id=msg_id,
                    conversation_id=conversation_id,
                    message_type="TEXT",
                    content=report_content,
                    status="SENT",
                    provider_message_id=response.provider_message_id,
                    provider_response=response.raw_response,
                )
                reports_sent += 1
                logger.info(f"[traceId: {trace_id}] Relatorio enviado para {clinic_name} ({clinic_phone})")
            else:
                tracker.track_outbound(
                    clinic_id=clinic_id,
                    phone=clinic_phone,
                    message_id=msg_id,
                    conversation_id=conversation_id,
                    message_type="TEXT",
                    content=report_content,
                    status="FAILED",
                    metadata={"error": response.error},
                )
                reports_failed += 1
                logger.error(f"[traceId: {trace_id}] Falha ao enviar relatorio para {clinic_name}: {response.error}")

        except Exception as e:
            reports_failed += 1
            logger.error(f"[traceId: {trace_id}] Erro ao processar relatorio da clinica {clinic_id}: {e}")

    logger.info(
        f"[traceId: {trace_id}] [DailyReport] Concluido: "
        f"{reports_sent} enviados, {reports_skipped} pulados, {reports_failed} falhas"
    )

    return {"sent": reports_sent, "skipped": reports_skipped, "failed": reports_failed}
