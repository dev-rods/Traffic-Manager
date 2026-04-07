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

    def __init__(self, db: PostgresService, reminder_service=None, lead_service=None):
        self.db = db
        self.reminder_service = reminder_service
        self.lead_service = lead_service

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
        full_name: Optional[str] = None,
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

        # 2b. Auto-calculate prices when not provided by caller
        if original_price_cents is None:
            if service_area_pairs:
                values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
                price_params = ()
                for pair in service_area_pairs:
                    price_params += (pair["service_id"], pair["area_id"])
                price_rows = self.db.execute_query(
                    f"""SELECT SUM(COALESCE(sa.price_cents, s.price_cents)) as total_price
                    FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                    JOIN scheduler.services s ON s.id = pairs.service_id AND s.active = TRUE
                    LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                    price_params,
                )
                original_price_cents = int(price_rows[0]["total_price"]) if price_rows and price_rows[0]["total_price"] else None
            else:
                original_price_cents = sum(s.get("price_cents") or 0 for s in services) or None

            if original_price_cents is not None:
                final_price_cents = original_price_cents * (100 - discount_pct) // 100

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
                full_name,
                status, created_at, updated_at, version
            ) VALUES (
                %s, %s::uuid, %s::uuid, %s::uuid,
                %s, %s::time, %s::time,
                %s,
                %s, %s, %s, %s,
                %s,
                'CONFIRMED', NOW(), NOW(), 1
            )
            RETURNING *
            """,
            (clinic_id, patient_id, prof_id_param, primary_service_id,
             date, time, end_time,
             duration_minutes,
             discount_pct, discount_reason, original_price_cents, final_price_cents,
             full_name),
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

        # 9. Mark lead as booked (if lead exists for this phone+clinic)
        if self.lead_service:
            try:
                self.lead_service.mark_as_booked(
                    clinic_id=clinic_id,
                    phone=phone,
                    appointment_id=appointment_id,
                    appointment_value=final_price_cents / 100.0 if final_price_cents else None,
                )
            except Exception as e:
                logger.error(f"[AppointmentService] Erro ao atualizar lead: {e}")

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

        logger.info(
            f"[AppointmentService] Agendamento remarcado: id={appointment_id} "
            f"newDate={new_date} newTime={new_time}"
        )

        return updated_appointment

    def update_appointment_services(
        self,
        appointment_id: str,
        service_id: str,
        service_area_pairs: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """Update the service and areas of an existing appointment, recalculating duration/end_time."""
        # 1. Fetch appointment with optimistic lock
        appointments = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid AND status = 'CONFIRMED'",
            (appointment_id,),
        )
        if not appointments:
            raise NotFoundError(f"Agendamento {appointment_id} não encontrado ou não confirmado")

        appointment = appointments[0]
        current_version = appointment.get("version", 1)
        clinic_id = appointment["clinic_id"]
        appt_date = str(appointment["appointment_date"])
        start_time = str(appointment["start_time"])[:5]

        # 2. Validate service exists
        services = self.db.execute_query(
            "SELECT id, duration_minutes, name, price_cents FROM scheduler.services WHERE id::text = %s AND active = TRUE",
            (service_id,),
        )
        if not services:
            raise NotFoundError("Serviço não encontrado")

        svc = services[0]

        # 3. Calculate new duration and price
        discount_pct = appointment.get("discount_pct") or 0
        if service_area_pairs:
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params: tuple = ()
            for pair in service_area_pairs:
                params += (pair["serviceId"], pair["areaId"])
            rows = self.db.execute_query(
                f"""SELECT SUM(COALESCE(sa.duration_minutes, s.duration_minutes)) as total_duration,
                       SUM(COALESCE(sa.price_cents, s.price_cents)) as total_price
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.services s ON s.id = pairs.service_id AND s.active = TRUE
                LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                params,
            )
            duration_minutes = int(rows[0]["total_duration"]) if rows and rows[0]["total_duration"] else svc["duration_minutes"]
            original_price_cents = int(rows[0]["total_price"]) if rows and rows[0]["total_price"] else svc.get("price_cents")
        else:
            duration_minutes = svc["duration_minutes"]
            original_price_cents = svc.get("price_cents")

        final_price_cents = original_price_cents * (100 - discount_pct) // 100 if original_price_cents else original_price_cents

        # 4. Calculate new end_time
        start_parts = start_time.split(":")
        start_hour, start_min = int(start_parts[0]), int(start_parts[1])
        total_minutes = start_hour * 60 + start_min + duration_minutes
        end_hour, end_min = total_minutes // 60, total_minutes % 60
        new_end_time = f"{end_hour:02d}:{end_min:02d}"

        # 5. Check conflicts with new duration
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
            (clinic_id, appt_date, appointment_id, new_end_time, start_time, new_end_time, start_time, start_time, new_end_time),
        )
        if conflicts:
            raise ConflictError(f"Conflito de horário com nova duração: {appt_date} {start_time}-{new_end_time}")

        # 6. Update appointment record
        updated_rows = self.db.execute_write(
            """
            UPDATE scheduler.appointments
            SET service_id = %s::uuid, end_time = %s::time, total_duration_minutes = %s,
                original_price_cents = %s, final_price_cents = %s,
                version = version + 1, updated_at = NOW()
            WHERE id = %s::uuid AND version = %s
            """,
            (service_id, new_end_time, duration_minutes, original_price_cents, final_price_cents, appointment_id, current_version),
        )
        if updated_rows == 0:
            raise OptimisticLockError("Agendamento foi modificado por outro processo")

        # 7. Replace junction table records
        self.db.execute_write(
            "DELETE FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid",
            (appointment_id,),
        )
        self.db.execute_write(
            "DELETE FROM scheduler.appointment_services WHERE appointment_id = %s::uuid",
            (appointment_id,),
        )

        if service_area_pairs:
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params = ()
            for pair in service_area_pairs:
                params += (pair["serviceId"], pair["areaId"])
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
            self.db.execute_write(
                """
                INSERT INTO scheduler.appointment_services
                    (appointment_id, service_id, service_name, duration_minutes, price_cents)
                VALUES (%s::uuid, %s::uuid, %s, %s, %s)
                """,
                (appointment_id, service_id, svc["name"], svc["duration_minutes"], svc.get("price_cents")),
            )

        # 8. Re-fetch and sync
        result = self.db.execute_query(
            "SELECT * FROM scheduler.appointments WHERE id = %s::uuid",
            (appointment_id,),
        )
        updated_appointment = result[0] if result else appointment

        logger.info(
            f"[AppointmentService] Serviço/áreas atualizados: id={appointment_id} "
            f"service={service_id} areas={len(service_area_pairs) if service_area_pairs else 0}"
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
        from src.utils.phone import normalize_phone
        phone = normalize_phone(phone)

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
