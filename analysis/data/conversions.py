"""Consultas determinísticas de conversão real no Supabase do scheduler."""
from datetime import date
from typing import Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection(supabase_config: Dict):
    return psycopg2.connect(
        host=supabase_config["host"],
        port=supabase_config["port"],
        dbname=supabase_config["dbname"],
        user=supabase_config["user"],
        password=supabase_config["password"],
        options="-c search_path=scheduler,public",
    )


def resolve_clinic_id(conn, customer_id: str) -> str:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT clinic_id FROM clinics WHERE google_ads_customer_id = %s",
            (customer_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Nenhuma clinic encontrada para customer_id={customer_id}")
    return row["clinic_id"]


def leads_in_period(conn, clinic_id: str, start: date, end: date) -> List[Dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, gclid, created_at, metadata
            FROM leads
            WHERE clinic_id = %s
              AND created_at::date BETWEEN %s AND %s
            """,
            (clinic_id, start, end),
        )
        return cur.fetchall()


def historical_cohort(conn, clinic_id: str) -> List[Dict]:
    """Coorte all-time: para cada gclid com >=1 conversão real, LTV/latência/recompras.

    Conversão real = appointments.status = 'CONFIRMED' AND appointment_date < CURRENT_DATE,
    idêntico a LeadService.get_pending_conversions.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                lc.gclid,
                MIN(lc.click_date) AS click_date,
                MIN(lc.conversion_date) AS first_conversion_date,
                COUNT(*) AS total_conversions,
                SUM(lc.value_cents) AS ltv_cents
            FROM lead_conversions lc
            JOIN appointments a ON a.id = lc.appointment_id
            WHERE lc.clinic_id = %s
              AND a.status = 'CONFIRMED'
              AND a.appointment_date < CURRENT_DATE
            GROUP BY lc.gclid
            """,
            (clinic_id,),
        )
        rows = cur.fetchall()

    for row in rows:
        click_date = row["click_date"]
        first_conversion = row["first_conversion_date"]
        click_date_only = click_date.date() if hasattr(click_date, "date") else click_date
        row["latencia_dias"] = (first_conversion - click_date_only).days
        row["recompras"] = max(row["total_conversions"] - 1, 0)

    return rows
