import logging
from datetime import datetime, date, time, timedelta
from typing import List, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)


class AvailabilityEngine:

    def __init__(self, db: PostgresService):
        self.db = db

    def get_available_slots(self, clinic_id: str, target_date: str, service_id: str) -> List[str]:
        try:
            # 1. Fetch service duration
            services = self.db.execute_query(
                "SELECT duration_minutes FROM scheduler.services WHERE id = %s::uuid AND active = TRUE",
                (service_id,),
            )
            if not services:
                logger.warning(f"[AvailabilityEngine] Servico {service_id} nao encontrado")
                return []
            duration_minutes = services[0]["duration_minutes"]

            # 2. Fetch clinic buffer
            clinics = self.db.execute_query(
                "SELECT buffer_minutes FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                (clinic_id,),
            )
            buffer_minutes = clinics[0]["buffer_minutes"] if clinics else 10

            # 3. Parse date and get day_of_week (0=Monday in Python, but DB stores 0=Sunday or ISO)
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            # Python: Monday=0, Sunday=6. Store as ISO: Monday=1, Sunday=7
            day_of_week = dt.isoweekday()  # 1=Monday, 7=Sunday

            # 4. Fetch availability rules for this day
            rules = self.db.execute_query(
                """
                SELECT start_time, end_time FROM scheduler.availability_rules
                WHERE clinic_id = %s AND day_of_week = %s AND active = TRUE
                """,
                (clinic_id, day_of_week),
            )
            if not rules:
                return []

            # 5. Check availability exceptions
            exceptions = self.db.execute_query(
                """
                SELECT exception_type, start_time, end_time FROM scheduler.availability_exceptions
                WHERE clinic_id = %s AND exception_date = %s
                """,
                (clinic_id, target_date),
            )

            for exc in exceptions:
                if exc["exception_type"] == "BLOCKED":
                    return []
                elif exc["exception_type"] == "SPECIAL_HOURS":
                    rules = [{"start_time": exc["start_time"], "end_time": exc["end_time"]}]

            # 6. Calculate slot duration
            slot_duration = duration_minutes + buffer_minutes

            # 7. Generate all possible slots from rules
            all_slots = []
            for rule in rules:
                rule_start = _time_to_minutes(rule["start_time"])
                rule_end = _time_to_minutes(rule["end_time"])

                current = rule_start
                while current + duration_minutes <= rule_end:
                    all_slots.append(current)
                    current += slot_duration

            # 8. Fetch existing confirmed appointments for this date
            appointments = self.db.execute_query(
                """
                SELECT start_time, end_time FROM scheduler.appointments
                WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED'
                """,
                (clinic_id, target_date),
            )

            # 9. Remove conflicting slots
            available_slots = []
            for slot_start in all_slots:
                slot_end = slot_start + duration_minutes
                if not self._check_conflict(appointments, slot_start, slot_end):
                    available_slots.append(_minutes_to_time_str(slot_start))

            return available_slots

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao calcular slots: {e}")
            return []

    def get_available_days(self, clinic_id: str, service_id: str, days_ahead: int = 14) -> List[str]:
        try:
            today = date.today()
            available_days = []

            for i in range(1, days_ahead + 1):
                target = today + timedelta(days=i)
                target_str = target.strftime("%Y-%m-%d")
                slots = self.get_available_slots(clinic_id, target_str, service_id)
                if slots:
                    available_days.append(target_str)

            return available_days

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao buscar dias disponiveis: {e}")
            return []

    def get_available_slots_for_areas(self, clinic_id: str, target_date: str, areas_text: str) -> List[str]:
        try:
            # Fetch all services for the clinic
            services = self.db.execute_query(
                "SELECT id, name, duration_minutes FROM scheduler.services WHERE clinic_id = %s AND active = TRUE",
                (clinic_id,),
            )

            if not services:
                return []

            # Fuzzy match areas against service names
            areas_lower = areas_text.lower()
            total_duration = 0
            matched = False

            for svc in services:
                svc_name_lower = svc["name"].lower()
                if svc_name_lower in areas_lower or areas_lower in svc_name_lower:
                    total_duration += svc["duration_minutes"]
                    matched = True

            # Fallback: use first service duration
            if not matched and services:
                total_duration = services[0]["duration_minutes"]

            # Get buffer
            clinics = self.db.execute_query(
                "SELECT buffer_minutes FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                (clinic_id,),
            )
            buffer_minutes = clinics[0]["buffer_minutes"] if clinics else 10

            # Get rules for the day
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            day_of_week = dt.isoweekday()

            rules = self.db.execute_query(
                """
                SELECT start_time, end_time FROM scheduler.availability_rules
                WHERE clinic_id = %s AND day_of_week = %s AND active = TRUE
                """,
                (clinic_id, day_of_week),
            )
            if not rules:
                return []

            # Check exceptions
            exceptions = self.db.execute_query(
                "SELECT exception_type, start_time, end_time FROM scheduler.availability_exceptions WHERE clinic_id = %s AND exception_date = %s",
                (clinic_id, target_date),
            )
            for exc in exceptions:
                if exc["exception_type"] == "BLOCKED":
                    return []
                elif exc["exception_type"] == "SPECIAL_HOURS":
                    rules = [{"start_time": exc["start_time"], "end_time": exc["end_time"]}]

            slot_duration = total_duration + buffer_minutes

            all_slots = []
            for rule in rules:
                rule_start = _time_to_minutes(rule["start_time"])
                rule_end = _time_to_minutes(rule["end_time"])
                current = rule_start
                while current + total_duration <= rule_end:
                    all_slots.append(current)
                    current += slot_duration

            appointments = self.db.execute_query(
                "SELECT start_time, end_time FROM scheduler.appointments WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED'",
                (clinic_id, target_date),
            )

            available_slots = []
            for slot_start in all_slots:
                slot_end = slot_start + total_duration
                if not self._check_conflict(appointments, slot_start, slot_end):
                    available_slots.append(_minutes_to_time_str(slot_start))

            return available_slots

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao calcular slots por areas: {e}")
            return []

    def _check_conflict(self, existing_appointments: list, slot_start: int, slot_end: int) -> bool:
        for appt in existing_appointments:
            appt_start = _time_to_minutes(appt["start_time"])
            appt_end = _time_to_minutes(appt["end_time"])

            # Overlap: slot_start < appt_end AND slot_end > appt_start
            if slot_start < appt_end and slot_end > appt_start:
                return True

        return False


def _time_to_minutes(t) -> int:
    if isinstance(t, time):
        return t.hour * 60 + t.minute
    elif isinstance(t, timedelta):
        total_seconds = int(t.total_seconds())
        return total_seconds // 60
    elif isinstance(t, str):
        parts = t.split(":")
        return int(parts[0]) * 60 + int(parts[1])
    return 0


def _minutes_to_time_str(minutes: int) -> str:
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"
