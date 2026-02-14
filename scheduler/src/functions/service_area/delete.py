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
    Handler para remover associacao entre servico e area (soft delete).

    DELETE /services/{serviceId}/areas/{areaId}
    """
    try:
        logger.info(f"Requisicao recebida para remocao de associacao: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        service_id = extract_path_param(event, "serviceId")
        if not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "serviceId nao fornecido no path"
            })

        area_id = extract_path_param(event, "areaId")
        if not area_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "areaId nao fornecido no path"
            })

        db = PostgresService()

        result = db.execute_write_returning(
            """
            UPDATE scheduler.service_areas
            SET active = FALSE
            WHERE service_id = %s::uuid AND area_id = %s::uuid
            RETURNING *
            """,
            (service_id, area_id),
        )

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Associacao nao encontrada: servico {service_id}, area {area_id}"
            })

        logger.info(f"Associacao removida: servico {service_id}, area {area_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Associacao removida com sucesso",
            "service_area": _serialize_row(result)
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao remover associacao: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
