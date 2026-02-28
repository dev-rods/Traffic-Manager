import json
import os
import time
import logging
from typing import Any, Dict, List, Optional

import boto3

from src.services.db.postgres import PostgresService
from src.services.template_service import TemplateService
from src.services.message_tracker import MessageTracker
from src.services.openai_service import OpenAIService, OpenAIError
from src.services.ai_tools import TOOL_DEFINITIONS, ToolExecutor
from src.providers.whatsapp_provider import IncomingMessage, WhatsAppProvider
from src.services.conversation_engine import OutgoingMessage, ConversationState

logger = logging.getLogger(__name__)

MAX_HISTORY_MESSAGES = 20
MAX_TOOL_LOOPS = 5
MAX_TURN_COUNT = 30
HANDOFF_TTL_SECONDS = 24 * 60 * 60  # 24h


class AIConversationEngine:

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
        self.openai = OpenAIService()
        self.tools = ToolExecutor(db, availability_engine, appointment_service)

        dynamodb = boto3.resource("dynamodb")
        self.sessions_table = dynamodb.Table(os.environ["CONVERSATION_SESSIONS_TABLE"])

    def process_message(self, clinic_id: str, incoming: IncomingMessage) -> List[OutgoingMessage]:
        phone = incoming.phone

        # 1. Load session
        session = self._load_session(clinic_id, phone)

        # 2. Check human attendant mode (same mechanism as deterministic engine)
        if self._is_human_mode_active(session, incoming):
            return []

        # 3. Check global commands
        global_result = self._check_global_commands(incoming, session, clinic_id, phone)
        if global_result is not None:
            return global_result

        # 4. Load clinic info for system prompt
        clinic = self._load_clinic(clinic_id)
        if not clinic:
            logger.error(f"[AIEngine] Clinic not found: {clinic_id}")
            return [OutgoingMessage(message_type="text", content="Desculpe, ocorreu um erro. Tente novamente.")]

        # 5. Build conversation history
        history = session.get("conversation_history", [])
        collected_data = session.get("collected_data", {})
        turn_count = session.get("turn_count", 0)

        # Safety: too many turns → human handoff
        if turn_count >= MAX_TURN_COUNT:
            logger.warning(f"[AIEngine] Turn limit reached ({MAX_TURN_COUNT}) for {phone}, triggering handoff")
            self._activate_handoff(session, clinic_id, phone, reason="turn_limit")
            return [OutgoingMessage(
                message_type="text",
                content="Vou te transferir para um atendente que poderá te ajudar melhor. Aguarde um momento! 😊",
            )]

        # 6. Build system prompt
        system_prompt = self._build_system_prompt(clinic_id, clinic, collected_data)

        # 7. Append user message to history
        user_content = incoming.content or ""
        if incoming.button_id:
            # For button responses, include both the button label and id for context
            user_content = incoming.button_text or incoming.button_id
        history.append({"role": "user", "content": user_content})

        # Trim history to sliding window
        if len(history) > MAX_HISTORY_MESSAGES:
            history = history[-MAX_HISTORY_MESSAGES:]

        # 8. Call LLM with tool loop
        try:
            messages = [{"role": "system", "content": system_prompt}] + history
            assistant_response, tool_results = self._run_tool_loop(messages, clinic_id, phone, collected_data)
        except OpenAIError as e:
            logger.error(f"[AIEngine] OpenAI error for {phone}: {e}")
            self._activate_handoff(session, clinic_id, phone, reason="api_error")
            return [OutgoingMessage(
                message_type="text",
                content="Desculpe, estou com dificuldades técnicas no momento. "
                        "Vou te transferir para um atendente. Aguarde um momento! 😊",
            )]

        # 9. Process tool results for side effects
        outgoing_messages = []
        handoff_requested = False
        present_options_data = None

        for tr in tool_results:
            if tr.get("tool_name") == "request_human_handoff" and tr.get("result", {}).get("handoff_requested"):
                handoff_requested = True
            if tr.get("tool_name") == "present_options" and tr.get("result", {}).get("presented"):
                present_options_data = tr["result"]
            # Update collected_data from tool results
            self._update_collected_data(collected_data, tr)

        # 10. Build outgoing messages
        response_text = assistant_response or ""

        if present_options_data:
            # Generate WhatsApp buttons from present_options
            options = present_options_data.get("options", [])
            button_message = present_options_data.get("message", response_text)

            if len(options) <= 3:
                # Use WhatsApp buttons (max 3)
                buttons = [{"id": opt["id"], "label": opt["label"][:24]} for opt in options[:3]]
                outgoing_messages.append(OutgoingMessage(
                    message_type="buttons",
                    content=button_message,
                    buttons=buttons,
                ))
            else:
                # Use WhatsApp list for more than 3 options
                rows = [{"id": opt["id"], "title": opt["label"][:72]} for opt in options]
                sections = [{"title": "Opções", "rows": rows}]
                outgoing_messages.append(OutgoingMessage(
                    message_type="list",
                    content=button_message,
                    sections=sections,
                    button_text="Selecione",
                ))

            # If LLM also generated text beyond present_options message, send it separately
            if response_text and response_text != button_message:
                outgoing_messages.insert(0, OutgoingMessage(
                    message_type="text",
                    content=response_text,
                ))
        elif response_text:
            outgoing_messages.append(OutgoingMessage(
                message_type="text",
                content=response_text,
            ))

        # 11. Handle handoff
        if handoff_requested:
            self._activate_handoff(session, clinic_id, phone, reason="ai_tool_request")

        # 12. Save session
        history.append({"role": "assistant", "content": response_text})
        if len(history) > MAX_HISTORY_MESSAGES:
            history = history[-MAX_HISTORY_MESSAGES:]

        session["ai_flow"] = True
        session["conversation_history"] = history
        session["collected_data"] = collected_data
        session["turn_count"] = turn_count + 1
        if handoff_requested:
            session["state"] = ConversationState.HUMAN_HANDOFF.value
            session["human_handoff_requested_at"] = int(time.time())

        self._save_session(clinic_id, phone, session)

        logger.info(
            f"[AIEngine] Response for {phone}: {len(outgoing_messages)} msg(s), "
            f"tools_called={len(tool_results)}, handoff={handoff_requested}, turn={turn_count + 1}"
        )

        return outgoing_messages

    # ──────────────────────────────────────────────
    # Tool loop
    # ──────────────────────────────────────────────

    def _run_tool_loop(
        self,
        messages: list,
        clinic_id: str,
        phone: str,
        collected_data: dict,
    ) -> tuple:
        """
        Call LLM, execute any tool calls, feed results back, repeat.
        Returns (final_text_response, list_of_tool_results).
        """
        all_tool_results = []

        for loop_i in range(MAX_TOOL_LOOPS):
            response = self.openai.chat_completion(
                messages=messages,
                tools=TOOL_DEFINITIONS,
            )

            choice = response.get("choices", [{}])[0]
            message = choice.get("message", {})
            finish_reason = choice.get("finish_reason", "")

            # No tool calls — return text response
            if finish_reason != "tool_calls" and not message.get("tool_calls"):
                return message.get("content", ""), all_tool_results

            # Process tool calls
            tool_calls = message.get("tool_calls", [])
            if not tool_calls:
                return message.get("content", ""), all_tool_results

            # Add the assistant message with tool_calls to the conversation
            messages.append(message)

            for tc in tool_calls:
                func = tc.get("function", {})
                tool_name = func.get("name", "")
                try:
                    arguments = json.loads(func.get("arguments", "{}"))
                except json.JSONDecodeError:
                    arguments = {}

                context = {
                    "clinic_id": clinic_id,
                    "phone": phone,
                    "collected_data": collected_data,
                }

                result = self.tools.execute(tool_name, arguments, context)
                all_tool_results.append({
                    "tool_name": tool_name,
                    "arguments": arguments,
                    "result": result,
                })

                # Add tool result to messages for next LLM call
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", ""),
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                })

        # If we exhausted the loop, return whatever we have
        logger.warning(f"[AIEngine] Tool loop exhausted ({MAX_TOOL_LOOPS} iterations) for {phone}")
        return messages[-1].get("content", ""), all_tool_results

    # ──────────────────────────────────────────────
    # System prompt
    # ──────────────────────────────────────────────

    def _build_system_prompt(self, clinic_id: str, clinic: dict, collected_data: dict) -> str:
        display_name = clinic.get("display_name") or clinic.get("name", "")
        address = clinic.get("address") or ""
        phone = clinic.get("phone") or ""
        hours = clinic.get("business_hours", {})
        hours_str = self._format_business_hours(hours) if hours else "Não informado"

        # Count services for context
        services = self.db.execute_query(
            "SELECT COUNT(*) as cnt FROM scheduler.services WHERE clinic_id = %s AND active = true",
            (clinic_id,),
        )
        services_count = services[0]["cnt"] if services else 0

        # Single service hint
        single_service_hint = ""
        if services_count == 1:
            svc = self.db.execute_query(
                "SELECT name FROM scheduler.services WHERE clinic_id = %s AND active = true LIMIT 1",
                (clinic_id,),
            )
            if svc:
                single_service_hint = (
                    f'- ATENÇÃO: Esta clínica oferece APENAS o serviço "{svc[0]["name"]}". '
                    f"NÃO pergunte qual serviço o cliente deseja. Assuma este serviço "
                    f"automaticamente e vá direto para a escolha de áreas."
                )

        # Collected data summary
        collected_summary = self._format_collected_data(collected_data)

        variables = {
            "clinic_display_name": display_name,
            "clinic_address": address,
            "clinic_phone": phone,
            "clinic_hours": hours_str,
            "collected_data_summary": collected_summary or "Nenhum dado coletado ainda.",
            "services_count": str(services_count),
            "single_service_hint": single_service_hint,
        }

        return self.template_service.get_and_render(clinic_id, "AI_SYSTEM_PROMPT", variables)

    def _format_business_hours(self, hours: dict) -> str:
        if isinstance(hours, str):
            return hours
        parts = []
        day_names = {
            "0": "Dom", "1": "Seg", "2": "Ter", "3": "Qua",
            "4": "Qui", "5": "Sex", "6": "Sáb",
        }
        for day, times in sorted(hours.items()):
            name = day_names.get(str(day), str(day))
            if isinstance(times, dict):
                parts.append(f"{name}: {times.get('start', '?')}-{times.get('end', '?')}")
            elif isinstance(times, list):
                for t in times:
                    parts.append(f"{name}: {t.get('start', '?')}-{t.get('end', '?')}")
        return ", ".join(parts) if parts else str(hours)

    def _format_collected_data(self, data: dict) -> str:
        if not data:
            return ""
        parts = []
        if data.get("service_names"):
            parts.append(f"- Serviço(s): {', '.join(data['service_names'])}")
        if data.get("area_names"):
            parts.append(f"- Área(s): {', '.join(data['area_names'])}")
        if data.get("date"):
            parts.append(f"- Data: {data['date']}")
        if data.get("time"):
            parts.append(f"- Horário: {data['time']}")
        if data.get("full_name"):
            parts.append(f"- Nome: {data['full_name']}")
        if data.get("total_price_cents"):
            parts.append(f"- Valor: R$ {data['total_price_cents'] / 100:.2f}")
        return "\n".join(parts)

    # ──────────────────────────────────────────────
    # Collected data updates from tool calls
    # ──────────────────────────────────────────────

    def _update_collected_data(self, collected_data: dict, tool_result: dict) -> None:
        tool_name = tool_result.get("tool_name")
        result = tool_result.get("result", {})
        args = tool_result.get("arguments", {})

        if tool_name == "list_services" and result.get("single_service"):
            services = result.get("services", [])
            if services:
                collected_data["service_ids"] = [services[0]["id"]]
                collected_data["service_names"] = [services[0]["name"]]

        if tool_name == "book_appointment" and result.get("success"):
            collected_data["date"] = args.get("date")
            collected_data["time"] = args.get("time")
            collected_data["full_name"] = args.get("full_name")
            collected_data["appointment_id"] = result.get("appointment_id")

    # ──────────────────────────────────────────────
    # Human attendant / handoff logic
    # ──────────────────────────────────────────────

    def _is_human_mode_active(self, session: dict, incoming: IncomingMessage) -> bool:
        state = session.get("state", "")
        if state not in (ConversationState.HUMAN_ATTENDANT_ACTIVE.value, ConversationState.HUMAN_HANDOFF.value):
            return False

        # Allow "resume_bot" button to reactivate
        if state == ConversationState.HUMAN_HANDOFF.value and incoming.button_id == "resume_bot":
            session.pop("human_handoff_requested_at", None)
            session["state"] = ""  # Will be treated as new conversation
            session.pop("conversation_history", None)
            session.pop("collected_data", None)
            session["turn_count"] = 0
            return False

        now = time.time()
        if state == ConversationState.HUMAN_ATTENDANT_ACTIVE.value:
            is_active = now < session.get("attendant_active_until", 0)
        else:
            handoff_at = session.get("human_handoff_requested_at", 0)
            is_active = now < (handoff_at + HANDOFF_TTL_SECONDS)

        if is_active:
            logger.info(f"[AIEngine] Bot paused (human mode) state={state}")
            return True

        # TTL expired — reset
        session["state"] = ""
        session.pop("attendant_active_until", None)
        session.pop("human_handoff_requested_at", None)
        session.pop("conversation_history", None)
        session.pop("collected_data", None)
        session["turn_count"] = 0
        return False

    def _check_global_commands(
        self, incoming: IncomingMessage, session: dict, clinic_id: str, phone: str
    ) -> Optional[List[OutgoingMessage]]:
        text = (incoming.content or "").strip().lower()
        if not text:
            return None

        HUMAN_COMMANDS = {
            "humano", "atendente", "pessoa", "ajuda", "suporte",
            "falar com atendente", "falar com alguem", "falar com alguém",
        }
        END_COMMANDS = {
            "encerrar", "sair", "tchau", "até logo", "ate logo",
            "finalizar", "encerrar atendimento",
        }

        if text in HUMAN_COMMANDS:
            self._activate_handoff(session, clinic_id, phone, reason="global_command")
            self._save_session(clinic_id, phone, session)
            return [OutgoingMessage(
                message_type="buttons",
                content="Entendi! Vamos encaminhar sua mensagem para nossa equipe. Em breve alguém entrará em contato.",
                buttons=[{"id": "resume_bot", "label": "Retomar atendimento"}],
            )]

        if text in END_COMMANDS:
            # Reset session
            session["state"] = ""
            session.pop("conversation_history", None)
            session.pop("collected_data", None)
            session["turn_count"] = 0
            self._save_session(clinic_id, phone, session)
            return [OutgoingMessage(
                message_type="text",
                content="Obrigado pelo contato e tenha uma ótima semana! Até a próxima!",
            )]

        return None

    def _activate_handoff(self, session: dict, clinic_id: str, phone: str, reason: str = "") -> None:
        session["state"] = ConversationState.HUMAN_HANDOFF.value
        session["human_handoff_requested_at"] = int(time.time())
        logger.info(f"[AIEngine] Handoff activated for {phone}, reason={reason}")

    # ──────────────────────────────────────────────
    # Session management (DynamoDB)
    # ──────────────────────────────────────────────

    def _load_session(self, clinic_id: str, phone: str) -> dict:
        try:
            response = self.sessions_table.get_item(
                Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
            )
            item = response.get("Item")
            if item:
                return item.get("session", {})
        except Exception as e:
            logger.error(f"[AIEngine] Error loading session: {e}")
        return {}

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
            logger.error(f"[AIEngine] Error saving session: {e}")

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _load_clinic(self, clinic_id: str) -> Optional[dict]:
        rows = self.db.execute_query(
            """
            SELECT clinic_id, name, display_name, phone, address, timezone,
                   business_hours, buffer_minutes, pre_session_instructions
            FROM scheduler.clinics
            WHERE clinic_id = %s AND active = true
            """,
            (clinic_id,),
        )
        return rows[0] if rows else None
