"""Flow simulation for lead GCLID tracking + recurring offline conversions.

Simulates the end-to-end path (lead -> appointment -> pending conversion -> upload
-> accumulated return) with an in-memory fake DB that models the routed queries.
Deterministic and dependency-free, so it runs as a normal unit test.

The eligibility rules validated here mirror the SQL in get_pending_conversions:
only CONFIRMED appointments whose date already passed and that fall within the
gclid 90-day window are returned, and never after being marked uploaded.
"""
import os
import unittest
from datetime import datetime, timedelta, timezone

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.lead_service import LeadService, normalize_first_name


def _to_dt(value):
    if isinstance(value, datetime):
        dt = value
    else:
        # accept "YYYY-MM-DD" or ISO strings
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


class FakeDB:
    """Minimal in-memory model of the leads / lead_conversions / appointments tables."""

    def __init__(self):
        self.leads = []          # list of lead dicts
        self.conversions = []    # list of conversion dicts
        self.appointments = {}   # appointment_id -> {"status", "appointment_date"}
        self._lead_seq = 0
        self._conv_seq = 0

    # --- test seeding helper ---
    def add_appointment(self, appointment_id, status, appointment_date):
        self.appointments[appointment_id] = {
            "status": status,
            "appointment_date": _to_dt(appointment_date).date(),
        }

    # --- DB interface used by LeadService ---
    def execute_write_returning(self, query, params):
        if "INSERT INTO scheduler.leads" in query:
            clinic_id, phone, name, first_name, email, gclid = params[0:6]
            existing = self._find_lead(clinic_id, phone, first_name)
            if existing:
                if gclid:
                    existing["gclid"] = existing["gclid"] or gclid
                if name:
                    existing["name"] = name
                if email:
                    existing["email"] = email
                return dict(existing)
            self._lead_seq += 1
            row = {
                "id": f"lead-{self._lead_seq}", "clinic_id": clinic_id, "phone": phone,
                "name": name, "first_name": first_name, "email": email, "gclid": gclid,
                "booked": False, "created_at": datetime.now(timezone.utc),
            }
            self.leads.append(row)
            return dict(row)

        if "INSERT INTO scheduler.lead_conversions" in query:
            # params: (clinic_id, lead_id, appointment_id, gclid, value_cents,
            #          conversion_date, click_date[for GREATEST], click_date[column])
            clinic_id, lead_id, appointment_id, gclid, value_cents = params[0:5]
            conversion_date, click_date = params[5], params[7]
            if any(c["appointment_id"] == appointment_id for c in self.conversions):
                return None  # ON CONFLICT (appointment_id) DO NOTHING
            self._conv_seq += 1
            click_dt = _to_dt(click_date)
            # mirror SQL GREATEST(conversion, click_date + 1 minute)
            conv_dt = max(_to_dt(conversion_date), click_dt + timedelta(minutes=1))
            row = {
                "id": f"conv-{self._conv_seq}", "clinic_id": clinic_id, "lead_id": lead_id,
                "appointment_id": appointment_id, "gclid": gclid, "value_cents": value_cents,
                "conversion_date": conv_dt, "click_date": click_dt,
                "uploaded_at": None,
            }
            self.conversions.append(row)
            return dict(row)

        raise AssertionError(f"Unexpected write_returning query: {query[:60]}")

    def execute_query(self, query, params):
        if "FROM scheduler.leads" in query and "gclid IS NOT NULL" in query:
            clinic_id, phone, first_name = params
            candidates = [
                l for l in self.leads
                if l["clinic_id"] == clinic_id and l["phone"] == phone and l["gclid"]
            ]
            candidates.sort(key=lambda l: (
                l["first_name"] == first_name, l["first_name"] == "", l["created_at"]
            ), reverse=True)
            return [dict(c) for c in candidates[:1]]

        if "SUM(lc.value_cents)" in query:
            clinic_id, lead_id = params
            total = sum(
                c["value_cents"] for c in self.conversions
                if c["clinic_id"] == clinic_id and c["lead_id"] == lead_id
                and self.appointments.get(c["appointment_id"], {}).get("status") == "CONFIRMED"
            )
            return [{"total_cents": total}]

        if "FROM scheduler.lead_conversions lc" in query and "JOIN scheduler.appointments" in query:
            (clinic_id,) = params
            today = datetime.now(timezone.utc).date()
            out = []
            for c in self.conversions:
                if c["clinic_id"] != clinic_id or c["uploaded_at"] is not None:
                    continue
                appt = self.appointments.get(c["appointment_id"])
                if not appt or appt["status"] != "CONFIRMED":
                    continue
                if not (appt["appointment_date"] < today):
                    continue
                if c["conversion_date"] > c["click_date"] + timedelta(days=90):
                    continue
                out.append({
                    "id": c["id"], "gclid": c["gclid"],
                    "value_cents": c["value_cents"], "conversion_date": c["conversion_date"],
                })
            out.sort(key=lambda r: r["conversion_date"])
            return out

        raise AssertionError(f"Unexpected query: {query[:60]}")

    def execute_write(self, query, params):
        if "UPDATE scheduler.lead_conversions SET uploaded_at" in query:
            (conv_id,) = params
            for c in self.conversions:
                if c["id"] == conv_id:
                    c["uploaded_at"] = datetime.now(timezone.utc)
            return 1
        raise AssertionError(f"Unexpected write query: {query[:60]}")

    def _find_lead(self, clinic_id, phone, first_name):
        for l in self.leads:
            if l["clinic_id"] == clinic_id and l["phone"] == phone and l["first_name"] == first_name:
                return l
        return None


