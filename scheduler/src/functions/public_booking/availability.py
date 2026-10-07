import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.availability_engine import AvailabilityEngine

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_DATES_PER_CALL = 31


def handler(event, context):
    """
    GET /public/clinics/{clinicId}/availability?dates=2026-09-14,2026-09-15&totalDuration=30

    Status por dia (CLOSED | FULL | AVAILABLE) + horários livres, para uma lista de
    datas — usado pelo seletor de semana do booking-site pra não oferecer dias sem
    agenda e pra distinguir "fechado" de "lotado". Reaproveita a mesma
    AvailabilityEngine do bot de WhatsApp (`get_days_status`).
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        dates_param = extract_query_param(event, "dates")
        total_duration_param = extract_query_param(event, "totalDuration")

        if not dates_param or not total_duration_param:
            return http_response(400, {
                "status": "ERROR",
                "message": "dates e totalDuration são obrigatórios",
            })

        dates = [d.strip() for d in dates_param.split(",") if d.strip()]
        if not dates:
            return http_response(400, {"status": "ERROR", "message": "dates vazio"})
        if len(dates) > MAX_DATES_PER_CALL:
            return http_response(400, {
                "status": "ERROR",
                "message": f"no máximo {MAX_DATES_PER_CALL} datas por chamada",
            })

        db = PostgresService()
        engine = AvailabilityEngine(db)
        days = engine.get_days_status(clinic_id, dates, int(total_duration_param))

        return http_response(200, {"status": "SUCCESS", "days": days})

    except Exception as e:
        logger.error(f"Erro ao buscar status dos dias: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": str(e)})
