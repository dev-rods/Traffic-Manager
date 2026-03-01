"""Unit tests for LeadService and GCLID extraction."""

import os
import unittest
from unittest.mock import MagicMock, patch, call

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.services.lead_service import LeadService, extract_gclid


class TestExtractGclid(unittest.TestCase):
    """Tests for the extract_gclid utility function."""

    def test_extracts_gclid_from_standard_message(self):
        msg = "Olá! Quero saber mais sobre a depilação a laser com Soprano Ice Platinum e agendar a minha primeira sessão. (ref: CjwKCAjw7pKBhAd)"
        self.assertEqual(extract_gclid(msg), "CjwKCAjw7pKBhAd")

    def test_extracts_gclid_with_spaces(self):
        msg = "Olá! (ref:  abc123def  )"
        self.assertEqual(extract_gclid(msg), "abc123def")

    def test_returns_none_without_ref(self):
        msg = "Olá! Quero agendar uma sessão."
        self.assertIsNone(extract_gclid(msg))

    def test_returns_none_for_empty_string(self):
        self.assertIsNone(extract_gclid(""))

    def test_extracts_gclid_with_special_chars(self):
        msg = "Teste (ref: Cj0KCQjw_5unBhCMARIsACZyzS3xY)"
        self.assertEqual(extract_gclid(msg), "Cj0KCQjw_5unBhCMARIsACZyzS3xY")

    def test_only_first_ref_extracted(self):
        msg = "Msg (ref: first123) e (ref: second456)"
        self.assertEqual(extract_gclid(msg), "first123")


class TestLeadServiceUpsert(unittest.TestCase):
    """Tests for LeadService.upsert_lead."""

    def setUp(self):
        self.db = MagicMock()
        self.service = LeadService(self.db)

    def test_upsert_calls_execute_write_returning(self):
        self.db.execute_write_returning.return_value = {
            "id": "uuid-1", "clinic_id": "clinic-1", "phone": "5511999990000",
            "gclid": "abc123", "booked": False,
        }

        result = self.service.upsert_lead(
            clinic_id="clinic-1",
            phone="5511999990000",
            gclid="abc123",
            raw_message="Olá (ref: abc123)",
        )

        self.db.execute_write_returning.assert_called_once()
        self.assertEqual(result["gclid"], "abc123")
        self.assertEqual(result["phone"], "5511999990000")

    def test_upsert_without_gclid(self):
        self.db.execute_write_returning.return_value = {
            "id": "uuid-2", "clinic_id": "clinic-1", "phone": "5511999990000",
            "gclid": None, "booked": False,
        }

        result = self.service.upsert_lead(
            clinic_id="clinic-1",
            phone="5511999990000",
        )

        self.db.execute_write_returning.assert_called_once()
        self.assertIsNone(result["gclid"])


class TestLeadServiceMarkAsBooked(unittest.TestCase):
    """Tests for LeadService.mark_as_booked."""

    def setUp(self):
        self.db = MagicMock()
        self.service = LeadService(self.db)

    def test_mark_as_booked_updates_lead(self):
        self.db.execute_write_returning.return_value = {
            "id": "uuid-1", "booked": True, "first_appointment_id": "appt-1",
            "first_appointment_value": 150.00,
        }

        result = self.service.mark_as_booked(
            clinic_id="clinic-1",
            phone="5511999990000",
            appointment_id="appt-1",
            appointment_value=150.00,
        )

        self.db.execute_write_returning.assert_called_once()
        self.assertTrue(result["booked"])
        self.assertEqual(result["first_appointment_id"], "appt-1")

    def test_mark_as_booked_returns_none_if_already_booked(self):
        self.db.execute_write_returning.return_value = None

        result = self.service.mark_as_booked(
            clinic_id="clinic-1",
            phone="5511999990000",
            appointment_id="appt-2",
        )

        self.assertIsNone(result)


class TestLeadServiceListLeads(unittest.TestCase):
    """Tests for LeadService.list_leads."""

    def setUp(self):
        self.db = MagicMock()
        self.service = LeadService(self.db)

    def test_list_leads_basic(self):
        self.db.execute_query.return_value = [
            {"id": "uuid-1", "phone": "5511999990000", "booked": False},
        ]

        result = self.service.list_leads(clinic_id="clinic-1")

        self.db.execute_query.assert_called_once()
        self.assertEqual(len(result), 1)

    def test_list_leads_with_booked_filter(self):
        self.db.execute_query.return_value = []

        self.service.list_leads(clinic_id="clinic-1", booked=True)

        args = self.db.execute_query.call_args
        self.assertIn("booked = %s", args[0][0])


class TestLeadServiceUpdateLead(unittest.TestCase):
    """Tests for LeadService.update_lead."""

    def setUp(self):
        self.db = MagicMock()
        self.service = LeadService(self.db)

    def test_update_lead_with_booked(self):
        self.db.execute_write_returning.return_value = {"id": "uuid-1", "booked": True}

        result = self.service.update_lead(lead_id="uuid-1", booked=True)

        self.db.execute_write_returning.assert_called_once()
        self.assertTrue(result["booked"])

    def test_update_lead_no_fields_returns_none(self):
        result = self.service.update_lead(lead_id="uuid-1")
        self.assertIsNone(result)
        self.db.execute_write_returning.assert_not_called()


if __name__ == "__main__":
    unittest.main()
