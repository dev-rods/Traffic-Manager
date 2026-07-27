"""
Lambda handler to create/capture a lead (landing page or external form).

POST /leads
Body: {
    "clinicId": "string (required)",
    "phone": "string (required)",
    "name": "string (required)",
    "email": "string (optional)",
    "gclid": "string (optional, Google Click Identifier from the ad URL)",
    "source": "string (optional, default: 'landing-page')",
    "metadata": {} (optional)
}
"""
import logging
from datetime import datetime, date, time
from decimal import Decimal

from src.utils.http import http_response, require_api_key, parse_body
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
        body = parse_body(event)

        api_key, error_response = require_api_key(event, body)
        if error_response:
            return error_response

        if not body:
            return http_response(400, {"status": "ERROR", "message": "Request body e obrigatorio"})

        missing = [f for f in ("clinicId", "phone", "name") if not body.get(f)]
        if missing:
            return http_response(400, {
                "status": "ERROR",
                "message": f"Campos obrigatorios ausentes: {', '.join(missing)}",
            })

        db = PostgresService()
        lead_service = LeadService(db)
        lead = lead_service.upsert_lead(
            clinic_id=body["clinicId"],
            phone=body["phone"],
            source=body.get("source", "landing-page"),
            name=body["name"],
            email=body.get("email"),
            gclid=body.get("gclid"),
            metadata=body.get("metadata"),
        )

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Lead registrado com sucesso",
            "lead": _serialize_row(lead) if lead else None,
        })

    except Exception as e:
        logger.error(f"Erro ao criar lead: {e}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
