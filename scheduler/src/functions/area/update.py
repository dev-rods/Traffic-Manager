import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {
    "name",
    "display_order",
    "active",
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
    Handler para atualizacao de area via API.

    PUT /areas/{areaId}
    Body esperado (todos os campos sao opcionais):
    {
        "name": "...",
        "display_order": 1,
        "active": true/false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de area: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisição vazio ou inválido"
            })

        # 3. Extrair areaId do path
        area_id = extract_path_param(event, "areaId")
        if not area_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "areaId não fornecido no path"
            })

        logger.info(f"Atualizando area: {area_id}")

        # 4. Construir query dinamica apenas com campos fornecidos
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

        # Sempre atualizar updated_at
        set_clauses.append("updated_at = NOW()")

        # Adicionar areaId no final dos params para o WHERE
        params.append(area_id)

        query = f"""
            UPDATE scheduler.areas
            SET {', '.join(set_clauses)}
            WHERE id = %s::uuid
            RETURNING *
        """

        # 5. Executar atualizacao
        db = PostgresService()

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Area não encontrada: {area_id}"
            })

        area = _serialize_row(result)

        logger.info(f"Area atualizada com sucesso: {area_id}")

        # 6. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "message": "Area atualizada com sucesso",
            "area": area
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
