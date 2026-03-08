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
    PATCH /clinics/{clinicId}/patients/{patientId}
    Atualiza nome, telefone e/ou genero de um paciente.
    """
    try:
        logger.info("Update patient request received")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        patient_id = extract_path_param(event, "patientId")
        if not clinic_id or not patient_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId e patientId sao obrigatorios"
            })

        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Body vazio ou invalido"
            })

        db = PostgresService()

        # Check patient exists and belongs to clinic
        existing = db.execute_query(
            "SELECT id FROM scheduler.patients WHERE id = %s::uuid AND clinic_id = %s",
            (patient_id, clinic_id),
        )
        if not existing:
            return http_response(404, {
                "status": "ERROR",
                "message": "Paciente nao encontrado"
            })

        # Build dynamic SET clause
        allowed_fields = {"name", "phone", "gender"}
        sets = []
        params = []
        for field in allowed_fields:
            if field in body:
                val = body[field]
                if field == "gender" and val and val not in ("M", "F"):
                    return http_response(400, {
                        "status": "ERROR",
                        "message": "Genero deve ser M ou F"
                    })
                if field == "phone" and val:
                    val = normalize_phone(val)
                sets.append(f"{field} = %s")
                params.append(val)

        if not sets:
            return http_response(400, {
                "status": "ERROR",
                "message": "Nenhum campo para atualizar"
            })

        sets.append("updated_at = NOW()")
        params.extend([patient_id, clinic_id])

        result = db.execute_write_returning(
            f"UPDATE scheduler.patients SET {', '.join(sets)} WHERE id = %s::uuid AND clinic_id = %s RETURNING *",
            tuple(params),
        )

        if not result:
            return http_response(500, {
                "status": "ERROR",
                "message": "Falha ao atualizar paciente"
            })

        patient = _serialize_row(result)
        logger.info(f"Patient updated: {patient_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "patient": patient,
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error updating patient: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": error_msg,
        })
