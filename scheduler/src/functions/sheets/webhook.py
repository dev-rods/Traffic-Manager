import json
import logging
import os
from datetime import datetime

from src.utils.http import parse_body, http_response
from src.services.db.postgres import PostgresService
from src.services.sheets_sync import SheetsSync
from src.services.appointment_service import AppointmentService, NotFoundError, ConflictError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

SUPPORTED_ACTIONS = {"BLOCK", "CANCEL", "RESCHEDULE", "UPDATE_AREAS", "CREATE"}


def handler(event, context):
    """
    POST /sheets/webhook

    Receives callbacks from Google Apps Script for bidirectional sync.

    Actions: BLOCK, CANCEL, RESCHEDULE, UPDATE_AREAS, CREATE
    """
    try:
        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        logger.info(f"[SheetsWebhook] Payload recebido: {json.dumps(body)[:500]}")

        # Validate shared secret token
        expected_token = os.environ.get("SHEETS_WEBHOOK_TOKEN", "")
        provided_token = body.get("token", "")

        if not expected_token or provided_token != expected_token:
            logger.warning("[SheetsWebhook] Token invalido ou ausente")
            return http_response(401, {"status": "ERROR", "message": "Token invalido"})

        action = body.get("action", "").upper()
        spreadsheet_id = body.get("spreadsheet_id")

        if not spreadsheet_id:
            return http_response(400, {"status": "ERROR", "message": "Campo obrigatorio: spreadsheet_id"})

        if action not in SUPPORTED_ACTIONS:
            return http_response(400, {"status": "ERROR", "message": f"Ação não suportada: {action}. Suportadas: {', '.join(sorted(SUPPORTED_ACTIONS))}"})

        db = PostgresService()

        # Find clinic by spreadsheet_id
        clinics = db.execute_query(
            "SELECT clinic_id FROM scheduler.clinics WHERE google_spreadsheet_id = %s AND active = TRUE",
            (spreadsheet_id,),
        )

        if not clinics:
            logger.warning(f"[SheetsWebhook] Clinica nao encontrada para spreadsheet_id={spreadsheet_id}")
            return http_response(404, {"status": "ERROR", "message": "Clinica nao encontrada para esta planilha"})

        clinic_id = clinics[0]["clinic_id"]

        # Dispatch by action
        if action == "BLOCK":
            return _handle_block(db, clinic_id, body)
        elif action == "CANCEL":
            return _handle_cancel(db, clinic_id, body)
        elif action == "RESCHEDULE":
            return _handle_reschedule(db, clinic_id, body)
        elif action == "UPDATE_AREAS":
            return _handle_update_areas(db, clinic_id, body)
        elif action == "CREATE":
            return _handle_create(db, clinic_id, body)

    except Exception as e:
        logger.error(f"[SheetsWebhook] Erro interno: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})


def _handle_block(db, clinic_id, body):
    block_date = body.get("date")
    block_time = body.get("time")

    if not block_date or not block_time:
        return http_response(400, {"status": "ERROR", "message": "BLOCK requer: date, time"})

    sheets_sync = SheetsSync(db)
    result = sheets_sync.create_block_from_sheet(
        clinic_id=clinic_id,
        block_date=block_date,
        start_time=block_time,
        end_time=body.get("end_time"),
        notes=body.get("notes", ""),
    )

    if not result:
        return http_response(500, {"status": "ERROR", "message": "Erro ao criar bloqueio"})

    logger.info(f"[SheetsWebhook] Bloqueio criado: clinic={clinic_id} date={block_date} time={block_time}")
    return http_response(201, {
        "status": "SUCCESS",
        "message": "Bloqueio criado com sucesso",
        "clinicId": clinic_id,
        "date": block_date,
        "time": block_time,
    })


def _handle_cancel(db, clinic_id, body):
    appointment_id = body.get("appointment_id")
    if not appointment_id:
        return http_response(400, {"status": "ERROR", "message": "CANCEL requer: appointment_id"})

    # sheets_sync=None to prevent loop
    appt_service = AppointmentService(db, sheets_sync=None)

    try:
        result = appt_service.cancel_appointment(appointment_id)
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})

    logger.info(f"[SheetsWebhook] Cancelamento via planilha: appointment={appointment_id} clinic={clinic_id}")
    return http_response(200, {
        "status": "SUCCESS",
        "message": "Agendamento cancelado com sucesso",
        "appointmentId": appointment_id,
    })


