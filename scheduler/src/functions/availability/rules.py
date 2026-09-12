import json
import logging
from datetime import datetime, date, time
from psycopg2 import errors as pg_errors
from src.utils.http import parse_body, http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger()
logger.setLevel(logging.INFO)

DAY_NAMES = ["Domingo", "Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado"]


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _parse_time(value):
    """Aceita HH:MM ou HH:MM:SS. Retorna time ou None se invalido."""
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(value, fmt).time()
        except (ValueError, TypeError):
            continue
    return None


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
        rule_date = body.get("rule_date")
        start_time = body.get("start_time")
        end_time = body.get("end_time")
        professional_id = body.get("professional_id")

        if start_time is None or end_time is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "start_time and end_time are required"
            })

        # Must have day_of_week OR rule_date, never both
        if day_of_week is not None and rule_date is not None:
            return http_response(400, {
                "status": "ERROR",
                "message": "Provide day_of_week OR rule_date, not both"
            })

        if day_of_week is None and rule_date is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "Either day_of_week or rule_date is required"
            })

        if rule_date is not None:
            try:
                datetime.strptime(rule_date, "%Y-%m-%d")
            except (ValueError, TypeError):
                return http_response(400, {
                    "status": "ERROR",
                    "message": "rule_date must be a valid date in YYYY-MM-DD format"
                })

        if day_of_week is not None:
            if not isinstance(day_of_week, int) or day_of_week < 0 or day_of_week > 6:
                return http_response(400, {
                    "status": "ERROR",
                    "message": "day_of_week must be an integer between 0 and 6"
                })

        parsed_start = _parse_time(start_time)
        parsed_end = _parse_time(end_time)
        if parsed_start is None or parsed_end is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "start_time and end_time must be valid times in HH:MM format"
            })

        if parsed_start >= parsed_end:
            return http_response(400, {
                "status": "ERROR",
                "message": "start_time must be earlier than end_time"
            })

        db = PostgresService()
        result = db.execute_write_returning(
            """
            INSERT INTO scheduler.availability_rules
                (id, clinic_id, day_of_week, rule_date, start_time, end_time, professional_id)
            VALUES
                (gen_random_uuid(), %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (clinic_id, day_of_week, rule_date, start_time, end_time, professional_id)
        )

        logger.info(f"[clinicId: {clinic_id}] Availability rule created: {result.get('id') if result else 'unknown'}")

        return http_response(201, {
            "status": "SUCCESS",
            "data": _serialize_row(result) if result else None
        })

    except pg_errors.UniqueViolation:
        # day_of_week e None em regras de data fixa: ramificar antes de indexar DAY_NAMES.
        if day_of_week is not None:
            day_name = DAY_NAMES[day_of_week] if 0 <= day_of_week <= 6 else str(day_of_week)
            message = f"Ja existe uma regra de disponibilidade para {day_name} nesta clinica"
        else:
            message = f"Ja existe um horario cadastrado para {rule_date} comecando as {start_time}"
        return http_response(409, {"status": "ERROR", "message": message})
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
            ORDER BY day_of_week NULLS LAST, rule_date, start_time
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


def delete_handler(event, context):
    """
    DELETE /clinics/{clinicId}/availability-rules/{ruleId}

    Hard delete. Soft delete nao serve aqui: a constraint
    uq_availability_rules_clinic_day (clinic_id, day_of_week) continuaria ocupada
    por uma linha invisivel na UI, impedindo recadastrar o mesmo dia da semana.
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        rule_id = extract_path_param(event, "ruleId")
        if not clinic_id or not rule_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId e ruleId sao obrigatorios"
            })

        db = PostgresService()
        deleted = db.execute_write_returning(
            """
            DELETE FROM scheduler.availability_rules
            WHERE id = %s::uuid AND clinic_id = %s
            RETURNING id
            """,
            (rule_id, clinic_id)
        )

        # Mesma resposta para "nao existe" e "pertence a outra clinica":
        # nao vazar existencia entre tenants.
        if not deleted:
            return http_response(404, {
                "status": "ERROR",
                "message": "Regra de disponibilidade nao encontrada"
            })

        logger.info(f"[clinicId: {clinic_id}] Availability rule deleted: {rule_id}")

        return http_response(200, {"status": "SUCCESS", "message": "Regra excluida"})

    except pg_errors.InvalidTextRepresentation:
        return http_response(400, {"status": "ERROR", "message": "ruleId invalido"})
    except Exception as e:
        logger.error(f"Error deleting availability rule: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})


def update_handler(event, context):
    """
    PATCH /clinics/{clinicId}/availability-rules/{ruleId}

    Altera apenas a faixa horaria. Mudar day_of_week ou rule_date e outra regra:
    o cliente deve excluir e criar.
    """
    try:
        body = parse_body(event)
        api_key, error_response = require_api_key(event, body)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        rule_id = extract_path_param(event, "ruleId")
        if not clinic_id or not rule_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId e ruleId sao obrigatorios"
            })

        if not body:
            return http_response(400, {"status": "ERROR", "message": "Request body is required"})

        start_time = body.get("start_time")
        end_time = body.get("end_time")

        if start_time is None and end_time is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "Informe start_time e/ou end_time"
            })

        db = PostgresService()
        existing = db.execute_query(
            "SELECT start_time, end_time FROM scheduler.availability_rules "
            "WHERE id = %s::uuid AND clinic_id = %s",
            (rule_id, clinic_id)
        )
        if not existing:
            return http_response(404, {
                "status": "ERROR",
                "message": "Regra de disponibilidade nao encontrada"
            })

        # Valida o intervalo resultante, nao so os campos enviados: um PATCH
        # parcial pode inverter a faixa combinando com o valor ja gravado.
        final_start = _parse_time(start_time) if start_time is not None else existing[0]["start_time"]
        final_end = _parse_time(end_time) if end_time is not None else existing[0]["end_time"]

        if final_start is None or final_end is None:
            return http_response(400, {
                "status": "ERROR",
                "message": "start_time and end_time must be valid times in HH:MM format"
            })

        if final_start >= final_end:
            return http_response(400, {
                "status": "ERROR",
                "message": "start_time must be earlier than end_time"
            })

        result = db.execute_write_returning(
            """
            UPDATE scheduler.availability_rules
            SET start_time = %s, end_time = %s
            WHERE id = %s::uuid AND clinic_id = %s
            RETURNING *
            """,
            (final_start, final_end, rule_id, clinic_id)
        )

        logger.info(f"[clinicId: {clinic_id}] Availability rule updated: {rule_id}")

        return http_response(200, {
            "status": "SUCCESS",
            "data": _serialize_row(result) if result else None
        })

    except pg_errors.InvalidTextRepresentation:
        return http_response(400, {"status": "ERROR", "message": "ruleId invalido"})
    except pg_errors.UniqueViolation:
        return http_response(409, {
            "status": "ERROR",
            "message": "Ja existe um horario cadastrado com essa faixa nesta data"
        })
    except Exception as e:
        logger.error(f"Error updating availability rule: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
