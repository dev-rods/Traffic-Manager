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
    Handler para exclusao (soft delete) de area via API.

    DELETE /areas/{areaId}
    Realiza soft delete, marcando active = FALSE.
    """
    try:
        logger.info(f"Requisicao recebida para exclusao de area: {json.dumps(event)}")

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

        logger.info(f"Excluindo area (soft delete): {area_id}")

        # 3. Executar soft delete
        db = PostgresService()

        query = """
            UPDATE scheduler.areas
            SET active = FALSE, updated_at = NOW()
            WHERE id = %s::uuid
            RETURNING *
        """

        result = db.execute_write_returning(query, (area_id,))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Area nao encontrada: {area_id}"
            })

        area = _serialize_row(result)

        logger.info(f"Area excluida com sucesso (soft delete): {area_id}")

        # 4. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "message": "Area excluida com sucesso",
            "area": area
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao excluir area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
