import logging
from datetime import datetime, date, time, timedelta
from typing import List, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

# Horizonte de busca por dias disponíveis, em dias corridos a partir de hoje.
MAX_SEARCH_DAYS = 90


class AvailabilityEngine:

    def __init__(self, db: PostgresService):
        self.db = db
        # Duração do serviço e buffer da clínica não mudam entre as datas de uma
        # mesma busca, mas eram relidos a cada dia verificado. Memorizar por
        # instância corta 2 das 5 queries por data. A instância vive o tempo de
        # uma requisição, então não há risco de servir valor obsoleto.
        self._duracao_servico = {}
        self._buffer_clinica = {}

    def _get_service_duration(self, service_id: str) -> Optional[int]:
        if service_id not in self._duracao_servico:
            rows = self.db.execute_query(
                "SELECT duration_minutes FROM scheduler.services WHERE id = %s::uuid AND active = TRUE",
                (service_id,),
            )
            self._duracao_servico[service_id] = rows[0]["duration_minutes"] if rows else None
        return self._duracao_servico[service_id]

    def _get_buffer_minutes(self, clinic_id: str) -> int:
        if clinic_id not in self._buffer_clinica:
            rows = self.db.execute_query(
                "SELECT buffer_minutes FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                (clinic_id,),
            )
            self._buffer_clinica[clinic_id] = rows[0]["buffer_minutes"] if rows else 10
        return self._buffer_clinica[clinic_id]

    def _candidate_dates(self, clinic_id: str, start: date, horizon_days: int) -> List[str]:
        """Datas do horizonte que têm alguma regra de disponibilidade.

        Resolve numa única query quais dias sequer podem ter horário, em vez de
        perguntar dia a dia. Cada verificação de dia custa 5 queries, então varrer
        90 dias custava ~450 idas ao banco — mais de 80s numa clínica que atende
        em poucas datas fixas por mês. Filtrando antes, só os dias com regra são
        calculados.
        """
        end = start + timedelta(days=horizon_days)
        rows = self.db.execute_query(
            """
            SELECT day_of_week, rule_date FROM scheduler.availability_rules
            WHERE clinic_id = %s AND active = TRUE
              AND (rule_date IS NULL OR rule_date BETWEEN %s AND %s)
            """,
            (clinic_id, start, end),
        )
        if not rows:
            return []

        datas_fixas = {r["rule_date"] for r in rows if r.get("rule_date")}
        dias_semana = {r["day_of_week"] for r in rows if r.get("day_of_week") is not None}

        candidatas = []
        for i in range(1, horizon_days + 1):
            alvo = start + timedelta(days=i)
            # day_of_week no banco: 0=domingo ... 6=sábado
            if alvo in datas_fixas or (alvo.isoweekday() % 7) in dias_semana:
                candidatas.append(alvo.strftime("%Y-%m-%d"))
        return candidatas

    def get_available_slots(self, clinic_id: str, target_date: str, service_id: str) -> List[str]:
        try:
            # 1. Fetch service duration
            duration_minutes = self._get_service_duration(service_id)
            if duration_minutes is None:
                logger.warning(f"[AvailabilityEngine] Servico {service_id} nao encontrado")
                return []

            # 2. Fetch clinic buffer
            buffer_minutes = self._get_buffer_minutes(clinic_id)

            # 3. Parse date and get day_of_week (DB stores 0=Sunday, 1=Monday, ..., 6=Saturday)
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            day_of_week = dt.isoweekday() % 7  # 0=Sunday, 1=Monday, ..., 6=Saturday

            # 4. Fetch availability rules for this day (recurring + fixed-date)
            rules = self.db.execute_query(
                """
                SELECT start_time, end_time, rule_date FROM scheduler.availability_rules
                WHERE clinic_id = %s AND active = TRUE
                  AND (day_of_week = %s OR rule_date = %s)
                """,
                (clinic_id, day_of_week, target_date),
            )
            if not rules:
                return []

            # Fixed-date rules take priority over recurring day_of_week rules
            fixed_rules = [r for r in rules if r.get("rule_date")]
            if fixed_rules:
                rules = fixed_rules

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

            # 6. Fetch existing confirmed appointments for this date
            appointments = self.db.execute_query(
                """
                SELECT start_time, end_time FROM scheduler.appointments
                WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED'
                """,
                (clinic_id, target_date),
            )

            # 7. Calculate free windows and generate slots in gaps
            free_windows = self._calculate_free_windows(rules, appointments, buffer_minutes)
            slot_minutes = self._generate_slots_in_windows(free_windows, duration_minutes, buffer_minutes)

            return [_minutes_to_time_str(s) for s in slot_minutes]

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao calcular slots: {e}")
            return []

    def get_available_days(self, clinic_id: str, service_id: str, max_dates: Optional[int] = None) -> List[str]:
        try:
            if max_dates is None:
                max_dates = self._get_max_future_dates(clinic_id)

            today = date.today()
            available_days = []

            for target_str in self._candidate_dates(clinic_id, today, MAX_SEARCH_DAYS):
                if len(available_days) >= max_dates:
                    break
                if self.get_available_slots(clinic_id, target_str, service_id):
                    available_days.append(target_str)

            return available_days

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao buscar dias disponiveis: {e}")
            return []

    def get_available_slots_multi(self, clinic_id: str, target_date: str, total_duration: int) -> List[str]:
        """Calculate available slots using a direct duration value (sum of selected services)."""
        try:
            # 1. Fetch clinic buffer
            buffer_minutes = self._get_buffer_minutes(clinic_id)

            # 2. Parse date and get day_of_week
            dt = datetime.strptime(target_date, "%Y-%m-%d").date()
            day_of_week = dt.isoweekday() % 7

            # 3. Fetch availability rules for this day (recurring + fixed-date)
            rules = self.db.execute_query(
                """
                SELECT start_time, end_time, rule_date FROM scheduler.availability_rules
                WHERE clinic_id = %s AND active = TRUE
                  AND (day_of_week = %s OR rule_date = %s)
                """,
                (clinic_id, day_of_week, target_date),
            )
            if not rules:
                return []

            # Fixed-date rules take priority over recurring day_of_week rules
            fixed_rules = [r for r in rules if r.get("rule_date")]
            if fixed_rules:
                rules = fixed_rules

            # 4. Check availability exceptions
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

            # 5. Fetch existing confirmed appointments for this date
            appointments = self.db.execute_query(
                """
                SELECT start_time, end_time FROM scheduler.appointments
                WHERE clinic_id = %s AND appointment_date = %s AND status = 'CONFIRMED'
                """,
                (clinic_id, target_date),
            )

            # 6. Calculate free windows and generate slots in gaps
            free_windows = self._calculate_free_windows(rules, appointments, buffer_minutes)
            slot_minutes = self._generate_slots_in_windows(free_windows, total_duration, buffer_minutes)

            return [_minutes_to_time_str(s) for s in slot_minutes]

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao calcular slots multi: {e}")
            return []

    def get_available_days_multi(self, clinic_id: str, total_duration: int, max_dates: Optional[int] = None) -> List[str]:
        """Find available days using a direct duration value (sum of selected services)."""
        try:
            if max_dates is None:
                max_dates = self._get_max_future_dates(clinic_id)

            today = date.today()
            available_days = []

            for target_str in self._candidate_dates(clinic_id, today, MAX_SEARCH_DAYS):
                if len(available_days) >= max_dates:
                    break
                if self.get_available_slots_multi(clinic_id, target_str, total_duration):
                    available_days.append(target_str)

            return available_days

        except Exception as e:
            logger.error(f"[AvailabilityEngine] Erro ao buscar dias disponiveis multi: {e}")
            return []

    @staticmethod
    def _calculate_free_windows(rules: list, appointments: list, buffer_minutes: int) -> List[tuple]:
        """Calculate free time windows by subtracting appointments (with buffer) from rules."""
        # Build sorted list of blocked intervals from appointments
        blocked = []
        for appt in appointments:
            appt_start = _time_to_minutes(appt["start_time"])
            appt_end = _time_to_minutes(appt["end_time"])
            blocked.append((max(0, appt_start - buffer_minutes), appt_end + buffer_minutes))
        blocked.sort()

        free_windows = []
        for rule in rules:
            rule_start = _time_to_minutes(rule["start_time"])
            rule_end = _time_to_minutes(rule["end_time"])

            # Subtract each blocked interval from the rule window
            current_start = rule_start
            for block_start, block_end in blocked:
                if block_end <= current_start:
                    continue
                if block_start >= rule_end:
                    break
                # There's a free gap before this blocked interval
                if block_start > current_start:
                    free_windows.append((current_start, min(block_start, rule_end)))
                current_start = max(current_start, block_end)

            # Remaining window after last blocked interval
            if current_start < rule_end:
                free_windows.append((current_start, rule_end))

        return free_windows

    @staticmethod
    def _generate_slots_in_windows(free_windows: list, duration: int, buffer: int) -> List[int]:
        """Generate slot start times within each free window."""
        slots = []
        for window_start, window_end in free_windows:
            current = window_start
            while current + duration <= window_end:
                slots.append(current)
                current += duration + buffer
        return slots

    def _get_max_future_dates(self, clinic_id: str) -> int:
        clinic = self.db.execute_query(
            "SELECT max_future_dates FROM scheduler.clinics WHERE clinic_id = %s",
            (clinic_id,),
        )
        return (clinic[0].get("max_future_dates") or 5) if clinic else 5


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
    minutes = int(minutes)
    h = minutes // 60
    m = minutes % 60
    return f"{h:02d}:{m:02d}"
