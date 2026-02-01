import json
import logging
import uuid
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key
from src.utils.auth import SchedulerAuth
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
    Handler para criacao de clinica via API.

    POST /clinics
    Body esperado:
    {
        "name": "Nome da Clinica",
        "business_hours": {"mon": {"start": "08:00", "end": "18:00"}, ...},
        "phone": "...",              (opcional)
        "address": "...",            (opcional)
        "timezone": "...",           (opcional)
        "buffer_minutes": 15,        (opcional)
        "welcome_message": "...",    (opcional)
        "pre_session_instructions": "...", (opcional)
        "zapi_instance_id": "...",   (opcional)
        "zapi_instance_token": "...", (opcional)
        "google_spreadsheet_id": "...", (opcional)
        "google_sheet_name": "..."   (opcional)
    }
    """
    try:
        logger.info(f"Requisicao recebida para criacao de clinica: {json.dumps(event)}")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body e validar campos obrigatorios
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisicao vazio ou invalido"
            })

        name = body.get("name")
        business_hours = body.get("business_hours")

        if not name or not business_hours:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: name, business_hours"
            })

        # 3. Gerar clinic_id
        clinic_id = SchedulerAuth.generate_clinic_id(name)

        logger.info(f"Criando clinica com ID: {clinic_id}")

        # 4. Inserir no banco de dados
        db = PostgresService()

        query = """
            INSERT INTO scheduler.clinics (
                clinic_id, name, phone, address, timezone,
                business_hours, buffer_minutes, welcome_message,
                pre_session_instructions, zapi_instance_id,
                zapi_instance_token, google_spreadsheet_id,
                google_sheet_name, active, created_at, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s,
                %s, %s, NOW(), NOW()
            )
            RETURNING *
        """

        from psycopg2.extras import Json

        params = (
            clinic_id,
            name,
            body.get("phone"),
            body.get("address"),
            body.get("timezone", "America/Sao_Paulo"),
            Json(business_hours),
            body.get("buffer_minutes", 15),
            body.get("welcome_message"),
            body.get("pre_session_instructions"),
            body.get("zapi_instance_id"),
            body.get("zapi_instance_token"),
            body.get("google_spreadsheet_id"),
            body.get("google_sheet_name"),
            True,
        )

        result = db.execute_write_returning(query, params)

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Erro ao criar clinica"
            })

        clinic = _serialize_row(result)

        logger.info(f"Clinica criada com sucesso: {clinic_id}")

        # 5. Retornar resposta
        return http_response(201, {
            "status": "SUCCESS",
            "message": "Clinica criada com sucesso",
            "clinicId": clinic_id,
            "clinic": clinic
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao criar clinica: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg
        })
