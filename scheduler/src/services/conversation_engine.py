import os
import time
import uuid
import logging
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
    AVAILABLE_DAYS = "AVAILABLE_DAYS"
    SELECT_DATE = "SELECT_DATE"
    SELECT_TIME = "SELECT_TIME"
    INPUT_AREAS = "INPUT_AREAS"
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    BOOKED = "BOOKED"
    RESCHEDULE_LOOKUP = "RESCHEDULE_LOOKUP"
    SHOW_CURRENT_APPOINTMENT = "SHOW_CURRENT_APPOINTMENT"
    SELECT_NEW_DATE = "SELECT_NEW_DATE"
    SELECT_NEW_TIME = "SELECT_NEW_TIME"
    CONFIRM_RESCHEDULE = "CONFIRM_RESCHEDULE"
    RESCHEDULED = "RESCHEDULED"
    FAQ_MENU = "FAQ_MENU"
    FAQ_ANSWER = "FAQ_ANSWER"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
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
            {"id": "schedule", "label": "Agendar sessao"},
            {"id": "reschedule", "label": "Remarcar sessao"},
            {"id": "faq", "label": "Duvidas sobre sessao"},
        ],
        "transitions": {
            "schedule": ConversationState.SCHEDULE_MENU,
            "reschedule": ConversationState.RESCHEDULE_LOOKUP,
            "faq": ConversationState.FAQ_MENU,
            "human": ConversationState.HUMAN_HANDOFF,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": None,
    },
    ConversationState.SCHEDULE_MENU: {
        "template_key": "SCHEDULE_MENU",
        "buttons": [
            {"id": "price_table", "label": "Ver tabela de precos"},
            {"id": "schedule_now", "label": "Agendar agora"},
        ],
        "transitions": {
            "price_table": ConversationState.PRICE_TABLE,
            "schedule_now": ConversationState.AVAILABLE_DAYS,
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
            "schedule_now": ConversationState.AVAILABLE_DAYS,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SCHEDULE_MENU,
    },
    ConversationState.AVAILABLE_DAYS: {
        "template_key": "AVAILABLE_DAYS",
        "buttons": [],  # Dynamic — populated by on_enter
        "transitions": {},  # Dynamic — date selection
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SCHEDULE_MENU,
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
    ConversationState.INPUT_AREAS: {
        "template_key": "INPUT_AREAS",
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.SELECT_TIME,
        "input_type": "free_text",
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
        "previous": ConversationState.INPUT_AREAS,
    },
    ConversationState.BOOKED: {
        "template_key": "BOOKED",
        "buttons": [
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "main_menu": ConversationState.MAIN_MENU,
        },
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
    ConversationState.RESCHEDULE_LOOKUP: {
        "template_key": None,  # Determined by on_enter (FOUND or NOT_FOUND)
        "buttons": [],
        "transitions": {},
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.MAIN_MENU,
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
            {"id": "faq_menu", "label": "Outras duvidas"},
            {"id": "main_menu", "label": "Menu principal"},
        ],
        "transitions": {
            "faq_menu": ConversationState.FAQ_MENU,
            "main_menu": ConversationState.MAIN_MENU,
        },
        "fallback": ConversationState.UNRECOGNIZED,
        "previous": ConversationState.FAQ_MENU,
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
    ConversationState.UNRECOGNIZED: {
        "template_key": "UNRECOGNIZED",
        "buttons": [],  # Repeat previous state's buttons
        "transitions": {},
        "fallback": ConversationState.MAIN_MENU,
        "previous": None,
    },
}


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
        conversation_id = f"{clinic_id}#{phone}"

        # 1. Load or create session
        session = self._load_session(clinic_id, phone)
        current_state = ConversationState(session.get("state", ConversationState.WELCOME))

        logger.info(
            f"[ConversationEngine] Processing message from {phone} | "
            f"currentState={current_state} | content='{incoming.content[:50]}'"
        )

        # 2. Identify input
        user_input = self._identify_input(incoming, session)

        # 3. Determine next state
        if current_state == ConversationState.WELCOME:
            next_state = ConversationState.MAIN_MENU
        elif user_input == "back":
            config = STATE_CONFIG.get(current_state, {})
            previous = config.get("previous")
            next_state = previous if previous else ConversationState.MAIN_MENU
        else:
            next_state = self._resolve_transition(current_state, user_input, session)

        logger.info(
            f"[ConversationEngine] Transition: {current_state} -> {next_state} (input='{user_input}')"
        )

        # 4. Execute on_enter and build response
        session["previousState"] = current_state.value
        session["state"] = next_state.value

        template_vars, dynamic_buttons, override_content = self._on_enter(
            next_state, clinic_id, phone, session
        )

        # 5. Build outgoing messages
        messages = self._build_messages(
            next_state, clinic_id, template_vars, dynamic_buttons, override_content, session
        )

        # 6. Save session
        self._save_session(clinic_id, phone, session)

        return messages

    def _identify_input(self, incoming: IncomingMessage, session: dict) -> str:
        # Button response
        if incoming.button_id:
            return incoming.button_id

        text = (incoming.content or "").strip().lower()

        if not text:
            return ""

        # Check for "voltar" / "back"
        if text in ("voltar", "back", "0"):
            return "back"

        # Check for "menu" / "inicio"
        if text in ("menu", "inicio", "oi", "ola", "hi", "hello"):
            return "main_menu"

        # Check for "humano" / "atendente"
        if text in ("humano", "atendente", "pessoa", "falar com alguem"):
            return "human"

        # Numeric input — map to button index
        current_state = ConversationState(session.get("state", ConversationState.WELCOME))
        config = STATE_CONFIG.get(current_state, {})
        buttons = session.get("dynamic_buttons") or config.get("buttons", [])

        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(buttons):
                return buttons[idx]["id"]

        # Free text input — return as-is for states that accept it
        return text

    def _resolve_transition(
        self, current_state: ConversationState, user_input: str, session: dict
    ) -> ConversationState:
        config = STATE_CONFIG.get(current_state, {})
        input_type = config.get("input_type")

        # Static transitions
        transitions = config.get("transitions", {})
        if user_input in transitions:
            return transitions[user_input]

        # Dynamic selection states — input is stored in session
        if input_type == "dynamic_selection":
            dynamic_transitions = session.get("dynamic_transitions", {})
            if user_input in dynamic_transitions:
                return ConversationState(dynamic_transitions[user_input])

        # Free text states — always transition to next state
        if input_type == "free_text":
            return self._get_free_text_next_state(current_state, user_input, session)

        # Fallback
        return config.get("fallback", ConversationState.UNRECOGNIZED)

    def _get_free_text_next_state(
        self, current_state: ConversationState, user_input: str, session: dict
    ) -> ConversationState:
        if current_state == ConversationState.INPUT_AREAS:
            session["areas"] = user_input
            return ConversationState.CONFIRM_BOOKING

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
                template_vars, override_content = self._on_enter_welcome(clinic_id, phone, session)

            elif state == ConversationState.PRICE_TABLE:
                template_vars, override_content = self._on_enter_price_table(clinic_id)

            elif state == ConversationState.AVAILABLE_DAYS:
                template_vars, dynamic_buttons = self._on_enter_available_days(clinic_id, session)

            elif state == ConversationState.SELECT_TIME:
                template_vars, dynamic_buttons = self._on_enter_select_time(clinic_id, session)

            elif state == ConversationState.CONFIRM_BOOKING:
                template_vars = self._on_enter_confirm_booking(clinic_id, session)

            elif state == ConversationState.BOOKED:
                template_vars, override_content = self._on_enter_booked(clinic_id, session)

            elif state == ConversationState.RESCHEDULE_LOOKUP:
                template_vars, dynamic_buttons, override_content = self._on_enter_reschedule_lookup(
                    clinic_id, phone, session
                )

            elif state == ConversationState.SHOW_CURRENT_APPOINTMENT:
                template_vars, dynamic_buttons = self._on_enter_show_current_appointment(
                    clinic_id, session
                )

            elif state == ConversationState.SELECT_NEW_TIME:
                template_vars, dynamic_buttons = self._on_enter_select_new_time(clinic_id, session)

            elif state == ConversationState.CONFIRM_RESCHEDULE:
                template_vars = self._on_enter_confirm_reschedule(clinic_id, session)

            elif state == ConversationState.RESCHEDULED:
                template_vars, override_content = self._on_enter_rescheduled(clinic_id, session)

            elif state == ConversationState.FAQ_MENU:
                template_vars, dynamic_buttons = self._on_enter_faq_menu(clinic_id, session)

            elif state == ConversationState.FAQ_ANSWER:
                template_vars, override_content = self._on_enter_faq_answer(clinic_id, session)

            elif state == ConversationState.UNRECOGNIZED:
                # Restore previous state's buttons
                prev_state_str = session.get("previousState", ConversationState.MAIN_MENU.value)
                prev_state = ConversationState(prev_state_str)
                prev_config = STATE_CONFIG.get(prev_state, {})
                prev_buttons = session.get("dynamic_buttons") or prev_config.get("buttons", [])
                dynamic_buttons = prev_buttons if prev_buttons else None

        except Exception as e:
            logger.error(f"[ConversationEngine] Error in on_enter for {state}: {e}")
            override_content = "Desculpe, ocorreu um erro. Tente novamente."
            session["state"] = ConversationState.MAIN_MENU.value

        return template_vars, dynamic_buttons, override_content

    # --- on_enter handlers ---

    def _on_enter_welcome(self, clinic_id: str, phone: str, session: dict) -> tuple:
        clinic = self._get_clinic(clinic_id)
        clinic_name = clinic.get("name", "") if clinic else ""

        patients = self.db.execute_query(
            "SELECT name FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
            (clinic_id, phone),
        )

        if patients and patients[0].get("name"):
            patient_name = patients[0]["name"]
            session["patient_name"] = patient_name
            template_key = "WELCOME_RETURNING"
            variables = {"patient_name": patient_name, "clinic_name": clinic_name}
        else:
            template_key = "WELCOME_NEW"
            variables = {"clinic_name": clinic_name}

        content = self.template_service.get_and_render(clinic_id, template_key, variables)
        return variables, content

    def _on_enter_price_table(self, clinic_id: str) -> tuple:
        services = self.db.execute_query(
            "SELECT name, duration_minutes, price_cents FROM scheduler.services WHERE clinic_id = %s AND active = TRUE ORDER BY name",
            (clinic_id,),
        )

        lines = []
        for svc in services:
            price = svc.get("price_cents", 0)
            price_str = f"R$ {price / 100:.2f}" if price else "Consultar"
            duration = svc.get("duration_minutes", 0)
            lines.append(f"- {svc['name']} ({duration}min): {price_str}")

        price_table = "\n".join(lines) if lines else "Nenhum servico cadastrado."
        variables = {"price_table": price_table}
        content = self.template_service.get_and_render(clinic_id, "PRICE_TABLE", variables)
        return variables, content

    def _on_enter_available_days(self, clinic_id: str, session: dict) -> tuple:
        days = []
        dynamic_buttons = []
        dynamic_transitions = {}

        if self.availability_engine:
            service_id = session.get("service_id")
            if not service_id:
                services = self.db.execute_query(
                    "SELECT id FROM scheduler.services WHERE clinic_id = %s AND active = TRUE LIMIT 1",
                    (clinic_id,),
                )
                if services:
                    service_id = str(services[0]["id"])
                    session["service_id"] = service_id

            if service_id:
                days = self.availability_engine.get_available_days(clinic_id, service_id)

        if days:
            for i, day in enumerate(days):
                btn_id = f"day_{day}"
                dynamic_buttons.append({"id": btn_id, "label": day})
                dynamic_transitions[btn_id] = ConversationState.SELECT_TIME.value
        else:
            dynamic_buttons = [{"id": "back", "label": "Voltar"}]

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        days_list = "\n".join([f"{i+1} - {d}" for i, d in enumerate(days)]) if days else "Nenhum dia disponivel no momento."
        variables = {"days_list": days_list}
        return variables, dynamic_buttons

    def _on_enter_select_time(self, clinic_id: str, session: dict) -> tuple:
        selected_date = session.get("selected_date", "")
        slots = []
        dynamic_buttons = []
        dynamic_transitions = {}

        if self.availability_engine and selected_date:
            service_id = session.get("service_id", "")
            slots = self.availability_engine.get_available_slots(clinic_id, selected_date, service_id)

        if slots:
            for i, slot_time in enumerate(slots):
                btn_id = f"time_{slot_time}"
                dynamic_buttons.append({"id": btn_id, "label": slot_time})
                dynamic_transitions[btn_id] = ConversationState.INPUT_AREAS.value
        else:
            dynamic_buttons = [{"id": "back", "label": "Voltar"}]

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        times_list = "\n".join([f"{i+1} - {t}" for i, t in enumerate(slots)]) if slots else "Nenhum horario disponivel."
        variables = {"date": selected_date, "times_list": times_list}
        return variables, dynamic_buttons

    def _on_enter_confirm_booking(self, clinic_id: str, session: dict) -> dict:
        clinic = self._get_clinic(clinic_id)
        service = self._get_service(session.get("service_id"))

        variables = {
            "date": session.get("selected_date", ""),
            "time": session.get("selected_time", ""),
            "service": service.get("name", "") if service else "",
            "areas": session.get("areas", ""),
            "clinic_name": clinic.get("name", "") if clinic else "",
            "address": clinic.get("address", "") if clinic else "",
        }
        return variables

    def _on_enter_booked(self, clinic_id: str, session: dict) -> tuple:
        result = None
        if self.appointment_service:
            try:
                result = self.appointment_service.create_appointment(
                    clinic_id=clinic_id,
                    phone=session.get("phone", ""),
                    service_id=session.get("service_id"),
                    date=session.get("selected_date"),
                    time=session.get("selected_time"),
                    areas=session.get("areas", ""),
                )
                session["appointment_id"] = str(result.get("id", ""))
            except Exception as e:
                logger.error(f"[ConversationEngine] Erro ao criar agendamento: {e}")
                return {}, "Desculpe, ocorreu um erro ao confirmar seu agendamento. Tente novamente."

        clinic = self._get_clinic(clinic_id)
        variables = {
            "date": session.get("selected_date", ""),
            "time": session.get("selected_time", ""),
            "pre_session_instructions": clinic.get("pre_session_instructions", "") if clinic else "",
        }
        content = self.template_service.get_and_render(clinic_id, "BOOKED", variables)
        return variables, content

    def _on_enter_reschedule_lookup(self, clinic_id: str, phone: str, session: dict) -> tuple:
        appointment = None
        if self.appointment_service:
            appointment = self.appointment_service.get_active_appointment_by_phone(clinic_id, phone)

        if appointment:
            session["reschedule_appointment_id"] = str(appointment.get("id", ""))
            session["reschedule_service_id"] = str(appointment.get("service_id", ""))
            session["state"] = ConversationState.SHOW_CURRENT_APPOINTMENT.value

            variables = {
                "date": str(appointment.get("appointment_date", "")),
                "time": str(appointment.get("start_time", "")),
                "service": appointment.get("service_name", ""),
            }
            content = self.template_service.get_and_render(clinic_id, "RESCHEDULE_FOUND", variables)

            # Fetch available days for rescheduling
            days = []
            if self.availability_engine:
                svc_id = session.get("reschedule_service_id")
                if svc_id:
                    days = self.availability_engine.get_available_days(clinic_id, svc_id)

            dynamic_buttons = []
            dynamic_transitions = {}
            for day in days:
                btn_id = f"newday_{day}"
                dynamic_buttons.append({"id": btn_id, "label": day})
                dynamic_transitions[btn_id] = ConversationState.SELECT_NEW_TIME.value

            if not dynamic_buttons:
                dynamic_buttons = [{"id": "back", "label": "Voltar"}]

            session["dynamic_buttons"] = dynamic_buttons
            session["dynamic_transitions"] = dynamic_transitions

            return variables, dynamic_buttons, content
        else:
            session["state"] = ConversationState.MAIN_MENU.value
            content = self.template_service.get_and_render(clinic_id, "RESCHEDULE_NOT_FOUND")
            return {}, None, content

    def _on_enter_show_current_appointment(self, clinic_id: str, session: dict) -> tuple:
        # Already handled in reschedule_lookup; this is for direct navigation
        return {}, session.get("dynamic_buttons")

    def _on_enter_select_new_time(self, clinic_id: str, session: dict) -> tuple:
        selected_date = session.get("selected_new_date", "")
        slots = []
        dynamic_buttons = []
        dynamic_transitions = {}

        if self.availability_engine and selected_date:
            svc_id = session.get("reschedule_service_id", "")
            slots = self.availability_engine.get_available_slots(clinic_id, selected_date, svc_id)

        if slots:
            for slot_time in slots:
                btn_id = f"newtime_{slot_time}"
                dynamic_buttons.append({"id": btn_id, "label": slot_time})
                dynamic_transitions[btn_id] = ConversationState.CONFIRM_RESCHEDULE.value
        else:
            dynamic_buttons = [{"id": "back", "label": "Voltar"}]

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions

        times_list = "\n".join([f"{i+1} - {t}" for i, t in enumerate(slots)]) if slots else "Nenhum horario disponivel."
        variables = {"date": selected_date, "times_list": times_list}
        return variables, dynamic_buttons

    def _on_enter_confirm_reschedule(self, clinic_id: str, session: dict) -> dict:
        clinic = self._get_clinic(clinic_id)
        return {
            "date": session.get("selected_new_date", ""),
            "time": session.get("selected_new_time", ""),
            "service": "",
            "areas": "",
            "clinic_name": clinic.get("name", "") if clinic else "",
            "address": clinic.get("address", "") if clinic else "",
        }

    def _on_enter_rescheduled(self, clinic_id: str, session: dict) -> tuple:
        if self.appointment_service:
            try:
                self.appointment_service.reschedule_appointment(
                    appointment_id=session.get("reschedule_appointment_id"),
                    new_date=session.get("selected_new_date"),
                    new_time=session.get("selected_new_time"),
                )
            except Exception as e:
                logger.error(f"[ConversationEngine] Erro ao remarcar: {e}")
                return {}, "Desculpe, ocorreu um erro ao remarcar. Tente novamente."

        variables = {
            "date": session.get("selected_new_date", ""),
            "time": session.get("selected_new_time", ""),
        }
        content = self.template_service.get_and_render(clinic_id, "RESCHEDULED", variables)
        return variables, content

    def _on_enter_faq_menu(self, clinic_id: str, session: dict) -> tuple:
        faqs = self.db.execute_query(
            "SELECT id, question_key, question_label FROM scheduler.faq_items WHERE clinic_id = %s AND active = TRUE ORDER BY display_order",
            (clinic_id,),
        )

        dynamic_buttons = []
        dynamic_transitions = {}
        for faq in faqs:
            btn_id = f"faq_{faq['question_key']}"
            dynamic_buttons.append({"id": btn_id, "label": faq["question_label"]})
            dynamic_transitions[btn_id] = ConversationState.FAQ_ANSWER.value

        session["dynamic_buttons"] = dynamic_buttons
        session["dynamic_transitions"] = dynamic_transitions
        session["faq_items"] = {f"faq_{f['question_key']}": f for f in faqs}

        return {}, dynamic_buttons

    def _on_enter_faq_answer(self, clinic_id: str, session: dict) -> tuple:
        selected_faq_key = session.get("selected_faq_key", "")
        faq_key = selected_faq_key.replace("faq_", "") if selected_faq_key.startswith("faq_") else selected_faq_key

        results = self.db.execute_query(
            "SELECT answer FROM scheduler.faq_items WHERE clinic_id = %s AND question_key = %s AND active = TRUE",
            (clinic_id, faq_key),
        )

        if results:
            content = results[0]["answer"]
        else:
            content = "Desculpe, nao encontramos a resposta para essa pergunta."

        return {}, content

    # --- Session management ---

    def _load_session(self, clinic_id: str, phone: str) -> dict:
        try:
            response = self.sessions_table.get_item(
                Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
            )
            item = response.get("Item")

            if item:
                return item.get("session", {"state": ConversationState.WELCOME.value})
        except Exception as e:
            logger.error(f"[ConversationEngine] Error loading session: {e}")

        return {"state": ConversationState.WELCOME.value}

    def _save_session(self, clinic_id: str, phone: str, session: dict) -> None:
        try:
            now = int(time.time())
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
            logger.error(f"[ConversationEngine] Error saving session: {e}")

    # --- Helpers ---

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
        elif config.get("template_key"):
            content = self.template_service.get_and_render(
                clinic_id, config["template_key"], template_vars
            )
        else:
            content = ""

        # Determine buttons
        buttons = dynamic_buttons if dynamic_buttons else config.get("buttons", [])

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

    def _extract_selection_from_input(self, user_input: str, prefix: str) -> str:
        if user_input.startswith(prefix):
            return user_input[len(prefix):]
        return user_input
