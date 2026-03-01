"""Service for managing leads with GCLID tracking for Google Ads conversion."""
import logging
import re
from typing import Any, Dict, Optional

from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)

# Regex to extract GCLID from WhatsApp message: (ref: GCLID_VALUE)
GCLID_PATTERN = re.compile(r"\(ref:\s*([^)]+)\)")


def extract_gclid(message: str) -> Optional[str]:
    """Extract GCLID from a WhatsApp message text."""
    match = GCLID_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    return None


class LeadService:

    def __init__(self, db: PostgresService):
        self.db = db

    def upsert_lead(
        self,
        clinic_id: str,
        phone: str,
        source: str = "whatsapp",
        name: Optional[str] = None,
        email: Optional[str] = None,
        gclid: Optional[str] = None,
        raw_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Insert a new lead or update an existing one (by clinic_id + phone).

        On conflict: updates gclid (if provided and not already set),
        name/email (if provided), and updated_at.
        """
        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.leads (clinic_id, phone, name, email, gclid, source, raw_message, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (clinic_id, phone) DO UPDATE SET
                gclid = COALESCE(NULLIF(%s, ''), scheduler.leads.gclid),
                name = COALESCE(NULLIF(%s, ''), scheduler.leads.name),
                email = COALESCE(NULLIF(%s, ''), scheduler.leads.email),
                raw_message = COALESCE(%s, scheduler.leads.raw_message),
                updated_at = NOW()
            RETURNING *
            """,
            (
                clinic_id, phone, name, email, gclid, source, raw_message,
                '{}' if not metadata else __import__('json').dumps(metadata),
                # ON CONFLICT params
                gclid, name, email, raw_message,
            ),
        )

        if result:
            logger.info(f"[LeadService] Lead upserted: clinic={clinic_id} phone={phone} gclid={gclid}")
        return result

    def mark_as_booked(
        self,
        clinic_id: str,
        phone: str,
        appointment_id: str,
        appointment_value: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark an existing lead as booked with the first appointment details."""
        result = self.db.execute_write_returning(
            """
            UPDATE scheduler.leads
            SET booked = TRUE,
                first_appointment_id = %s::uuid,
                first_appointment_value = %s,
                updated_at = NOW()
            WHERE clinic_id = %s AND phone = %s AND booked = FALSE
            RETURNING *
            """,
            (appointment_id, appointment_value, clinic_id, phone),
        )

        if result:
            logger.info(
                f"[LeadService] Lead marked as booked: clinic={clinic_id} phone={phone} "
                f"appointment={appointment_id} value={appointment_value}"
            )
        return result

    def get_lead(self, clinic_id: str, phone: str) -> Optional[Dict[str, Any]]:
        """Get a lead by clinic_id and phone."""
        rows = self.db.execute_query(
            "SELECT * FROM scheduler.leads WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )
        return rows[0] if rows else None

    def list_leads(
        self,
        clinic_id: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        booked: Optional[bool] = None,
        limit: int = 50,
        offset: int = 0,
    ):
        """List leads for a clinic with optional filters."""
        conditions = ["clinic_id = %s"]
        params = [clinic_id]

        if start_date:
            conditions.append("created_at >= %s")
            params.append(start_date)
        if end_date:
            conditions.append("created_at <= %s")
            params.append(end_date)
        if booked is not None:
            conditions.append("booked = %s")
            params.append(booked)

        where = " AND ".join(conditions)
        params.extend([limit, offset])

        return self.db.execute_query(
            f"SELECT * FROM scheduler.leads WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
            tuple(params),
        )

    def update_lead(
        self,
        lead_id: str,
        booked: Optional[bool] = None,
        first_appointment_value: Optional[float] = None,
        name: Optional[str] = None,
        email: Optional[str] = None,
        gclid: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Manually update a lead's fields."""
        sets = []
        params = []

        if booked is not None:
            sets.append("booked = %s")
            params.append(booked)
        if first_appointment_value is not None:
            sets.append("first_appointment_value = %s")
            params.append(first_appointment_value)
        if name is not None:
            sets.append("name = %s")
            params.append(name)
        if email is not None:
            sets.append("email = %s")
            params.append(email)
        if gclid is not None:
            sets.append("gclid = %s")
            params.append(gclid)

        if not sets:
            return None

        sets.append("updated_at = NOW()")
        params.append(lead_id)

        return self.db.execute_write_returning(
            f"UPDATE scheduler.leads SET {', '.join(sets)} WHERE id = %s::uuid RETURNING *",
            tuple(params),
        )
