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
    Handler para atualizar uma associacao servico-area.

    PUT /services/{serviceId}/areas/{areaId}
    Body esperado:
    {
        "duration_minutes": 30   // null to clear override
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de service_area: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisição vazio ou inválido"
            })

        service_id = extract_path_param(event, "serviceId")
        if not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "serviceId não fornecido no path"
            })

        area_id = extract_path_param(event, "areaId")
        if not area_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "areaId não fornecido no path"
            })

        db = PostgresService()

        # Build SET clause dynamically
        updates = []
        params = []

        if "duration_minutes" in body:
            updates.append("duration_minutes = %s")
            params.append(body["duration_minutes"])  # can be None to clear

        if "price_cents" in body:
            updates.append("price_cents = %s")
            params.append(body["price_cents"])  # can be None to clear

        if "pre_session_instructions" in body:
            updates.append("pre_session_instructions = %s")
            params.append(body["pre_session_instructions"])  # can be None to clear

        if not updates:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo para atualizar. Campos aceitos: duration_minutes, price_cents, pre_session_instructions"
            })

        params.extend([service_id, area_id])
        set_clause = ", ".join(updates)

        result = db.execute_write_returning(
            f"""
            UPDATE scheduler.service_areas
            SET {set_clause}
            WHERE service_id = %s::uuid AND area_id = %s::uuid AND active = TRUE
            RETURNING *
            """,
            tuple(params),
        )

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Associação não encontrada: serviço {service_id}, área {area_id}"
            })

        logger.info(f"Service_area atualizada: servico {service_id}, area {area_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Associação atualizada com sucesso",
            "service_area": _serialize_row(result)
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar service_area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
