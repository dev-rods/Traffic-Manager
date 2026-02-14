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
    Handler para criacao de profissional via API.

    POST /clinics/{clinicId}/professionals
    Body esperado:
    {
        "name": "Nome do Profissional",
        "role": "Fisioterapeuta"     (opcional)
    }
    """
    try:
        logger.info(f"Requisicao recebida para criacao de profissional: {json.dumps(event)}")

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

        if not name:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campo obrigatorio: name"
            })

        logger.info(f"Criando profissional para clinica: {clinic_id}")

        # 5. Inserir profissional no banco de dados
        db = PostgresService()

        query = """
            INSERT INTO scheduler.professionals (
                id, clinic_id, name, role
            ) VALUES (
                gen_random_uuid(), %s, %s, %s
            )
            RETURNING *
        """

        params = (
            clinic_id,
            name,
            body.get("role"),
        )

        result = db.execute_write_returning(query, params)

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Erro ao criar profissional"
            })

        professional = _serialize_row(result)

        logger.info(f"Profissional criado com sucesso: {professional.get('id')}")

        # 6. Retornar resposta
        return http_response(201, {
            "status": "SUCCESS",
            "message": "Profissional criado com sucesso",
            "professional": professional
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao criar profissional: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
