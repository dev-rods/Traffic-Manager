import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
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
    GET /clinics/{clinicId}/appointments?date=YYYY-MM-DD&status=CONFIRMED

    Lists appointments for a clinic, optionally filtered by date and status.
    Includes patient name and phone via JOIN.
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e obrigatorio"})

        date_filter = extract_query_param(event, "date")
        status_filter = extract_query_param(event, "status")

        db = PostgresService()

        query = """
            SELECT
                a.id, a.clinic_id, a.appointment_date, a.start_time, a.end_time,
                a.areas, a.status, a.notes, a.version, a.created_at, a.updated_at,
                p.name as patient_name, p.phone as patient_phone,
                s.name as service_name, s.duration_minutes,
                pr.name as professional_name
            FROM scheduler.appointments a
            LEFT JOIN scheduler.patients p ON a.patient_id = p.id
            LEFT JOIN scheduler.services s ON a.service_id = s.id
            LEFT JOIN scheduler.professionals pr ON a.professional_id = pr.id
            WHERE a.clinic_id = %s
        """
        params = [clinic_id]

        if date_filter:
            query += " AND a.appointment_date = %s"
            params.append(date_filter)

        if status_filter:
            query += " AND a.status = %s"
            params.append(status_filter)

        query += " ORDER BY a.appointment_date ASC, a.start_time ASC"

        results = db.execute_query(query, tuple(params))
        appointments = [_serialize_row(r) for r in results]

        return http_response(200, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "appointments": appointments,
            "total": len(appointments),
        })

    except Exception as e:
        logger.error(f"Erro ao listar agendamentos: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
