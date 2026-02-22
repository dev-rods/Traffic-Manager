import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {
    "first_session_discount_pct",
    "tier_2_min_areas",
    "tier_2_max_areas",
    "tier_2_discount_pct",
    "tier_3_min_areas",
    "tier_3_discount_pct",
    "is_active",
}


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
    Handler para atualizacao de discount rules via API.

    PUT /clinics/{clinicId}/discount-rules
    Body esperado (todos os campos sao opcionais):
    {
        "first_session_discount_pct": 25,
        "tier_2_discount_pct": 12,
        "is_active": false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de discount rules: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisição vazio ou inválido"
            })

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        logger.info(f"Atualizando discount rules para clinica: {clinic_id}")

        set_clauses = []
        params = []

        for field in ALLOWED_FIELDS:
            if field in body:
                set_clauses.append(f"{field} = %s")
                params.append(body[field])

        if not set_clauses:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo válido fornecido para atualização"
            })

        set_clauses.append("updated_at = NOW()")
        params.append(clinic_id)

        query = f"""
            UPDATE scheduler.discount_rules
            SET {', '.join(set_clauses)}
            WHERE clinic_id = %s
            RETURNING *
        """

        db = PostgresService()

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Discount rules não encontradas para clinica: {clinic_id}"
            })

        logger.info(f"Discount rules atualizadas para clinica: {clinic_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Discount rules atualizadas com sucesso",
            "discount_rules": _serialize_row(result)
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar discount rules: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
