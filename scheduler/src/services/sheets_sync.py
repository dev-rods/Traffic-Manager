import os
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

SHEET_HEADERS = [
    "Data", "Horário", "Paciente", "Telefone", "Serviço",
    "Áreas", "Status", "Observações", "AppointmentId", "UltimaAtualização"
]


class SheetsSync:

    def __init__(self, db: PostgresService):
        self.db = db
        self._sheets_service = None

    def _get_sheets_service(self):
        if self._sheets_service:
            return self._sheets_service

        try:
            sa_json = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", "")
            if not sa_json:
                logger.warning("[SheetsSync] GOOGLE_SHEETS_SERVICE_ACCOUNT nao configurada")
                return None

            from google.oauth2.service_account import Credentials
            from googleapiclient.discovery import build

            creds_info = json.loads(sa_json)
            creds = Credentials.from_service_account_info(
                creds_info,
                scopes=["https://www.googleapis.com/auth/spreadsheets"],
            )
            self._sheets_service = build("sheets", "v4", credentials=creds)
            return self._sheets_service
        except Exception as e:
            logger.error(f"[SheetsSync] Erro ao inicializar Google Sheets: {e}")
            return None

    def sync_appointment(self, appointment: Dict[str, Any], action: str) -> None:
        try:
            clinic_id = appointment.get("clinic_id", "")
            clinics = self.db.execute_query(
                "SELECT google_spreadsheet_id, google_sheet_name FROM scheduler.clinics WHERE clinic_id = %s",
                (clinic_id,),
            )

            if not clinics:
                return

            clinic = clinics[0]
            spreadsheet_id = clinic.get("google_spreadsheet_id")
            sheet_name = clinic.get("google_sheet_name", "Agenda")

            if not spreadsheet_id:
                return

            appointment_id = str(appointment.get("id", ""))
            row_values = [
                str(appointment.get("appointment_date", "")),
                str(appointment.get("start_time", "")),
                appointment.get("patient_name", ""),
                appointment.get("patient_phone", appointment.get("phone", "")),
                appointment.get("service_name", ""),
                appointment.get("areas", ""),
                appointment.get("status", ""),
                appointment.get("notes", ""),
                appointment_id,
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            ]

            if action == "CREATED":
                self._append_row(spreadsheet_id, sheet_name, row_values)
                logger.info(f"[SheetsSync] Appointment {appointment_id} adicionado ao Sheets")
            elif action in ("RESCHEDULED", "CANCELLED"):
                row_number = self._find_row_by_appointment_id(spreadsheet_id, sheet_name, appointment_id)
                if row_number:
                    self._update_row(spreadsheet_id, sheet_name, row_number, row_values)
                    logger.info(f"[SheetsSync] Appointment {appointment_id} atualizado no Sheets (row {row_number})")
                else:
                    self._append_row(spreadsheet_id, sheet_name, row_values)
                    logger.info(f"[SheetsSync] Appointment {appointment_id} nao encontrado, adicionado como nova linha")

        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao sincronizar com Sheets (nao critico): {e}")

    def _find_row_by_appointment_id(
        self, spreadsheet_id: str, sheet_name: str, appointment_id: str
    ) -> Optional[int]:
        try:
            service = self._get_sheets_service()
            if not service:
                return None

            # AppointmentId is in column I (index 9)
            range_str = f"{sheet_name}!I:I"
            result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=range_str,
            ).execute()

            values = result.get("values", [])
            for i, row in enumerate(values):
                if row and row[0] == appointment_id:
                    return i + 1  # 1-indexed

            return None
        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao buscar linha por appointmentId: {e}")
            return None

    def _append_row(self, spreadsheet_id: str, sheet_name: str, values: List) -> None:
        try:
            service = self._get_sheets_service()
            if not service:
                return

            range_str = f"{sheet_name}!A:J"
            body = {"values": [values]}

            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=range_str,
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body=body,
            ).execute()
        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao adicionar linha: {e}")

    def _update_row(self, spreadsheet_id: str, sheet_name: str, row_number: int, values: List) -> None:
        try:
            service = self._get_sheets_service()
            if not service:
                return

            range_str = f"{sheet_name}!A{row_number}:J{row_number}"
            body = {"values": [values]}

            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_str,
                valueInputOption="RAW",
                body=body,
            ).execute()
        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao atualizar linha: {e}")
