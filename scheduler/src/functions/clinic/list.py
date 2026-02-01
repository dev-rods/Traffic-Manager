import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key
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
    Handler para listagem de clinicas via API.

    GET /clinics
    Retorna todas as clinicas ativas ordenadas por data de criacao (mais recente primeiro).
    """
    try:
        logger.info(f"Requisicao recebida para listagem de clinicas: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Buscar clinicas ativas
        db = PostgresService()

        query = """
            SELECT * FROM scheduler.clinics
            WHERE active = true
            ORDER BY created_at DESC
        """

        rows = db.execute_query(query)

        # 3. Serializar campos datetime/date
        clinics = [_serialize_row(row) for row in rows]

        logger.info(f"Listagem concluida: {len(clinics)} clinica(s) encontrada(s)")

        # 4. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "clinics": clinics
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao listar clinicas: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
