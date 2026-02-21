import os
import time
import uuid
import unicodedata
import logging
from datetime import date, datetime, time as dt_time, timedelta
from decimal import Decimal
from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.services.db.postgres import PostgresService
from src.services.template_service import TemplateService
from src.services.message_tracker import MessageTracker
from src.providers.whatsapp_provider import IncomingMessage, WhatsAppProvider

logger = logging.getLogger(__name__)

class ConversationState(str, Enum):
    WELCOME = "WELCOME"
    MAIN_MENU = "MAIN_MENU"
    SCHEDULE_MENU = "SCHEDULE_MENU"
    PRICE_TABLE = "PRICE_TABLE"
    SELECT_SERVICES = "SELECT_SERVICES"
    CONFIRM_SERVICES = "CONFIRM_SERVICES"
    SELECT_AREAS = "SELECT_AREAS"
    CONFIRM_AREAS = "CONFIRM_AREAS"
    AVAILABLE_DAYS = "AVAILABLE_DAYS"
    SELECT_DATE = "SELECT_DATE"
    SELECT_TIME = "SELECT_TIME"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    BOOKED = "BOOKED"
    RESCHEDULE_LOOKUP = "RESCHEDULE_LOOKUP"
    SELECT_APPOINTMENT = "SELECT_APPOINTMENT"
    SHOW_CURRENT_APPOINTMENT = "SHOW_CURRENT_APPOINTMENT"
    SELECT_NEW_DATE = "SELECT_NEW_DATE"
    SELECT_NEW_TIME = "SELECT_NEW_TIME"
    CONFIRM_RESCHEDULE = "CONFIRM_RESCHEDULE"
    RESCHEDULED = "RESCHEDULED"
    FAQ_MENU = "FAQ_MENU"
    FAQ_ANSWER = "FAQ_ANSWER"
    CANCEL_LOOKUP = "CANCEL_LOOKUP"
    SELECT_CANCEL_APPOINTMENT = "SELECT_CANCEL_APPOINTMENT"
    CONFIRM_CANCEL = "CONFIRM_CANCEL"
    CANCELLED = "CANCELLED"
    FAREWELL = "FAREWELL"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    HUMAN_ATTENDANT_ACTIVE = "HUMAN_ATTENDANT_ACTIVE"
    UNRECOGNIZED = "UNRECOGNIZED"


@dataclass
class OutgoingMessage:
    message_type: str  # text, buttons, list
    content: str
    buttons: Optional[List[Dict[str, str]]] = None
    sections: Optional[List[Dict]] = None
    button_text: Optional[str] = None


