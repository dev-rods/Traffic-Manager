import json
import logging
from datetime import datetime, date, time

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, NotFoundError, OptimisticLockError, ConflictError

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

    Body (all fields optional, at least one required):
    {
        "status": "CANCELLED",
        "notes": "Observacoes",
        "date": "2026-03-15",
        "time": "14:00",
        "serviceId": "uuid",
        "serviceAreaPairs": [{"serviceId":"..","areaId":".."}]
    }

    Supports combined operations in a single request (e.g. reschedule + change service + update notes).
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
        new_date = body.get("date")
        new_time = body.get("time")
        new_service_id = body.get("serviceId")
        new_service_area_pairs = body.get("serviceAreaPairs")
        new_discount_pct = body.get("discountPct")
        new_discount_reason = body.get("discountReason")

        from src.services.sheets_sync import SheetsSync
        sheets_sync = SheetsSync(db)
        service = AppointmentService(db, sheets_sync=sheets_sync)

        # Cancel is exclusive — cannot combine with other operations
        if new_status == "CANCELLED":
            result = service.cancel_appointment(appointment_id)
            return http_response(200, {
                "status": "SUCCESS",
                "message": "Agendamento cancelado com sucesso",
                "appointment": _serialize_row(result),
            })

        # Process all non-cancel changes sequentially
        changed = False
        messages = []

        # 1. Update service/areas first (changes duration → affects end_time calculation)
        if new_service_id:
            service.update_appointment_services(
                appointment_id, new_service_id, new_service_area_pairs
            )
            changed = True
            messages.append("serviço/áreas")

        # 2. Reschedule date/time (recalculates end_time with current duration)
        if new_date or new_time:
            if not new_date or not new_time:
                existing = db.execute_query(
                    "SELECT appointment_date, start_time FROM scheduler.appointments WHERE id = %s::uuid",
                    (appointment_id,),
                )
                if not existing:
                    return http_response(404, {"status": "ERROR", "message": "Agendamento nao encontrado"})
                if not new_date:
                    new_date = str(existing[0]["appointment_date"])
                if not new_time:
                    new_time = str(existing[0]["start_time"])[:5]

            service.reschedule_appointment(appointment_id, new_date, new_time)
            changed = True
            messages.append("data/horário")

        # 3. Update simple fields (notes, status, discount)
        updates = []
        params = []

        if new_status:
            updates.append("status = %s")
            params.append(new_status)
            messages.append("status")

        if notes is not None:
            updates.append("notes = %s")
            params.append(notes)
            messages.append("observações")

        if new_discount_pct is not None:
            discount_pct = int(new_discount_pct)
            if discount_pct < 0 or discount_pct > 100:
                return http_response(400, {"status": "ERROR", "message": "Desconto deve ser entre 0 e 100"})
            updates.append("discount_pct = %s")
            params.append(discount_pct)
            updates.append("discount_reason = %s")
            params.append(new_discount_reason)
            # Recalculate final price
            existing = db.execute_query(
                "SELECT original_price_cents FROM scheduler.appointments WHERE id = %s::uuid",
                (appointment_id,),
            )
            if existing and existing[0].get("original_price_cents") is not None:
                orig = existing[0]["original_price_cents"]
                updates.append("final_price_cents = %s")
                params.append(orig * (100 - discount_pct) // 100)
            messages.append("desconto")

        if updates:
            updates.append("updated_at = NOW()")
            params.append(appointment_id)
            query = f"""
                UPDATE scheduler.appointments
                SET {', '.join(updates)}
                WHERE id = %s::uuid
                RETURNING *
            """
            db.execute_write_returning(query, tuple(params))
            changed = True

        if not changed:
            return http_response(400, {"status": "ERROR", "message": "Nenhum campo para atualizar"})

        # Re-fetch final state
        final = db.execute_query("SELECT * FROM scheduler.appointments WHERE id = %s::uuid", (appointment_id,))
        if not final:
            return http_response(404, {"status": "ERROR", "message": "Agendamento não encontrado"})

        return http_response(200, {
            "status": "SUCCESS",
            "message": f"Agendamento atualizado ({', '.join(messages)})",
            "appointment": _serialize_row(final[0]),
        })

    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})

    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})

    except OptimisticLockError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})

    except Exception as e:
        logger.error(f"Erro ao atualizar agendamento: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
