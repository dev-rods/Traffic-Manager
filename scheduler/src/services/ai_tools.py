import json
import logging
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional

from src.services.duration_rules import calcula_duracao

logger = logging.getLogger(__name__)


_PT_WEEKDAY_SHORT = ["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo"]
_PT_MONTH = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _format_pt_br_date_label(iso_date: str) -> str:
    """Format an ISO date (YYYY-MM-DD) as 'Terça, 12 de maio' (PT-BR)."""
    try:
        d = datetime.strptime(iso_date, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return iso_date
    weekday = _PT_WEEKDAY_SHORT[d.weekday()]
    month = _PT_MONTH[d.month - 1]
    return f"{weekday}, {d.day} de {month}"


# ──────────────────────────────────────────────
# Tool definitions (OpenAI function calling format)
# ──────────────────────────────────────────────

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "list_services",
            "description": "List all active services offered by the clinic. Returns service name, description, and base price.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_areas",
            "description": "List available treatment areas for given services. Only call this when the patient has confirmed they want to BOOK an appointment and the service has been identified. Do NOT call for questions/doubts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "UUIDs (format: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx) of the services, as returned by list_services. NEVER use service names or slugs.",
                    },
                },
                "required": ["service_ids"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_availability",
            "description": "Check which days have available slots for the selected areas. Only call AFTER the patient has selected areas and confirmed. Do NOT call for questions/doubts. Returns objects with `date` (YYYY-MM-DD, used internally) and `label` (PT-BR formatted, ALWAYS use this for display — never compute the weekday yourself).",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_area_pairs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "area_id": {"type": "string"},
                            },
                            "required": ["service_id", "area_id"],
                        },
                        "description": "Areas the patient selected. The session duration is derived from these — never state or estimate a duration yourself.",
                    },
                },
                "required": ["service_area_pairs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time_slots",
            "description": "Get available time slots for a specific date and the selected areas. Only call AFTER the patient has chosen a date from check_availability. Returns `available_slots` (HH:MM strings) and `date_label` (PT-BR formatted date — use for display).",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                    "service_area_pairs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "area_id": {"type": "string"},
                            },
                            "required": ["service_id", "area_id"],
                        },
                        "description": "Areas the patient selected. The session duration is derived from these — never state or estimate a duration yourself.",
                    },
                },
                "required": ["date", "service_area_pairs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sem_consulta_necessaria",
            "description": (
                "Declare that this message needs no data lookup — the patient is giving you "
                "registration details (name, birth date, CPF, e-mail), agreeing, thanking or "
                "chatting. Call this INSTEAD of answering directly when no other tool applies. "
                "Never call it to avoid looking something up: if the patient asked about price, "
                "schedule, duration, availability or anything about the procedure, the answer "
                "comes from a tool, not from you."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "motivo": {
                        "type": "string",
                        "description": "Why no lookup is needed, in a few words.",
                    },
                },
                "required": ["motivo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_duration",
            "description": "How long the session will take for the selected areas, in minutes. Call this before stating ANY duration to the patient — never add up area durations yourself and never answer from memory. Returns `total_duration_minutes`, already rounded and within the clinic limits.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_area_pairs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "area_id": {"type": "string"},
                            },
                            "required": ["service_id", "area_id"],
                        },
                        "description": "Areas the patient selected.",
                    },
                },
                "required": ["service_area_pairs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_appointments",
            "description": "Look up active appointments for the current patient by phone number.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_faq_answer",
            "description": "Search the clinic FAQ for an answer to the patient's question. ALWAYS call this FIRST when the patient asks a question (phrases with 'posso', 'pode', 'como funciona', 'quanto custa', 'é possível', etc.) BEFORE calling any booking tools.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "The patient's question or topic to search for",
                    },
                },
                "required": ["question"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_clinic_info",
            "description": "Get clinic information: name, address, phone, business hours.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "book_appointment",
            "description": "Book an appointment. Requires all data to be collected: service areas, date, time, and the patient registration data (full name, birth date, CPF, email). Always call check_availability and get_time_slots before booking. Always call calculate_discount before booking to get the correct pricing.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_area_pairs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "area_id": {"type": "string"},
                            },
                            "required": ["service_id", "area_id"],
                        },
                        "description": "List of service-area pairs to book",
                    },
                    "date": {
                        "type": "string",
                        "description": "Appointment date in YYYY-MM-DD format",
                    },
                    "time": {
                        "type": "string",
                        "description": "Appointment start time in HH:MM format",
                    },
                    "full_name": {
                        "type": "string",
                        "description": "Patient's full name",
                    },
                    "birth_date": {
                        "type": "string",
                        "description": "Patient's birth date in YYYY-MM-DD format",
                    },
                    "cpf": {
                        "type": "string",
                        "description": "Patient's CPF, digits only or formatted",
                    },
                    "email": {
                        "type": "string",
                        "description": "Patient's email address",
                    },
                    "discount_pct": {
                        "type": "integer",
                        "description": "Discount percentage from calculate_discount (0 if no discount)",
                    },
                    "discount_reason": {
                        "type": "string",
                        "description": "Discount reason from calculate_discount (e.g. 'first_session', 'tier_2')",
                    },
                    "original_price_cents": {
                        "type": "integer",
                        "description": "Original total price in cents before discount",
                    },
                    "final_price_cents": {
                        "type": "integer",
                        "description": "Final price in cents after discount",
                    },
                },
                "required": ["service_area_pairs", "date", "time", "full_name"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "reschedule_appointment",
            "description": "Reschedule an existing appointment to a new date and time. Call lookup_appointments first to get the appointment_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to reschedule",
                    },
                    "new_date": {
                        "type": "string",
                        "description": "New date in YYYY-MM-DD format",
                    },
                    "new_time": {
                        "type": "string",
                        "description": "New time in HH:MM format",
                    },
                },
                "required": ["appointment_id", "new_date", "new_time"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "cancel_appointment",
            "description": "Cancel an existing appointment. Call lookup_appointments first to get the appointment_id.",
            "parameters": {
                "type": "object",
                "properties": {
                    "appointment_id": {
                        "type": "string",
                        "description": "UUID of the appointment to cancel",
                    },
                },
                "required": ["appointment_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "request_human_handoff",
            "description": "Transfer the conversation to a human attendant. Use when the patient explicitly asks, or when you cannot help after 2 attempts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Reason for handoff (e.g., 'patient_request', 'incompreensão', 'complex_issue')",
                    },
                },
                "required": ["reason"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "present_options",
            "description": "Present structured options to the patient as WhatsApp buttons. ALWAYS use this when showing choices (services, areas, dates, times).",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message text to display above the options",
                    },
                    "options": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "id": {"type": "string", "description": "Unique option identifier"},
                                "label": {"type": "string", "description": "Display text (max 24 chars for WhatsApp buttons)"},
                            },
                            "required": ["id", "label"],
                        },
                        "description": "List of options to present as buttons",
                    },
                },
                "required": ["message", "options"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_discount",
            "description": "Calculate applicable discount for the patient based on clinic rules. Call this BEFORE showing the booking summary so you can display the correct price. Returns discount percentage, original price, and discounted price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_area_pairs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "area_id": {"type": "string"},
                            },
                            "required": ["service_id", "area_id"],
                        },
                        "description": "List of service-area pairs selected by the patient",
                    },
                },
                "required": ["service_area_pairs"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_pre_session_instructions",
            "description": "Get pre-session care instructions for the booked service areas. Call this AFTER a successful booking to inform the patient about preparation steps.",
            "parameters": {
                "type": "object",
                "properties": {
                    "service_area_pairs": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "service_id": {"type": "string"},
                                "area_id": {"type": "string"},
                            },
                            "required": ["service_id", "area_id"],
                        },
                        "description": "List of service-area pairs that were booked",
                    },
                },
                "required": ["service_area_pairs"],
            },
        },
    },
]


