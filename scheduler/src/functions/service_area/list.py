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
    Handler para listagem de areas associadas a um servico.

    GET /services/{serviceId}/areas
    Retorna todas as areas ativas do servico com JOIN na tabela areas.
    """
    try:
        logger.info(f"Requisicao recebida para listagem de areas: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        service_id = extract_path_param(event, "serviceId")
        if not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "serviceId não fornecido no path"
            })

        db = PostgresService()

        rows = db.execute_query(
            """
            SELECT sa.id as service_area_id, sa.service_id, sa.area_id,
                   a.name, a.display_order, a.active as area_active,
                   sa.duration_minutes,
                   s.duration_minutes as service_duration_minutes,
                   COALESCE(sa.duration_minutes, s.duration_minutes) as effective_duration_minutes,
                   sa.pre_session_instructions,
                   sa.active, sa.created_at
            FROM scheduler.service_areas sa
            JOIN scheduler.areas a ON sa.area_id = a.id
            JOIN scheduler.services s ON sa.service_id = s.id
            WHERE sa.service_id = %s::uuid
            AND sa.active = TRUE AND a.active = TRUE
            ORDER BY a.display_order, a.name
            """,
            (service_id,),
        )

        areas = [_serialize_row(row) for row in rows]

        logger.info(f"Listagem concluida: {len(areas)} area(s) encontrada(s)")

        return http_response(200, {
            "status": "SUCCESS",
            "areas": areas
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao listar areas: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
