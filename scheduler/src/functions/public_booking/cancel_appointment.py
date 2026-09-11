import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.booking_verification import verify_token
from src.utils.phone import normalize_phone
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, NotFoundError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/appointments/{appointmentId}/cancel
    Body: { "phone": "string", "token": "string" }

    Cancela um agendamento pelo próprio cliente. Confirma que o agendamento
    pertence ao telefone verificado antes de cancelar — evita que alguém
    cancele o horário de outra pessoa.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        appointment_id = extract_path_param(event, "appointmentId")
        if not clinic_id or not appointment_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e appointmentId são obrigatórios no path"})

        body = parse_body(event) or {}
        phone = body.get("phone")
        token = body.get("token")
        if not phone or not token:
            return http_response(400, {"status": "ERROR", "message": "phone e token são obrigatórios"})

        if not verify_token(clinic_id, phone, token):
            return http_response(401, {"status": "ERROR", "message": "Verificação por WhatsApp expirada. Confirme o código novamente."})

        db = PostgresService()

        owned = db.execute_query(
            """
            SELECT a.id FROM scheduler.appointments a
            JOIN scheduler.patients p ON p.id = a.patient_id
            WHERE a.id = %s::uuid AND a.clinic_id = %s AND p.phone = %s AND a.status = 'CONFIRMED'
            """,
            (appointment_id, clinic_id, normalize_phone(phone)),
        )
        if not owned:
            return http_response(404, {"status": "ERROR", "message": "Agendamento não encontrado para este telefone"})

        service = AppointmentService(db)
        result = service.cancel_appointment(appointment_id)

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Agendamento cancelado com sucesso",
            "appointment": _serialize_row(result),
        })

    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao cancelar agendamento público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
