import json
import logging
from datetime import datetime, date, time
from psycopg2 import errors as pg_errors
from src.utils.http import parse_body, http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def create_handler(event, context):
    try:
        body = parse_body(event)
        api_key, error_response = require_api_key(event, body)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId is required"})

        if not body:
            return http_response(400, {"status": "ERROR", "message": "Request body is required"})

        day_of_week = body.get("day_of_week")
        start_time = body.get("start_time")
        end_time = body.get("end_time")
        professional_id = body.get("professional_id")

        if day_of_week is None or start_time is None or end_time is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "day_of_week, start_time and end_time are required"
            })

        if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
            return http_response(400, {
                "status": "ERROR",
                "message": "day_of_week must be an integer between 0 and 6"
            })

        db = PostgresService()
        result = db.execute_write_returning(
            """
            INSERT INTO scheduler.availability_rules
                (id, clinic_id, day_of_week, start_time, end_time, professional_id)
            VALUES
                (gen_random_uuid(), %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (clinic_id, day_of_week, start_time, end_time, professional_id)
        )

        logger.info(f"[clinicId: {clinic_id}] Availability rule created: {result.get('id') if result else 'unknown'}")

        return http_response(201, {
            "status": "SUCCESS",
            "data": _serialize_row(result) if result else None
        })

    except pg_errors.UniqueViolation:
        DAY_NAMES = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"]
        day_name = DAY_NAMES[day_of_week] if 0 <= day_of_week <= 6 else str(day_of_week)
        return http_response(409, {
            "status": "ERROR",
            "message": f"Ja existe uma regra de disponibilidade para {day_name} nesta clinica"
        })
    except Exception as e:
        logger.error(f"Error creating availability rule: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})


def list_handler(event, context):
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId is required"})

        db = PostgresService()
        results = db.execute_query(
            """
            SELECT * FROM scheduler.availability_rules
            WHERE clinic_id = %s AND active = true
            ORDER BY day_of_week, start_time
            """,
            (clinic_id,)
        )

        logger.info(f"[clinicId: {clinic_id}] Listed {len(results)} availability rules")

        return http_response(200, {
            "status": "SUCCESS",
            "data": [_serialize_row(row) for row in results]
        })

    except Exception as e:
        logger.error(f"Error listing availability rules: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