# ──────────────────────────────────────────────
# Format conversion helper
# ──────────────────────────────────────────────

def get_tool_definitions(format="anthropic"):
    """
    Return tool definitions in the requested format.

    - "openai": Original OpenAI function calling format
    - "anthropic": Anthropic tool use format
    """
    if format == "openai":
        return TOOL_DEFINITIONS

    # Convert OpenAI format → Anthropic format
    anthropic_tools = []
    for tool in TOOL_DEFINITIONS:
        func = tool["function"]
        anthropic_tools.append({
            "name": func["name"],
            "description": func["description"],
            "input_schema": func["parameters"],
        })
    return anthropic_tools


# ──────────────────────────────────────────────
# Tool Executor
# ──────────────────────────────────────────────

class ToolExecutor:
    """Executes AI tool calls by delegating to existing services."""

    def __init__(self, db, availability_engine, appointment_service):
        self.db = db
        self.availability_engine = availability_engine
        self.appointment_service = appointment_service

    def execute(self, tool_name, arguments, context):
        """
        Execute a tool and return the result dict.

        context must contain: clinic_id, phone
        """
        clinic_id = context["clinic_id"]
        phone = context.get("phone", "")

        logger.info(f"[ToolExecutor] Executing {tool_name} with args={json.dumps(arguments)[:200]}")

        try:
            handler = getattr(self, f"_tool_{tool_name}", None)
            if not handler:
                return {"error": f"Unknown tool: {tool_name}"}
            return handler(arguments, clinic_id, phone, context)
        except Exception as e:
            logger.error(f"[ToolExecutor] Error executing {tool_name}: {e}")
            return {"error": str(e)}

    # ── Read-only tools ──

    def _tool_list_services(self, args, clinic_id, phone, ctx):
        rows = self.db.execute_query(
            """
            SELECT id, name, description, duration_minutes, price_cents
            FROM scheduler.services
            WHERE clinic_id = %s AND active = true
            ORDER BY name
            """,
            (clinic_id,),
        )
        services = []
        for r in rows:
            services.append({
                "id": str(r["id"]),
                "name": r["name"],
                "description": r.get("description") or "",
                "duration_minutes": r["duration_minutes"],
                "price_cents": r.get("price_cents"),
            })
        single_service = len(services) == 1
        return {"services": services, "single_service": single_service}

    def _tool_list_areas(self, args, clinic_id, phone, ctx):
        service_ids = args.get("service_ids", [])
        if not service_ids:
            return {"error": "service_ids is required"}

        placeholders = ",".join(["%s"] * len(service_ids))
        rows = self.db.execute_query(
            f"""
            SELECT sa.id as service_area_id, sa.service_id, s.name as service_name,
                   sa.area_id, a.name as area_name,
                   COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                   COALESCE(sa.price_cents, s.price_cents) as price_cents
            FROM scheduler.service_areas sa
            JOIN scheduler.services s ON s.id = sa.service_id
            JOIN scheduler.areas a ON a.id = sa.area_id
            WHERE sa.service_id IN ({placeholders})
              AND sa.active = true AND s.active = true AND a.active = true
            ORDER BY a.display_order, a.name
            """,
            tuple(service_ids),
        )
        areas = []
        for r in rows:
            price_cents = r.get("price_cents")
            areas.append({
                "service_id": str(r["service_id"]),
                "area_id": str(r["area_id"]),
                "service_name": r["service_name"],
                "area_name": r["area_name"],
                # A duração por área não é exposta ao modelo de propósito. Ela é
                # insumo do cálculo, não resposta: vendo 10 min por área, ele
                # soma seis e diz 60, ou repete o 10 de uma área como se fosse a
                # sessão inteira - que na verdade é 15, o piso. A duração da
                # sessão vem de calculate_duration, e só de lá.
                "price_display": f"R$ {price_cents / 100:.2f}" if price_cents else None,
                "price_cents": price_cents,
            })
        return {"areas": areas}

    def _tool_check_availability(self, args, clinic_id, phone, ctx):
        if not self.availability_engine:
            return {"error": "Availability engine not available"}
        # A duração é derivada das áreas, nunca do que o modelo informa. Ver
        # duration_rules.py: ele já pediu horário para uma sessão de 4 minutos.
        total_duration = calcula_duracao(self.db, clinic_id, args.get("service_area_pairs"))
        days = self.availability_engine.get_available_days_multi(clinic_id, total_duration)
        return {
            "available_dates": [
                {"date": d, "label": _format_pt_br_date_label(d)} for d in days
            ]
        }

    def _tool_get_time_slots(self, args, clinic_id, phone, ctx):
        target_date = args.get("date")
        if not target_date:
            return {"error": "date is required"}
        if not self.availability_engine:
            return {"error": "Availability engine not available"}
        total_duration = calcula_duracao(self.db, clinic_id, args.get("service_area_pairs"))
        slots = self.availability_engine.get_available_slots_multi(clinic_id, target_date, total_duration)
        return {
            "date": target_date,
            "date_label": _format_pt_br_date_label(target_date),
            "available_slots": slots,
        }

    def _tool_sem_consulta_necessaria(self, args, clinic_id, phone, ctx):
        """A saída para quando a mensagem realmente não pede dado nenhum.

        Existe porque a alternativa era o código adivinhar pelo formato do texto
        se a pessoa estava mandando um nome ou escolhendo uma área - e "Buço
        Completo" tem exatamente a cara de um nome próprio. Quem sabe o que a
        mensagem significa é quem tem a conversa inteira.

        Devolve dicionário vazio de propósito: nada aqui pode respaldar uma
        afirmação factual na resposta.
        """
        logger.info(f"[SemConsulta] {phone}: {str(args.get('motivo'))[:80]}")
        return {}

    def _tool_calculate_duration(self, args, clinic_id, phone, ctx):
        """A duração da sessão para as áreas escolhidas.

        Existe para o agente poder AFIRMAR uma duração com respaldo. Sem ela,
        em 02/09/2026 ele respondeu "quanto tempo dura?" de memória, sem
        chamar tool nenhuma - não havia o que chamar.
        """
        pares = args.get("service_area_pairs") or []
        minutos = calcula_duracao(self.db, clinic_id, pares)
        return {
            "total_duration_minutes": minutos,
            "area_count": len(pares),
        }

    def _tool_lookup_appointments(self, args, clinic_id, phone, ctx):
        if not self.appointment_service:
            return {"error": "Appointment service not available"}
        appointments = self.appointment_service.get_active_appointments_by_phone(clinic_id, phone)
        result = []
        for appt in appointments:
            result.append({
                "id": str(appt["id"]),
                "date": str(appt.get("appointment_date", "")),
                "time": str(appt.get("start_time", "")),
                "status": appt.get("status", ""),
                "service_name": appt.get("service_name", ""),
                "full_name": appt.get("full_name", ""),
            })
        return {"appointments": result}

    def _tool_get_faq_answer(self, args, clinic_id, phone, ctx):
        question = args.get("question", "")

        rows = self.db.execute_query(
            """
            SELECT question_label, answer
            FROM scheduler.faq_items
            WHERE clinic_id = %s AND active = true
              AND (question_label ILIKE %s OR answer ILIKE %s)
            ORDER BY display_order
            LIMIT 3
            """,
            (clinic_id, f"%{question}%", f"%{question}%"),
        )
        if rows:
            return {"answers": [{"question": r["question_label"], "answer": r["answer"]} for r in rows]}

        keywords = [w for w in question.lower().split() if len(w) >= 3]
        if keywords:
            conditions = []
            params = [clinic_id]
            for kw in keywords[:5]:
                conditions.append("(question_label ILIKE %s OR answer ILIKE %s)")
                params.extend([f"%{kw}%", f"%{kw}%"])

            where_clause = " OR ".join(conditions)
            rows = self.db.execute_query(
                f"""
                SELECT question_label, answer
                FROM scheduler.faq_items
                WHERE clinic_id = %s AND active = true AND ({where_clause})
                ORDER BY display_order
                LIMIT 3
                """,
                tuple(params),
            )
            if rows:
                return {"answers": [{"question": r["question_label"], "answer": r["answer"]} for r in rows]}

        # A mensagem anterior aqui mandava "use seu conhecimento sobre depilação
        # a laser para responder" - a própria tool autorizando a invenção que o
        # resto do sistema existe para impedir. Cada clínica tem protocolo
        # próprio: intervalo entre sessões, cuidados e contraindicações não são
        # conhecimento geral, são política da casa.
        return {
            "answers": [],
            "message": (
                "Nenhuma resposta encontrada no FAQ desta clínica. Você NÃO SABE a "
                "resposta. Não use conhecimento geral. Diga que vai confirmar com uma "
                "especialista e chame request_human_handoff."
            ),
        }

    def _tool_get_clinic_info(self, args, clinic_id, phone, ctx):
        rows = self.db.execute_query(
            """
            SELECT name, display_name, phone, address, timezone, business_hours
            FROM scheduler.clinics
            WHERE clinic_id = %s
            """,
            (clinic_id,),
        )
        if not rows:
            return {"error": "Clinic not found"}
        c = rows[0]
        return {
            "name": c.get("display_name") or c["name"],
            "phone": c.get("phone") or "",
            "address": c.get("address") or "",
            "timezone": c.get("timezone", "America/Sao_Paulo"),
            "business_hours": c.get("business_hours", {}),
        }

    # ── Write tools ──

    def _salva_cadastro_do_paciente(self, clinic_id, phone, *, birth_date=None, cpf=None, email=None):
        """Grava os dados de cadastro no paciente, se vieram.

        COALESCE preserva o que já existe: se a pessoa informar só parte dos dados
        numa conversa e o resto em outra, nada é apagado. Nunca propaga erro —
        perder o agendamento por causa de um CPF mal formatado seria pior.
        """
        if not any([birth_date, cpf, email]):
            return
        try:
            from src.utils.phone import normalize_phone

            cpf_digitos = re.sub(r"\D", "", cpf) if cpf else None
            self.db.execute_write(
                """
                UPDATE scheduler.patients
                SET birth_date = COALESCE(%s::date, birth_date),
                    cpf = COALESCE(%s, cpf),
                    email = COALESCE(%s, email),
                    updated_at = NOW()
                WHERE clinic_id = %s AND phone = %s
                """,
                (birth_date or None, cpf_digitos or None, email or None,
                 clinic_id, normalize_phone(phone)),
            )
        except Exception as e:
            logger.warning(f"[ToolExecutor] Falha ao gravar cadastro do paciente: {e}")

    def _tool_book_appointment(self, args, clinic_id, phone, ctx):
        if not self.appointment_service:
            return {"error": "Appointment service not available"}

        service_area_pairs = args.get("service_area_pairs", [])
        date = args.get("date")
        time_str = args.get("time")
        full_name = args.get("full_name")

        if not all([service_area_pairs, date, time_str, full_name]):
            return {"error": "Missing required fields: service_area_pairs, date, time, full_name"}

        total_duration = calcula_duracao(self.db, clinic_id, service_area_pairs)

        primary_service_id = service_area_pairs[0]["service_id"]

        # Extract optional discount fields
        discount_pct = args.get("discount_pct", 0)
        discount_reason = args.get("discount_reason")
        original_price_cents = args.get("original_price_cents")
        final_price_cents = args.get("final_price_cents")

        # Dados de cadastro: gravados no paciente, não no agendamento. São opcionais
        # na tool para o agendamento não falhar se a pessoa se recusar a informar,
        # mas o prompt instrui a pedir todos antes de chamar.
        self._salva_cadastro_do_paciente(
            clinic_id, phone,
            birth_date=args.get("birth_date"),
            cpf=args.get("cpf"),
            email=args.get("email"),
        )

        result = self.appointment_service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=primary_service_id,
            date=date,
            time=time_str,
            service_area_pairs=service_area_pairs,
            total_duration_minutes=total_duration,
            full_name=full_name,
            discount_pct=discount_pct,
            discount_reason=discount_reason,
            original_price_cents=original_price_cents,
            final_price_cents=final_price_cents,
        )
        return {
            "success": True,
            "appointment_id": str(result.get("id", "")),
            "date": date,
            "time": time_str,
            "full_name": full_name,
            "total_duration_minutes": total_duration,
            # Sem isto, dizer "agendamento confirmado" logo depois de criar o
            # agendamento era acusado de afirmação sem respaldo - o fato tinha
            # acabado de acontecer, mas a tool não o devolvia.
            #
            # Vem do RETURNING do INSERT, não de constante: cravar "CONFIRMED"
            # aqui faria a tool respaldar um status que ela mesma inventou, que
            # é o oposto do que a proveniência existe para garantir.
            "status": result.get("status"),
        }

    def _tool_reschedule_appointment(self, args, clinic_id, phone, ctx):
        if not self.appointment_service:
            return {"error": "Appointment service not available"}
        appointment_id = args.get("appointment_id")
        new_date = args.get("new_date")
        new_time = args.get("new_time")
        if not all([appointment_id, new_date, new_time]):
            return {"error": "Missing required fields: appointment_id, new_date, new_time"}
        self.appointment_service.reschedule_appointment(appointment_id, new_date, new_time)
        return {"success": True, "new_date": new_date, "new_time": new_time}

    def _tool_cancel_appointment(self, args, clinic_id, phone, ctx):
        if not self.appointment_service:
            return {"error": "Appointment service not available"}
        appointment_id = args.get("appointment_id")
        if not appointment_id:
            return {"error": "appointment_id is required"}
        self.appointment_service.cancel_appointment(appointment_id)
        return {"success": True, "appointment_id": appointment_id}

    def _tool_request_human_handoff(self, args, clinic_id, phone, ctx):
        reason = args.get("reason", "patient_request")
        return {"success": True, "handoff_requested": True, "reason": reason}

    def _tool_present_options(self, args, clinic_id, phone, ctx):
        return {
            "presented": True,
            "message": args.get("message", ""),
            "options": args.get("options", []),
        }

    # ── New tools ──

    def _tool_calculate_discount(self, args, clinic_id, phone, ctx):
        service_area_pairs = args.get("service_area_pairs", [])
        if not service_area_pairs:
            return {"error": "service_area_pairs is required"}

        # Calculate total price from service_area_pairs
        total_price_cents = 0
        for pair in service_area_pairs:
            rows = self.db.execute_query(
                """
                SELECT COALESCE(sa.price_cents, s.price_cents) as price_cents
                FROM scheduler.service_areas sa
                JOIN scheduler.services s ON s.id = sa.service_id
                WHERE sa.service_id = %s AND sa.area_id = %s
                """,
                (pair["service_id"], pair["area_id"]),
            )
            if rows and rows[0].get("price_cents"):
                total_price_cents += rows[0]["price_cents"]

        if not total_price_cents:
            return {
                "discount_pct": 0,
                "discount_reason": None,
                "original_price_cents": 0,
                "discounted_price_cents": 0,
                "price_display": "Valor a consultar",
            }

        # Fetch discount rules
        rules_rows = self.db.execute_query(
            "SELECT * FROM scheduler.discount_rules WHERE clinic_id = %s AND is_active = TRUE",
            (clinic_id,),
        )
        rules = rules_rows[0] if rules_rows else None

        if not rules:
            return {
                "discount_pct": 0,
                "discount_reason": None,
                "original_price_cents": total_price_cents,
                "discounted_price_cents": total_price_cents,
                "price_display": f"R$ {total_price_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            }

        # Check if first session
        count_rows = self.db.execute_query(
            """SELECT COUNT(*) as cnt FROM scheduler.appointments a
               JOIN scheduler.patients p ON a.patient_id = p.id
               WHERE a.clinic_id = %s AND p.phone = %s AND a.status = 'CONFIRMED'""",
            (clinic_id, phone),
        )
        is_first = int(count_rows[0]["cnt"]) == 0 if count_rows else True

        # Evaluate every applicable rule and pick the best (highest pct) for the patient.
        # Discounts are mutually exclusive — only the winner is applied.
        candidates = []

        first_pct = int(rules.get("first_session_discount_pct") or 0)
        if is_first and first_pct > 0:
            candidates.append((first_pct, "first_session"))

        area_count = len(service_area_pairs)
        t2_min = int(rules.get("tier_2_min_areas") or 0)
        t3_min = int(rules.get("tier_3_min_areas") or 0)
        t2_pct = int(rules.get("tier_2_discount_pct") or 0)
        t3_pct = int(rules.get("tier_3_discount_pct") or 0)

        if t3_min and area_count >= t3_min and t3_pct > 0:
            candidates.append((t3_pct, "tier_3"))
        elif t2_min and area_count >= t2_min and t2_pct > 0:
            candidates.append((t2_pct, "tier_2"))

        if candidates:
            discount_pct, discount_reason = max(candidates, key=lambda c: c[0])
        else:
            discount_pct = 0
            discount_reason = None

        discounted_price = total_price_cents * (100 - discount_pct) // 100

        original_display = f"R$ {total_price_cents / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        discounted_display = f"R$ {discounted_price / 100:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

        result = {
            "discount_pct": discount_pct,
            "discount_reason": discount_reason,
            "original_price_cents": total_price_cents,
            "discounted_price_cents": discounted_price,
            "original_price_display": original_display,
            "discounted_price_display": discounted_display,
            "is_first_session": is_first,
        }

        if discount_pct > 0:
            result["discount_message"] = (
                f"Desconto de {discount_pct}% aplicado! "
                f"De {original_display} por {discounted_display}"
            )

        logger.info(
            f"[ToolExecutor] calculate_discount: pct={discount_pct} reason={discount_reason} "
            f"original={total_price_cents} discounted={discounted_price}"
        )

        return result

    def _tool_get_pre_session_instructions(self, args, clinic_id, phone, ctx):
        service_area_pairs = args.get("service_area_pairs", [])
        if not service_area_pairs:
            return {"has_instructions": False, "instructions": ""}

        # Get clinic-level instructions
        clinic_rows = self.db.execute_query(
            "SELECT pre_session_instructions FROM scheduler.clinics WHERE clinic_id = %s",
            (clinic_id,),
        )
        clinic_instructions = ""
        if clinic_rows and clinic_rows[0].get("pre_session_instructions"):
            clinic_instructions = clinic_rows[0]["pre_session_instructions"]

        # Get service_area-level instructions (more specific, take priority)
        sa_instructions = ""
        if service_area_pairs:
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
        instructions = "\n\n".join(parts)

        return {
            "has_instructions": bool(instructions),
            "instructions": instructions,
        }
