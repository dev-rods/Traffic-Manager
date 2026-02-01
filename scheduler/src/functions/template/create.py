import json
import logging
from datetime import datetime, date, time

from psycopg2.extras import Json

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
    Handler para criacao de template de mensagem via API.

    POST /clinics/{clinicId}/templates
    Body esperado:
    {
        "template_key": "WELCOME",
        "content": "Ola! Bem-vindo a {{clinic_name}}.",
        "buttons": [{"id": "1", "label": "Agendar"}]  (opcional)
    }
    """
    try:
        logger.info(f"Requisicao recebida para criacao de template: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body e extrair clinicId do path
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisicao vazio ou invalido"
            })

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId nao fornecido no path"
            })

        # 3. Validar campos obrigatorios
        template_key = body.get("template_key")
        content = body.get("content")

        if not template_key or not content:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: template_key, content"
            })

        buttons = body.get("buttons")

        logger.info(f"[clinicId: {clinic_id}] Criando template: {template_key}")

        # 4. Inserir no banco de dados
        db = PostgresService()

        query = """
            INSERT INTO scheduler.message_templates (
                id, clinic_id, template_key, content, buttons
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s
            )
            RETURNING *
        """

        params = (
            clinic_id,
            template_key,
            content,
            Json(buttons) if buttons else None,
        )

        result = db.execute_write_returning(query, params)

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Erro ao criar template"
            })

        template = _serialize_row(result)

        logger.info(f"[clinicId: {clinic_id}] Template criado com sucesso: {template_key}")

        # 5. Retornar resposta
        return http_response(201, {
            "status": "SUCCESS",
            "message": "Template criado com sucesso",
            "data": template
        })

    except Exception as e:
        error_msg = str(e)

        # Handle unique constraint violation (clinic_id, template_key)
        if "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
            logger.warning(f"[clinicId: {clinic_id}] Template duplicado: {body.get('template_key')}")
            return http_response(409, {
                "status": "ERROR",
                "message": "Ja existe um template com essa template_key para esta clinica"
            })

        logger.error(f"Erro ao criar template: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
