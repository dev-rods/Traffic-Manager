import json
import logging
import os
import time

import boto3

from src.utils.http import parse_body, http_response, require_api_key, extract_query_param
from src.services.conversation_engine import ConversationState

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ATTENDANT_TTL_SECONDS = 24 * 60 * 60


def _get_sessions_table():
    dynamodb = boto3.resource("dynamodb")
    return dynamodb.Table(os.environ["CONVERSATION_SESSIONS_TABLE"])


def _load_session(table, clinic_id, phone):
    try:
        response = table.get_item(
            Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}
        )
        return response.get("Item", {})
    except Exception as e:
        logger.error(f"[Attendant] Error loading session: {e}")
        return {}


def _save_session(table, clinic_id, phone, item):
    try:
        session = item.get("session", {})
        now = int(time.time())
        table.put_item(
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
        logger.error(f"[Attendant] Error saving session: {e}")


def handler(event, context):
    """
    Attendant control API.

    POST /attendant/activate   — pause bot for a phone
    POST /attendant/deactivate — resume bot for a phone
    GET  /attendant/status     — check bot status for a phone
    """
    method = event.get("httpMethod", "").upper()
    path = event.get("path", "")

    _, auth_error = require_api_key(event)
    if auth_error:
        return auth_error

    if method == "GET" and path.endswith("/status"):
        return _handle_status(event)
    elif method == "POST" and path.endswith("/activate"):
        return _handle_activate(event)
    elif method == "POST" and path.endswith("/deactivate"):
        return _handle_deactivate(event)
    else:
        return http_response(404, {"status": "ERROR", "message": "Rota nao encontrada"})


def _handle_activate(event):
    body = parse_body(event)
    if not body:
        return http_response(400, {"status": "ERROR", "message": "Body obrigatorio"})

    clinic_id = body.get("clinic_id")
    phone = body.get("phone")
    if not clinic_id or not phone:
        return http_response(400, {"status": "ERROR", "message": "clinic_id e phone obrigatorios"})

    phone = _normalize_phone(phone)
    table = _get_sessions_table()
    item = _load_session(table, clinic_id, phone)
    session = item.get("session", {})

    session["_previous_state_before_attendant"] = session.get("state", "")
    session["state"] = ConversationState.HUMAN_ATTENDANT_ACTIVE.value
    session["attendant_active_until"] = int(time.time()) + ATTENDANT_TTL_SECONDS
    item["session"] = session

    _save_session(table, clinic_id, phone, item)
    logger.info(f"[Attendant] Bot pausado para {phone} na clinica {clinic_id}")

    return http_response(200, {
        "status": "OK",
        "message": f"Bot pausado para {phone} por 24h",
        "attendant_active_until": session["attendant_active_until"],
    })


def _handle_deactivate(event):
    body = parse_body(event)
    if not body:
        return http_response(400, {"status": "ERROR", "message": "Body obrigatorio"})

    clinic_id = body.get("clinic_id")
    phone = body.get("phone")
    if not clinic_id or not phone:
        return http_response(400, {"status": "ERROR", "message": "clinic_id e phone obrigatorios"})

    phone = _normalize_phone(phone)
    table = _get_sessions_table()
    item = _load_session(table, clinic_id, phone)
    session = item.get("session", {})

    session["state"] = ConversationState.WELCOME.value
    session.pop("attendant_active_until", None)
    session.pop("human_handoff_requested_at", None)
    session.pop("_previous_state_before_attendant", None)
    item["session"] = session

    _save_session(table, clinic_id, phone, item)
    logger.info(f"[Attendant] Bot retomado para {phone} na clinica {clinic_id}")

    return http_response(200, {
        "status": "OK",
        "message": f"Bot retomado para {phone}",
    })


def _handle_status(event):
    clinic_id = extract_query_param(event, "clinic_id")
    phone = extract_query_param(event, "phone")
    if not clinic_id or not phone:
        return http_response(400, {"status": "ERROR", "message": "clinic_id e phone obrigatorios como query params"})

    phone = _normalize_phone(phone)
    table = _get_sessions_table()
    item = _load_session(table, clinic_id, phone)
    session = item.get("session", {})

    state = session.get("state", "")
    is_paused = state in (
        ConversationState.HUMAN_ATTENDANT_ACTIVE.value,
        ConversationState.HUMAN_HANDOFF.value,
    )

    ttl = session.get("attendant_active_until", 0)
    now = int(time.time())
    expired = ttl > 0 and now >= ttl

    if is_paused and expired:
        is_paused = False

    return http_response(200, {
        "status": "OK",
        "bot_paused": is_paused,
        "conversation_state": state,
        "attendant_active_until": ttl if is_paused else None,
        "ttl_remaining_seconds": max(0, ttl - now) if is_paused and ttl else 0,
    })


def _normalize_phone(phone):
    return "".join(c for c in phone if c.isdigit())
