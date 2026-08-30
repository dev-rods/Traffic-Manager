import json
import logging
import os
import time

import boto3

from src.utils.http import parse_body, http_response, require_api_key, extract_query_param
from src.services.conversation_engine import ConversationState
from src.services.bot_policy import should_bot_reply

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ATTENDANT_TTL_SECONDS = 24 * 60 * 60

# Payload da auto-invocação assíncrona. Não vem do API Gateway.
TAREFA_RETOMADA = "responder_retomada"


def _get_clinic(clinic_id):
    """Clínica com a política de resposta. Falha vira dict vazio, que o
    should_bot_reply trata como política ALL — o comportamento histórico."""
    try:
        from src.services.db.postgres import PostgresService

        rows = PostgresService().execute_query(
            "SELECT bot_autoreply_policy, bot_pilot_phones, bot_paused "
            "FROM scheduler.clinics WHERE clinic_id = %s",
            (clinic_id,),
        )
        return rows[0] if rows else {}
    except Exception as e:
        logger.warning(f"[Attendant] Não consegui ler a política de {clinic_id}: {e}")
        return {}


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
    # Execução assíncrona que a própria função agendou. Chega sem httpMethod:
    # não passou pelo API Gateway, então não tem o teto de 29s.
    if event.get("internal_task") == TAREFA_RETOMADA:
        from src.services.conversation_resume import responder_se_ficou_em_aberto

        return {"replied": responder_se_ficou_em_aberto(event["clinic_id"], event["phone"])}

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
        return _handle_deactivate(event, context)
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


def _handle_deactivate(event, context):
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
    # Marca a conversa como elegível. Sem isso, retomar o bot não teria efeito nas
    # clínicas com política LEADS_ONLY: limpar o modo atendente libera a conversa,
    # mas o bot só responde quem está marcado. Retomar tem que valer em qualquer
    # política, senão o botão do painel mente para quem clica.
    session["bot_enabled"] = True
    item["session"] = session

    _save_session(table, clinic_id, phone, item)
    logger.info(f"[Attendant] Bot retomado para {phone} na clinica {clinic_id}")

    respondendo = _agendar_retomada(clinic_id, phone, context)

    return http_response(200, {
        "status": "OK",
        "message": f"Bot retomado para {phone}",
        "answering_open_question": respondendo,
    })


def _agendar_retomada(clinic_id, phone, context):
    """Faz o bot responder o que ficou em aberto. Devolve se há o que responder.

    O guard roda aqui, e não no agente, por dois motivos: a tela precisa saber na
    hora se o bot vai falar, e chamar o LLM para ele concluir que não há nada a
    dizer custa caro e arrisca uma mensagem indevida.

    O envio vai para uma execução assíncrona porque o agente leva de 3 a 15s e o
    API Gateway corta em 29 - falhar ali mostraria erro na tela depois de a
    mensagem já ter saído.
    """
    try:
        from src.services.conversation_resume import (
            EVENTOS_PARA_CONTEXTO,
            ha_pergunta_em_aberto,
        )
        from src.services.message_tracker import MessageTracker

        eventos = MessageTracker().get_conversation_messages(
            clinic_id, phone, limit=EVENTOS_PARA_CONTEXTO
        )
        if not ha_pergunta_em_aberto(eventos):
            logger.info(f"[Attendant] Nada pendente com {phone}, bot só ativado")
            return False

        boto3.client("lambda").invoke(
            FunctionName=context.invoked_function_arn,
            InvocationType="Event",
            Payload=json.dumps({
                "internal_task": TAREFA_RETOMADA,
                "clinic_id": clinic_id,
                "phone": phone,
            }),
        )
        logger.info(f"[Attendant] Retomada agendada para {phone}")
        return True
    except Exception as e:
        # Ativar o bot já funcionou e foi salvo; responder o pendente é um extra.
        logger.error(f"[Attendant] Não consegui agendar a retomada de {phone}: {e}")
        return False


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
    atendente_ativo = state in (
        ConversationState.HUMAN_ATTENDANT_ACTIVE.value,
        ConversationState.HUMAN_HANDOFF.value,
    )

    ttl = session.get("attendant_active_until", 0)
    now = int(time.time())
    expired = ttl > 0 and now >= ttl

    if atendente_ativo and expired:
        atendente_ativo = False

    # A política da clínica também decide. Sem consultá-la, o painel mostrava
    # "Pausar bot" numa conversa que o bot já não atendia — o botão prometia uma
    # ação sem efeito. Esta é a mesma decisão que o webhook toma.
    clinic = _get_clinic(clinic_id)
    responde = should_bot_reply(clinic, session, phone) and not clinic.get("bot_paused", False)

    return http_response(200, {
        "status": "OK",
        "bot_paused": not responde,
        "pause_reason": (
            "attendant" if atendente_ativo
            else "clinic_paused" if clinic.get("bot_paused", False)
            else "not_eligible" if not responde
            else None
        ),
        "conversation_state": state,
        "attendant_active_until": ttl if atendente_ativo else None,
        "ttl_remaining_seconds": max(0, ttl - now) if atendente_ativo and ttl else 0,
    })


def _normalize_phone(phone):
    return "".join(c for c in phone if c.isdigit())
