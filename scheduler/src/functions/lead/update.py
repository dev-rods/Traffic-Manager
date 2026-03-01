"""
Lambda handler to manually update a lead.

PUT /leads/{leadId}
Body: { "booked": true, "first_appointment_value": 150.00, "name": "...", "email": "...", "gclid": "..." }
"""
import logging
from datetime import datetime, date, time
from decimal import Decimal

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
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

        lead_id = extract_path_param(event, "leadId")
        if not lead_id:
            return http_response(400, {"status": "ERROR", "message": "leadId e obrigatorio"})

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Request body e obrigatorio"})

        db = PostgresService()
        lead_service = LeadService(db)

        result = lead_service.update_lead(
            lead_id=lead_id,
            booked=body.get("booked"),
            first_appointment_value=body.get("first_appointment_value"),
            name=body.get("name"),
            email=body.get("email"),
            gclid=body.get("gclid"),
        )

        if not result:
            return http_response(404, {"status": "ERROR", "message": "Lead nao encontrado"})

        return http_response(200, {
            "status": "SUCCESS",
            "lead": _serialize_row(result),
        })

    except Exception as e:
        logger.error(f"Erro ao atualizar lead: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
