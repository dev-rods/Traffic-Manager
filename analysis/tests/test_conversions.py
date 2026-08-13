from datetime import date, datetime
from unittest.mock import MagicMock

from analysis.data.conversions import (
    historical_cohort,
    leads_in_period,
    resolve_clinic_id,
)


def _conn_returning(rows):
    """Fake psycopg2 connection whose cursor().fetchone()/fetchall() return `rows`."""
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    cursor.fetchall.return_value = rows
    cursor.fetchone.return_value = rows[0] if rows else None

    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_resolve_clinic_id_returns_clinic_id_for_customer():
    conn, cursor = _conn_returning([{"clinic_id": "essencia-sp-abc123"}])

    clinic_id = resolve_clinic_id(conn, "4601912200")

    assert clinic_id == "essencia-sp-abc123"
    cursor.execute.assert_called_once()
    query, params = cursor.execute.call_args[0]
    assert "google_ads_customer_id" in query
    assert params == ("4601912200",)


def test_resolve_clinic_id_raises_when_customer_not_found():
    conn, _ = _conn_returning([])

    try:
        resolve_clinic_id(conn, "0000000000")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "0000000000" in str(exc)


def test_leads_in_period_returns_rows_from_query():
    expected_rows = [
        {"id": "lead-1", "gclid": "abc", "created_at": datetime(2026, 7, 1), "metadata": {}},
    ]
    conn, cursor = _conn_returning(expected_rows)

    rows = leads_in_period(conn, "essencia-sp-abc123", date(2026, 7, 1), date(2026, 7, 31))

    assert rows == expected_rows
    query, params = cursor.execute.call_args[0]
    assert "leads" in query
    assert params == ("essencia-sp-abc123", date(2026, 7, 1), date(2026, 7, 31))


def test_historical_cohort_computes_latencia_and_recompras():
    raw_rows = [
        {
            "gclid": "abc",
            "click_date": datetime(2026, 1, 1),
            "first_conversion_date": date(2026, 1, 10),
            "total_conversions": 3,
            "ltv_cents": 45000,
        }
    ]
    conn, cursor = _conn_returning(raw_rows)

    cohort = historical_cohort(conn, "essencia-sp-abc123")

    assert cohort == [
        {
            "gclid": "abc",
            "click_date": datetime(2026, 1, 1),
            "first_conversion_date": date(2026, 1, 10),
            "total_conversions": 3,
            "ltv_cents": 45000,
            "latencia_dias": 9,
            "recompras": 2,
        }
    ]
    query = cursor.execute.call_args[0][0]
    assert "CONFIRMED" in query
    assert "appointment_date < CURRENT_DATE" in query
