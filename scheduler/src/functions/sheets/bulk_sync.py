import logging
from collections import defaultdict
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService
from src.services.sheets_sync import SheetsSync

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_value(value):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value if value is not None else ""


def handler(event, context):
    """
    POST /clinics/{clinicId}/sheets/sync

    Bulk-syncs all confirmed future appointments from DB to the Google Sheet.
    Groups by month and writes each month tab.
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e obrigatorio"})

        db = PostgresService()

        # Fetch spreadsheet_id for this clinic
        clinics = db.execute_query(
            "SELECT google_spreadsheet_id FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )

        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Clinica nao encontrada"})

        spreadsheet_id = clinics[0].get("google_spreadsheet_id")
        if not spreadsheet_id:
            return http_response(400, {"status": "ERROR", "message": "Clinica nao possui planilha configurada"})

        # Query confirmed future appointments (same JOIN pattern as appointment/list.py)
        appointments = db.execute_query(
            """
            SELECT
                a.id, a.clinic_id, a.appointment_date, a.start_time, a.end_time,
                a.status, a.notes,
                p.name as patient_name, p.phone as patient_phone,
                s.name as service_name,
                areas_q.areas_display as areas
            FROM scheduler.appointments a
            LEFT JOIN scheduler.patients p ON a.patient_id = p.id
            LEFT JOIN scheduler.services s ON a.service_id = s.id
            LEFT JOIN LATERAL (
                SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at) as areas_display
                FROM scheduler.appointment_service_areas asa
                WHERE asa.appointment_id = a.id
            ) areas_q ON TRUE
            WHERE a.clinic_id = %s
              AND a.appointment_date >= CURRENT_DATE
              AND a.status = 'CONFIRMED'
            ORDER BY a.appointment_date ASC, a.start_time ASC
            """,
            (clinic_id,),
        )

        # Serialize date/time values
        serialized = []
        for row in appointments:
            serialized.append({k: _serialize_value(v) for k, v in row.items()})

        # Group by (year, month)
        by_month = defaultdict(list)
        for appt in serialized:
            appt_date_str = appt.get("appointment_date", "")
            try:
                d = datetime.strptime(appt_date_str, "%Y-%m-%d").date()
            except (ValueError, TypeError):
                continue
            by_month[(d.year, d.month)].append(appt)

        sheets_sync = SheetsSync(db)
        total_synced = 0

        for (year, month), month_appointments in sorted(by_month.items()):
            target_date = date(year, month, 1)
            count = sheets_sync.bulk_sync_month(spreadsheet_id, target_date, month_appointments)
            total_synced += count

        logger.info(f"[SheetsBulkSync] Sync completo: clinic={clinic_id} total={total_synced} meses={len(by_month)}")

        return http_response(200, {
            "status": "SUCCESS",
            "message": f"Sync completo: {total_synced} agendamentos em {len(by_month)} mes(es)",
            "clinicId": clinic_id,
            "totalSynced": total_synced,
            "monthsProcessed": len(by_month),
        })

    except Exception as e:
        logger.error(f"[SheetsBulkSync] Erro interno: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
