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


def should_bot_reply(clinic: Optional[Dict], session: Optional[Dict], phone: str) -> bool:
    """O bot deve responder automaticamente esta conversa?

    Atendente humano ativo sempre suspende o bot, em qualquer política: se alguém
    da clínica assumiu a conversa, o bot não fala por cima.

    Política ausente ou nula equivale a ALL, que é o comportamento histórico —
    uma clínica lida antes da migration não pode ficar sem bot.
    """
    session = session or {}
    clinic = clinic or {}

    ativo_ate = session.get("attendant_active_until")
    if ativo_ate and int(ativo_ate) > int(time.time()):
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