def _handle_reschedule(db, clinic_id, body):
    appointment_id = body.get("appointment_id")
    new_date = body.get("date")
    new_time = body.get("time")

    if not all([appointment_id, new_date, new_time]):
        return http_response(400, {"status": "ERROR", "message": "RESCHEDULE requer: appointment_id, date, time"})

    # sheets_sync=None to prevent loop
    appt_service = AppointmentService(db, sheets_sync=None)

    try:
        result = appt_service.reschedule_appointment(appointment_id, new_date, new_time)
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})

    logger.info(f"[SheetsWebhook] Remarcação via planilha: appointment={appointment_id} -> {new_date} {new_time}")
    return http_response(200, {
        "status": "SUCCESS",
        "message": "Agendamento remarcado com sucesso",
        "appointmentId": appointment_id,
        "newDate": new_date,
        "newTime": new_time,
    })


def _handle_update_areas(db, clinic_id, body):
    appointment_id = body.get("appointment_id")
    areas_str = body.get("areas", "")

    if not appointment_id or not areas_str:
        return http_response(400, {"status": "ERROR", "message": "UPDATE_AREAS requer: appointment_id, areas"})

    # Parse area names
    area_names = [a.strip() for a in areas_str.split(",") if a.strip()]
    if not area_names:
        return http_response(400, {"status": "ERROR", "message": "Nenhuma area valida fornecida"})

    # Fetch current appointment
    appointments = db.execute_query(
        "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
        (appointment_id,),
    )
    if not appointments:
        return http_response(404, {"status": "ERROR", "message": f"Agendamento {appointment_id} nao encontrado"})

    appointment = appointments[0]
    service_id = str(appointment["service_id"])

    # Resolve area names to area_ids for this clinic
    resolved_areas = []
    for area_name in area_names:
        rows = db.execute_query(
            "SELECT a.id as area_id, a.name as area_name FROM scheduler.areas a WHERE a.clinic_id = %s AND LOWER(a.name) = LOWER(%s) AND a.active = TRUE",
            (clinic_id, area_name),
        )
        if rows:
            resolved_areas.append({
                "area_id": str(rows[0]["area_id"]),
                "area_name": rows[0]["area_name"],
                "service_id": service_id,
            })
        else:
            logger.warning(f"[SheetsWebhook] Area nao encontrada: '{area_name}' para clinic={clinic_id}")

    if not resolved_areas:
        return http_response(400, {"status": "ERROR", "message": "Nenhuma area encontrada no banco"})

    # Delete existing appointment_service_areas
    db.execute_write(
        "DELETE FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid",
        (appointment_id,),
    )

    # Re-insert with resolved areas and calculate duration
    total_duration = 0
    for area in resolved_areas:
        # Get duration for this (service, area) pair
        dur_rows = db.execute_query(
            """SELECT COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                      COALESCE(sa.price_cents, s.price_cents) as price_cents,
                      s.name as service_name
               FROM scheduler.services s
               LEFT JOIN scheduler.service_areas sa ON sa.service_id = s.id AND sa.area_id = %s::uuid AND sa.active = TRUE
               WHERE s.id = %s::uuid""",
            (area["area_id"], area["service_id"]),
        )
        duration = dur_rows[0]["duration_minutes"] if dur_rows else 30
        price_cents = dur_rows[0].get("price_cents") if dur_rows else None
        service_name = dur_rows[0].get("service_name", "") if dur_rows else ""
        total_duration += duration

        db.execute_write(
            """INSERT INTO scheduler.appointment_service_areas
                (appointment_id, service_id, area_id, area_name, service_name, duration_minutes, price_cents)
               VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s)""",
            (appointment_id, area["service_id"], area["area_id"],
             area["area_name"], service_name, duration, price_cents),
        )

    # Recalculate end_time
    start_time = appointment["start_time"]
    if hasattr(start_time, "hour"):
        start_minutes = start_time.hour * 60 + start_time.minute
    else:
        parts = str(start_time).split(":")
        start_minutes = int(parts[0]) * 60 + int(parts[1])

    end_minutes = start_minutes + total_duration
    new_end_time = f"{end_minutes // 60:02d}:{end_minutes % 60:02d}"

    db.execute_write(
        """UPDATE scheduler.appointments
           SET total_duration_minutes = %s, end_time = %s::time, updated_at = NOW(), version = version + 1
           WHERE id = %s::uuid""",
        (total_duration, new_end_time, appointment_id),
    )

    logger.info(f"[SheetsWebhook] Areas atualizadas via planilha: appointment={appointment_id} areas={area_names} duration={total_duration}")
    return http_response(200, {
        "status": "SUCCESS",
        "message": f"Areas atualizadas: {', '.join(area_names)}",
        "appointmentId": appointment_id,
        "totalDuration": total_duration,
        "newEndTime": new_end_time,
    })


