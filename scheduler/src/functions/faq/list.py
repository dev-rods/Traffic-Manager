import json
import logging
from datetime import datetime, date

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
    Handler para listagem de itens de FAQ via API.

    GET /clinics/{clinicId}/faq
    Retorna todos os itens de FAQ ativos ordenados por display_order.
    """
    try:
        logger.info(f"Requisicao recebida para listagem de FAQ: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Extrair clinicId do path
        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId nao fornecido no path"
            })

        # 3. Buscar FAQ items ativos
        db = PostgresService()

        query = """
            SELECT * FROM scheduler.faq_items
            WHERE clinic_id = %s AND active = true
            ORDER BY display_order
        """

        rows = db.execute_query(query, (clinic_id,))

        faq_items = [_serialize_row(row) for row in rows]

        logger.info(f"[clinicId: {clinic_id}] Listagem concluida: {len(faq_items)} FAQ item(s) encontrado(s)")

        # 4. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "data": faq_items
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao listar FAQ: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
