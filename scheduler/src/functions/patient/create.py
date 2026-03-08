import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param, parse_body
from src.utils.phone import normalize_phone
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
    POST /clinics/{clinicId}/patients
    Cria um novo paciente.
    Body: { name, phone, gender? }
    """
    try:
        logger.info("Create patient request received")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId nao fornecido"
            })

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Body vazio ou invalido"
            })

        name = body.get("name", "").strip()
        phone = body.get("phone", "").strip()
        gender = body.get("gender")

        if not name:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nome e obrigatorio"
            })

        if not phone:
            return http_response(400, {
                "status": "ERROR",
                "message": "Telefone e obrigatorio"
            })

        phone = normalize_phone(phone)

        if gender and gender not in ("M", "F"):
            return http_response(400, {
                "status": "ERROR",
                "message": "Genero deve ser M ou F"
            })

        db = PostgresService()

        # Check if phone already exists for this clinic
        existing = db.execute_query(
            "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )
        if existing:
            return http_response(409, {
                "status": "ERROR",
                "message": "Ja existe um paciente com esse telefone"
            })

        result = db.execute_write_returning("""
            INSERT INTO scheduler.patients (clinic_id, name, phone, gender, created_at, updated_at)
            VALUES (%s, %s, %s, %s, NOW(), NOW())
            RETURNING *
        """, (clinic_id, name, phone, gender))

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Falha ao criar paciente"
            })

        patient = _serialize_row(result)
        logger.info(f"Patient created: {patient['id']} for clinic {clinic_id}")

        return http_response(201, {
            "status": "SUCCESS",
            "patient": patient,
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error creating patient: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": error_msg,
        })
