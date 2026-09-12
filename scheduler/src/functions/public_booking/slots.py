import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.availability_engine import AvailabilityEngine

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    GET /public/clinics/{clinicId}/available-slots?date=YYYY-MM-DD&serviceId=UUID[&totalDuration=INT]

    Espelha o endpoint autenticado clinics/{clinicId}/available-slots, sem exigir
    o x-api-key do painel — usa a mesma AvailabilityEngine (clinic-wide).
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId is required"})

        date_param = extract_query_param(event, "date")
        service_id = extract_query_param(event, "serviceId")
        total_duration_param = extract_query_param(event, "totalDuration")

        if not date_param or not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "date and serviceId query parameters are required",
            })

        db = PostgresService()
        engine = AvailabilityEngine(db)

        if total_duration_param:
            slots = engine.get_available_slots_multi(clinic_id, date_param, int(total_duration_param))
        else:
            slots = engine.get_available_slots(clinic_id, date_param, service_id)

        return http_response(200, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "date": date_param,
            "serviceId": service_id,
            "slots": slots,
            "totalSlots": len(slots),
        })

    except Exception as e:
        logger.error(f"Erro ao buscar horários públicos: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": str(e)})
