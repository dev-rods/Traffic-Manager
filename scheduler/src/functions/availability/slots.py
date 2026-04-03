import json
import logging
from datetime import datetime, date

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.availability_engine import AvailabilityEngine

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    GET /clinics/{clinicId}/available-slots?date=YYYY-MM-DD&serviceId=UUID[&totalDuration=INT]

    Returns available time slots for a given clinic, date, and service.
    When totalDuration (minutes) is provided, uses it directly instead of
    looking up the service's default duration — useful when specific areas
    are selected and their summed duration differs from the base service.
    """
    try:
        api_key, error_response = require_api_key(event)
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
                "message": "date and serviceId query parameters are required"
            })

        logger.info(f"[clinicId: {clinic_id}] Getting available slots for date={date_param}, serviceId={service_id}, totalDuration={total_duration_param}")

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
        logger.error(f"Error getting available slots: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
