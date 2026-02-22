import logging
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


class OptimisticLockError(Exception):
    pass


class AppointmentService:

    def __init__(self, db: PostgresService, reminder_service=None, sheets_sync=None):
        self.db = db
        self.reminder_service = reminder_service
        self.sheets_sync = sheets_sync

    def create_appointment(
        self,
        clinic_id: str,
        phone: str,
        service_id: str,
        date: str,
        time: str,
        professional_id: Optional[str] = None,
        service_ids: Optional[List[str]] = None,
        total_duration_minutes: Optional[int] = None,
        service_area_pairs: Optional[List[Dict[str, str]]] = None,
        discount_pct: int = 0,
        discount_reason: Optional[str] = None,
        original_price_cents: Optional[int] = None,
        final_price_cents: Optional[int] = None,
    ) -> Dict[str, Any]:
        # 1. Get or create patient
        patient = self._get_or_create_patient(clinic_id, phone)
        patient_id = str(patient["id"])

        # 2. Resolve service list and duration
        all_service_ids = service_ids if service_ids else [service_id]
        primary_service_id = all_service_ids[0]

        # Fetch base service info
        placeholders = ", ".join(["%s"] * len(all_service_ids))
        services = self.db.execute_query(
            f"SELECT id, duration_minutes, name, price_cents FROM scheduler.services WHERE id::text IN ({placeholders}) AND active = TRUE",
            tuple(all_service_ids),
        )
        if not services:
            raise NotFoundError(f"Serviço(s) não encontrado(s)")

        # Build a lookup by id for ordering and data
        svc_lookup = {str(s["id"]): s for s in services}

        if total_duration_minutes:
            duration_minutes = int(total_duration_minutes)
        elif service_area_pairs:
            # Sum duration for each (service, area) pair with area-specific override
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params = ()
            for pair in service_area_pairs:
                params += (pair["service_id"], pair["area_id"])
            rows = self.db.execute_query(
                f"""SELECT SUM(COALESCE(sa.duration_minutes, s.duration_minutes)) as total_duration
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.services s ON s.id = pairs.service_id AND s.active = TRUE
                LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                params,
            )
            duration_minutes = int(rows[0]["total_duration"]) if rows and rows[0]["total_duration"] else sum(s["duration_minutes"] for s in services)
        else:
            duration_minutes = sum(s["duration_minutes"] for s in services)

        # 3. Calculate end_time
        start_parts = time.split(":")
        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        end_hour, end_min = total_minutes // 60, total_minutes % 60
        end_time = f"{end_hour:02d}:{end_min:02d}"

        # 4. Check for conflicts
        conflicts = self.db.execute_query(
            """
            SELECT id FROM scheduler.appointments
            WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED'
            AND (
                (start_time < %s::time AND end_time > %s::time)
                OR (start_time < %s::time AND end_time > %s::time)
                OR (start_time >= %s::time AND end_time <= %s::time)
            )
            """,
            (clinic_id, date, end_time, time, end_time, time, time, end_time),
        )

        if conflicts:
            raise ConflictError(f"Conflito de horário: já existe agendamento para {date} {time}-{end_time}")

        # 5. Resolve professional
        prof_id_param = None
        if professional_id:
            prof_id_param = professional_id
        else:
            professionals = self.db.execute_query(
                "SELECT id FROM scheduler.professionals WHERE clinic_id = %s AND active = TRUE LIMIT 1",
                (clinic_id,),
            )
            if professionals:
                prof_id_param = str(professionals[0]["id"])

        # 6. Insert appointment
        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.appointments (
                clinic_id, patient_id, professional_id, service_id,
                appointment_date, start_time, end_time,
                total_duration_minutes,
                discount_pct, discount_reason, original_price_cents, final_price_cents,
                status, created_at, updated_at, version
            ) VALUES (
                %s, %s::uuid, %s::uuid, %s::uuid,
                %s, %s::time, %s::time,
                %s,
                %s, %s, %s, %s,
                'CONFIRMED', NOW(), NOW(), 1
            )
            RETURNING *
            """,
            (clinic_id, patient_id, prof_id_param, primary_service_id,
             date, time, end_time,
             duration_minutes,
             discount_pct, discount_reason, original_price_cents, final_price_cents),
        )

        if not result:
            raise Exception("Erro ao criar agendamento")

        appointment_id = str(result["id"])

        # 7. Insert into junction tables
        if service_area_pairs:
            # Services WITH areas -> appointment_service_areas (1 row per pair)
            # Fetch info for each pair
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params = ()
            for pair in service_area_pairs:
                params += (pair["service_id"], pair["area_id"])
            pair_rows = self.db.execute_query(
                f"""SELECT pairs.service_id, pairs.area_id,
                       s.name as service_name, a.name as area_name,
                       COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                       COALESCE(sa.price_cents, s.price_cents) as price_cents
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.services s ON s.id = pairs.service_id
                JOIN scheduler.areas a ON a.id = pairs.area_id
                LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                params,
            )
            for row in pair_rows:
                self.db.execute_write(
                    """
                    INSERT INTO scheduler.appointment_service_areas
                        (appointment_id, service_id, area_id, area_name, service_name, duration_minutes, price_cents)
                    VALUES (%s::uuid, %s::uuid, %s::uuid, %s, %s, %s, %s)
                    """,
                    (appointment_id, str(row["service_id"]), str(row["area_id"]),
                     row["area_name"], row["service_name"],
                     row["duration_minutes"], row.get("price_cents")),
                )
        else:
            # Services WITHOUT areas -> appointment_services (as before)
            for sid in all_service_ids:
                svc = svc_lookup.get(sid)
                if svc:
                    self.db.execute_write(
                        """
                        INSERT INTO scheduler.appointment_services
                            (appointment_id, service_id, service_name, duration_minutes, price_cents)
                        VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                        """,
                        (appointment_id, sid, svc["name"], svc["duration_minutes"], svc.get("price_cents")),
                    )

        logger.info(
            f"[AppointmentService] Agendamento criado: id={result['id']} "
            f"clinic={clinic_id} date={date} time={time} services={len(all_service_ids)} "
            f"service_area_pairs={len(service_area_pairs) if service_area_pairs else 0}"
        )

        # 8. Schedule reminder (if available)
        if self.reminder_service:
            try:
                self.reminder_service.schedule_reminder(result)
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao agendar lembrete: {e}")

        # 9. Sync to Google Sheets (if available)
        if self.sheets_sync:
            try:
                self.sheets_sync.sync_appointment(result, "CREATED")
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao sincronizar com Sheets: {e}")

        return result

    def reschedule_appointment(
        self, appointment_id: str, new_date: str, new_time: str
    ) -> Dict[str, Any]:
        # 1. Fetch with optimistic lock
        appointments = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )

        if not appointments:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")

        appointment = appointments[0]
        current_version = appointment.get("version", 1)
        clinic_id = appointment["clinic_id"]

        # 2. Get duration: prefer total_duration_minutes, then appointment_service_areas, then appointment_services, then service default
        duration_minutes = appointment.get("total_duration_minutes")
        if not duration_minutes:
            # Try appointment_service_areas first (services with areas)
            asa_junction = self.db.execute_query(
                "SELECT SUM(duration_minutes) as total FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid",
                (appointment_id,),
            )
            if asa_junction and asa_junction[0].get("total"):
                duration_minutes = int(asa_junction[0]["total"])
            else:
                # Try appointment_services (services without areas)
                junction = self.db.execute_query(
                    "SELECT SUM(duration_minutes) as total FROM scheduler.appointment_services WHERE appointment_id = %s::uuid",
                    (appointment_id,),
                )
                if junction and junction[0].get("total"):
                    duration_minutes = int(junction[0]["total"])
                else:
                    services = self.db.execute_query(
                        "SELECT duration_minutes FROM scheduler.services WHERE id = %s::uuid",
                        (str(appointment["service_id"]),),
                    )
                    duration_minutes = services[0]["duration_minutes"] if services else 60

        # 3. Calculate new end_time
        duration_minutes = int(duration_minutes)
        start_parts = new_time.split(":")
        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        end_hour, end_min = total_minutes // 60, total_minutes % 60
        new_end_time = f"{end_hour:02d}:{end_min:02d}"

        # 4. Check conflicts in new slot
        conflicts = self.db.execute_query(
            """
            SELECT id FROM scheduler.appointments
            WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED'
            AND id != %s::uuid
            AND (
                (start_time < %s::time AND end_time > %s::time)
                OR (start_time < %s::time AND end_time > %s::time)
                OR (start_time >= %s::time AND end_time <= %s::time)
            )
            """,
            (clinic_id, new_date, appointment_id, new_end_time, new_time, new_end_time, new_time, new_time, new_end_time),
        )

        if conflicts:
            raise ConflictError(f"Conflito de horário no novo slot: {new_date} {new_time}-{new_end_time}")

        # 5. Update with optimistic lock
        updated_rows = self.db.execute_write(
            """
            UPDATE scheduler.appointments
            SET appointment_date = %s, start_time = %s::time, end_time = %s::time,
                version = version + 1, updated_at = NOW()
            WHERE id = %s::uuid AND version = %s
            """,
            (new_date, new_time, new_end_time, appointment_id, current_version),
        )

        if updated_rows == 0:
            raise OptimisticLockError("Agendamento foi modificado por outro processo")

        # 6. Cancel old reminder and schedule new
        if self.reminder_service:
            try:
                self.reminder_service.cancel_reminder(appointment_id)
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao cancelar lembrete antigo: {e}")

        result = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid",
            (appointment_id,),
        )
        updated_appointment = result[0] if result else appointment

        if self.reminder_service:
            try:
                self.reminder_service.schedule_reminder(updated_appointment)
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao agendar novo lembrete: {e}")

        # 7. Sync to Sheets
        if self.sheets_sync:
            try:
                self.sheets_sync.sync_appointment(updated_appointment, "RESCHEDULED")
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao sincronizar remarcacao: {e}")

        logger.info(
            f"[AppointmentService] Agendamento remarcado: id={appointment_id} "
            f"newDate={new_date} newTime={new_time}"
        )

        return updated_appointment

    def cancel_appointment(self, appointment_id: str) -> Dict[str, Any]:
        result = self.db.execute_write_returning(
            """
            UPDATE scheduler.appointments
            SET status = 'CANCELLED', updated_at = NOW(), version = version + 1
            WHERE id = %s::uuid AND status = 'CONFIRMED'
            RETURNING *
            """,
            (appointment_id,),
        )

        if not result:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou já cancelado")

        if self.reminder_service:
            try:
                self.reminder_service.cancel_reminder(appointment_id)
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao cancelar lembrete: {e}")

        if self.sheets_sync:
            try:
                self.sheets_sync.sync_appointment(result, "CANCELLED")
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao sincronizar cancelamento: {e}")

        logger.info(f"[AppointmentService] Agendamento cancelado: id={appointment_id}")
        return result

    def get_active_appointment_by_phone(
        self, clinic_id: str, phone: str
    ) -> Optional[Dict[str, Any]]:
        patients = self.db.execute_query(
            "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )

        if not patients:
            return None

        patient_id = str(patients[0]["id"])

        appointments = self.db.execute_query(
            """
            SELECT a.*, s.name as service_name,
                   areas_q.areas_display
            FROM scheduler.appointments a
            LEFT JOIN scheduler.services s ON a.service_id = s.id
            LEFT JOIN LATERAL (
                SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at) as areas_display
                FROM scheduler.appointment_service_areas asa
                WHERE asa.appointment_id = a.id
            ) areas_q ON TRUE
            WHERE a.patient_id = %s::uuid AND a.status = 'CONFIRMED'
            AND a.appointment_date >= CURRENT_DATE
            ORDER BY a.appointment_date ASC, a.start_time ASC
            LIMIT 1
            """,
            (patient_id,),
        )

        return appointments[0] if appointments else None

    def get_active_appointments_by_phone(
        self, clinic_id: str, phone: str
    ) -> List[Dict[str, Any]]:
        patients = self.db.execute_query(
            "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )

        if not patients:
            return []

        patient_id = str(patients[0]["id"])

        appointments = self.db.execute_query(
            """
            SELECT a.*, s.name as service_name,
                   areas_q.areas_display
            FROM scheduler.appointments a
            LEFT JOIN scheduler.services s ON a.service_id = s.id
            LEFT JOIN LATERAL (
                SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at) as areas_display
                FROM scheduler.appointment_service_areas asa
                WHERE asa.appointment_id = a.id
            ) areas_q ON TRUE
            WHERE a.patient_id = %s::uuid AND a.status = 'CONFIRMED'
            AND a.appointment_date >= CURRENT_DATE
            ORDER BY a.appointment_date ASC, a.start_time ASC
            """,
            (patient_id,),
        )

        return appointments

    def _get_or_create_patient(self, clinic_id: str, phone: str) -> Dict[str, Any]:
        patients = self.db.execute_query(
            "SELECT * FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )

        if patients:
            return patients[0]

        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.patients (clinic_id, phone, created_at, updated_at)
            VALUES (%s, %s, NOW(), NOW())
            RETURNING *
            """,
            (clinic_id, phone),
        )

        return result
