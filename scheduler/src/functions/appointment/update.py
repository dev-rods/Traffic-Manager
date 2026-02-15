import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, NotFoundError, OptimisticLockError

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
    PUT /appointments/{appointmentId}

    Body:
    {
        "status": "CANCELLED",    (opcional)
        "notes": "Observacoes"    (opcional)
    }
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        appointment_id = extract_path_param(event, "appointmentId")
        if not appointment_id:
            return http_response(400, {"status": "ERROR", "message": "appointmentId e obrigatorio"})

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        db = PostgresService()
        new_status = body.get("status")
        notes = body.get("notes")

        # If cancelling, use AppointmentService
        if new_status == "CANCELLED":
            from src.services.sheets_sync import SheetsSync
            sheets_sync = SheetsSync(db)
            service = AppointmentService(db, sheets_sync=sheets_sync)
            result = service.cancel_appointment(appointment_id)
            appointment = _serialize_row(result)

            return http_response(200, {
                "status": "SUCCESS",
                "message": "Agendamento cancelado com sucesso",
                "appointment": appointment,
            })

        # Otherwise, direct update of allowed fields
        updates = []
        params = []

        if new_status:
            updates.append("status = %s")
            params.append(new_status)

        if notes is not None:
            updates.append("notes = %s")
            params.append(notes)

        if not updates:
            return http_response(400, {"status": "ERROR", "message": "Nenhum campo para atualizar"})

        updates.append("updated_at = NOW()")
        params.append(appointment_id)

        query = f"""
            UPDATE scheduler.appointments
            SET {', '.join(updates)}
            WHERE id = %s::uuid
            RETURNING *
        """

        result = db.execute_write_returning(query, tuple(params))

        if not result:
            return http_response(404, {"status": "ERROR", "message": "Agendamento não encontrado"})

        appointment = _serialize_row(result)

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Agendamento atualizado com sucesso",
            "appointment": appointment,
        })

    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})

    except OptimisticLockError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})

    except Exception as e:
        logger.error(f"Erro ao atualizar agendamento: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
