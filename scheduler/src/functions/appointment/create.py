import json
import logging
from datetime import datetime, date

from src.utils.http import parse_body, http_response, require_api_key
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, ConflictError, NotFoundError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def handler(event, context):
    """
    POST /appointments

    Body:
    {
        "clinicId": "laser-beauty-sp-abc123",
        "phone": "5511999999999",
        "serviceId": "uuid",
        "date": "2026-02-10",
        "time": "10:00",
        "areas": "Pernas e axilas",
        "professionalId": "uuid"  (opcional)
    }
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisicao vazio ou invalido"})

        clinic_id = body.get("clinicId")
        phone = body.get("phone")
        service_id = body.get("serviceId")
        appt_date = body.get("date")
        appt_time = body.get("time")

        if not all([clinic_id, phone, service_id, appt_date, appt_time]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: clinicId, phone, serviceId, date, time"
            })

        db = PostgresService()
        service = AppointmentService(db)

        result = service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=service_id,
            date=appt_date,
            time=appt_time,
            areas=body.get("areas", ""),
            professional_id=body.get("professionalId"),
        )

        appointment = _serialize_row(result)

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Agendamento criado com sucesso",
            "appointment": appointment,
        })

    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})

    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})

    except Exception as e:
        logger.error(f"Erro ao criar agendamento: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