def _handle_create(db, clinic_id, body):
    phone = body.get("phone")
    service_name = body.get("service_name")
    appt_date = body.get("date")
    appt_time = body.get("time")
    areas_str = body.get("areas", "")
    notes = body.get("notes", "")

    if not all([phone, service_name, appt_date, appt_time]):
        return http_response(400, {"status": "ERROR", "message": "CREATE requer: phone, service_name, date, time"})

    # Resolve service_name -> service_id
    services = db.execute_query(
        "SELECT id FROM scheduler.services WHERE clinic_id = %s AND LOWER(name) = LOWER(%s) AND active = TRUE",
        (clinic_id, service_name),
    )
    if not services:
        return http_response(404, {"status": "ERROR", "message": f"Serviço '{service_name}' nao encontrado"})

    service_id = str(services[0]["id"])

    # Resolve area names -> service_area_pairs
    service_area_pairs = None
    if areas_str:
        area_names = [a.strip() for a in areas_str.split(",") if a.strip()]
        if area_names:
            service_area_pairs = []
            for area_name in area_names:
                rows = db.execute_query(
                    "SELECT id FROM scheduler.areas WHERE clinic_id = %s AND LOWER(name) = LOWER(%s) AND active = TRUE",
                    (clinic_id, area_name),
                )
                if rows:
                    service_area_pairs.append({
                        "service_id": service_id,
                        "area_id": str(rows[0]["id"]),
                    })
                else:
                    logger.warning(f"[SheetsWebhook] Area nao encontrada para CREATE: '{area_name}'")

            if not service_area_pairs:
                service_area_pairs = None

    # sheets_sync=None to prevent loop
    appt_service = AppointmentService(db, sheets_sync=None)

    try:
        result = appt_service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=service_id,
            date=appt_date,
            time=appt_time,
            service_area_pairs=service_area_pairs,
        )
    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})

    appointment_id = str(result["id"])

    # Write-back appointment_id to the sheet
    row_number = body.get("row_number")
    sheet_name = body.get("sheet_name")
    spreadsheet_id = body.get("spreadsheet_id")

    if row_number and sheet_name and spreadsheet_id:
        sheets_sync = SheetsSync(db)
        sheets_sync.update_cell(spreadsheet_id, sheet_name, int(row_number), "I", appointment_id)
        sheets_sync.update_cell(spreadsheet_id, sheet_name, int(row_number), "J",
                                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"))

    logger.info(f"[SheetsWebhook] Agendamento criado via planilha: appointment={appointment_id} clinic={clinic_id}")
    return http_response(201, {
        "status": "SUCCESS",
        "message": "Agendamento criado com sucesso",
        "appointmentId": appointment_id,
        "clinicId": clinic_id,
        "date": appt_date,
        "time": appt_time,
    })
