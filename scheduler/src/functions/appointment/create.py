import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key
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
    POST /appointments

    Body:
    {
        "clinicId": "laser-beauty-sp-abc123",
        "phone": "5511999999999",
        "serviceId": "uuid",            // single service (backwards compat)
        "serviceIds": ["uuid", "uuid"],  // multiple services (preferred)
        "date": "2026-02-10",
        "time": "10:00",
        "serviceAreaPairs": [            // optional, for services with areas
            {"serviceId": "uuid", "areaId": "uuid"}
        ],
        "professionalId": "uuid"         // optional
    }
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        clinic_id = body.get("clinicId")
        phone = body.get("phone")
        service_id = body.get("serviceId")
        service_ids = body.get("serviceIds")
        appt_date = body.get("date")
        appt_time = body.get("time")

        # Accept either serviceId (string) or serviceIds (array)
        if not service_id and not service_ids:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: clinicId, phone, serviceId ou serviceIds, date, time"
            })

        if not all([clinic_id, phone, appt_date, appt_time]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: clinicId, phone, serviceId ou serviceIds, date, time"
            })

        # Normalize: if serviceIds provided, use it; otherwise wrap serviceId
        if not service_ids:
            service_ids = [service_id]
        if not service_id:
            service_id = service_ids[0]

        db = PostgresService()

        from src.services.sheets_sync import SheetsSync
        sheets_sync = SheetsSync(db)
        service = AppointmentService(db, sheets_sync=sheets_sync)

        # Parse serviceAreaPairs from body
        raw_pairs = body.get("serviceAreaPairs")
        service_area_pairs = None
        if raw_pairs and isinstance(raw_pairs, list):
            service_area_pairs = [
                {"service_id": p.get("serviceId"), "area_id": p.get("areaId")}
                for p in raw_pairs
                if p.get("serviceId") and p.get("areaId")
            ]

        result = service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=service_id,
            date=appt_date,
            time=appt_time,
            professional_id=body.get("professionalId"),
            service_ids=service_ids,
            service_area_pairs=service_area_pairs if service_area_pairs else None,
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
