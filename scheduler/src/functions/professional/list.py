import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param
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
    Handler para listagem de profissionais de uma clinica via API.

    GET /clinics/{clinicId}/professionals
    Retorna todos os profissionais ativos da clinica ordenados por nome.
    """
    try:
        logger.info(f"Requisicao recebida para listagem de profissionais: {json.dumps(event)}")

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

        logger.info(f"Listando profissionais da clinica: {clinic_id}")

        # 3. Buscar profissionais ativos da clinica
        db = PostgresService()

        query = """
            SELECT * FROM scheduler.professionals
            WHERE clinic_id = %s AND active = true
            ORDER BY name
        """

        rows = db.execute_query(query, (clinic_id,))

        # 4. Serializar campos datetime/date
        professionals = [_serialize_row(row) for row in rows]

        logger.info(f"Listagem concluida: {len(professionals)} profissional(is) encontrado(s)")

        # 5. Retornar resposta
        return http_response(200, {
            "status": "SUCCESS",
            "professionals": professionals
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao listar profissionais: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
