import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
                        "description": "UUIDs of the services to list areas for",
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
            "description": "Check which days have available slots for the given total duration. Only call AFTER the patient has selected areas and confirmed. Do NOT call for questions/doubts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "total_duration_minutes": {
                        "type": "integer",
                        "description": "Total duration of all selected areas combined (in minutes)",
                    },
                },
                "required": ["total_duration_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_time_slots",
            "description": "Get available time slots for a specific date and total duration. Only call AFTER the patient has chosen a date from check_availability.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "Date in YYYY-MM-DD format",
                    },
                    "total_duration_minutes": {
                        "type": "integer",
                        "description": "Total duration of all selected areas combined (in minutes)",
                    },
                },
                "required": ["date", "total_duration_minutes"],
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
            "description": "Book an appointment. Requires all data to be collected: service areas, date, time, and patient full name. Always call check_availability and get_time_slots before booking.",
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
]


# ──────────────────────────────────────────────
# Tool Executor
# ──────────────────────────────────────────────

class ToolExecutor:
    """Executes AI tool calls by delegating to existing services."""

    def __init__(self, db, availability_engine, appointment_service):
        self.db = db
        self.availability_engine = availability_engine
        self.appointment_service = appointment_service

    def execute(self, tool_name: str, arguments: dict, context: dict) -> dict:
        """
        Execute a tool and return the result dict.

        context must contain: clinic_id, phone
        context may contain: collected_data (for validation)
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

    def _tool_list_services(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
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

    def _tool_list_areas(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
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
                "duration_minutes": r["duration_minutes"],
                "price_display": f"R$ {price_cents / 100:.2f}" if price_cents else None,
                "price_cents": price_cents,
            })
        return {"areas": areas}

    def _tool_check_availability(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        total_duration = args.get("total_duration_minutes", 60)
        if not self.availability_engine:
            return {"error": "Availability engine not available"}
        days = self.availability_engine.get_available_days_multi(clinic_id, total_duration)
        return {"available_dates": days}

    def _tool_get_time_slots(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        date = args.get("date")
        total_duration = args.get("total_duration_minutes", 60)
        if not date:
            return {"error": "date is required"}
        if not self.availability_engine:
            return {"error": "Availability engine not available"}
        slots = self.availability_engine.get_available_slots_multi(clinic_id, date, total_duration)
        return {"date": date, "available_slots": slots}

    def _tool_lookup_appointments(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
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

    def _tool_get_faq_answer(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        question = args.get("question", "")

        # First: try exact ILIKE match on the full question
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

        # Second: try matching individual keywords (3+ chars) from the question
        keywords = [w for w in question.lower().split() if len(w) >= 3]
        if keywords:
            conditions = []
            params = [clinic_id]
            for kw in keywords[:5]:  # max 5 keywords
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

        return {"answers": [], "message": "Nenhuma resposta encontrada no FAQ. Use seu conhecimento sobre depilação a laser para responder, ou ofereça transferir para um atendente."}

    def _tool_get_clinic_info(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
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

    def _tool_book_appointment(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        if not self.appointment_service:
            return {"error": "Appointment service not available"}

        service_area_pairs = args.get("service_area_pairs", [])
        date = args.get("date")
        time_str = args.get("time")
        full_name = args.get("full_name")

        if not all([service_area_pairs, date, time_str, full_name]):
            return {"error": "Missing required fields: service_area_pairs, date, time, full_name"}

        # Calculate total duration from service_area_pairs
        total_duration = 0
        for pair in service_area_pairs:
            rows = self.db.execute_query(
                """
                SELECT COALESCE(sa.duration_minutes, s.duration_minutes) as duration_minutes,
                       COALESCE(sa.price_cents, s.price_cents) as price_cents
                FROM scheduler.service_areas sa
                JOIN scheduler.services s ON s.id = sa.service_id
                WHERE sa.service_id = %s AND sa.area_id = %s
                """,
                (pair["service_id"], pair["area_id"]),
            )
            if rows:
                total_duration += rows[0]["duration_minutes"] or 0

        # Use the first service_id for the primary service field
        primary_service_id = service_area_pairs[0]["service_id"]

        result = self.appointment_service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=primary_service_id,
            date=date,
            time=time_str,
            service_area_pairs=service_area_pairs,
            total_duration_minutes=total_duration,
            full_name=full_name,
        )
        return {
            "success": True,
            "appointment_id": str(result.get("id", "")),
            "date": date,
            "time": time_str,
            "full_name": full_name,
            "total_duration_minutes": total_duration,
        }

    def _tool_reschedule_appointment(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        if not self.appointment_service:
            return {"error": "Appointment service not available"}
        appointment_id = args.get("appointment_id")
        new_date = args.get("new_date")
        new_time = args.get("new_time")
        if not all([appointment_id, new_date, new_time]):
            return {"error": "Missing required fields: appointment_id, new_date, new_time"}
        result = self.appointment_service.reschedule_appointment(appointment_id, new_date, new_time)
        return {"success": True, "new_date": new_date, "new_time": new_time}

    def _tool_cancel_appointment(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        if not self.appointment_service:
            return {"error": "Appointment service not available"}
        appointment_id = args.get("appointment_id")
        if not appointment_id:
            return {"error": "appointment_id is required"}
        result = self.appointment_service.cancel_appointment(appointment_id)
        return {"success": True, "appointment_id": appointment_id}

    def _tool_request_human_handoff(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        reason = args.get("reason", "patient_request")
        # Signal to the engine that handoff was requested
        return {"success": True, "handoff_requested": True, "reason": reason}

    def _tool_present_options(self, args: dict, clinic_id: str, phone: str, ctx: dict) -> dict:
        # This tool is special — the engine intercepts it to generate WhatsApp buttons.
        # Return the data as-is for the engine to handle.
        return {
            "presented": True,
            "message": args.get("message", ""),
            "options": args.get("options", []),
        }
