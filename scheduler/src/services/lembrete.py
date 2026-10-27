# -*- coding: utf-8 -*-
"""A sobreposicao de lembrete (PRD 027), nos moldes de `campanha.py`.

Gravada na sessao no ato da ENTREGA do lembrete, nunca inferida pelo modelo.
Enquanto viva (ate o fim do dia da sessao, no fuso da clinica):

- com site de autoatendimento, `cancel_appointment` e `reschedule_appointment`
  NAO vao ao modelo: a pessoa recebe o link e resolve sozinha. Nao e so prompt:
  a ferramenta nao existe para ele.
- sem site, nada e removido: o bot cancela e remarca como sempre.
- `confirm_attendance` so existe aqui: resposta positiva vira Confirmado.

Funcoes puras, sem I/O.
"""
import time
from datetime import datetime, timedelta
from typing import Dict, FrozenSet, Optional

from src.services.autoatendimento import link_de_autoatendimento
from src.services.business_hours import fuso

CHAVE = "lembrete"
FERRAMENTAS_DE_SAIDA = frozenset({"reschedule_appointment", "cancel_appointment"})
FERRAMENTA_DE_CONFIRMACAO = "confirm_attendance"


def _hora(valor) -> str:
    if hasattr(valor, "strftime"):
        return valor.strftime("%H:%M")
    if isinstance(valor, timedelta):
        s = int(valor.total_seconds())
        return f"{s // 3600:02d}:{(s % 3600) // 60:02d}"
    return str(valor)[:5]


def _dia(valor) -> str:
    return valor.isoformat() if hasattr(valor, "isoformat") else str(valor)[:10]


def abre(appointment: Dict, clinic: Dict, agora: Optional[int] = None) -> Dict:
    """Monta o que vai para `session["lembrete"]`. Expira no fim do dia da sessao."""
    dia = _dia(appointment.get("appointment_date"))
    tz = fuso(clinic)
    fim = tz.localize(datetime.strptime(dia, "%Y-%m-%d").replace(hour=23, minute=59, second=59))
    return {
        "appointment_id": str(appointment.get("id")),
        "dia": dia,
        "hora": _hora(appointment.get("start_time")),
        "areas": appointment.get("areas") or "",
        "expira_em": int(fim.timestamp()),
    }


def definicao_da_tool() -> Dict:
    """`confirm_attendance` no formato Anthropic. Nao esta em TOOL_DEFINITIONS de
    proposito: so existe para o modelo enquanto a sobreposicao esta viva, e o
    agente a acrescenta na hora (ver `ferramentas_a_liberar`)."""
    return {
        "name": FERRAMENTA_DE_CONFIRMACAO,
        "description": (
            "A pessoa confirmou que vai à sessão sobre a qual acabou de receber o lembrete "
            "(ok, confirmado, estarei lá, joinha). Marca a presença como confirmada. "
            "Não pede nenhum dado: o agendamento é o do lembrete."
        ),
        "input_schema": {"type": "object", "properties": {}, "required": []},
    }


def _dados(session) -> Optional[Dict]:
    d = (session or {}).get(CHAVE)
    return d if isinstance(d, dict) else None


def esta_vivo(session, agora: Optional[int] = None) -> bool:
    """Falha fechada em toda duvida, como a campanha: sem lembrete, malformado
    ou vencido, o bot se comporta como sempre."""
    d = _dados(session)
    if not d:
        return False
    try:
        expira = int(d["expira_em"])
    except (KeyError, TypeError, ValueError):
        return False
    return expira > int(agora if agora is not None else time.time())


def appointment_id(session, agora: Optional[int] = None) -> Optional[str]:
    return _dados(session)["appointment_id"] if esta_vivo(session, agora) else None


def ferramentas_a_remover(session, clinic, agora: Optional[int] = None) -> FrozenSet[str]:
    if not esta_vivo(session, agora) or not link_de_autoatendimento(clinic):
        return frozenset()
    return FERRAMENTAS_DE_SAIDA


def ferramentas_a_liberar(session, agora: Optional[int] = None) -> FrozenSet[str]:
    return frozenset({FERRAMENTA_DE_CONFIRMACAO}) if esta_vivo(session, agora) else frozenset()


def bloco_de_prompt(session, clinic, agora: Optional[int] = None) -> str:
    if not esta_vivo(session, agora):
        return ""
    d = _dados(session)
    dia_br = datetime.strptime(d["dia"], "%Y-%m-%d").strftime("%d/%m")
    link = link_de_autoatendimento(clinic)
    if link:
        saida = (
            f"Se ela quiser CANCELAR ou REMARCAR, NÃO execute nada: envie o link {link} e diga "
            "que ela resolve em um minuto por lá, com o mesmo número de WhatsApp. "
            "Se disser que não vai poder ir sem pedir nada, pergunte se prefere remarcar ou "
            "cancelar e então envie o link.\n"
        )
    else:
        saida = "Se ela quiser cancelar ou remarcar, pode resolver por aqui mesmo com as ferramentas, como sempre.\n"
    areas = f" ({d['areas']})" if d.get("areas") else ""
    return (
        "\n═══ LEMBRETE ENVIADO ═══\n"
        f"Esta pessoa acabou de receber o lembrete da sessão de {dia_br} às {d['hora']}{areas}.\n"
        "Se ela responder confirmando que vai (ok, confirmado, estarei lá, joinha), use "
        f"`{FERRAMENTA_DE_CONFIRMACAO}` e agradeça em uma linha, sem perguntar mais nada.\n"
        + saida
        + "Dúvidas sobre a sessão, preparo e endereço: responda normalmente.\n"
    )
