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
    Handler para criacao de area de tratamento de um servico.

    POST /services/{serviceId}/areas
    Body esperado:
    {
        "name": "Pernas",
        "display_order": 1   (opcional, default 0)
    }

    Aceita tambem um array para criacao em lote:
    [
        {"name": "Pernas", "display_order": 1},
        {"name": "Axilas", "display_order": 2}
    ]
    """
    try:
        logger.info(f"Requisicao recebida para criacao de area: {json.dumps(event)}")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisicao vazio ou invalido"
            })

        service_id = extract_path_param(event, "serviceId")
        if not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "serviceId nao fornecido no path"
            })

        db = PostgresService()

        # Verify service exists
        svc_check = db.execute_query(
            "SELECT 1 FROM scheduler.services WHERE id = %s::uuid",
            (service_id,)
        )
        if not svc_check:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Servico nao encontrado: {service_id}"
            })

        # Support batch creation
        items = body if isinstance(body, list) else [body]
        created = []

        for item in items:
            name = item.get("name")
            if not name:
                return http_response(400, {
                    "status": "ERROR",
                    "message": "Campo obrigatorio: name"
                })

            result = db.execute_write_returning(
                """
                INSERT INTO scheduler.service_areas (id, service_id, name, display_order)
                VALUES (gen_random_uuid(), %s::uuid, %s, %s)
                RETURNING *
                """,
                (service_id, name, item.get("display_order", 0)),
            )

            if result:
                created.append(_serialize_row(result))

        logger.info(f"{len(created)} area(s) criada(s) para servico {service_id}")

        return http_response(201, {
            "status": "SUCCESS",
            "message": f"{len(created)} area(s) criada(s) com sucesso",
            "areas": created
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao criar area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
