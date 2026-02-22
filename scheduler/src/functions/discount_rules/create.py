import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
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
    Handler para criacao/upsert de discount rules via API.

    POST /clinics/{clinicId}/discount-rules
    Body esperado:
    {
        "first_session_discount_pct": 20,
        "tier_2_min_areas": 2,
        "tier_2_max_areas": 4,
        "tier_2_discount_pct": 10,
        "tier_3_min_areas": 5,
        "tier_3_discount_pct": 15
    }
    """
    try:
        logger.info(f"Requisicao recebida para criacao de discount rules: {json.dumps(event)}")

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

        logger.info(f"Criando discount rules para clinica: {clinic_id}")

        db = PostgresService()

        clinic_check = db.execute_query(
            "SELECT 1 FROM scheduler.clinics WHERE clinic_id = %s",
            (clinic_id,)
        )
        if not clinic_check:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Clinica não encontrada: {clinic_id}"
            })

        first_session_pct = body.get("first_session_discount_pct", 0)
        t2_min = body.get("tier_2_min_areas", 2)
        t2_max = body.get("tier_2_max_areas", 4)
        t2_pct = body.get("tier_2_discount_pct", 0)
        t3_min = body.get("tier_3_min_areas", 5)
        t3_pct = body.get("tier_3_discount_pct", 0)

        result = db.execute_write_returning(
            """
            INSERT INTO scheduler.discount_rules (
                clinic_id, first_session_discount_pct,
                tier_2_min_areas, tier_2_max_areas, tier_2_discount_pct,
                tier_3_min_areas, tier_3_discount_pct
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (clinic_id) DO UPDATE SET
                first_session_discount_pct = EXCLUDED.first_session_discount_pct,
                tier_2_min_areas = EXCLUDED.tier_2_min_areas,
                tier_2_max_areas = EXCLUDED.tier_2_max_areas,
                tier_2_discount_pct = EXCLUDED.tier_2_discount_pct,
                tier_3_min_areas = EXCLUDED.tier_3_min_areas,
                tier_3_discount_pct = EXCLUDED.tier_3_discount_pct,
                updated_at = NOW()
            RETURNING *
            """,
            (clinic_id, first_session_pct, t2_min, t2_max, t2_pct, t3_min, t3_pct),
        )

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Erro ao criar discount rules"
            })

        logger.info(f"Discount rules criadas/atualizadas para clinica: {clinic_id}")

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Discount rules criadas com sucesso",
            "discount_rules": _serialize_row(result)
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao criar discount rules: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