# State machine configuration
STATE_CONFIG = {
    ConversationState.MAIN_MENU: {
        "template_key": "MAIN_MENU",
        "buttons": [
            {"id": "schedule", "label": "Agendar sessão"},
            {"id": "reschedule", "label": "Remarcar sessão"},
            {"id": "cancel_session", "label": "Cancelar sessão"},
            {"id": "faq", "label": "Saber mais sobre atendimento"},
        ],
        "transitions": {
            "schedule": ConversationState.SCHEDULE_MENU,
            "reschedule": ConversationState.RESCHEDULE_LOOKUP,
            "cancel_session": ConversationState.CANCEL_LOOKUP,
            "faq": ConversationState.FAQ_MENU,
            "human": ConversationState.HUMAN_HANDOFF,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": None,
    },
    ConversationState.SCHEDULE_MENU: {
        "template_key": "SCHEDULE_MENU",
        "buttons": [
            {"id": "price_table", "label": "Ver tabela de preços"},
            {"id": "schedule_now", "label": "Agendar agora"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "price_table": ConversationState.PRICE_TABLE,
            "schedule_now": ConversationState.SELECT_SERVICES,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
    },
    ConversationState.PRICE_TABLE: {
        "template_key": "PRICE_TABLE",
        "buttons": [
            {"id": "schedule_now", "label": "Agendar agora"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "schedule_now": ConversationState.SELECT_SERVICES,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SCHEDULE_MENU,
    },
    ConversationState.SELECT_SERVICES: {
        "template_key": "SELECT_SERVICES",
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SCHEDULE_MENU,
        "input_type": "free_text",
    },
    ConversationState.CONFIRM_SERVICES: {
        "template_key": "CONFIRM_SERVICES",
        "buttons": [
            {"id": "confirm_services", "label": "Confirmar"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "confirm_services": ConversationState.SELECT_AREAS,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SELECT_SERVICES,
    },
    ConversationState.SELECT_AREAS: {
        "template_key": "SELECT_AREAS",
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SELECT_SERVICES,
        "input_type": "free_text",
    },
    ConversationState.CONFIRM_AREAS: {
        "template_key": "CONFIRM_AREAS",
        "buttons": [
            {"id": "confirm_areas", "label": "Confirmar"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "confirm_areas": ConversationState.AVAILABLE_DAYS,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SELECT_AREAS,
    },
    ConversationState.AVAILABLE_DAYS: {
        "template_key": "AVAILABLE_DAYS",
        "buttons": [],  # Dynamic — populated by on_enter
        "transitions": {},  # Dynamic — date selection
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.CONFIRM_AREAS,
        "input_type": "dynamic_selection",
    },
    ConversationState.SELECT_TIME: {
        "template_key": "SELECT_TIME",
        "buttons": [],  # Dynamic
        "transitions": {},  # Dynamic
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.AVAILABLE_DAYS,
        "input_type": "dynamic_selection",
    },
    ConversationState.CONFIRM_BOOKING: {
        "template_key": "CONFIRM_BOOKING",
        "buttons": [
            {"id": "confirm", "label": "Confirmar"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "confirm": ConversationState.BOOKED,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SELECT_TIME,
    },
    ConversationState.BOOKED: {
        "template_key": "BOOKED",
        "buttons": [
            {"id": "farewell", "label": "Finalizar atendimento"},
            {"id": "main_menu", "label": "Menu principal"},
            {"id": "human", "label": "Falar com atendente"},
        ],
        "transitions": {
            "farewell": ConversationState.FAREWELL,
            "main_menu": ConversationState.MAIN_MENU,
            "human": ConversationState.HUMAN_HANDOFF,
        },
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
    ConversationState.FAREWELL: {
        "template_key": "FAREWELL",
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.WELCOME,
        "previous": None,
    },
    ConversationState.RESCHEDULE_LOOKUP: {
        "template_key": None,  # Determined by on_enter (FOUND or NOT_FOUND)
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
        "input_type": "dynamic_selection",
    },
    ConversationState.SELECT_APPOINTMENT: {
        "template_key": "RESCHEDULE_SELECT_APPOINTMENT",
        "buttons": [],  # Dynamic — appointment list
        "transitions": {},  # Dynamic
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
        "input_type": "dynamic_selection",
    },
    ConversationState.SHOW_CURRENT_APPOINTMENT: {
        "template_key": "RESCHEDULE_FOUND",
        "buttons": [],  # Dynamic — available days
        "transitions": {},  # Dynamic
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
        "input_type": "dynamic_selection",
    },
    ConversationState.SELECT_NEW_TIME: {
        "template_key": "SELECT_TIME",
        "buttons": [],  # Dynamic
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SHOW_CURRENT_APPOINTMENT,
        "input_type": "dynamic_selection",
    },
    ConversationState.CONFIRM_RESCHEDULE: {
        "template_key": "CONFIRM_BOOKING",
        "buttons": [
            {"id": "confirm", "label": "Confirmar"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "confirm": ConversationState.RESCHEDULED,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SELECT_NEW_TIME,
    },
    ConversationState.RESCHEDULED: {
        "template_key": "RESCHEDULED",
        "buttons": [
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "main_menu": ConversationState.MAIN_MENU,
        },
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
    ConversationState.FAQ_MENU: {
        "template_key": "FAQ_MENU",
        "buttons": [],  # Dynamic — FAQ items
        "transitions": {},  # Dynamic
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
        "input_type": "dynamic_selection",
    },
    ConversationState.FAQ_ANSWER: {
        "template_key": None,  # Content from FAQ
        "buttons": [
            {"id": "go_faq_menu", "label": "Outras dúvidas"},
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "go_faq_menu": ConversationState.FAQ_MENU,
            "main_menu": ConversationState.MAIN_MENU,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.FAQ_MENU,
    },
    ConversationState.CANCEL_LOOKUP: {
        "template_key": None,  # Determined by on_enter
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
        "input_type": "dynamic_selection",
    },
    ConversationState.SELECT_CANCEL_APPOINTMENT: {
        "template_key": "CANCEL_SELECT_APPOINTMENT",
        "buttons": [],  # Dynamic — appointment list
        "transitions": {},  # Dynamic
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
        "input_type": "dynamic_selection",
    },
    ConversationState.CONFIRM_CANCEL: {
        "template_key": "CONFIRM_CANCEL",
        "buttons": [
            {"id": "confirm_cancel", "label": "Confirmar cancelamento"},
            {"id": "back", "label": "Voltar"},
        ],
        "transitions": {
            "confirm_cancel": ConversationState.CANCELLED,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
    },
    ConversationState.CANCELLED: {
        "template_key": "CANCELLED",
        "buttons": [
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "main_menu": ConversationState.MAIN_MENU,
        },
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
    ConversationState.HUMAN_HANDOFF: {
        "template_key": "HUMAN_HANDOFF",
        "buttons": [
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "main_menu": ConversationState.MAIN_MENU,
        },
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
    ConversationState.HUMAN_ATTENDANT_ACTIVE: {
        "template_key": None,
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.HUMAN_ATTENDANT_ACTIVE,
        "previous": None,
    },
    ConversationState.UNRECOGNIZED: {
        "template_key": "UNRECOGNIZED",
        "buttons": [],  # Repeat previous state's buttons
        "transitions": {"main_menu": ConversationState.MAIN_MENU},
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
}


FLOW_SESSION_KEYS = [
    "selected_service_ids", "selected_services_display", "total_duration_minutes", "total_price_cents",
    "selected_area_ids", "selected_areas_display", "selected_service_area_pairs",
    "selected_date", "selected_time",
    "service_id", "selected_new_date", "selected_new_time",
    "reschedule_appointment_id", "reschedule_service_id",
    "dynamic_buttons", "dynamic_transitions",
    "selected_faq_key", "appointment_id", "faq_items",
    "cancel_appointment_id", "_appointments_cache", "_cancel_appointments_cache",
    "_available_services", "_services_input",
    "_available_areas", "_areas_input",
]


class ConversationEngine:

    def __init__(
        self,
        db: PostgresService,
        template_service: TemplateService,
        availability_engine,
        appointment_service,
        provider: WhatsAppProvider,
        message_tracker: MessageTracker,
    ):
        self.db = db
        self.template_service = template_service
        self.availability_engine = availability_engine
        self.appointment_service = appointment_service
        self.provider = provider
        self.message_tracker = message_tracker

        dynamodb = boto3.resource("dynamodb")
        self.sessions_table = dynamodb.Table(os.environ["CONVERSATION_SESSIONS_TABLE"])

    def process_message(self, clinic_id: str, incoming: IncomingMessage) -> List[OutgoingMessage]:
        phone = incoming.phone
        
        # 1. Load or create session
        session = self._load_session(clinic_id, phone)
        current_state = ConversationState(session.get("state", ConversationState.WELCOME))

        logger.info(
            f"[ConversationEngine] Processing message from {phone} | "
            f"currentState={current_state} | content='{incoming.content[:50]}'"
        )

        # 1.5 Check if human attendant mode is active
        if current_state == ConversationState.HUMAN_ATTENDANT_ACTIVE:
            attendant_until = session.get("attendant_active_until", 0)
            if time.time() < attendant_until:
                logger.info(f"[ConversationEngine] Bot pausado (atendimento humano) para {phone}")
                return []
            else:
                logger.info(f"[ConversationEngine] TTL atendimento expirado para {phone}, resetando")
                session["state"] = ConversationState.WELCOME.value
                session.pop("attendant_active_until", None)
                session.pop("human_handoff_requested_at", None)
                self._save_session(clinic_id, phone, session)
                current_state = ConversationState.WELCOME

        # 2. Identify input
        user_input = self._identify_input(incoming, session)

        # 3. Determine next state
        if current_state == ConversationState.WELCOME:
            next_state = ConversationState.MAIN_MENU
        elif user_input == "back":
            config = STATE_CONFIG.get(current_state, {})
            previous = config.get("previous")
            next_state = previous if previous else ConversationState.MAIN_MENU
            # When areas were skipped, back from AVAILABLE_DAYS should go to CONFIRM_SERVICES
            if current_state == ConversationState.AVAILABLE_DAYS and session.pop("_skipped_areas", False):
                next_state = ConversationState.CONFIRM_SERVICES
                logger.info("[ConversationEngine] Back navigation: skipped areas, redirecting to CONFIRM_SERVICES")
            # Clear service selection when navigating back from or through SELECT_SERVICES
            if current_state == ConversationState.SELECT_SERVICES or next_state == ConversationState.SELECT_SERVICES:
                session.pop("selected_service_ids", None)
                session.pop("total_duration_minutes", None)
                session.pop("total_price_cents", None)
                session.pop("_available_services", None)
                session.pop("_services_input", None)
                logger.info("[ConversationEngine] Back navigation: cleared service selection keys")
            # Clear area selection when navigating back from or through SELECT_AREAS
            if current_state in (ConversationState.SELECT_AREAS, ConversationState.CONFIRM_AREAS) or next_state == ConversationState.SELECT_AREAS:
                session.pop("selected_area_ids", None)
                session.pop("selected_areas_display", None)
                session.pop("selected_service_area_pairs", None)
                session.pop("_available_areas", None)
                session.pop("_areas_input", None)
                logger.info("[ConversationEngine] Back navigation: cleared area selection keys")
        elif user_input == "human":
            next_state = ConversationState.HUMAN_HANDOFF
        else:
            next_state = self._resolve_transition(current_state, user_input, session)

        logger.info(
            f"[ConversationEngine] Transition: {current_state} -> {next_state} (input='{user_input}')"
        )

        # 3.5 Extract values from dynamic button IDs into session
        self._extract_dynamic_selection(user_input, session)

        # 3.6 Store raw input for free-text states that need it
        if current_state == ConversationState.SELECT_SERVICES:
            session["_services_input"] = user_input
            logger.info(f"[ConversationEngine] Stored _services_input='{user_input}'")
        if current_state == ConversationState.SELECT_AREAS:
            session["_areas_input"] = user_input
            logger.info(f"[ConversationEngine] Stored _areas_input='{user_input}'")

        # 4. Execute on_enter and build response
        session["previousState"] = current_state.value
        session["state"] = next_state.value

        logger.info(f"[ConversationEngine] Executing _on_enter for state={next_state}")
        template_vars, dynamic_buttons, override_content = self._on_enter(
            next_state, clinic_id, phone, session
        )

        # 5. Build outgoing messages (use effective state — on_enter may redirect)
        effective_state = ConversationState(session["state"])
        if effective_state != next_state:
            logger.info(f"[ConversationEngine] on_enter redirected: {next_state} -> {effective_state}")

        messages = self._build_messages(
            effective_state, clinic_id, template_vars, dynamic_buttons, override_content, session
        )

        logger.info(
            f"[ConversationEngine] Response: {len(messages)} message(s) | "
            f"effectiveState={effective_state} | "
            f"hasButtons={bool(dynamic_buttons)} | hasOverride={bool(override_content)} | "
            f"templateVars={list(template_vars.keys()) if template_vars else []}"
        )

        # 6. Save session
        self._save_session(clinic_id, phone, session)

        return messages

    def _identify_input(self, incoming: IncomingMessage, session: dict) -> str:
        # Button response
        if incoming.button_id:
            logger.info(f"[ConversationEngine] _identify_input: button_id='{incoming.button_id}'")
            return incoming.button_id

        text = (incoming.content or "").strip().lower()

        if not text:
            logger.info("[ConversationEngine] _identify_input: empty text input")
            return ""

        # Check for "voltar" / "back"
        if text in ("voltar", "back", "0"):
            logger.info(f"[ConversationEngine] _identify_input: matched 'back' from text='{text}'")
            return "back"

        # Check for "menu" / "inicio"
        if text in ("menu", "inicio", "oi", "ola", "hi", "hello"):
            logger.info(f"[ConversationEngine] _identify_input: matched 'main_menu' from text='{text}'")
            return "main_menu"

        # Check for "humano" / "atendente"
        if text in ("humano", "atendente", "pessoa", "falar com alguem"):
            logger.info(f"[ConversationEngine] _identify_input: matched 'human' from text='{text}'")
            return "human"

        # Synonym matching for confirm/back intents
        CONFIRM_SYNONYMS = {"sim", "s", "ok", "confirmar", "confirmo", "pode", "isso", "certo", "bora"}
        BACK_SYNONYMS = {"nao", "não", "n", "cancelar"}

        current_state = ConversationState(session.get("state", ConversationState.WELCOME))
        config = STATE_CONFIG.get(current_state, {})
        buttons = session.get("dynamic_buttons") or config.get("buttons", [])

        if text in CONFIRM_SYNONYMS:
            for btn in buttons:
                if btn["id"].startswith("confirm"):
                    logger.info(f"[ConversationEngine] _identify_input: confirm synonym '{text}' -> '{btn['id']}'")
                    return btn["id"]

        if text in BACK_SYNONYMS:
            logger.info(f"[ConversationEngine] _identify_input: back synonym '{text}' -> 'back'")
            return "back"

        # Numeric input — map to button index (skip for free_text states where numbers are data)
        input_type = config.get("input_type")
        if text.isdigit() and input_type != "free_text":
            idx = int(text) - 1
            if 0 <= idx < len(buttons):
                logger.info(f"[ConversationEngine] _identify_input: numeric '{text}' -> button '{buttons[idx]['id']}'")
                return buttons[idx]["id"]
            else:
                logger.info(f"[ConversationEngine] _identify_input: numeric '{text}' out of range (buttons={len(buttons)})")

        # Fuzzy label matching — normalized substring + word overlap
        if buttons and text:
            normalized_input = self._normalize_text(text)
            normalized_buttons = [
                (btn, self._normalize_text(btn.get("label", "")))
                for btn in buttons
            ]

            # 1st pass: normalized substring (input in label OR label in input)
            substr_matches = [
                btn for btn, norm_label in normalized_buttons
                if normalized_input in norm_label or norm_label in normalized_input
            ]
            if len(substr_matches) == 1:
                logger.info(f"[ConversationEngine] _identify_input: fuzzy substring match '{text}' -> '{substr_matches[0]['id']}'")
                return substr_matches[0]["id"]

            # 2nd pass: word overlap scoring (>= 50% of input words match)
            if not substr_matches or len(substr_matches) > 1:
                input_words = set(normalized_input.split())
                if input_words:
                    scored = []
                    for btn, norm_label in normalized_buttons:
                        label_words = set(norm_label.split())
                        overlap = len(input_words & label_words)
                        score = overlap / len(input_words)
                        if score >= 0.5:
                            scored.append((btn, score))
                    if scored:
                        scored.sort(key=lambda x: x[1], reverse=True)
                        if len(scored) == 1 or scored[0][1] > scored[1][1]:
                            logger.info(f"[ConversationEngine] _identify_input: fuzzy word overlap '{text}' -> '{scored[0][0]['id']}' (score={scored[0][1]:.2f})")
                            return scored[0][0]["id"]

        # Free text input — return as-is for states that accept it
        logger.info(f"[ConversationEngine] _identify_input: free text passthrough '{text}'")
        return text

    def _resolve_transition(
        self, current_state: ConversationState, user_input: str, session: dict
    ) -> ConversationState:
        config = STATE_CONFIG.get(current_state, {})
        input_type = config.get("input_type")

        # Static transitions
        transitions = config.get("transitions", {})
        if user_input in transitions:
            next_state = transitions[user_input]
            logger.info(f"[ConversationEngine] _resolve_transition: static '{user_input}' -> {next_state}")
            return next_state

        # Dynamic selection states — input is stored in session
        if input_type == "dynamic_selection":
            dynamic_transitions = session.get("dynamic_transitions", {})
            if user_input in dynamic_transitions:
                next_state = ConversationState(dynamic_transitions[user_input])
                logger.info(f"[ConversationEngine] _resolve_transition: dynamic '{user_input}' -> {next_state}")
                return next_state
            else:
                logger.info(
                    f"[ConversationEngine] _resolve_transition: dynamic_selection but '{user_input}' not in dynamic_transitions "
                    f"(keys={list(dynamic_transitions.keys())[:5]})"
                )

        # Free text states — always transition to next state
        if input_type == "free_text":
            next_state = self._get_free_text_next_state(current_state, user_input, session)
            logger.info(f"[ConversationEngine] _resolve_transition: free_text -> {next_state}")
            return next_state

        # Fallback
        fallback = config.get("fallback", ConversationState.UNRECOGNIZED)
        logger.info(f"[ConversationEngine] _resolve_transition: fallback -> {fallback} (input='{user_input}', input_type={input_type})")
        return fallback

    def _get_free_text_next_state(
        self, current_state: ConversationState, user_input: str, session: dict
    ) -> ConversationState:
        if current_state == ConversationState.SELECT_SERVICES:
            return ConversationState.CONFIRM_SERVICES
        if current_state == ConversationState.SELECT_AREAS:
            return ConversationState.CONFIRM_AREAS
        return ConversationState.UNRECOGNIZED

    def _on_enter(
        self,
        state: ConversationState,
        clinic_id: str,
        phone: str,
        session: dict,
    ) -> tuple:
        """Returns (template_vars, dynamic_buttons, override_content)."""
        template_vars = {}
        dynamic_buttons = None
        override_content = None

        try:
            if state == ConversationState.WELCOME or state == ConversationState.MAIN_MENU:
                self._clear_flow_session_keys(session)
                template_vars, override_content = self._on_enter_welcome(clinic_id, phone, session)
                # Always land on MAIN_MENU so buttons are included
                session["state"] = ConversationState.MAIN_MENU.value

            elif state == ConversationState.PRICE_TABLE:
                template_vars, override_content = self._on_enter_price_table(clinic_id)

            elif state == ConversationState.SELECT_SERVICES:
                template_vars, override_content, dynamic_buttons = self._on_enter_select_services(clinic_id, session)

            elif state == ConversationState.CONFIRM_SERVICES:
                template_vars, override_content = self._on_enter_confirm_services(clinic_id, session)

            elif state == ConversationState.SELECT_AREAS:
                result = self._on_enter_select_areas(clinic_id, session)
                if result is None:
                    # No areas configured — fall through to AVAILABLE_DAYS
                    session["state"] = ConversationState.AVAILABLE_DAYS.value
                    session["_skipped_areas"] = True
                    template_vars, dynamic_buttons = self._on_enter_available_days(clinic_id, session)
                else:
                    template_vars, override_content, dynamic_buttons = result

            elif state == ConversationState.CONFIRM_AREAS:
                template_vars, override_content = self._on_enter_confirm_areas(clinic_id, session)

            elif state == ConversationState.AVAILABLE_DAYS:
                template_vars, dynamic_buttons = self._on_enter_available_days(clinic_id, session)

            elif state == ConversationState.SELECT_TIME:
                template_vars, dynamic_buttons = self._on_enter_select_time(clinic_id, session)

            elif state == ConversationState.CONFIRM_BOOKING:
                template_vars = self._on_enter_confirm_booking(clinic_id, session)

            elif state == ConversationState.BOOKED:
                template_vars, override_content = self._on_enter_booked(clinic_id, phone, session)

            elif state == ConversationState.RESCHEDULE_LOOKUP:
                template_vars, dynamic_buttons, override_content = self._on_enter_reschedule_lookup(
                    clinic_id, phone, session
                )

            elif state == ConversationState.SELECT_APPOINTMENT:
                dynamic_buttons = session.get("dynamic_buttons")

            elif state == ConversationState.SHOW_CURRENT_APPOINTMENT:
                template_vars, dynamic_buttons = self._on_enter_show_current_appointment(
                    clinic_id, phone, session
                )

            elif state == ConversationState.SELECT_NEW_TIME:
                template_vars, dynamic_buttons = self._on_enter_select_new_time(clinic_id, session)

            elif state == ConversationState.CONFIRM_RESCHEDULE:
                template_vars = self._on_enter_confirm_reschedule(clinic_id, session)

            elif state == ConversationState.RESCHEDULED:
                template_vars, override_content = self._on_enter_rescheduled(clinic_id, session)

            elif state == ConversationState.CANCEL_LOOKUP:
                template_vars, dynamic_buttons, override_content = self._on_enter_cancel_lookup(
                    clinic_id, phone, session
                )

            elif state == ConversationState.SELECT_CANCEL_APPOINTMENT:
                dynamic_buttons = session.get("dynamic_buttons")

            elif state == ConversationState.CONFIRM_CANCEL:
                template_vars = self._on_enter_confirm_cancel(clinic_id, session)

            elif state == ConversationState.CANCELLED:
                template_vars, override_content = self._on_enter_cancelled(clinic_id, session)

            elif state == ConversationState.FAQ_MENU:
                template_vars, dynamic_buttons = self._on_enter_faq_menu(clinic_id, session)

            elif state == ConversationState.FAQ_ANSWER:
                template_vars, override_content = self._on_enter_faq_answer(clinic_id, session)

            elif state == ConversationState.FAREWELL:
                logger.info("[ConversationEngine] _on_enter: FAREWELL -> clearing flow session keys")
                self._clear_flow_session_keys(session)

            elif state == ConversationState.HUMAN_HANDOFF:
                session["human_handoff_requested_at"] = int(time.time())
                logger.info(f"[ConversationEngine] _on_enter: HUMAN_HANDOFF requested at {session['human_handoff_requested_at']}")

            elif state == ConversationState.UNRECOGNIZED:
                # Restore previous state's buttons + append "Menu principal"
                prev_state_str = session.get("previousState", ConversationState.MAIN_MENU.value)
                prev_state = ConversationState(prev_state_str)
                prev_config = STATE_CONFIG.get(prev_state, {})
                prev_buttons = session.get("dynamic_buttons") or prev_config.get("buttons", [])
                buttons = list(prev_buttons) if prev_buttons else []
                # Append "Menu principal" if not already present
                if not any(b["id"] == "main_menu" for b in buttons):
                    buttons.append({"id": "main_menu", "label": "Menu principal"})
                dynamic_buttons = buttons if buttons else None
                logger.info(f"[ConversationEngine] _on_enter: UNRECOGNIZED from prev_state={prev_state} | restoring {len(buttons)} buttons")

        except Exception as e:
            logger.error(f"[ConversationEngine] Error in on_enter for {state}: {e}", exc_info=True)
            override_content = "Desculpe, ocorreu um erro. Tente novamente."
            session["state"] = ConversationState.MAIN_MENU.value

        # If on_enter redirected and set dynamic_buttons in session, pick them up
        effective_state = ConversationState(session.get("state", state.value))
        if effective_state != state and not dynamic_buttons:
            dynamic_buttons = session.get("dynamic_buttons")

        return template_vars, dynamic_buttons, override_content

    # --- on_enter handlers ---

    def _on_enter_welcome(self, clinic_id: str, phone: str, session: dict) -> tuple:
        clinic = self._get_clinic(clinic_id)
        clinic_name = clinic.get("name", "") if clinic else ""
        logger.info(f"[ConversationEngine] _on_enter_welcome: clinic='{clinic_name}' phone={phone}")

        patients = self.db.execute_query(
            "SELECT name, gender FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )

        gender = patients[0].get("gender") if patients else None
        bem_vindx, Bem_vindx = self._get_greeting_by_gender(gender)

        if patients and patients[0].get("name"):
            patient_name = patients[0]["name"]
            session["patient_name"] = patient_name
            template_key = "WELCOME_RETURNING"
            variables = {"patient_name": patient_name, "clinic_name": clinic_name, "bem_vindx": bem_vindx, "Bem_vindx": Bem_vindx}
            logger.info(f"[ConversationEngine] _on_enter_welcome: returning patient='{patient_name}' gender={gender}")
        else:
            template_key = "WELCOME_NEW"
            variables = {"clinic_name": clinic_name, "bem_vindx": bem_vindx, "Bem_vindx": Bem_vindx}
            logger.info(f"[ConversationEngine] _on_enter_welcome: new patient (no record found)")

        content = self.template_service.get_and_render(clinic_id, template_key, variables)
        return variables, content

    @staticmethod
    def _get_greeting_by_gender(gender: Optional[str]) -> tuple:
        if gender == "M":
            return "bem-vindo", "Bem-vindo"
        elif gender == "F":
            return "bem-vinda", "Bem-vinda"
        return "bem-vindo(a)", "Bem-vindo(a)"

    def _on_enter_price_table(self, clinic_id: str) -> tuple:
        # Fetch services with area-specific overrides
        rows = self.db.execute_query(
            """SELECT s.id as service_id, s.name as service_name,
                      s.duration_minutes as service_duration, s.price_cents as service_price,
                      a.name as area_name,
                      COALESCE(sa.duration_minutes, s.duration_minutes) as duration,
                      COALESCE(sa.price_cents, s.price_cents) as price
               FROM scheduler.services s
               LEFT JOIN scheduler.service_areas sa ON sa.service_id = s.id AND sa.active = TRUE
               LEFT JOIN scheduler.areas a ON sa.area_id = a.id AND a.active = TRUE
               WHERE s.clinic_id = %s AND s.active = TRUE
               ORDER BY s.name, a.display_order, a.name""",
            (clinic_id,),
        )
        logger.info(f"[ConversationEngine] _on_enter_price_table: {len(rows)} rows found")

        # Group by service
        from collections import OrderedDict
        svc_map = OrderedDict()
        for row in rows:
            sid = str(row["service_id"])
            if sid not in svc_map:
                svc_map[sid] = {
                    "name": row["service_name"],
                    "base_price": row["service_price"],
                    "base_duration": row["service_duration"],
                    "areas": [],
                }
            if row["area_name"]:
                svc_map[sid]["areas"].append({
                    "name": row["area_name"],
                    "price": row["price"],
                    "duration": row["duration"],
                })

        lines = []
        for svc in svc_map.values():
            lines.append(f"*{svc['name']}*")
            if svc["areas"]:
                for area in svc["areas"]:
                    price_str = self._format_price_brl(area["price"]) if area["price"] else "Consultar"
                    dur = area["duration"]
                    dur_str = f"{dur}min" if dur else ""
                    lines.append(f"  • {area['name']}: {price_str} ({dur_str})")
            else:
                price_str = self._format_price_brl(svc["base_price"]) if svc["base_price"] else "Consultar"
                dur = svc["base_duration"]
                dur_str = f" ({dur}min)" if dur else ""
                lines.append(f"  {price_str}{dur_str}")
            lines.append("")  # blank line between services

        price_table = "\n".join(lines).rstrip() if lines else "Nenhum serviço cadastrado."
        variables = {"price_table": price_table}
        content = self.template_service.get_and_render(clinic_id, "PRICE_TABLE", variables)
        return variables, content

    def _on_enter_select_services(self, clinic_id: str, session: dict) -> tuple:
        # Fetch all active services
        services = self.db.execute_query(
            "SELECT id, name, duration_minutes, price_cents FROM scheduler.services WHERE clinic_id = %s AND active = TRUE ORDER BY name",
            (clinic_id,),
        )
        logger.info(f"[ConversationEngine] _on_enter_select_services: {len(services)} active services")

        if not services:
            logger.warning(f"[ConversationEngine] _on_enter_select_services: no services found for clinic={clinic_id}")
            content = "Nenhum serviço cadastrado para esta clínica."
            return {}, content, None

        # Cache services for later use in CONFIRM_SERVICES
        session["_available_services"] = [
            {
                "id": str(s["id"]),
                "name": s["name"],
                "price_cents": s.get("price_cents", 0),
            }
            for s in services
        ]

        # Build numbered list for the user
        lines = []
        for i, svc in enumerate(services, 1):
            price = svc.get("price_cents", 0)
            price_str = f" - R${price / 100:.2f}" if price else ""
            lines.append(f"{i} - {svc['name']}{price_str}")

        services_list = "\n".join(lines)
        content = f"Selecione os serviços (digite os números separados por vírgula):\n\n{services_list}"

        back_button = [{"id": "back", "label": "Voltar"}]
        session["dynamic_buttons"] = back_button
        return {}, content, back_button

    def _on_enter_confirm_services(self, clinic_id: str, session: dict) -> tuple:
        raw_input = session.pop("_services_input", "")
        available_services = session.get("_available_services", [])
        logger.info(
            f"[ConversationEngine] _on_enter_confirm_services: raw_input='{raw_input}' | "
            f"available_services={len(available_services)}"
        )

        if not available_services:
            return {}, "Nenhum serviço disponível."

        # Parse user input: "1, 3" or "1 3" or "1,3"
        raw_input = raw_input.replace(",", " ")
        tokens = raw_input.split()

        selected_service_ids = []
        selected_service_names = []
        for token in tokens:
            if token.isdigit():
                idx = int(token) - 1
                if 0 <= idx < len(available_services):
                    svc = available_services[idx]
                    if svc["id"] not in selected_service_ids:
                        selected_service_ids.append(svc["id"])
                        selected_service_names.append(svc["name"])

        if not selected_service_ids:
            # Invalid input — go back to SELECT_SERVICES and re-show the list
            logger.warning(f"[ConversationEngine] _on_enter_confirm_services: no valid services parsed from '{raw_input}' -> redirecting to SELECT_SERVICES")
            session["state"] = ConversationState.SELECT_SERVICES.value
            lines = []
            for i, svc in enumerate(available_services, 1):
                price = svc.get("price_cents", 0)
                price_str = f" - R${price / 100:.2f}" if price else ""
                lines.append(f"{i} - {svc['name']}{price_str}")
            services_list = "\n".join(lines)
            content = f"Nenhum serviço válido selecionado. Tente novamente.\n\n{services_list}"
            back_button = [{"id": "back", "label": "Voltar"}]
            session["dynamic_buttons"] = back_button
            return {}, content

        session["selected_service_ids"] = selected_service_ids
        selected_text = ", ".join(selected_service_names)
        session["selected_services_display"] = selected_text

        logger.info(f"[ConversationEngine] _on_enter_confirm_services: selected {len(selected_service_ids)} services: {selected_text}")

        content = f"Serviços selecionados:\n{selected_text}\n\nDeseja confirmar?"
        return {}, content

    @staticmethod
    def _build_areas_list(available_areas: list, multi_service: bool) -> str:
        """Build the numbered areas list, grouped by service when multi_service."""
        if not multi_service:
            return "\n".join(f"{i} - {a['name']}" for i, a in enumerate(available_areas, 1))

        lines = []
        current_service = None
        for i, area in enumerate(available_areas, 1):
            svc = area.get("service_name", "")
            if svc != current_service:
                if current_service is not None:
                    lines.append("")  # blank line between groups
                lines.append(f"📌 {svc}:")
                current_service = svc
            lines.append(f"{i} - {area['name']}")
        return "\n".join(lines)

    def _on_enter_select_areas(self, clinic_id: str, session: dict) -> tuple:
        selected_service_ids = session.get("selected_service_ids", [])
        logger.info(f"[ConversationEngine] _on_enter_select_areas: service_ids={selected_service_ids}")
        if not selected_service_ids:
            logger.warning("[ConversationEngine] _on_enter_select_areas: no services in session")
            return {}, "Nenhum serviço selecionado.", None

        # Fetch areas for all selected services (JOIN with areas table)
        placeholders = ", ".join(["%s"] * len(selected_service_ids))
        areas = self.db.execute_query(
            f"""
            SELECT a.id, a.name, sa.service_id, s.name as service_name
            FROM scheduler.service_areas sa
            JOIN scheduler.areas a ON sa.area_id = a.id
            JOIN scheduler.services s ON sa.service_id = s.id
            WHERE sa.service_id::text IN ({placeholders})
            AND sa.active = TRUE AND a.active = TRUE
            ORDER BY s.name, a.display_order, a.name
            """,
            tuple(selected_service_ids),
        )

        if not areas:
            # No areas configured — skip to AVAILABLE_DAYS
            logger.info(f"[ConversationEngine] _on_enter_select_areas: no areas configured for services -> skipping to AVAILABLE_DAYS")
            session["selected_areas_display"] = ""
            return None

        logger.info(f"[ConversationEngine] _on_enter_select_areas: {len(areas)} areas found")

        # Cache areas for later use in CONFIRM_AREAS (includes service_id for pair tracking)
        session["_available_areas"] = [
            {"id": str(a["id"]), "name": a["name"], "service_id": str(a["service_id"]), "service_name": a.get("service_name", "")}
            for a in areas
        ]

        # Determine distinct services that have areas
        service_names = list(dict.fromkeys(a.get("service_name", "") for a in areas))
        multi_service = len(service_names) > 1

        areas_list = self._build_areas_list(session["_available_areas"], multi_service)
        content = f"Selecione as áreas de tratamento (digite os números separados por vírgula):\n\n{areas_list}"

        back_button = [{"id": "back", "label": "Voltar"}]
        session["dynamic_buttons"] = back_button
        return {}, content, back_button

    def _on_enter_confirm_areas(self, clinic_id: str, session: dict) -> tuple:
        raw_input = session.pop("_areas_input", "")
        available_areas = session.get("_available_areas", [])
        logger.info(
            f"[ConversationEngine] _on_enter_confirm_areas: raw_input='{raw_input}' | "
            f"available_areas={len(available_areas)}"
        )

        if not available_areas:
            session["selected_areas_display"] = ""
            return {}, None

        # Parse user input: "1, 3, 5" or "1 3 5" or "1,3,5"
        raw_input = raw_input.replace(",", " ")
        tokens = raw_input.split()

        selected_area_ids = []
        selected_area_names = []
        selected_service_area_pairs = []
        seen_pairs = set()
        for token in tokens:
            if token.isdigit():
                idx = int(token) - 1
                if 0 <= idx < len(available_areas):
                    area = available_areas[idx]
                    pair_key = (area["service_id"], area["id"])
                    if pair_key not in seen_pairs:
                        seen_pairs.add(pair_key)
                        selected_service_area_pairs.append(
                            {"service_id": area["service_id"], "area_id": area["id"]}
                        )
                        if area["id"] not in selected_area_ids:
                            selected_area_ids.append(area["id"])
                        selected_area_names.append(area["name"])

        if not selected_service_area_pairs:
            # Invalid input — go back to SELECT_AREAS and re-show the list
            logger.warning(f"[ConversationEngine] _on_enter_confirm_areas: no valid areas parsed from '{raw_input}' -> redirecting to SELECT_AREAS")
            session["state"] = ConversationState.SELECT_AREAS.value
            service_names = list(dict.fromkeys(a.get("service_name", "") for a in available_areas))
            multi_service = len(service_names) > 1
            areas_list = self._build_areas_list(available_areas, multi_service)
            content = f"Nenhuma área válida selecionada. Tente novamente.\n\n{areas_list}"
            back_button = [{"id": "back", "label": "Voltar"}]
            session["dynamic_buttons"] = back_button
            return {}, content

        session["selected_area_ids"] = selected_area_ids
        session["selected_service_area_pairs"] = selected_service_area_pairs
        areas_display = ", ".join(selected_area_names)
        session["selected_areas_display"] = areas_display

        logger.info(f"[ConversationEngine] _on_enter_confirm_areas: selected {len(selected_service_area_pairs)} service-area pairs: {areas_display}")

        content = f"Áreas selecionadas:\n{areas_display}\n\nDeseja confirmar?"
        return {}, content

    def _on_enter_available_days(self, clinic_id: str, session: dict) -> tuple:
        days = []
        dynamic_buttons = []
        dynamic_transitions = {}

        logger.info(f"[ConversationEngine] _on_enter_available_days: availability_engine={'yes' if self.availability_engine else 'no'}")

        if self.availability_engine:
            selected_service_ids = session.get("selected_service_ids", [])
            if selected_service_ids:
                # Sum durations: for each (service, area) pair use area-specific override, fallback to service default
                service_area_pairs = session.get("selected_service_area_pairs", [])
                svc_placeholders = ", ".join(["%s"] * len(selected_service_ids))
                if service_area_pairs:
                    # Build VALUES list for exact (service_id, area_id) pairs
                    values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
                    params = ()
                    for pair in service_area_pairs:
                        params += (pair["service_id"], pair["area_id"])
                    rows = self.db.execute_query(
                        f"""SELECT SUM(COALESCE(sa.duration_minutes, s.duration_minutes)) as total_duration,
                               SUM(COALESCE(sa.price_cents, s.price_cents)) as total_price_cents
                        FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                        JOIN scheduler.services s ON s.id = pairs.service_id AND s.active = TRUE
                        LEFT JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id AND sa.active = TRUE""",
                        params,
                    )
                    total_duration = int(rows[0]["total_duration"]) if rows and rows[0]["total_duration"] else 0
                    total_price = int(rows[0]["total_price_cents"]) if rows and rows[0]["total_price_cents"] else 0

                    # Add duration/price for services without area pairs (no areas configured)
                    paired_service_ids = {pair["service_id"] for pair in service_area_pairs}
                    unpaired_service_ids = [sid for sid in selected_service_ids if sid not in paired_service_ids]
                    if unpaired_service_ids:
                        unpaired_placeholders = ", ".join(["%s"] * len(unpaired_service_ids))
                        unpaired_rows = self.db.execute_query(
                            f"SELECT duration_minutes, price_cents FROM scheduler.services WHERE id::text IN ({unpaired_placeholders}) AND active = TRUE",
                            tuple(unpaired_service_ids),
                        )
                        for row in unpaired_rows:
                            total_duration += int(row["duration_minutes"] or 0)
                            total_price += int(row["price_cents"] or 0)
                else:
                    services = self.db.execute_query(
                        f"SELECT id, duration_minutes, price_cents FROM scheduler.services WHERE id::text IN ({svc_placeholders}) AND active = TRUE",
                        tuple(selected_service_ids),
                    )
                    total_duration = sum(s["duration_minutes"] for s in services)
                    total_price = sum(s.get("price_cents") or 0 for s in services)
                session["total_duration_minutes"] = total_duration
                session["total_price_cents"] = total_price
                logger.info(f"[ConversationEngine] _on_enter_available_days: multi-service total_duration={total_duration}min, service_ids={selected_service_ids}")
                days = self.availability_engine.get_available_days_multi(clinic_id, total_duration)
            else:
                # Fallback: single service (legacy compat)
                service_id = session.get("service_id")
                if not service_id:
                    svc_rows = self.db.execute_query(
                        "SELECT id FROM scheduler.services WHERE clinic_id = %s AND active = TRUE LIMIT 1",
                        (clinic_id,),
                    )
                    if svc_rows:
                        service_id = str(svc_rows[0]["id"])
                        session["service_id"] = service_id
                if service_id:
                    logger.info(f"[ConversationEngine] _on_enter_available_days: single-service service_id={service_id}")
                    days = self.availability_engine.get_available_days(clinic_id, service_id)

        logger.info(f"[ConversationEngine] _on_enter_available_days: {len(days)} available days found")
        if days:
            for i, day in enumerate(days):
                btn_id = f"day_{day}"
                dynamic_buttons.append({"id": btn_id, "label": self._format_date_br(day)})
                dynamic_transitions[btn_id] = ConversationState.SELECT_TIME.value

        dynamic_buttons.append({"id": "human", "label": "Falar com atendente"})
        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        days_list = "\n".join([f"{i+1} - {self._format_date_br(d)}" for i, d in enumerate(days)]) if days else "Nenhum dia disponível no momento."
        variables = {"days_list": days_list}
        return variables, dynamic_buttons

    def _on_enter_select_time(self, clinic_id: str, session: dict) -> tuple:
        selected_date = session.get("selected_date", "")
        slots = []
        dynamic_buttons = []
        dynamic_transitions = {}

        logger.info(f"[ConversationEngine] _on_enter_select_time: selected_date='{selected_date}'")

        if self.availability_engine and selected_date:
            total_duration = session.get("total_duration_minutes")
            if total_duration:
                logger.info(f"[ConversationEngine] _on_enter_select_time: multi-service total_duration={total_duration}min")
                slots = self.availability_engine.get_available_slots_multi(clinic_id, selected_date, total_duration)
            else:
                service_id = session.get("service_id", "")
                logger.info(f"[ConversationEngine] _on_enter_select_time: single-service service_id={service_id}")
                slots = self.availability_engine.get_available_slots(clinic_id, selected_date, service_id)

        logger.info(f"[ConversationEngine] _on_enter_select_time: {len(slots)} time slots found for date={selected_date}")

        if slots:
            for i, slot_time in enumerate(slots):
                btn_id = f"time_{slot_time}"
                dynamic_buttons.append({"id": btn_id, "label": slot_time})
                dynamic_transitions[btn_id] = ConversationState.CONFIRM_BOOKING.value

        dynamic_buttons.append({"id": "human", "label": "Falar com atendente"})
        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        times_list = "\n".join([f"{i+1} - {t}" for i, t in enumerate(slots)]) if slots else "Nenhum horário disponível."
        variables = {"date": self._format_date_br(selected_date), "times_list": times_list}
        return variables, dynamic_buttons

    def _on_enter_confirm_booking(self, clinic_id: str, session: dict) -> dict:
        clinic = self._get_clinic(clinic_id)

        logger.info(
            f"[ConversationEngine] _on_enter_confirm_booking: date={session.get('selected_date')} "
            f"time={session.get('selected_time')} services={session.get('selected_service_ids')} "
            f"areas={session.get('selected_areas_display', '')}"
        )

        # Build service display from selected services
        selected_ids = session.get("selected_service_ids", [])
        if selected_ids:
            placeholders = ", ".join(["%s"] * len(selected_ids))
            services = self.db.execute_query(
                f"SELECT id, name FROM scheduler.services WHERE id::text IN ({placeholders}) AND active = TRUE",
                tuple(selected_ids),
            )
            svc_lookup = {str(s["id"]): s["name"] for s in services}
            service_names = [svc_lookup[sid] for sid in selected_ids if sid in svc_lookup]
            service_display = ", ".join(service_names)
        else:
            service = self._get_service(session.get("service_id"))
            service_display = service.get("name", "") if service else ""

        total_min = session.get("total_duration_minutes")
        if total_min:
            hours, mins = divmod(int(total_min), 60)
            duration_str = f"{hours}h{mins:02d}min" if hours else f"{total_min}min"
        else:
            duration_str = ""

        price_str = self._format_price_brl(session.get("total_price_cents"))

        variables = {
            "date": self._format_date_br(session.get("selected_date", "")),
            "time": session.get("selected_time", ""),
            "service": service_display,
            "areas": session.get("selected_areas_display", ""),
            "duration": duration_str,
            "price": price_str,
            "clinic_name": clinic.get("name", "") if clinic else "",
            "address": clinic.get("address", "") if clinic else "",
        }
        return variables

    def _on_enter_booked(self, clinic_id: str, phone: str, session: dict) -> tuple:
        result = None
        if self.appointment_service:
            try:
                selected_ids = session.get("selected_service_ids", [])
                primary_service_id = selected_ids[0] if selected_ids else session.get("service_id")
                logger.info(
                    f"[ConversationEngine] _on_enter_booked: creating appointment | "
                    f"phone={phone} date={session.get('selected_date')} time={session.get('selected_time')} "
                    f"primary_service_id={primary_service_id} all_service_ids={selected_ids} "
                    f"service_area_pairs={session.get('selected_service_area_pairs')} "
                    f"total_duration={session.get('total_duration_minutes')}"
                )
                result = self.appointment_service.create_appointment(
                    clinic_id=clinic_id,
                    phone=phone,
                    service_id=primary_service_id,
                    date=session.get("selected_date"),
                    time=session.get("selected_time"),
                    service_ids=selected_ids if selected_ids else None,
                    total_duration_minutes=session.get("total_duration_minutes"),
                    service_area_pairs=session.get("selected_service_area_pairs") or None,
                )
                session["appointment_id"] = str(result.get("id", ""))
                logger.info(f"[ConversationEngine] _on_enter_booked: appointment created id={session['appointment_id']}")
            except Exception as e:
                logger.error(f"[ConversationEngine] _on_enter_booked: FAILED to create appointment: {e}", exc_info=True)
                return {}, "Desculpe, ocorreu um erro ao confirmar seu agendamento. Tente novamente."

        clinic = self._get_clinic(clinic_id)
        clinic_instructions = (clinic.get("pre_session_instructions") or "") if clinic else ""

        # Hierarchical: service_area instructions take priority, then clinic-level
        sa_instructions = ""
        service_area_pairs = session.get("selected_service_area_pairs")
        if service_area_pairs and self.db:
            values_clause = ", ".join(["(%s::uuid, %s::uuid)"] * len(service_area_pairs))
            params = ()
            for pair in service_area_pairs:
                params += (pair["service_id"], pair["area_id"])
            rows = self.db.execute_query(
                f"""
                SELECT pre_session_instructions
                FROM (VALUES {values_clause}) AS pairs(service_id, area_id)
                JOIN scheduler.service_areas sa ON sa.service_id = pairs.service_id AND sa.area_id = pairs.area_id
                WHERE sa.pre_session_instructions IS NOT NULL
                AND sa.active = TRUE
                """,
                params,
            )
            sa_parts = [r["pre_session_instructions"] for r in rows if r.get("pre_session_instructions")]
            sa_instructions = "\n".join(sa_parts)

        parts = [p for p in [sa_instructions, clinic_instructions] if p]
        pre_instructions = "\n\n".join(parts)

        total_min = session.get("total_duration_minutes")
        if total_min:
            hours, mins = divmod(int(total_min), 60)
            duration_str = f"{hours}h{mins:02d}min" if hours else f"{total_min}min"
        else:
            duration_str = ""

        price_str = self._format_price_brl(session.get("total_price_cents"))

        variables = {
            "date": self._format_date_br(session.get("selected_date", "")),
            "time": session.get("selected_time", ""),
            "duration": duration_str,
            "price": price_str,
            "pre_session_instructions": pre_instructions,
        }
        content = self.template_service.get_and_render(clinic_id, "BOOKED", variables)
        # Remove trailing whitespace/newlines when pre_session_instructions is empty
        if not pre_instructions:
            content = content.rstrip()
        return variables, content

    def _on_enter_reschedule_lookup(self, clinic_id: str, phone: str, session: dict) -> tuple:
        appointments = []
        if self.appointment_service:
            appointments = self.appointment_service.get_active_appointments_by_phone(clinic_id, phone)

        logger.info(f"[ConversationEngine] _on_enter_reschedule_lookup: phone={phone} appointments_found={len(appointments)}")

        if not appointments:
            session["state"] = ConversationState.RESCHEDULE_LOOKUP.value
            content = self.template_service.get_and_render(clinic_id, "RESCHEDULE_NOT_FOUND")
            dynamic_buttons = [
                {"id": "main_menu", "label": "Menu principal"},
                {"id": "human", "label": "Falar com atendente"},
            ]
            dynamic_transitions = {
                "main_menu": ConversationState.MAIN_MENU.value,
                "human": ConversationState.HUMAN_HANDOFF.value,
            }
            session["dynamic_buttons"] = dynamic_buttons
            session["dynamic_transitions"] = dynamic_transitions
            logger.info("[ConversationEngine] _on_enter_reschedule_lookup: no appointments found")
            return {}, dynamic_buttons, content

        if len(appointments) == 1:
            # Single appointment — skip picker, go directly to show
            appt = appointments[0]
            session["reschedule_appointment_id"] = str(appt.get("id", ""))
            session["reschedule_service_id"] = str(appt.get("service_id", ""))
            session["state"] = ConversationState.SHOW_CURRENT_APPOINTMENT.value
            logger.info(
                f"[ConversationEngine] _on_enter_reschedule_lookup: single appointment id={session['reschedule_appointment_id']} "
                f"service_id={session['reschedule_service_id']} -> redirecting to SHOW_CURRENT_APPOINTMENT"
            )

            variables = {
                "date": self._format_date_br(appt.get("appointment_date", "")),
                "time": str(appt.get("start_time", "")),
                "service": appt.get("service_name", ""),
            }
            content = self.template_service.get_and_render(clinic_id, "RESCHEDULE_FOUND", variables)

            days = []
            if self.availability_engine:
                svc_id = session.get("reschedule_service_id")
                if svc_id:
                    days = self.availability_engine.get_available_days(clinic_id, svc_id)

            dynamic_buttons = []
            dynamic_transitions = {}
            for day in days:
                btn_id = f"newday_{day}"
                dynamic_buttons.append({"id": btn_id, "label": self._format_date_br(day)})
                dynamic_transitions[btn_id] = ConversationState.SELECT_NEW_TIME.value

            dynamic_buttons.append({"id": "human", "label": "Falar com atendente"})
            dynamic_buttons.append({"id": "back", "label": "Voltar"})

            session["dynamic_buttons"] = dynamic_buttons
            session["dynamic_transitions"] = dynamic_transitions

            return variables, dynamic_buttons, content

        # Multiple appointments — show picker
        logger.info(f"[ConversationEngine] _on_enter_reschedule_lookup: {len(appointments)} appointments -> showing picker")
        session["state"] = ConversationState.SELECT_APPOINTMENT.value
        session["_appointments_cache"] = self._serialize_for_dynamo(
            {str(a["id"]): a for a in appointments}
        )

        dynamic_buttons = []
        dynamic_transitions = {}
        for appt in appointments:
            appt_id = str(appt["id"])
            btn_id = f"appt_{appt_id}"
            label = f"{self._format_date_br(appt.get('appointment_date', ''))} {appt.get('start_time', '')} - {appt.get('service_name', '')}"
            dynamic_buttons.append({"id": btn_id, "label": label})
            dynamic_transitions[btn_id] = ConversationState.SHOW_CURRENT_APPOINTMENT.value

        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        content = self.template_service.get_and_render(clinic_id, "RESCHEDULE_SELECT_APPOINTMENT")
        return {}, dynamic_buttons, content

    def _on_enter_show_current_appointment(self, clinic_id: str, phone: str, session: dict) -> tuple:
        appt_id = session.get("reschedule_appointment_id")
        svc_id = session.get("reschedule_service_id")
        logger.info(f"[ConversationEngine] _on_enter_show_current_appointment: appt_id={appt_id} svc_id={svc_id}")

        # Try to get appointment data from cache (multi-appointment flow)
        cache = session.get("_appointments_cache", {})
        appt = cache.get(appt_id) if appt_id else None

        if not appt and appt_id:
            logger.info(f"[ConversationEngine] _on_enter_show_current_appointment: cache miss, fetching from DB")
            # Fallback: fetch from DB
            results = self.db.execute_query(
                """
                SELECT a.*, s.name as service_name
                FROM scheduler.appointments a
                LEFT JOIN scheduler.services s ON a.service_id = s.id
                WHERE a.id = %s::uuid AND a.status = 'CONFIRMED'
                """,
                (appt_id,),
            )
            appt = results[0] if results else None

        if not appt:
            logger.warning(f"[ConversationEngine] _on_enter_show_current_appointment: appointment not found for id={appt_id}")
            return {}, None

        variables = {
            "date": self._format_date_br(appt.get("appointment_date", "")),
            "time": str(appt.get("start_time", "")),
            "service": appt.get("service_name", ""),
        }
        logger.info(f"[ConversationEngine] _on_enter_show_current_appointment: current appt date={variables['date']} time={variables['time']} service='{variables['service']}'")
        content = self.template_service.get_and_render(clinic_id, "RESCHEDULE_FOUND", variables)

        # Fetch available days for rescheduling
        days = []
        if self.availability_engine and svc_id:
            days = self.availability_engine.get_available_days(clinic_id, svc_id)
            logger.info(f"[ConversationEngine] _on_enter_show_current_appointment: {len(days)} available days for rescheduling")

        dynamic_buttons = []
        dynamic_transitions = {}
        for day in days:
            btn_id = f"newday_{day}"
            dynamic_buttons.append({"id": btn_id, "label": self._format_date_br(day)})
            dynamic_transitions[btn_id] = ConversationState.SELECT_NEW_TIME.value

        dynamic_buttons.append({"id": "human", "label": "Falar com atendente"})
        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        return variables, dynamic_buttons

    def _on_enter_select_new_time(self, clinic_id: str, session: dict) -> tuple:
        selected_date = session.get("selected_new_date", "")
        slots = []
        dynamic_buttons = []
        dynamic_transitions = {}

        logger.info(f"[ConversationEngine] _on_enter_select_new_time: selected_new_date='{selected_date}'")

        if self.availability_engine and selected_date:
            svc_id = session.get("reschedule_service_id", "")
            logger.info(f"[ConversationEngine] _on_enter_select_new_time: querying slots for service_id={svc_id}")
            slots = self.availability_engine.get_available_slots(clinic_id, selected_date, svc_id)
            logger.info(f"[ConversationEngine] _on_enter_select_new_time: {len(slots)} slots found")

        if slots:
            for slot_time in slots:
                btn_id = f"newtime_{slot_time}"
                dynamic_buttons.append({"id": btn_id, "label": slot_time})
                dynamic_transitions[btn_id] = ConversationState.CONFIRM_RESCHEDULE.value

        dynamic_buttons.append({"id": "human", "label": "Falar com atendente"})
        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        times_list = "\n".join([f"{i+1} - {t}" for i, t in enumerate(slots)]) if slots else "Nenhum horário disponível."
        variables = {"date": self._format_date_br(selected_date), "times_list": times_list}
        return variables, dynamic_buttons

    def _on_enter_confirm_reschedule(self, clinic_id: str, session: dict) -> dict:
        clinic = self._get_clinic(clinic_id)
        appt_id = session.get("reschedule_appointment_id")
        logger.info(
            f"[ConversationEngine] _on_enter_confirm_reschedule: appt_id={appt_id} "
            f"new_date={session.get('selected_new_date')} new_time={session.get('selected_new_time')}"
        )

        service_display = ""
        areas_display = ""

        service = self._get_service(session.get("reschedule_service_id"))
        if service:
            service_display = service.get("name", "")

        if appt_id:
            area_rows = self.db.execute_query(
                "SELECT area_name FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid ORDER BY created_at",
                (appt_id,),
            )
            if area_rows:
                areas_display = ", ".join(r["area_name"] for r in area_rows)

        return {
            "date": self._format_date_br(session.get("selected_new_date", "")),
            "time": session.get("selected_new_time", ""),
            "service": service_display,
            "areas": areas_display,
            "clinic_name": clinic.get("name", "") if clinic else "",
            "address": clinic.get("address", "") if clinic else "",
        }

    def _on_enter_rescheduled(self, clinic_id: str, session: dict) -> tuple:
        if self.appointment_service:
            try:
                appt_id = session.get("reschedule_appointment_id")
                new_date = session.get("selected_new_date")
                new_time = session.get("selected_new_time")
                logger.info(f"[ConversationEngine] _on_enter_rescheduled: rescheduling appt_id={appt_id} to date={new_date} time={new_time}")
                self.appointment_service.reschedule_appointment(
                    appointment_id=appt_id,
                    new_date=new_date,
                    new_time=new_time,
                )
                logger.info(f"[ConversationEngine] _on_enter_rescheduled: SUCCESS appt_id={appt_id}")
            except Exception as e:
                logger.error(f"[ConversationEngine] _on_enter_rescheduled: FAILED appt_id={session.get('reschedule_appointment_id')}: {e}", exc_info=True)
                return {}, "Desculpe, ocorreu um erro ao remarcar. Tente novamente."

        variables = {
            "date": self._format_date_br(session.get("selected_new_date", "")),
            "time": session.get("selected_new_time", ""),
        }
        content = self.template_service.get_and_render(clinic_id, "RESCHEDULED", variables)
        return variables, content

    def _on_enter_cancel_lookup(self, clinic_id: str, phone: str, session: dict) -> tuple:
        appointments = []
        if self.appointment_service:
            appointments = self.appointment_service.get_active_appointments_by_phone(clinic_id, phone)

        logger.info(f"[ConversationEngine] _on_enter_cancel_lookup: phone={phone} appointments_found={len(appointments)}")

        if not appointments:
            session["state"] = ConversationState.CANCEL_LOOKUP.value
            content = self.template_service.get_and_render(clinic_id, "CANCEL_NOT_FOUND")
            dynamic_buttons = [
                {"id": "main_menu", "label": "Menu principal"},
                {"id": "human", "label": "Falar com atendente"},
            ]
            dynamic_transitions = {
                "main_menu": ConversationState.MAIN_MENU.value,
                "human": ConversationState.HUMAN_HANDOFF.value,
            }
            session["dynamic_buttons"] = dynamic_buttons
            session["dynamic_transitions"] = dynamic_transitions
            logger.info("[ConversationEngine] _on_enter_cancel_lookup: no appointments found")
            return {}, dynamic_buttons, content

        if len(appointments) == 1:
            # Single appointment — go directly to confirm cancel
            appt = appointments[0]
            session["cancel_appointment_id"] = str(appt.get("id", ""))
            session["state"] = ConversationState.CONFIRM_CANCEL.value
            logger.info(f"[ConversationEngine] _on_enter_cancel_lookup: single appointment id={session['cancel_appointment_id']} -> redirecting to CONFIRM_CANCEL")

            variables = {
                "date": self._format_date_br(appt.get("appointment_date", "")),
                "time": str(appt.get("start_time", "")),
                "service": appt.get("service_name", ""),
            }
            content = self.template_service.get_and_render(clinic_id, "CONFIRM_CANCEL", variables)
            return variables, None, content

        # Multiple appointments — show picker
        logger.info(f"[ConversationEngine] _on_enter_cancel_lookup: {len(appointments)} appointments -> showing picker")
        session["state"] = ConversationState.SELECT_CANCEL_APPOINTMENT.value
        session["_cancel_appointments_cache"] = self._serialize_for_dynamo(
            {str(a["id"]): a for a in appointments}
        )

        dynamic_buttons = []
        dynamic_transitions = {}
        for appt in appointments:
            appt_id = str(appt["id"])
            btn_id = f"cancelappt_{appt_id}"
            label = f"{self._format_date_br(appt.get('appointment_date', ''))} {appt.get('start_time', '')} - {appt.get('service_name', '')}"
            dynamic_buttons.append({"id": btn_id, "label": label})
            dynamic_transitions[btn_id] = ConversationState.CONFIRM_CANCEL.value

        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        content = self.template_service.get_and_render(clinic_id, "CANCEL_SELECT_APPOINTMENT")
        return {}, dynamic_buttons, content

    def _on_enter_confirm_cancel(self, clinic_id: str, session: dict) -> dict:
        appt_id = session.get("cancel_appointment_id")
        logger.info(f"[ConversationEngine] _on_enter_confirm_cancel: appt_id={appt_id}")

        # Try cache first
        cache = session.get("_cancel_appointments_cache", {})
        appt = cache.get(appt_id) if appt_id else None

        if not appt and appt_id:
            logger.info(f"[ConversationEngine] _on_enter_confirm_cancel: cache miss, fetching from DB")
            results = self.db.execute_query(
                """
                SELECT a.*, s.name as service_name
                FROM scheduler.appointments a
                LEFT JOIN scheduler.services s ON a.service_id = s.id
                WHERE a.id = %s::uuid AND a.status = 'CONFIRMED'
                """,
                (appt_id,),
            )
            appt = results[0] if results else None

        if not appt:
            logger.warning(f"[ConversationEngine] _on_enter_confirm_cancel: appointment not found for id={appt_id}")
            return {}

        areas_display = ""
        cancel_appt_id = str(appt.get("id", ""))
        if cancel_appt_id:
            area_rows = self.db.execute_query(
                "SELECT area_name FROM scheduler.appointment_service_areas WHERE appointment_id = %s::uuid ORDER BY created_at",
                (cancel_appt_id,),
            )
            if area_rows:
                areas_display = ", ".join(r["area_name"] for r in area_rows)

        logger.info(f"[ConversationEngine] _on_enter_confirm_cancel: appt date={appt.get('appointment_date')} time={appt.get('start_time')} service='{appt.get('service_name')}'")
        return {
            "date": self._format_date_br(appt.get("appointment_date", "")),
            "time": str(appt.get("start_time", "")),
            "service": appt.get("service_name", ""),
            "areas": areas_display,
        }

    def _on_enter_cancelled(self, clinic_id: str, session: dict) -> tuple:
        appt_id = session.get("cancel_appointment_id")
        if self.appointment_service and appt_id:
            try:
                logger.info(f"[ConversationEngine] _on_enter_cancelled: cancelling appt_id={appt_id}")
                self.appointment_service.cancel_appointment(appt_id)
                logger.info(f"[ConversationEngine] _on_enter_cancelled: SUCCESS appt_id={appt_id}")
            except Exception as e:
                logger.error(f"[ConversationEngine] _on_enter_cancelled: FAILED appt_id={appt_id}: {e}", exc_info=True)
                return {}, "Desculpe, ocorreu um erro ao cancelar. Tente novamente."

        content = self.template_service.get_and_render(clinic_id, "CANCELLED")
        return {}, content

    def _on_enter_faq_menu(self, clinic_id: str, session: dict) -> tuple:
        faqs = self.db.execute_query(
            "SELECT id, question_key, question_label FROM scheduler.faq_items WHERE clinic_id = %s AND active = TRUE ORDER BY display_order",
            (clinic_id,),
        )
        logger.info(f"[ConversationEngine] _on_enter_faq_menu: {len(faqs)} FAQ items loaded")

        dynamic_buttons = []
        dynamic_transitions = {}
        for faq in faqs:
            btn_id = f"faq_{faq['question_key']}"
            dynamic_buttons.append({"id": btn_id, "label": faq["question_label"]})
            dynamic_transitions[btn_id] = ConversationState.FAQ_ANSWER.value

        dynamic_buttons.append({"id": "back", "label": "Voltar"})

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions
        session["faq_items"] = {f"faq_{f['question_key']}": f for f in faqs}

        return {}, dynamic_buttons

    def _on_enter_faq_answer(self, clinic_id: str, session: dict) -> tuple:
        selected_faq_key = session.get("selected_faq_key", "")
        faq_key = selected_faq_key.replace("faq_", "") if selected_faq_key.startswith("faq_") else selected_faq_key
        logger.info(f"[ConversationEngine] _on_enter_faq_answer: selected_faq_key='{selected_faq_key}' resolved_key='{faq_key}'")

        results = self.db.execute_query(
            "SELECT answer FROM scheduler.faq_items WHERE clinic_id = %s AND question_key = %s AND active = TRUE",
            (clinic_id, faq_key),
        )

        if results:
            content = results[0]["answer"]
            logger.info(f"[ConversationEngine] _on_enter_faq_answer: answer found (len={len(content)})")
        else:
            content = "Desculpe, não encontramos a resposta para essa pergunta."
            logger.warning(f"[ConversationEngine] _on_enter_faq_answer: no answer found for key='{faq_key}'")

        return {}, content

    # --- Session management ---

    def _clear_flow_session_keys(self, session: dict) -> None:
        cleared = [key for key in FLOW_SESSION_KEYS if key in session]
        for key in FLOW_SESSION_KEYS:
            session.pop(key, None)
        if cleared:
            logger.info(f"[ConversationEngine] _clear_flow_session_keys: cleared {len(cleared)} keys: {cleared}")

    def _load_session(self, clinic_id: str, phone: str) -> dict:
        try:
            response = self.sessions_table.get_item(
                Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
            )
            item = response.get("Item")

            if item:
                session = item.get("session", {"state": ConversationState.WELCOME.value})
                logger.info(f"[ConversationEngine] _load_session: existing session state={session.get('state')} for phone={phone}")
                return session
            else:
                logger.info(f"[ConversationEngine] _load_session: no session found for phone={phone} -> new WELCOME session")
        except Exception as e:
            logger.error(f"[ConversationEngine] _load_session: ERROR loading session for phone={phone}: {e}", exc_info=True)

        return {"state": ConversationState.WELCOME.value}

    def _save_session(self, clinic_id: str, phone: str, session: dict) -> None:
        try:
            now = int(time.time())
            logger.info(f"[ConversationEngine] _save_session: state={session.get('state')} phone={phone}")
            self.sessions_table.put_item(
                Item={
                    "pk": f"CLINIC#{clinic_id}",
                    "sk": f"PHONE#{phone}",
                    "session": session,
                    "clinicId": clinic_id,
                    "phone": phone,
                    "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
                }
            )
        except Exception as e:
            logger.error(f"[ConversationEngine] _save_session: ERROR saving session for phone={phone}: {e}", exc_info=True)

    # --- Helpers ---

    @staticmethod
    def _serialize_for_dynamo(obj):
        """Convert a dict (or list of dicts) so all values are DynamoDB-safe."""
        if isinstance(obj, list):
            return [ConversationEngine._serialize_for_dynamo(item) for item in obj]
        if isinstance(obj, dict):
            return {k: ConversationEngine._serialize_for_dynamo(v) for k, v in obj.items()}
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        if isinstance(obj, dt_time):
            return obj.strftime("%H:%M")
        if isinstance(obj, timedelta):
            total = int(obj.total_seconds())
            h, remainder = divmod(total, 3600)
            m, s = divmod(remainder, 60)
            return f"{h:02d}:{m:02d}"
        if isinstance(obj, Decimal):
            return int(obj) if obj == int(obj) else float(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        return obj

    def _get_clinic(self, clinic_id: str) -> Optional[dict]:
        results = self.db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        return results[0] if results else None

    def _get_service(self, service_id: Optional[str]) -> Optional[dict]:
        if not service_id:
            return None
        results = self.db.execute_query(
            "SELECT * FROM scheduler.services WHERE id = %s::uuid AND active = TRUE",
            (service_id,),
        )
        return results[0] if results else None

    @staticmethod
    def _format_price_brl(price_cents) -> str:
        """Format price in cents to BRL string: 15000 -> 'R$ 150,00'"""
        if not price_cents:
            return ""
        price_cents = int(price_cents)
        reais = price_cents // 100
        centavos = price_cents % 100
        return f"R$ {reais},{centavos:02d}"

    @staticmethod
    def _format_date_br(date_value) -> str:
        if isinstance(date_value, date):
            return date_value.strftime("%d/%m/%Y")
        if isinstance(date_value, str) and date_value:
            try:
                return datetime.strptime(date_value, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                return date_value
        return str(date_value)

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for fuzzy comparison: lowercase, strip accents and punctuation."""
        text = text.lower().strip()
        nfkd = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in nfkd if not unicodedata.combining(c))
        text = "".join(c for c in text if c.isalnum() or c.isspace())
        text = " ".join(text.split())
        return text

    def _build_messages(
        self,
        state: ConversationState,
        clinic_id: str,
        template_vars: dict,
        dynamic_buttons: Optional[List[Dict]],
        override_content: Optional[str],
        session: dict,
    ) -> List[OutgoingMessage]:
        config = STATE_CONFIG.get(state, {})

        # Determine content
        if override_content:
            content = override_content
            content_source = "override"
        elif config.get("template_key"):
            content = self.template_service.get_and_render(
                clinic_id, config["template_key"], template_vars
            )
            content_source = f"template:{config['template_key']}"
        else:
            content = ""
            content_source = "empty"

        # Determine buttons
        buttons = dynamic_buttons if dynamic_buttons else config.get("buttons", [])

        logger.info(
            f"[ConversationEngine] _build_messages: state={state} | content_source={content_source} | "
            f"content_len={len(content)} | buttons={len(buttons)} | "
            f"button_ids={[b['id'] for b in buttons[:5]]}{'...' if len(buttons) > 5 else ''}"
        )

        if buttons:
            return [
                OutgoingMessage(
                    message_type="buttons",
                    content=content,
                    buttons=buttons,
                )
            ]
        else:
            return [
                OutgoingMessage(
                    message_type="text",
                    content=content,
                )
            ]

    def _extract_dynamic_selection(self, user_input: str, session: dict) -> None:
        """Extract values from dynamic button IDs and store in session."""
        # Appointment selection for reschedule
        if user_input.startswith("appt_"):
            appt_id = user_input[len("appt_"):]
            session["reschedule_appointment_id"] = appt_id
            cache = session.get("_appointments_cache", {})
            appt = cache.get(appt_id)
            if appt:
                session["reschedule_service_id"] = str(appt.get("service_id", ""))
            logger.info(f"[ConversationEngine] Selected reschedule appointment: {appt_id}")
            return

        # Appointment selection for cancellation
        if user_input.startswith("cancelappt_"):
            appt_id = user_input[len("cancelappt_"):]
            session["cancel_appointment_id"] = appt_id
            logger.info(f"[ConversationEngine] Selected cancel appointment: {appt_id}")
            return

        PREFIX_TO_KEY = {
            "day_": "selected_date",
            "time_": "selected_time",
            "newday_": "selected_new_date",
            "newtime_": "selected_new_time",
            "faq_": "selected_faq_key",
        }
        for prefix, session_key in PREFIX_TO_KEY.items():
            if user_input.startswith(prefix):
                session[session_key] = user_input[len(prefix):]
                logger.info(
                    f"[ConversationEngine] Extracted {session_key}='{session[session_key]}' from input '{user_input}'"
                )
                return
