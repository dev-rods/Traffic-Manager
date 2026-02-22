import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

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
    Handler para busca de discount rules por clinicId via API.

    GET /clinics/{clinicId}/discount-rules
    Retorna as discount rules da clinica.
    """
    try:
        logger.info(f"Requisicao recebida para busca de discount rules: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        logger.info(f"Buscando discount rules para clinica: {clinic_id}")

        db = PostgresService()

        rows = db.execute_query(
            "SELECT * FROM scheduler.discount_rules WHERE clinic_id = %s",
            (clinic_id,),
        )

        if not rows:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Discount rules não encontradas para clinica: {clinic_id}"
            })

        logger.info(f"Discount rules encontradas para clinica: {clinic_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "discount_rules": _serialize_row(rows[0])
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao buscar discount rules: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