class TestLeadConversionFlow(unittest.TestCase):

    def setUp(self):
        self.db = FakeDB()
        self.service = LeadService(self.db)
        self.clinic = "clinic-1"
        self.phone = "5511900000001"
        self.yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date().isoformat()

    def _create_gclid_lead(self, name="Maria Silva", gclid="G1"):
        return self.service.upsert_lead(
            clinic_id=self.clinic, phone=self.phone, source="landing-page",
            name=name, gclid=gclid,
        )

    def test_full_happy_path(self):
        lead = self._create_gclid_lead()
        self.assertEqual(lead["first_name"], "maria")
        self.assertEqual(lead["gclid"], "G1")

        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        conv = self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        self.assertIsNotNone(conv)

        pending = self.service.get_pending_conversions(self.clinic)
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["gclid"], "G1")
        self.assertEqual(pending[0]["value_cents"], 15000)

        self.service.mark_conversion_uploaded(pending[0]["id"])
        self.assertEqual(self.service.get_pending_conversions(self.clinic), [])

        self.assertEqual(self.service.get_accumulated_return(self.clinic, lead["id"]), 15000)

    def test_recurring_accumulates(self):
        lead = self._create_gclid_lead()
        for i, cents in enumerate([15000, 12000, 18000], start=1):
            self.db.add_appointment(f"appt-{i}", "CONFIRMED", self.yesterday)
            self.service.record_conversion(
                clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
                appointment_id=f"appt-{i}", value_cents=cents, conversion_date=self.yesterday,
            )
        self.assertEqual(len(self.service.get_pending_conversions(self.clinic)), 3)
        self.assertEqual(self.service.get_accumulated_return(self.clinic, lead["id"]), 45000)

    def test_no_conversion_without_gclid_lead(self):
        # organic phone, no lead with gclid
        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        conv = self.service.record_conversion(
            clinic_id=self.clinic, phone="5511999999999", name="Joao",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        self.assertIsNone(conv)
        self.assertEqual(self.service.get_pending_conversions(self.clinic), [])

    def test_idempotent_per_appointment(self):
        self._create_gclid_lead()
        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        first = self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        second = self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        self.assertIsNotNone(first)
        self.assertIsNone(second)
        self.assertEqual(len(self.service.get_pending_conversions(self.clinic)), 1)

    def test_future_appointment_not_eligible(self):
        self._create_gclid_lead()
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
        self.db.add_appointment("appt-1", "CONFIRMED", tomorrow)
        self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=tomorrow,
        )
        self.assertEqual(self.service.get_pending_conversions(self.clinic), [])

    def test_cancelled_appointment_not_eligible(self):
        self._create_gclid_lead()
        self.db.add_appointment("appt-1", "CANCELLED", self.yesterday)
        self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        self.assertEqual(self.service.get_pending_conversions(self.clinic), [])

    def test_outside_90_day_window_not_eligible(self):
        lead = self._create_gclid_lead()
        # force click_date far in the past so the appointment is beyond 90 days
        for l in self.db.leads:
            l["created_at"] = datetime.now(timezone.utc) - timedelta(days=120)
        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        self.assertEqual(self.service.get_pending_conversions(self.clinic), [])

    def test_phone_format_mismatch_still_matches(self):
        # Regression: LP creates the lead with a formatted phone; the appointment
        # flow uses the digits-only canonical form. Both must resolve to one lead.
        self.service.upsert_lead(
            clinic_id=self.clinic, phone="(11) 90000-0001", source="landing-page",
            name="Maria Silva", gclid="G1",
        )
        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        conv = self.service.record_conversion(
            clinic_id=self.clinic, phone="5511900000001", name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        self.assertIsNotNone(conv)
        self.assertEqual(len(self.service.get_pending_conversions(self.clinic)), 1)

    def test_upsert_normalizes_phone_no_duplicate(self):
        self.service.upsert_lead(
            clinic_id=self.clinic, phone="(11) 90000-0001", name="Maria Silva", gclid="G1",
        )
        self.service.upsert_lead(
            clinic_id=self.clinic, phone="5511900000001", name="Maria Silva", gclid="G1",
        )
        self.assertEqual(len(self.db.leads), 1)

    def test_conversion_never_precedes_click(self):
        # Click after the appointment date -> conversion must be clamped past the click
        # so Google never sees CONVERSION_PRECEDES_EVENT.
        lead = self._create_gclid_lead()  # created_at = now
        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        conv = self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=15000, conversion_date=self.yesterday,
        )
        click = next(l for l in self.db.leads if l["id"] == lead["id"])["created_at"]
        self.assertGreater(conv["conversion_date"], click)

    def test_whatsapp_lead_without_name_still_matches(self):
        # WhatsApp lead created without a name (first_name = ''), carries gclid
        self.service.upsert_lead(
            clinic_id=self.clinic, phone=self.phone, source="whatsapp", gclid="G-WA",
        )
        self.db.add_appointment("appt-1", "CONFIRMED", self.yesterday)
        # appointment brings the name; must still resolve the empty-first_name lead
        conv = self.service.record_conversion(
            clinic_id=self.clinic, phone=self.phone, name="Maria Silva",
            appointment_id="appt-1", value_cents=20000, conversion_date=self.yesterday,
        )
        self.assertIsNotNone(conv)
        self.assertEqual(conv["gclid"], "G-WA")


if __name__ == "__main__":
    unittest.main()
