import json
import logging
import os

from src.utils.http import parse_body, http_response
from src.services.db.postgres import PostgresService
from src.services.sheets_sync import SheetsSync

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    POST /sheets/webhook

    Receives callbacks from Google Apps Script when a row is marked as blocked.

    Body:
    {
        "spreadsheet_id": "abc123...",
        "action": "BLOCK",
        "date": "2026-02-14",
        "time": "10:00",
        "end_time": "11:00",    (opcional)
        "notes": "Ocupado",     (opcional)
        "token": "shared_secret"
    }
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

        spreadsheet_id = body.get("spreadsheet_id")
        action = body.get("action", "").upper()
        block_date = body.get("date")
        block_time = body.get("time")

        if not all([spreadsheet_id, action, block_date, block_time]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: spreadsheet_id, action, date, time"
            })

        if action != "BLOCK":
            return http_response(400, {"status": "ERROR", "message": f"Ação não suportada: {action}"})

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

    except Exception as e:
        logger.error(f"[SheetsWebhook] Erro interno: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
