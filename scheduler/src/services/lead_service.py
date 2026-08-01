"""Service for managing leads with GCLID tracking for Google Ads conversion."""
import logging
import re
import unicodedata
from typing import Any, Dict, List, Optional

from src.services.db.postgres import PostgresService
from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)

# Regex to extract GCLID from WhatsApp message: (ref: GCLID_VALUE)
GCLID_PATTERN = re.compile(r"\(ref:\s*([^)]+)\)")


def extract_gclid(message: str) -> Optional[str]:
    """Extract GCLID from a WhatsApp message text."""
    match = GCLID_PATTERN.search(message)
    if match:
        return match.group(1).strip()
    return None


def normalize_first_name(name: Optional[str]) -> str:
    """Normalize a name into its first-name identity token.

    Lowercase, strip accents, keep only the first whitespace-separated token.
    Used as part of the lead identity key (clinic_id + phone + first_name),
    so it MUST be applied consistently at lead creation and at appointment
    matching. Returns '' when no usable name is given.
    """
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_name = "".join(c for c in decomposed if not unicodedata.combining(c))
    first = ascii_name.strip().lower().split()
    return first[0] if first else ""


class LeadService:

    def __init__(self, db: PostgresService):
        self.db = db

    def _resolve_lead(
        self, clinic_id: str, phone: str, first_name: str, require_gclid: bool
    ) -> Optional[Dict[str, Any]]:
        """Resolve a single lead for (clinic_id, phone) with consistent preference.

        Prefers an exact first_name match, then an empty first_name (WhatsApp leads
        that never carried a name), then the most recent. `phone` must already be
        normalized. When require_gclid is True, only leads carrying a gclid match.
        """
        gclid_filter = "AND gclid IS NOT NULL AND gclid <> ''" if require_gclid else ""
        rows = self.db.execute_query(
            f"""
            SELECT id, gclid, created_at, first_name
            FROM scheduler.leads
            WHERE clinic_id = %s AND phone = %s {gclid_filter}
            ORDER BY (first_name = %s) DESC, (first_name = '') DESC, created_at DESC
            LIMIT 1
            """,
            (clinic_id, phone, first_name),
        )
        return rows[0] if rows else None

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
        Insert a new lead or update an existing one (by clinic_id + phone + first_name).

        Phone is normalized to the canonical form so the lead identity matches the
        one used on the appointment/patient side. The identity key includes first_name
        (normalized) to distinguish people who share a phone number. On conflict:
        a newly provided gclid OVERWRITES the stored one (last-click attribution),
        name/email are updated when provided, and updated_at is bumped.
        """
        phone = normalize_phone(phone)
        first_name = normalize_first_name(name)
        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.leads (clinic_id, phone, name, first_name, email, gclid, source, raw_message, metadata)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (clinic_id, phone, first_name) DO UPDATE SET
                gclid = COALESCE(NULLIF(%s, ''), scheduler.leads.gclid),
                name = COALESCE(NULLIF(%s, ''), scheduler.leads.name),
                email = COALESCE(NULLIF(%s, ''), scheduler.leads.email),
                raw_message = COALESCE(%s, scheduler.leads.raw_message),
                updated_at = NOW()
            RETURNING *
            """,
            (
                clinic_id, phone, name, first_name, email, gclid, source, raw_message,
                '{}' if not metadata else __import__('json').dumps(metadata),
                # ON CONFLICT params
                gclid, name, email, raw_message,
            ),
        )

        if result:
            logger.info(f"[LeadService] Lead upserted: clinic={clinic_id} phone={phone} first_name={first_name} gclid={gclid}")
        return result

    def mark_as_booked(
        self,
        clinic_id: str,
        phone: str,
        appointment_id: str,
        appointment_value: Optional[float] = None,
        name: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Mark the lead behind an appointment as booked (first appointment details).

        Resolves exactly one lead (same preference as record_conversion) and updates
        it by id, so the relaxed (clinic_id, phone, first_name) key never causes a
        shared-phone appointment to mark multiple lead rows.
        """
        phone = normalize_phone(phone)
        first_name = normalize_first_name(name)
        lead = self._resolve_lead(clinic_id, phone, first_name, require_gclid=False)
        if not lead:
            return None

        result = self.db.execute_write_returning(
            """
            UPDATE scheduler.leads
            SET booked = TRUE,
                first_appointment_id = %s::uuid,
                first_appointment_value = %s,
                updated_at = NOW()
            WHERE id = %s::uuid AND booked = FALSE
            RETURNING *
            """,
            (appointment_id, appointment_value, str(lead["id"])),
        )

        if result:
            logger.info(
                f"[LeadService] Lead marked as booked: clinic={clinic_id} phone={phone} "
                f"appointment={appointment_id} value={appointment_value}"
            )
        return result

    def get_lead(self, clinic_id: str, phone: str) -> Optional[Dict[str, Any]]:
        """Get a lead by clinic_id and (normalized) phone."""
        phone = normalize_phone(phone)
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
            # Keep first_name (part of the identity key) in sync with name
            sets.append("first_name = %s")
            params.append(normalize_first_name(name))
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

    def record_conversion(
        self,
        clinic_id: str,
        phone: str,
        name: Optional[str],
        appointment_id: str,
        value_cents: Optional[int],
        conversion_date: str,
    ) -> Optional[Dict[str, Any]]:
        """Register an appointment as a conversion tied to a gclid lead.

        `phone` is normalized to match the lead identity. Resolves the gclid lead
        among rows for (clinic_id, phone): prefers an exact first_name match, then a
        lead with empty first_name (WhatsApp-originated leads that never carried a
        name), then the most recent. Only records when a matching lead carries a gclid
        (organic patients are ignored). `conversion_date` should be a tz-aware
        timestamp string (e.g. "2026-07-20 18:00-03:00"); it is clamped to just after
        the click so Google never sees a conversion preceding its click. Idempotent
        per appointment via UNIQUE(appointment_id).
        """
        phone = normalize_phone(phone)
        first_name = normalize_first_name(name)
        lead_row = self._resolve_lead(clinic_id, phone, first_name, require_gclid=True)
        if not lead_row:
            logger.debug(
                f"[LeadService] No gclid lead for conversion: clinic={clinic_id} "
                f"phone={phone} first_name={first_name} appointment={appointment_id}"
            )
            return None

        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.lead_conversions
                (clinic_id, lead_id, appointment_id, gclid, value_cents, conversion_date, click_date)
            VALUES (
                %s, %s::uuid, %s::uuid, %s, %s,
                GREATEST(%s::timestamptz, %s::timestamptz + INTERVAL '1 minute'),
                %s::timestamptz
            )
            ON CONFLICT (appointment_id) DO NOTHING
            RETURNING *
            """,
            (
                clinic_id, str(lead_row["id"]), appointment_id, lead_row["gclid"],
                value_cents or 0,
                conversion_date, lead_row["created_at"],  # GREATEST(conversion, click+1min)
                lead_row["created_at"],                     # click_date column
            ),
        )
        if result:
            logger.info(
                f"[LeadService] Conversion recorded: clinic={clinic_id} phone={phone} "
                f"appointment={appointment_id} value_cents={value_cents} gclid={lead_row['gclid']}"
            )
        return result

    def update_conversion_date(self, appointment_id: str, conversion_date: str) -> None:
        """Refresh a pending conversion's date after a reschedule (clamped to click).

        Only touches conversions not yet uploaded, so already-sent conversions are
        left immutable. Keeps conversion_date consistent with the moved appointment
        and avoids reporting a session on a date it no longer occurs.
        """
        self.db.execute_write(
            """
            UPDATE scheduler.lead_conversions
            SET conversion_date = GREATEST(%s::timestamptz, click_date + INTERVAL '1 minute')
            WHERE appointment_id = %s::uuid AND uploaded_at IS NULL
            """,
            (conversion_date, appointment_id),
        )

    def get_pending_conversions(self, clinic_id: str) -> List[Dict[str, Any]]:
        """Return conversions ready to upload to Google Ads for a clinic.

        Eligibility (delay against cancellations + gclid 90-day window):
          - not yet uploaded
          - appointment still CONFIRMED (not CANCELLED)
          - appointment date already passed (session occurred; no COMPLETED status exists)
          - within 90 days of the click (lead.created_at proxy)
        """
        return self.db.execute_query(
            """
            SELECT lc.id, lc.gclid, lc.value_cents, lc.conversion_date
            FROM scheduler.lead_conversions lc
            JOIN scheduler.appointments a ON a.id = lc.appointment_id
            WHERE lc.clinic_id = %s
              AND lc.uploaded_at IS NULL
              AND a.status = 'CONFIRMED'
              AND a.appointment_date < CURRENT_DATE
              AND lc.conversion_date <= lc.click_date + INTERVAL '90 days'
            ORDER BY lc.conversion_date ASC
            """,
            (clinic_id,),
        )

    def mark_conversion_uploaded(self, conversion_id: str) -> None:
        """Mark a conversion as successfully uploaded to Google Ads."""
        self.db.execute_write(
            "UPDATE scheduler.lead_conversions SET uploaded_at = NOW() WHERE id = %s::uuid",
            (conversion_id,),
        )

    def get_accumulated_return(self, clinic_id: str, lead_id: str) -> int:
        """Total value (cents) of non-cancelled appointments for a lead (recurring return)."""
        rows = self.db.execute_query(
            """
            SELECT COALESCE(SUM(lc.value_cents), 0) AS total_cents
            FROM scheduler.lead_conversions lc
            JOIN scheduler.appointments a ON a.id = lc.appointment_id
            WHERE lc.clinic_id = %s AND lc.lead_id = %s::uuid
              AND a.status = 'CONFIRMED'
            """,
            (clinic_id, lead_id),
        )
        return int(rows[0]["total_cents"]) if rows else 0
