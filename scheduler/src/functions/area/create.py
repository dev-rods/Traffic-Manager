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
    Handler para criacao de area via API.

    POST /clinics/{clinicId}/areas
    Body esperado:
    {
        "name": "Pernas",
        "display_order": 1       (opcional)
    }
    Tambem aceita array para criacao em lote.
    """
    try:
        logger.info(f"Requisicao recebida para criacao de area: {json.dumps(event)}")

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

        logger.info(f"Criando area(s) para clinica: {clinic_id}")

        # 4. Verificar se a clinica existe
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

        # 5. Suportar batch (array) ou objeto unico
        items = body if isinstance(body, list) else [body]

        created_areas = []
        for item in items:
            name = item.get("name")
            if not name:
                return http_response(400, {
                    "status": "ERROR",
                    "message": "Campo obrigatorio: name"
                })

            display_order = item.get("display_order", 0)

            # 6. Inserir area no banco de dados
            query = """
                INSERT INTO scheduler.areas (
                    id, clinic_id, name, display_order
                ) VALUES (
                    gen_random_uuid(), %s, %s, %s
                )
                RETURNING *
            """

            params = (
                clinic_id,
                name,
                display_order,
            )

            result = db.execute_write_returning(query, params)

            if not result:
                return http_response(500, {
                    "status": "ERROR",
                    "message": f"Erro ao criar area: {name}"
                })

            created_areas.append(_serialize_row(result))

        logger.info(f"Area(s) criada(s) com sucesso: {len(created_areas)}")

        # 7. Retornar resposta
        return http_response(201, {
            "status": "SUCCESS",
            "message": f"{len(created_areas)} area(s) criada(s) com sucesso",
            "areas": created_areas
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao criar area: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
