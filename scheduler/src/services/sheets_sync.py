import os
import json
import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

MONTH_NAMES_PT = {
    1: "Jan", 2: "Fev", 3: "Mar", 4: "Abr", 5: "Mai", 6: "Jun",
    7: "Jul", 8: "Ago", 9: "Set", 10: "Out", 11: "Nov", 12: "Dez",
}

SHEET_HEADERS = [
    "Data", "Horário", "Paciente", "Telefone", "Serviço",
    "Áreas", "Status", "Observações", "AppointmentId", "UltimaAtualização"
]

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


class SheetsSync:

    def __init__(self, db: PostgresService):
        self.db = db
        self._sheets_service = None
        self._drive_service = None

    def _get_credentials(self):
        sa_json = os.environ.get("GOOGLE_SHEETS_SERVICE_ACCOUNT", "")
        if not sa_json:
            logger.warning("[SheetsSync] GOOGLE_SHEETS_SERVICE_ACCOUNT nao configurada")
            return None

        from google.oauth2.service_account import Credentials

        creds_info = json.loads(sa_json)
        return Credentials.from_service_account_info(creds_info, scopes=SCOPES)

    def _get_sheets_service(self):
        if self._sheets_service:
            return self._sheets_service

        try:
            creds = self._get_credentials()
            if not creds:
                return None

            from googleapiclient.discovery import build

            self._sheets_service = build("sheets", "v4", credentials=creds)
            return self._sheets_service
        except Exception as e:
            logger.error(f"[SheetsSync] Erro ao inicializar Google Sheets: {e}")
            return None

    def _get_drive_service(self):
        if self._drive_service:
            return self._drive_service

        try:
            creds = self._get_credentials()
            if not creds:
                return None

            from googleapiclient.discovery import build

            self._drive_service = build("drive", "v3", credentials=creds)
            return self._drive_service
        except Exception as e:
            logger.error(f"[SheetsSync] Erro ao inicializar Google Drive: {e}")
            return None

    # ------------------------------------------------------------------
    # Spreadsheet creation (called when a clinic is created)
    # ------------------------------------------------------------------

    def create_spreadsheet(self, clinic_name: str, owner_email: Optional[str] = None) -> Optional[str]:
        try:
            service = self._get_sheets_service()
            if not service:
                return None

            today = date.today()
            month_tab = self._month_tab_name(today)

            spreadsheet_body = {
                "properties": {"title": f"Agenda - {clinic_name}"},
                "sheets": [{"properties": {"title": month_tab}}],
            }

            spreadsheet = (
                service.spreadsheets()
                .create(body=spreadsheet_body, fields="spreadsheetId")
                .execute()
            )
            spreadsheet_id = spreadsheet["spreadsheetId"]

            # Add headers to the first tab
            self._write_headers(spreadsheet_id, month_tab)

            # Share with owner
            if owner_email:
                self._share_with_email(spreadsheet_id, owner_email)

            logger.info(f"[SheetsSync] Planilha criada: {spreadsheet_id} para '{clinic_name}'")
            return spreadsheet_id

        except Exception as e:
            logger.error(f"[SheetsSync] Erro ao criar planilha: {e}")
            return None

    def _share_with_email(self, spreadsheet_id: str, email: str) -> None:
        try:
            drive = self._get_drive_service()
            if not drive:
                return

            drive.permissions().create(
                fileId=spreadsheet_id,
                body={"type": "user", "role": "writer", "emailAddress": email},
                fields="id",
                sendNotificationEmail=True,
            ).execute()

            logger.info(f"[SheetsSync] Planilha compartilhada com {email}")
        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao compartilhar planilha: {e}")

    # ------------------------------------------------------------------
    # Monthly tab management
    # ------------------------------------------------------------------

    @staticmethod
    def _month_tab_name(d: date) -> str:
        return f"{MONTH_NAMES_PT.get(d.month, d.strftime('%b'))} {d.year}"

    def _ensure_month_tab(self, spreadsheet_id: str, target_date: date) -> str:
        tab_name = self._month_tab_name(target_date)

        try:
            service = self._get_sheets_service()
            if not service:
                return tab_name

            # Check if tab already exists
            meta = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id, fields="sheets.properties.title"
            ).execute()

            existing_tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]

            if tab_name not in existing_tabs:
                service.spreadsheets().batchUpdate(
                    spreadsheetId=spreadsheet_id,
                    body={"requests": [{"addSheet": {"properties": {"title": tab_name}}}]},
                ).execute()
                self._write_headers(spreadsheet_id, tab_name)
                logger.info(f"[SheetsSync] Aba '{tab_name}' criada em {spreadsheet_id}")

        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao garantir aba do mes: {e}")

        return tab_name

    def _write_headers(self, spreadsheet_id: str, sheet_name: str) -> None:
        try:
            service = self._get_sheets_service()
            if not service:
                return

            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1:J1",
                valueInputOption="RAW",
                body={"values": [SHEET_HEADERS]},
            ).execute()
        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao escrever headers: {e}")

    # ------------------------------------------------------------------
    # Appointment sync (called by AppointmentService)
    # ------------------------------------------------------------------

    def sync_appointment(self, appointment: Dict[str, Any], action: str) -> None:
        try:
            clinic_id = appointment.get("clinic_id", "")
            clinics = self.db.execute_query(
                "SELECT google_spreadsheet_id FROM scheduler.clinics WHERE clinic_id = %s",
                (clinic_id,),
            )

            if not clinics:
                return

            clinic = clinics[0]
            spreadsheet_id = clinic.get("google_spreadsheet_id")

            if not spreadsheet_id:
                return

            # Determine the month tab from appointment date
            appt_date = appointment.get("appointment_date")
            if isinstance(appt_date, str):
                appt_date = datetime.strptime(appt_date, "%Y-%m-%d").date()
            elif isinstance(appt_date, datetime):
                appt_date = appt_date.date()

            if not isinstance(appt_date, date):
                logger.warning("[SheetsSync] appointment_date invalida, usando data atual")
                appt_date = date.today()

            sheet_name = self._ensure_month_tab(spreadsheet_id, appt_date)

            appointment_id = str(appointment.get("id", ""))

            # Fetch areas from appointment_service_areas
            areas_display = ""
            if appointment_id:
                area_rows = self.db.execute_query(
                    "SELECT area_name FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid ORDER BY created_at",
                    (appointment_id,),
                )
                if area_rows:
                    areas_display = ", ".join(r["area_name"] for r in area_rows)

            # Fetch patient info if not in appointment dict
            patient_name = appointment.get("patient_name", "")
            patient_phone = appointment.get("patient_phone", appointment.get("phone", ""))
            if not patient_name and appointment.get("patient_id"):
                patients = self.db.execute_query(
                    "SELECT name, phone FROM scheduler.patients WHERE id = %s::uuid",
                    (str(appointment["patient_id"]),),
                )
                if patients:
                    patient_name = patients[0].get("name", "")
                    if not patient_phone:
                        patient_phone = patients[0].get("phone", "")

            # Fetch service name if not in appointment dict
            service_name = appointment.get("service_name", "")
            if not service_name and appointment.get("service_id"):
                services = self.db.execute_query(
                    "SELECT name FROM scheduler.services WHERE id = %s::uuid",
                    (str(appointment["service_id"]),),
                )
                if services:
                    service_name = services[0].get("name", "")

            row_values = [
                str(appointment.get("appointment_date", "")),
                str(appointment.get("start_time", "")),
                patient_name,
                patient_phone,
                service_name,
                areas_display,
                appointment.get("status", ""),
                appointment.get("notes", ""),
                appointment_id,
                datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
            ]

            if action == "CREATED":
                self._append_row(spreadsheet_id, sheet_name, row_values)
                logger.info(f"[SheetsSync] Appointment {appointment_id} adicionado ao Sheets")
            elif action in ("RESCHEDULED", "CANCELLED"):
                # Try to find in all month tabs
                row_number = self._find_row_by_appointment_id(spreadsheet_id, sheet_name, appointment_id)
                if row_number:
                    self._update_row(spreadsheet_id, sheet_name, row_number, row_values)
                    logger.info(f"[SheetsSync] Appointment {appointment_id} atualizado no Sheets (row {row_number})")
                else:
                    self._append_row(spreadsheet_id, sheet_name, row_values)
                    logger.info(f"[SheetsSync] Appointment {appointment_id} nao encontrado, adicionado como nova linha")

        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao sincronizar com Sheets (nao critico): {e}")

    # ------------------------------------------------------------------
    # Bulk sync (DB → Sheet)
    # ------------------------------------------------------------------

    def bulk_sync_month(
        self, spreadsheet_id: str, target_date: date, appointments: List[Dict[str, Any]]
    ) -> int:
        try:
            service = self._get_sheets_service()
            if not service:
                return 0

            sheet_name = self._ensure_month_tab(spreadsheet_id, target_date)

            # Clear rows 2+ (preserve headers)
            service.spreadsheets().values().clear(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A2:J",
                body={},
            ).execute()

            if not appointments:
                logger.info(f"[SheetsSync] bulk_sync_month: aba '{sheet_name}' limpa (0 appointments)")
                return 0

            # Sort by date ASC, time ASC
            appointments.sort(key=lambda a: (str(a.get("appointment_date", "")), str(a.get("start_time", ""))))

            rows = []
            for appt in appointments:
                rows.append([
                    str(appt.get("appointment_date", "")),
                    str(appt.get("start_time", "")),
                    appt.get("patient_name", ""),
                    appt.get("patient_phone", ""),
                    appt.get("service_name", ""),
                    appt.get("areas", ""),
                    appt.get("status", ""),
                    appt.get("notes", "") or "",
                    str(appt.get("id", "")),
                    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
                ])

            row_count = len(rows)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A2:J{row_count + 1}",
                valueInputOption="RAW",
                body={"values": rows},
            ).execute()

            logger.info(f"[SheetsSync] bulk_sync_month: {row_count} appointments escritos na aba '{sheet_name}'")
            return row_count

        except Exception as e:
            logger.error(f"[SheetsSync] Erro no bulk_sync_month: {e}")
            return 0

    def update_cell(self, spreadsheet_id: str, sheet_name: str, row_number: int, column: str, value: str) -> None:
        try:
            service = self._get_sheets_service()
            if not service:
                return

            range_str = f"{sheet_name}!{column}{row_number}"
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=range_str,
                valueInputOption="RAW",
                body={"values": [[value]]},
            ).execute()
        except Exception as e:
            logger.warning(f"[SheetsSync] Erro ao atualizar celula {column}{row_number}: {e}")

    # ------------------------------------------------------------------
    # Block creation from sheet edits (bidirectional sync)
    # ------------------------------------------------------------------

    def create_block_from_sheet(
        self, clinic_id: str, block_date: str, start_time: str, end_time: Optional[str] = None, notes: str = ""
    ) -> Optional[Dict[str, Any]]:
        try:
            result = self.db.execute_write_returning(
                """
                INSERT INTO scheduler.availability_exceptions
                    (clinic_id, exception_date, exception_type, start_time, end_time, reason)
                VALUES (%s, %s, 'BLOCKED', %s::time, %s::time, %s)
                RETURNING *
                """,
                (clinic_id, block_date, start_time, end_time or start_time, notes or "Bloqueado via planilha"),
            )
            logger.info(f"[SheetsSync] Bloqueio criado via planilha: {clinic_id} {block_date} {start_time}")
            return result
        except Exception as e:
            logger.error(f"[SheetsSync] Erro ao criar bloqueio: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

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
