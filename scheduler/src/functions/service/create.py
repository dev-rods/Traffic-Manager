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
    Handler para criacao de servico via API.

    POST /clinics/{clinicId}/services
    Body esperado:
    {
        "name": "Nome do Servico",
        "duration_minutes": 60,
        "price_cents": 15000,       (opcional)
        "description": "..."        (opcional)
    }
    """
    try:
        logger.info(f"Requisicao recebida para criacao de servico: {json.dumps(event)}")

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

        # 3. Extrair clinicId do path
        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId não fornecido no path"
            })

        # 4. Validar campos obrigatorios
        name = body.get("name")
        duration_minutes = body.get("duration_minutes")

        if not name or duration_minutes is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: name, duration_minutes"
            })

        logger.info(f"Criando servico para clinica: {clinic_id}")

        # 5. Verificar se a clinica existe
        db = PostgresService()

        clinic_check = db.execute_query(
            "SELECT 1 FROM scheduler.clinics WHERE clinic_id = %s",
            (clinic_id,)
        )

        if not clinic_check:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Clinica não encontrada: {clinic_id}"
            })

        # 6. Inserir servico no banco de dados
        query = """
            INSERT INTO scheduler.services (
                id, clinic_id, name, duration_minutes, price_cents, description
            ) VALUES (
                gen_random_uuid(), %s, %s, %s, %s, %s
            )
            RETURNING *
        """

        params = (
            clinic_id,
            name,
            duration_minutes,
            body.get("price_cents"),
            body.get("description"),
        )

        result = db.execute_write_returning(query, params)

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Erro ao criar serviço"
            })

        service = _serialize_row(result)

        logger.info(f"Servico criado com sucesso: {service.get('id')}")

        # 7. Retornar resposta
        return http_response(201, {
            "status": "SUCCESS",
            "message": "Servico criado com sucesso",
            "service": service
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao criar servico: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
