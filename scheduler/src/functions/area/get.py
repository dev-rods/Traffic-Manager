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
    Handler para busca de area por ID via API.

    GET /areas/{areaId}
    Retorna a area correspondente ao ID informado.
    """
    try:
        logger.info(f"Requisicao recebida para busca de area: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Extrair areaId do path
        area_id = extract_path_param(event, "areaId")
        if not area_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "areaId nao fornecido no path"
            })

        logger.info(f"Buscando area: {area_id}")

        # 3. Buscar area no banco de dados
        db = PostgresService()

        query = "SELECT * FROM scheduler.areas WHERE id = %s::uuid"

        rows = db.execute_query(query, (area_id,))

        if not rows:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Area nao encontrada: {area_id}"
            })

        area = _serialize_row(rows[0])

        logger.info(f"Area encontrada: {area_id}")

        # 4. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "area": area
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao buscar area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
