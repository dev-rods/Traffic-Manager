"""Unit tests for the database -> Google Sheet lead mirror.

Covers the pure functions only: phone matching, the presence index built from the
sheet, and the database row -> sheet row mapping. The Google Sheets and PostgreSQL
calls are I/O and are exercised by running the script with its default dry-run.

The phone tests carry the real drift the mirror has to survive: the sheet stores
phones typed by hand and rendered as numbers (11999961308) while the database
normalizes to 55DDDNNNNNNNNN, and the mobile 9th digit is present in one and absent
in the other often enough to matter.
"""
import os
import unittest
from datetime import datetime, timezone

os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.scripts.mirror_leads_to_sheet import (
    existing_phone_keys,
    phone_key,
    to_sheet_row,
)


class TestPhoneKey(unittest.TestCase):
    def test_country_code_present_or_absent_matches(self):
        self.assertEqual(phone_key("5511999961308"), phone_key("11999961308"))

    def test_formatting_is_ignored(self):
        self.assertEqual(phone_key("+55 (11) 99996-1308"), phone_key("5511999961308"))

    def test_sheet_number_rendering_matches(self):
        # openpyxl/Sheets hand back the phone column as a float
        self.assertEqual(phone_key(11999961308.0), phone_key("5511999961308"))

    def test_missing_ninth_digit_still_matches(self):
        # 8-digit legacy mobile vs the 9-digit form of the same line
        self.assertEqual(phone_key("551199961308"), phone_key("5511999961308"))

    def test_different_numbers_do_not_collide(self):
        self.assertNotEqual(phone_key("5511999961308"), phone_key("5511910522808"))

    def test_different_ddd_does_not_collide(self):
        self.assertNotEqual(phone_key("5511987471357"), phone_key("5541987471357"))

    def test_empty_input_is_empty_key(self):
        self.assertEqual(phone_key(None), "")
        self.assertEqual(phone_key(""), "")


class TestExistingPhoneKeys(unittest.TestCase):
    def test_skips_header_and_indexes_phone_column(self):
        rows = [
            ["Datetime", "origem", "Nome", "Telefone", "Procedimentos", "Observações"],
            ["2026/08/06 10:21:04", "depilacao", "Tamyres", "11999961308", "", ""],
        ]

        self.assertEqual(existing_phone_keys(rows), {phone_key("5511999961308")})

    def test_tolerates_short_rows_and_blank_phones(self):
        rows = [
            ["Datetime", "origem", "Nome", "Telefone"],
            ["2026/08/06 10:21:04", "depilacao", "Sem telefone"],  # row ends early
            ["2026/08/06 11:00:00", "depilacao", "Vazio", ""],
            ["2026/08/06 12:00:00", "depilacao", "Ok", "11999961308"],
        ]

        self.assertEqual(existing_phone_keys(rows), {phone_key("11999961308")})

    def test_empty_sheet_has_no_keys(self):
        self.assertEqual(existing_phone_keys([]), set())


def _lead(**overrides):
    lead = {
        "name": "Carolina",
        "phone": "5511910522808",
        "source": "landing-page",
        # 2026-08-14 20:07 UTC is 17:07 in São Paulo
        "created_at": datetime(2026, 8, 14, 20, 7, 41, tzinfo=timezone.utc),
        "metadata": {},
        "raw_message": None,
    }
    lead.update(overrides)
    return lead


class TestToSheetRow(unittest.TestCase):
    def test_converts_utc_to_clinic_local_time(self):
        self.assertEqual(to_sheet_row(_lead())[0], "2026/08/14 17:07:41")

    def test_naive_timestamp_is_read_as_utc(self):
        row = to_sheet_row(_lead(created_at=datetime(2026, 8, 14, 20, 7, 41)))

        self.assertEqual(row[0], "2026/08/14 17:07:41")

    def test_landing_page_source_becomes_depilacao_origem(self):
        self.assertEqual(to_sheet_row(_lead())[1], "depilacao")

    def test_known_source_passes_through(self):
        self.assertEqual(to_sheet_row(_lead(source="harmonizacao"))[1], "harmonizacao")

    def test_unknown_source_is_kept_verbatim(self):
        self.assertEqual(to_sheet_row(_lead(source="instagram"))[1], "instagram")

    def test_phone_is_written_without_country_code(self):
        # matches how every existing row in the sheet is stored
        self.assertEqual(to_sheet_row(_lead())[3], "11910522808")

    def test_procedimentos_list_is_joined(self):
        row = to_sheet_row(_lead(metadata={"procedimentos": ["Axila", "Virilha"]}))

        self.assertEqual(row[4], "Axila, Virilha")

    def test_observacoes_falls_back_to_raw_message(self):
        row = to_sheet_row(_lead(raw_message="Quero saber o valor"))

        self.assertEqual(row[5], "Quero saber o valor")

    def test_metadata_observacoes_wins_over_raw_message(self):
        row = to_sheet_row(
            _lead(metadata={"observacoes": "do formulário"}, raw_message="do whatsapp")
        )

        self.assertEqual(row[5], "do formulário")

    def test_missing_optional_fields_become_empty_strings(self):
        row = to_sheet_row(_lead(name=None, metadata=None, raw_message=None))

        self.assertEqual(row[2], "")
        self.assertEqual(row[4], "")
        self.assertEqual(row[5], "")

    def test_row_has_exactly_the_sheet_columns(self):
        self.assertEqual(len(to_sheet_row(_lead())), 6)


if __name__ == "__main__":
    unittest.main()
