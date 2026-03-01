"""
Lambda handler to list leads for a clinic.

GET /clinics/{clinicId}/leads?startDate=&endDate=&booked=true&limit=50&offset=0
"""
import logging
from datetime import datetime, date, time
from decimal import Decimal

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.lead_service import LeadService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def handler(event, context):
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e obrigatorio"})

        start_date = extract_query_param(event, "startDate")
        end_date = extract_query_param(event, "endDate")
        booked_param = extract_query_param(event, "booked")
        limit = int(extract_query_param(event, "limit") or "50")
        offset = int(extract_query_param(event, "offset") or "0")

        booked = None
        if booked_param is not None:
            booked = booked_param.lower() in ("true", "1", "yes")

        db = PostgresService()
        lead_service = LeadService(db)
        leads = lead_service.list_leads(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            booked=booked,
            limit=limit,
            offset=offset,
        )

        return http_response(200, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "leads": [_serialize_row(r) for r in leads],
            "total": len(leads),
        })

    except Exception as e:
        logger.error(f"Erro ao listar leads: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
