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
    Handler para associar areas a um servico.

    POST /services/{serviceId}/areas
    Body esperado:
    {
        "area_id": "uuid-da-area"
    }

    Aceita tambem um array para associacao em lote:
    [
        {"area_id": "uuid-1"},
        {"area_id": "uuid-2"}
    ]

    Ou formato simplificado com array de IDs:
    {
        "area_ids": ["uuid-1", "uuid-2"]
    }
    """
    try:
        logger.info(f"Requisicao recebida para associacao de area: {json.dumps(event)}")

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

        # Support multiple formats:
        # 1. {"area_ids": ["uuid-1", "uuid-2"]}
        # 2. [{"area_id": "uuid-1"}, {"area_id": "uuid-2"}]
        # 3. {"area_id": "uuid-1"}
        area_ids = []
        if isinstance(body, list):
            for item in body:
                aid = item.get("area_id")
                if aid:
                    area_ids.append(aid)
        elif "area_ids" in body:
            area_ids = body["area_ids"]
        elif "area_id" in body:
            area_ids = [body["area_id"]]

        if not area_ids:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campo obrigatorio: area_id ou area_ids"
            })

        created = []

        for area_id in area_ids:
            # Verify area exists
            area_check = db.execute_query(
                "SELECT 1 FROM scheduler.areas WHERE id = %s::uuid AND active = TRUE",
                (area_id,)
            )
            if not area_check:
                return http_response(404, {
                    "status": "ERROR",
                    "message": f"Area nao encontrada: {area_id}"
                })

            result = db.execute_write_returning(
                """
                INSERT INTO scheduler.service_areas (id, service_id, area_id)
                VALUES (gen_random_uuid(), %s::uuid, %s::uuid)
                ON CONFLICT (service_id, area_id) DO UPDATE SET active = TRUE
                RETURNING *
                """,
                (service_id, area_id),
            )

            if result:
                created.append(_serialize_row(result))

        logger.info(f"{len(created)} associacao(oes) criada(s) para servico {service_id}")

        return http_response(201, {
            "status": "SUCCESS",
            "message": f"{len(created)} associacao(oes) criada(s) com sucesso",
            "service_areas": created
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao associar area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
