import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
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
    Handler para listagem de templates de mensagem via API.

    GET /clinics/{clinicId}/templates
    Query params opcionais:
        - template_key: filtra por template_key especifica
    """
    try:
        logger.info(f"Requisicao recebida para listagem de templates: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Extrair clinicId do path
        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        # 3. Verificar filtro opcional por template_key
        template_key = extract_query_param(event, "template_key")

        db = PostgresService()

        if template_key:
            query = """
                SELECT * FROM scheduler.message_templates
                WHERE clinic_id = %s AND template_key = %s AND active = true
                ORDER BY template_key
            """
            params = (clinic_id, template_key)
        else:
            query = """
                SELECT * FROM scheduler.message_templates
                WHERE clinic_id = %s AND active = true
                ORDER BY template_key
            """
            params = (clinic_id,)

        rows = db.execute_query(query, params)

        templates = [_serialize_row(row) for row in rows]

        logger.info(f"[clinicId: {clinic_id}] Listagem concluida: {len(templates)} template(s) encontrado(s)")

        # 4. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "data": templates
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao listar templates: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
