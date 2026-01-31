import json
import logging
from datetime import datetime, date

from psycopg2.extras import Json

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ALLOWED_FIELDS = {"content", "buttons", "active"}
JSONB_FIELDS = {"buttons"}


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def handler(event, context):
    """
    Handler para atualizacao de template de mensagem via API.

    PUT /templates/{templateId}
    Body esperado (todos os campos sao opcionais):
    {
        "content": "Novo conteudo do template",
        "buttons": [{"id": "1", "label": "Agendar"}],
        "active": true/false
    }
    """
    try:
        logger.info(f"Requisicao recebida para atualizacao de template: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body e extrair templateId do path
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisicao vazio ou invalido"
            })

        template_id = extract_path_param(event, "templateId")
        if not template_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "templateId nao fornecido no path"
            })

        logger.info(f"Atualizando template: {template_id}")

        # 3. Construir query dinamica apenas com campos fornecidos
        set_clauses = []
        params = []

        for field in ALLOWED_FIELDS:
            if field in body:
                value = body[field]
                if field in JSONB_FIELDS:
                    value = Json(value)
                set_clauses.append(f"{field} = %s")
                params.append(value)

        if not set_clauses:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo valido fornecido para atualizacao"
            })

        # Sempre atualizar updated_at
        set_clauses.append("updated_at = NOW()")

        # Adicionar templateId no final dos params para o WHERE
        params.append(template_id)

        query = f"""
            UPDATE scheduler.message_templates
            SET {', '.join(set_clauses)}
            WHERE id = %s::uuid
            RETURNING *
        """

        # 4. Executar atualizacao
        db = PostgresService()

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Template nao encontrado: {template_id}"
            })

        template = _serialize_row(result)

        logger.info(f"Template atualizado com sucesso: {template_id}")

        # 5. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "message": "Template atualizado com sucesso",
            "data": template
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao atualizar template: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
