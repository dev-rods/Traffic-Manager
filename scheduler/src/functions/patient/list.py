import json
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
from src.utils.phone import normalize_phone
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


def handler(event, context):
    """
    GET /clinics/{clinicId}/patients?search=&page=1&per_page=20
    Lista pacientes com busca opcional por nome ou telefone.
    """
    try:
        logger.info("List patients request received")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId nao fornecido"
            })

        search = extract_query_param(event, "search") or ""
        next_visit = extract_query_param(event, "next_visit") or ""  # "with" | "without" | ""
        page = int(extract_query_param(event, "page") or "1")
        per_page = int(extract_query_param(event, "per_page") or "20")
        offset = (page - 1) * per_page

        db = PostgresService()

        # Build WHERE clause
        where = "WHERE p.clinic_id = %s"
        params = [clinic_id]

        if search.strip():
            search_term = search.strip()
            # If search looks like a phone number (digits, +, spaces, dashes), normalize it
            import re
            digits_only = re.sub(r'\D', '', search_term)
            if len(digits_only) >= 6:
                normalized = normalize_phone(search_term)
                where += " AND (p.name ILIKE %s OR p.phone ILIKE %s)"
                params.extend([f"%{search_term}%", f"%{normalized}%"])
            else:
                where += " AND (p.name ILIKE %s OR p.phone ILIKE %s)"
                like = f"%{search_term}%"
                params.extend([like, like])

        # Build HAVING clause for next_visit filter (aggregate-based)
        having = ""
        if next_visit == "with":
            having = "HAVING MIN(a.appointment_date) FILTER (WHERE a.appointment_date >= CURRENT_DATE) IS NOT NULL"
        elif next_visit == "without":
            having = "HAVING MIN(a.appointment_date) FILTER (WHERE a.appointment_date >= CURRENT_DATE) IS NULL"

        # Count total (with HAVING filter applied)
        count_rows = db.execute_query(f"""
            SELECT COUNT(*) as total FROM (
                SELECT p.id
                FROM scheduler.patients p
                LEFT JOIN scheduler.appointments a ON a.patient_id = p.id AND a.status != 'CANCELLED'
                {where}
                GROUP BY p.id
                {having}
            ) sub
        """, tuple(params))
        total = count_rows[0]["total"] if count_rows else 0

        # Fetch patients with appointment stats
        rows = db.execute_query(f"""
            SELECT
                p.id,
                p.clinic_id,
                p.phone,
                p.name,
                p.gender,
                p.created_at,
                p.updated_at,
                COUNT(a.id) as total_visits,
                MAX(a.appointment_date) as last_visit,
                MIN(a.appointment_date) FILTER (WHERE a.appointment_date >= CURRENT_DATE) as next_visit,
                COALESCE(SUM(a.final_price_cents) FILTER (WHERE a.status != 'CANCELLED'), 0) as total_spent_cents
            FROM scheduler.patients p
            LEFT JOIN scheduler.appointments a ON a.patient_id = p.id AND a.status != 'CANCELLED'
            {where}
            GROUP BY p.id
            {having}
            ORDER BY p.created_at DESC
            LIMIT %s OFFSET %s
        """, tuple(params + [per_page, offset]))

        items = [_serialize_row(r) for r in rows]

        logger.info(f"Listed {len(items)} patients for {clinic_id} (total: {total})")

        return http_response(200, {
            "items": items,
            "total": total,
            "page": page,
            "per_page": per_page,
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error listing patients: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": error_msg,
        })
