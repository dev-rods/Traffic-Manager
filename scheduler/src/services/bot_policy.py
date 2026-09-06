"""Decide se o bot responde automaticamente uma conversa.

Função pura, sem I/O: recebe a clínica, a sessão e o telefone, devolve sim ou não.
Fica fora do handler porque é a regra que muda a cada fase do rollout, e precisa
ser testável sem subir webhook.
"""
import time
from typing import Dict, Optional

from src.utils.phone import normalize_phone

POLICY_ALL = "ALL"
POLICY_PILOT = "PILOT"
POLICY_LEADS_ONLY = "LEADS_ONLY"
POLICY_OFF = "OFF"

# Por que a conversa está pausada. O valor é informativo; o que importa é o
# campo existir - qualquer valor pausa.
PAUSA_ATENDENTE = "ATENDENTE"          # alguém da clínica respondeu
PAUSA_CONTATO_MANUAL = "CONTATO_MANUAL"  # marcaram "Já iniciada" no painel
PAUSA_CHAT_ANTERIOR = "CHAT_ANTERIOR"    # já havia conversa antes de nós
PAUSA_HANDOFF = "HANDOFF"                # o próprio bot pediu ajuda humana

CAMPO_DE_PAUSA = "bot_pausado_por"


def esta_pausado(session: Optional[Dict]) -> bool:
    """A conversa foi entregue a uma pessoa e o bot não fala até liberarem.

    A pausa NÃO vence sozinha, e essa é a mudança. Antes ela era um prazo de 24h
    (`attendant_active_until`): uma atendente assumia a conversa hoje e o bot
    voltava a responder amanhã, no meio do atendimento dela, sem ninguém pedir.

    Quem tira a pausa é gente, pelo botão "Retomar bot" no painel. Um bot que
    volta sozinho é pior que um bot desligado: ninguém está esperando por ele.

    `attendant_active_until` continua sendo lido para não perder as pausas que já
    existiam quando isto subiu.
    """
    session = session or {}
    if session.get(CAMPO_DE_PAUSA):
        return True

    ativo_ate = session.get("attendant_active_until")
    return bool(ativo_ate and int(ativo_ate) > int(time.time()))


def should_bot_reply(clinic: Optional[Dict], session: Optional[Dict], phone: str) -> bool:
    """O bot deve responder automaticamente esta conversa?

    Conversa pausada sempre suspende o bot, em qualquer política: se alguém da
    clínica assumiu, o bot não fala por cima.

    Política ausente ou nula equivale a ALL, que é o comportamento histórico —
    uma clínica lida antes da migration não pode ficar sem bot.
    """
    session = session or {}
    clinic = clinic or {}

    if esta_pausado(session):
        return False

    policy = clinic.get("bot_autoreply_policy") or POLICY_ALL

    if policy == POLICY_ALL:
        return True

    if policy == POLICY_PILOT:
        piloto = {normalize_phone(p) for p in (clinic.get("bot_pilot_phones") or [])}
        return normalize_phone(phone) in piloto

    if policy == POLICY_LEADS_ONLY:
        return bool(session.get("bot_enabled"))

    # OFF e qualquer valor inesperado falham fechado: só chegariam aqui por
    # escrita manual fora do CHECK da coluna.
    return False
