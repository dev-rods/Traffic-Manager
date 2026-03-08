import json
import logging
from datetime import datetime, date, time, timedelta

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _get_week_bounds(today):
    """Returns (monday, sunday) of the current week."""
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)
    return monday, sunday


def _get_month_bounds(today):
    """Returns (first_day, last_day) of the current month."""
    first = today.replace(day=1)
    if today.month == 12:
        last = today.replace(year=today.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        last = today.replace(month=today.month + 1, day=1) - timedelta(days=1)
    return first, last


def handler(event, context):
    """
    Handler para GET /clinics/{clinicId}/dashboard
    Agrega dados do dia, semana e mes para o painel da clinica.
    """
    try:
        logger.info("Dashboard request received")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId nao fornecido no path"
            })

        db = PostgresService()
        today = date.today()
        week_start, week_end = _get_week_bounds(today)
        month_start, month_end = _get_month_bounds(today)

        # ── Summary (today) ──────────────────────────────────────
        summary_rows = db.execute_query("""
            SELECT
                COUNT(*) as total_appointments,
                COUNT(*) FILTER (WHERE status = 'CONFIRMED') as confirmed_appointments,
                COUNT(*) FILTER (WHERE status = 'CANCELLED') as cancelled_appointments,
                COALESCE(SUM(final_price_cents) FILTER (WHERE status != 'CANCELLED'), 0) as net_revenue_cents,
                COALESCE(SUM(original_price_cents) FILTER (WHERE status != 'CANCELLED'), 0) as gross_revenue_cents,
                COALESCE(SUM(original_price_cents - final_price_cents) FILTER (WHERE status != 'CANCELLED' AND discount_pct > 0), 0) as total_discount_cents,
                COUNT(*) FILTER (WHERE status = 'PENDING') as pending_appointments
            FROM scheduler.appointments
            WHERE clinic_id = %s AND appointment_date = %s
        """, (clinic_id, today))

        s = summary_rows[0] if summary_rows else {}
        total = s.get("total_appointments", 0) or 0
        confirmed = s.get("confirmed_appointments", 0) or 0
        cancelled = s.get("cancelled_appointments", 0) or 0

        summary = {
            "total_appointments": total,
            "confirmed_appointments": confirmed,
            "cancelled_appointments": cancelled,
            "new_patients": 0,
            "gross_revenue_cents": s.get("gross_revenue_cents", 0) or 0,
            "total_discount_cents": s.get("total_discount_cents", 0) or 0,
            "net_revenue_cents": s.get("net_revenue_cents", 0) or 0,
            "confirmation_rate": round((confirmed / total) * 100) if total > 0 else 0,
            "cancellation_rate": round((cancelled / total) * 100) if total > 0 else 0,
        }

        # ── Today's appointments ─────────────────────────────────
        appt_rows = db.execute_query("""
            SELECT
                a.id,
                a.appointment_date,
                a.start_time,
                a.end_time,
                a.status,
                a.full_name as patient_name,
                a.total_duration_minutes as duration_minutes,
                a.discount_pct,
                a.discount_reason,
                a.original_price_cents,
                a.final_price_cents,
                p.phone as patient_phone,
                p.name as patient_db_name,
                pr.name as professional
            FROM scheduler.appointments a
            LEFT JOIN scheduler.patients p ON p.id = a.patient_id
            LEFT JOIN scheduler.professionals pr ON pr.id = a.professional_id
            WHERE a.clinic_id = %s AND a.appointment_date = %s
            ORDER BY a.start_time ASC
        """, (clinic_id, today))

        # Get areas for each appointment
        appt_ids = [r["id"] for r in appt_rows]
        areas_by_appt = {}
        if appt_ids:
            area_rows = db.execute_query("""
                SELECT appointment_id, service_name, area_name
                FROM scheduler.appointment_service_areas
                WHERE appointment_id = ANY(%s)
            """, (appt_ids,))
            for ar in area_rows:
                aid = str(ar["appointment_id"])
                if aid not in areas_by_appt:
                    areas_by_appt[aid] = {"service_name": ar["service_name"], "areas": []}
                areas_by_appt[aid]["areas"].append(ar["area_name"])

        today_appointments = []
        for row in appt_rows:
            aid = str(row["id"])
            appt_info = areas_by_appt.get(aid, {})
            scheduled_at = datetime.combine(row["appointment_date"], row["start_time"]).isoformat()

            today_appointments.append({
                "id": aid,
                "patient_name": row.get("patient_name") or row.get("patient_db_name") or "Sem nome",
                "patient_phone": row.get("patient_phone") or "",
                "service_name": appt_info.get("service_name", ""),
                "areas": appt_info.get("areas", []),
                "professional": row.get("professional") or "",
                "scheduled_at": scheduled_at,
                "duration_minutes": row.get("duration_minutes") or 0,
                "status": (row.get("status") or "PENDING").lower(),
                "original_price_cents": row.get("original_price_cents") or 0,
                "discount_pct": row.get("discount_pct") or 0,
                "discount_reason": row.get("discount_reason"),
                "final_price_cents": row.get("final_price_cents") or 0,
            })

        # ── Daily counts (current week) ─────────────────────────
        daily_rows = db.execute_query("""
            SELECT appointment_date, COUNT(*) as count
            FROM scheduler.appointments
            WHERE clinic_id = %s
              AND appointment_date BETWEEN %s AND %s
              AND status != 'CANCELLED'
            GROUP BY appointment_date
            ORDER BY appointment_date
        """, (clinic_id, week_start, week_end))

        daily_map = {str(r["appointment_date"]): r["count"] for r in daily_rows}
        daily_counts = []
        for i in range(7):
            d = week_start + timedelta(days=i)
            daily_counts.append({
                "date": d.isoformat(),
                "count": daily_map.get(str(d), 0),
            })

        # ── Discount breakdown (current month) ──────────────────
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
        """, (clinic_id, month_start, month_end))

        discount_breakdown = [
            {
                "reason": r["reason"],
                "count": r["count"],
                "total_discount_cents": r["total_discount_cents"] or 0,
            }
            for r in discount_rows
        ]

        # ── Top services (current month) ─────────────────────────
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
        """, (clinic_id, month_start, month_end))

        top_services = [
            {
                "service_id": "",
                "service_name": r["service_name"],
                "count": r["count"],
                "revenue_cents": r["revenue_cents"] or 0,
            }
            for r in service_rows
        ]

        logger.info(f"Dashboard loaded for {clinic_id}: {summary['total_appointments']} appointments today")

        return http_response(200, {
            "summary": summary,
            "today_appointments": today_appointments,
            "daily_counts": daily_counts,
            "discount_breakdown": discount_breakdown,
            "top_services": top_services,
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Dashboard error: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": error_msg,
        })
