import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param, parse_body
from src.utils.phone import normalize_phone
from src.services.db.postgres import PostgresService
from src.utils.cadastro import normaliza_cpf, normaliza_data_nascimento

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
        # Opcionais: o cadastro completo raramente existe no primeiro contato.
        # Vazio grava NULL - o campo fica visivelmente pendente na tela, em vez
        # de parecer preenchido com string vazia.
        cpf = normaliza_cpf(body.get("cpf"))
        birth_date = normaliza_data_nascimento(body.get("birth_date"))
        if cpf is False:
            return http_response(400, {"status": "ERROR",
                                       "message": "CPF deve ter 11 digitos"})
        if birth_date is False:
            return http_response(400, {"status": "ERROR",
                                       "message": "Data de nascimento invalida"})
        email = (body.get("email") or "").strip() or None

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

        # Check if phone already exists for this clinic (active or soft-deleted)
        existing = db.execute_query(
            "SELECT id, deleted_at FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )

        if existing:
            row = existing[0]
            if row.get("deleted_at") is None:
                return http_response(409, {
                    "status": "ERROR",
                    "message": "Ja existe um paciente com esse telefone"
                })

            # Soft-deleted patient with same phone — restore and update fields
            restored = db.execute_write_returning("""
                UPDATE scheduler.patients
                SET name = %s, gender = %s,
                    -- COALESCE: restaurar nao pode apagar CPF e nascimento que
                    -- ja estavam la so porque o formulario veio sem eles.
                    cpf = COALESCE(%s, cpf),
                    birth_date = COALESCE(%s::date, birth_date),
                    email = COALESCE(%s, email),
                    deleted_at = NULL, updated_at = NOW()
                WHERE id = %s::uuid
                RETURNING *
            """, (name, gender, cpf, birth_date, email, str(row["id"])))

            if not restored:
                return http_response(500, {
                    "status": "ERROR",
                    "message": "Falha ao restaurar paciente"
                })

            patient = _serialize_row(restored)
            logger.info(f"Patient restored: {patient['id']} for clinic {clinic_id}")
            return http_response(200, {
                "status": "RESTORED",
                "patient": patient,
            })

        result = db.execute_write_returning("""
            INSERT INTO scheduler.patients (clinic_id, name, phone, gender, cpf, birth_date, email, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s::date, %s, NOW(), NOW())
            RETURNING *
        """, (clinic_id, name, phone, gender, cpf, birth_date, email))

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Falha ao criar paciente"
            })

        patient = _serialize_row(result)
        logger.info(f"Patient created: {patient['id']} for clinic {clinic_id}")

        return http_response(201, {
            "status": "CREATED",
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
