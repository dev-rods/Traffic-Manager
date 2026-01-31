import json
import logging
from datetime import datetime, date
from src.utils.http import parse_body, http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

VALID_EXCEPTION_TYPES = ["BLOCKED", "SPECIAL_HOURS"]


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date)):
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

        exception_date = body.get("exception_date")
        exception_type = body.get("exception_type")
        start_time = body.get("start_time")
        end_time = body.get("end_time")
        professional_id = body.get("professional_id")
        reason = body.get("reason")

        if not exception_date or not exception_type:
            return http_response(400, {
                "status": "ERROR",
                "message": "exception_date and exception_type are required"
            })

        if exception_type not in VALID_EXCEPTION_TYPES:
            return http_response(400, {
                "status": "ERROR",
                "message": f"exception_type must be one of: {', '.join(VALID_EXCEPTION_TYPES)}"
            })

        if exception_type == "SPECIAL_HOURS" and (not start_time or not end_time):
            return http_response(400, {
                "status": "ERROR",
                "message": "start_time and end_time are required for SPECIAL_HOURS exception type"
            })

        db = PostgresService()
        result = db.execute_write_returning(
            """
            INSERT INTO scheduler.availability_exceptions
                (id, clinic_id, exception_date, exception_type, start_time, end_time, professional_id, reason)
            VALUES
                (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (clinic_id, exception_date, exception_type, start_time, end_time, professional_id, reason)
        )

        logger.info(f"[clinicId: {clinic_id}] Availability exception created: {result.get('id') if result else 'unknown'}")

        return http_response(201, {
            "status": "SUCCESS",
            "data": _serialize_row(result) if result else None
        })

    except Exception as e:
        logger.error(f"Error creating availability exception: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})


def list_handler(event, context):
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId is required"})

        from_date = extract_query_param(event, "from_date")
        to_date = extract_query_param(event, "to_date")

        query = "SELECT * FROM scheduler.availability_exceptions WHERE clinic_id = %s"
        params = [clinic_id]

        if from_date:
            query += " AND exception_date >= %s"
            params.append(from_date)

        if to_date:
            query += " AND exception_date <= %s"
            params.append(to_date)

        query += " ORDER BY exception_date"

        db = PostgresService()
        results = db.execute_query(query, tuple(params))

        logger.info(f"[clinicId: {clinic_id}] Listed {len(results)} availability exceptions")

        return http_response(200, {
            "status": "SUCCESS",
            "data": [_serialize_row(row) for row in results]
        })

    except Exception as e:
        logger.error(f"Error listing availability exceptions: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
