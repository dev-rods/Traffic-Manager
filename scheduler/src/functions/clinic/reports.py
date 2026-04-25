import logging
from datetime import date, timedelta

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MONTHS_PT = [
    "", "Janeiro", "Fevereiro", "Marco", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _month_bounds(ref: date):
    first = ref.replace(day=1)
    if ref.month == 12:
        last = ref.replace(year=ref.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = ref.replace(month=ref.month + 1, day=1) - timedelta(days=1)
    return first, last


def _subtract_months(ref: date, months: int) -> date:
    """Subtract N months from a date, clamping day to valid range."""
    month = ref.month - months
    year = ref.year
    while month < 1:
        month += 12
        year -= 1
    # Clamp day
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    return date(year, month, min(ref.day, max_day))


def _period_range(period: str, today: date):
    """Returns (start, end, prev_start, prev_end, label)."""
    if period == "last_3_months":
        start = _subtract_months(today, 2).replace(day=1)
        _, end = _month_bounds(today)
        prev_start = _subtract_months(start, 3)
        prev_end = start - timedelta(days=1)
        label = f"{MONTHS_PT[start.month]} a {MONTHS_PT[today.month]} {today.year}"
    elif period == "current_year":
        start = today.replace(month=1, day=1)
        end = today.replace(month=12, day=31)
        prev_start = date(today.year - 1, 1, 1)
        prev_end = date(today.year - 1, 12, 31)
        label = str(today.year)
    else:  # current_month
        start, end = _month_bounds(today)
        prev_month_ref = _subtract_months(today, 1)
        prev_start, prev_end = _month_bounds(prev_month_ref)
        label = f"{MONTHS_PT[today.month]} {today.year}"

    return start, end, prev_start, prev_end, label


def handler(event, context):
    """
    GET /clinics/{clinicId}/reports?period=current_month|last_3_months|current_year
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e obrigatorio"})

        period = extract_query_param(event, "period") or "current_month"
        if period not in ("current_month", "last_3_months", "current_year"):
            return http_response(400, {"status": "ERROR", "message": "period invalido"})

        db = PostgresService()
        today = date.today()
        start, end, prev_start, prev_end, label = _period_range(period, today)

        # ── Summary (current period) ──────────────────────────────
        summary_row = db.execute_query("""
            SELECT
                COUNT(*) FILTER (WHERE status != 'CANCELLED') as total_appointments,
                COUNT(*) FILTER (WHERE status = 'CONFIRMED') as confirmed_appointments,
                COUNT(*) FILTER (WHERE status = 'CANCELLED') as cancelled_appointments,
                COALESCE(SUM(original_price_cents) FILTER (WHERE status != 'CANCELLED'), 0) as gross_revenue_cents,
                COALESCE(SUM(final_price_cents) FILTER (WHERE status != 'CANCELLED'), 0) as net_revenue_cents,
                COALESCE(SUM(original_price_cents - final_price_cents) FILTER (WHERE status != 'CANCELLED' AND discount_pct > 0), 0) as total_discount_cents
            FROM scheduler.appointments
            WHERE clinic_id = %s AND appointment_date BETWEEN %s AND %s
        """, (clinic_id, start, end))

        s = summary_row[0] if summary_row else {}
        total = s.get("total_appointments", 0) or 0
        confirmed = s.get("confirmed_appointments", 0) or 0
        cancelled = s.get("cancelled_appointments", 0) or 0
        gross = s.get("gross_revenue_cents", 0) or 0
        discounts = s.get("total_discount_cents", 0) or 0

        # New patients in period (excluding soft-deleted)
        new_patients_row = db.execute_query("""
            SELECT COUNT(*) as count
            FROM scheduler.patients
            WHERE clinic_id = %s AND created_at::date BETWEEN %s AND %s
              AND deleted_at IS NULL
        """, (clinic_id, start, end))
        new_patients = (new_patients_row[0]["count"] or 0) if new_patients_row else 0

        # ── Previous period (for comparison) ──────────────────────
        prev_row = db.execute_query("""
            SELECT
                COUNT(*) FILTER (WHERE status != 'CANCELLED') as total_appointments,
                COALESCE(SUM(original_price_cents) FILTER (WHERE status != 'CANCELLED'), 0) as gross_revenue_cents,
                COALESCE(SUM(original_price_cents - final_price_cents) FILTER (WHERE status != 'CANCELLED' AND discount_pct > 0), 0) as total_discount_cents
            FROM scheduler.appointments
            WHERE clinic_id = %s AND appointment_date BETWEEN %s AND %s
        """, (clinic_id, prev_start, prev_end))

        prev = prev_row[0] if prev_row else {}
        prev_total = prev.get("total_appointments", 0) or 0
        prev_gross = prev.get("gross_revenue_cents", 0) or 0

        prev_patients_row = db.execute_query("""
            SELECT COUNT(*) as count
            FROM scheduler.patients
            WHERE clinic_id = %s AND created_at::date BETWEEN %s AND %s
              AND deleted_at IS NULL
        """, (clinic_id, prev_start, prev_end))
        prev_patients = (prev_patients_row[0]["count"] or 0) if prev_patients_row else 0

        def pct_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100)

        summary = {
            "total_appointments": total,
            "confirmed_appointments": confirmed,
            "cancelled_appointments": cancelled,
            "new_patients": new_patients,
            "gross_revenue_cents": gross,
            "total_discount_cents": discounts,
            "net_revenue_cents": s.get("net_revenue_cents", 0) or 0,
            "confirmation_rate": round((confirmed / total) * 100) if total > 0 else 0,
            "cancellation_rate": round((cancelled / total) * 100) if total > 0 else 0,
            "appointments_change_pct": pct_change(total, prev_total),
            "revenue_change_pct": pct_change(gross, prev_gross),
            "patients_change_pct": pct_change(new_patients, prev_patients),
        }

        # ── Top services ──────────────────────────────────────────
        service_rows = db.execute_query("""
            SELECT
                asa.service_name,
                COUNT(DISTINCT asa.appointment_id) as count,
                COALESCE(SUM(asa.price_cents), 0) as revenue_cents
            FROM scheduler.appointment_service_areas asa
            JOIN scheduler.appointments a ON a.id = asa.appointment_id
            WHERE a.clinic_id = %s
              AND a.appointment_date BETWEEN %s AND %s
              AND a.status != 'CANCELLED'
            GROUP BY asa.service_name
            ORDER BY count DESC
            LIMIT 5
        """, (clinic_id, start, end))

        top_services = [
            {
                "service_name": r["service_name"],
                "count": r["count"],
                "revenue_cents": r["revenue_cents"] or 0,
            }
            for r in service_rows
        ]

        # ── Discount breakdown ────────────────────────────────────
        discount_rows = db.execute_query("""
            SELECT
                discount_reason as reason,
                COUNT(*) as count,
                COALESCE(SUM(original_price_cents - final_price_cents), 0) as total_discount_cents
            FROM scheduler.appointments
            WHERE clinic_id = %s
              AND appointment_date BETWEEN %s AND %s
              AND discount_pct > 0
              AND discount_reason IS NOT NULL
              AND status != 'CANCELLED'
            GROUP BY discount_reason
        """, (clinic_id, start, end))

        discount_breakdown = [
            {
                "reason": r["reason"],
                "count": r["count"],
                "total_discount_cents": r["total_discount_cents"] or 0,
            }
            for r in discount_rows
        ]

        logger.info(f"Reports loaded for {clinic_id}: period={period} appointments={total}")

        return http_response(200, {
            "period": period,
            "label": label,
            "summary": summary,
            "top_services": top_services,
            "discount_breakdown": discount_breakdown,
        })

    except Exception as e:
        logger.error(f"Reports error: {e}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": str(e),
        })
