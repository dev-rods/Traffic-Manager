"""Decide se o bot responde automaticamente uma conversa.

Função pura, sem I/O: recebe a clínica, a sessão e o telefone, devolve sim ou não.
Fica fora do handler porque é a regra que muda a cada fase do rollout, e precisa
ser testável sem subir webhook.
"""
import time
from typing import Dict, Optional

from src.services.campanha import esta_viva as campanha_viva
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

# As que NAO vencem por tempo. Elas nao descrevem um atendimento em curso, e sim
# de quem e a conversa - e isso nao muda no dia seguinte.
PAUSAS_PERMANENTES = frozenset({PAUSA_CONTATO_MANUAL, PAUSA_CHAT_ANTERIOR})


def esta_pausado(session: Optional[Dict]) -> bool:
    """A conversa foi entregue a uma pessoa e o bot não fala.

    Duas naturezas de pausa, e elas vencem diferente porque dizem coisas
    diferentes:

    ATENDENTE e HANDOFF descrevem um ATENDIMENTO EM CURSO. Alguém está na
    conversa agora. Isso é verdade por um tempo e depois deixa de ser - por
    decisão do André em 06/09/2026, 24h. Sem prazo, uma conversa atendida uma
    vez ficaria morta para sempre e ninguém lembraria de reabrir.

    CONTATO_MANUAL e CHAT_ANTERIOR descrevem QUEM COMEÇOU a conversa. Isso não
    para de ser verdade amanhã. Se vencessem, o bot entraria no dia seguinte
    numa conversa que uma pessoa conduz - exatamente o dano que o botão "Já
    iniciada" existe para impedir.

    Em ambos os casos o "Retomar bot" no painel libera na hora.
    """
    session = session or {}
    motivo = session.get(CAMPO_DE_PAUSA)

    if motivo in PAUSAS_PERMANENTES:
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
        # Dois caminhos independentes para a mesma politica, e nenhum sabe do
        # outro:
        #   `bot_enabled` - lead da landing page que escreveu para nos.
        #   campanha viva - paciente cadastrada para quem NOS escrevemos.
        #
        # O segundo VENCE, e e por isso que ele nao virou outro `bot_enabled`:
        # a tabela de sessoes esta sem TTL, entao marca permanente aqui deixaria
        # um rastro mensal de gente que o bot atende para sempre. Ver campanha.py.
        return bool(session.get("bot_enabled")) or campanha_viva(session)

    # OFF e qualquer valor inesperado falham fechado: só chegariam aqui por
    # escrita manual fora do CHECK da coluna.
    return False
