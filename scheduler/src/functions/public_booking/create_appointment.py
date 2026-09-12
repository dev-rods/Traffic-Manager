import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.booking_verification import verify_token
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, ConflictError, NotFoundError

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
    POST /public/clinics/{clinicId}/appointments

    Body:
    {
        "token": "string",           // emitido por /verify/confirm
        "phone": "string",
        "fullName": "string",
        "serviceIds": ["uuid", ...], // carrinho — 1+ serviços
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "professionalId": "uuid"     // opcional
    }
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        phone = body.get("phone")
        token = body.get("token")
        service_ids = body.get("serviceIds")
        appt_date = body.get("date")
        appt_time = body.get("time")
        full_name = body.get("fullName")

        if not all([phone, token, service_ids, appt_date, appt_time, full_name]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: phone, token, serviceIds, date, time, fullName",
            })

        if not verify_token(clinic_id, phone, token):
            return http_response(401, {"status": "ERROR", "message": "Verificação por WhatsApp expirada. Confirme o código novamente."})

        db = PostgresService()
        service = AppointmentService(db)

        result = service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=service_ids[0],
            date=appt_date,
            time=appt_time,
            professional_id=body.get("professionalId"),
            service_ids=service_ids,
            full_name=full_name,
        )

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Agendamento criado com sucesso",
            "appointment": _serialize_row(result),
        })

    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao criar agendamento público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
