import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {
    "name",
    "duration_minutes",
    "price_cents",
    "description",
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
    Handler para atualizacao de servico via API.

    PUT /services/{serviceId}
    Body esperado (todos os campos sao opcionais):
    {
        "name": "...",
        "duration_minutes": 60,
        "price_cents": 15000,
        "description": "...",
        "active": true/false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de servico: {json.dumps(event)}")

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

        # 3. Extrair serviceId do path
        service_id = extract_path_param(event, "serviceId")
        if not service_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "serviceId não fornecido no path"
            })

        logger.info(f"Atualizando servico: {service_id}")

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

        # Adicionar serviceId no final dos params para o WHERE
        params.append(service_id)

        query = f"""
            UPDATE scheduler.services
            SET {', '.join(set_clauses)}
            WHERE id = %s
            RETURNING *
        """

        # 5. Executar atualizacao
        db = PostgresService()

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Servico não encontrado: {service_id}"
            })

        service = _serialize_row(result)

        logger.info(f"Servico atualizado com sucesso: {service_id}")

        # 6. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "message": "Servico atualizado com sucesso",
            "service": service
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar servico: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
