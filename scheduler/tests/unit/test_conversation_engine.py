"""Unit tests for ConversationEngine._identify_input and _extract_dynamic_selection."""

import os
import unittest
from unittest.mock import MagicMock, patch

# Set required env var before importing the module
os.environ.setdefault("CONVERSATION_SESSIONS_TABLE", "test-sessions")

from src.providers.whatsapp_provider import IncomingMessage
from src.services.conversation_engine import ConversationEngine, ConversationState


def _make_incoming(content="", button_id=None):
    return IncomingMessage(
        message_id="msg-1",
        phone="5511999990000",
        sender_name="Test",
        timestamp=0,
        message_type="BUTTON_RESPONSE" if button_id else "TEXT",
        content=content,
        button_id=button_id,
    )


def _make_engine():
    with patch("src.services.conversation_engine.boto3"):
        engine = ConversationEngine(
            db=MagicMock(),
            template_service=MagicMock(),
            availability_engine=MagicMock(),
            appointment_service=MagicMock(),
            provider=MagicMock(),
            message_tracker=MagicMock(),
        )
    return engine


class TestIdentifyInputButtonClick(unittest.TestCase):
    """Button clicks (button_id) always have highest priority."""

    def setUp(self):
        self.engine = _make_engine()

    def test_button_id_returned_directly(self):
        incoming = _make_incoming(button_id="schedule")
        result = self.engine._identify_input(incoming, {"state": "MAIN_MENU"})
        self.assertEqual(result, "schedule")

    def test_button_id_ignores_content(self):
        incoming = _make_incoming(content="some random text", button_id="faq")
        result = self.engine._identify_input(incoming, {"state": "MAIN_MENU"})
        self.assertEqual(result, "faq")


class TestIdentifyInputGlobalShortcuts(unittest.TestCase):
    """Global shortcuts work regardless of current state."""

    def setUp(self):
        self.engine = _make_engine()
        self.session = {"state": "MAIN_MENU"}

    def test_voltar(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("voltar"), self.session), "back")

    def test_back(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("back"), self.session), "back")

    def test_zero(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("0"), self.session), "back")

    def test_menu(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("menu"), self.session), "main_menu")

    def test_oi(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("oi"), self.session), "main_menu")

    def test_humano(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("humano"), self.session), "human")

    def test_atendente(self):
        self.assertEqual(self.engine._identify_input(_make_incoming("atendente"), self.session), "human")

    def test_empty_returns_empty(self):
        self.assertEqual(self.engine._identify_input(_make_incoming(""), self.session), "")


class TestIdentifyInputNumeric(unittest.TestCase):
    """Numeric input maps to button index (1-based)."""

    def setUp(self):
        self.engine = _make_engine()
        self.session = {"state": "MAIN_MENU"}

    def test_digit_1_maps_to_first_button(self):
        result = self.engine._identify_input(_make_incoming("1"), self.session)
        self.assertEqual(result, "schedule")

    def test_digit_2_maps_to_second_button(self):
        result = self.engine._identify_input(_make_incoming("2"), self.session)
        self.assertEqual(result, "reschedule")

    def test_digit_3_maps_to_third_button(self):
        result = self.engine._identify_input(_make_incoming("3"), self.session)
        self.assertEqual(result, "faq")

    def test_out_of_range_falls_through(self):
        result = self.engine._identify_input(_make_incoming("9"), self.session)
        self.assertEqual(result, "9")

    def test_dynamic_buttons_used_when_present(self):
        session = {
            "state": "AVAILABLE_DAYS",
            "dynamic_buttons": [
                {"id": "day_2026-02-10", "label": "2026-02-10"},
                {"id": "day_2026-02-11", "label": "2026-02-11"},
            ],
        }
        result = self.engine._identify_input(_make_incoming("2"), session)
        self.assertEqual(result, "day_2026-02-11")


class TestIdentifyInputFuzzyMatch(unittest.TestCase):
    """LIKE '%text%' matching against button labels."""

    def setUp(self):
        self.engine = _make_engine()
        self.session = {"state": "MAIN_MENU"}

    def test_agendar_matches_schedule(self):
        result = self.engine._identify_input(_make_incoming("agendar"), self.session)
        self.assertEqual(result, "schedule")

    def test_remarcar_matches_reschedule(self):
        result = self.engine._identify_input(_make_incoming("remarcar"), self.session)
        self.assertEqual(result, "reschedule")

    def test_duvida_matches_faq(self):
        result = self.engine._identify_input(_make_incoming("duvida"), self.session)
        self.assertEqual(result, "faq")

    def test_ambiguous_sessao_falls_through(self):
        """'sessao' matches all 3 MAIN_MENU buttons — should NOT resolve."""
        result = self.engine._identify_input(_make_incoming("sessao"), self.session)
        self.assertEqual(result, "sessao")

    def test_preco_matches_in_schedule_menu(self):
        session = {"state": "SCHEDULE_MENU"}
        result = self.engine._identify_input(_make_incoming("preco"), session)
        self.assertEqual(result, "price_table")

    def test_partial_word_matches(self):
        result = self.engine._identify_input(_make_incoming("remar"), self.session)
        self.assertEqual(result, "reschedule")

    def test_case_insensitive(self):
        result = self.engine._identify_input(_make_incoming("AGENDAR"), self.session)
        self.assertEqual(result, "schedule")

    def test_no_match_returns_raw_text(self):
        result = self.engine._identify_input(_make_incoming("xyz123"), self.session)
        self.assertEqual(result, "xyz123")

    def test_fuzzy_on_dynamic_buttons(self):
        session = {
            "state": "FAQ_MENU",
            "dynamic_buttons": [
                {"id": "faq_depilacao", "label": "Como funciona a depilacao?"},
                {"id": "faq_preco", "label": "Qual o preco?"},
            ],
        }
        result = self.engine._identify_input(_make_incoming("depilacao"), session)
        self.assertEqual(result, "faq_depilacao")


class TestExtractDynamicSelection(unittest.TestCase):
    """_extract_dynamic_selection stores prefixed values in session."""

    def setUp(self):
        self.engine = _make_engine()

    def test_day_prefix(self):
        session = {}
        self.engine._extract_dynamic_selection("day_2026-02-10", session)
        self.assertEqual(session["selected_date"], "2026-02-10")

    def test_time_prefix(self):
        session = {}
        self.engine._extract_dynamic_selection("time_14:00", session)
        self.assertEqual(session["selected_time"], "14:00")

    def test_newday_prefix(self):
        session = {}
        self.engine._extract_dynamic_selection("newday_2026-03-01", session)
        self.assertEqual(session["selected_new_date"], "2026-03-01")

    def test_newtime_prefix(self):
        session = {}
        self.engine._extract_dynamic_selection("newtime_10:30", session)
        self.assertEqual(session["selected_new_time"], "10:30")

    def test_faq_prefix(self):
        session = {}
        self.engine._extract_dynamic_selection("faq_depilacao", session)
        self.assertEqual(session["selected_faq_key"], "depilacao")

    def test_no_prefix_no_change(self):
        session = {}
        self.engine._extract_dynamic_selection("some_text", session)
        self.assertNotIn("selected_date", session)
        self.assertNotIn("selected_time", session)
        self.assertNotIn("selected_faq_key", session)

    def test_plain_text_no_change(self):
        session = {"existing_key": "value"}
        self.engine._extract_dynamic_selection("hello", session)
        self.assertEqual(session, {"existing_key": "value"})


if __name__ == "__main__":
    unittest.main()
