# -*- coding: utf-8 -*-
"""Até quando o site público aceita agendamento: o fim do mês corrente.

Decisão da reunião de outubro/2026 (Rodrigo e André): o site mostra só datas do
mês vigente, e o mês seguinte abre na virada. A clínica monta a agenda mês a
mês, e oferecer novembro em meados de outubro é oferecer horário que ainda vai
mudar.

O custo conhecido está no PRD 023: no fim do mês, com a agenda cheia, o cliente
fica sem nenhum dia. A tela trata esse caso dizendo quando o próximo mês abre,
e a janela mora inteira aqui, para mudar a regra num lugar só se a decisão
mudar.

Vale SÓ para o site. Bot e painel marcam para qualquer data, e não importam
este módulo.

O "hoje" é o da clínica, não o do servidor (UTC) nem o do navegador: às 23h30
de 31/10 em São Paulo ainda é outubro, mesmo com a Lambda já em novembro.
"""
import calendar
import logging
from datetime import date, datetime, timedelta
from typing import Optional, Tuple

import pytz

logger = logging.getLogger(__name__)

FUSO_PADRAO = "America/Sao_Paulo"


def agora_na_clinica(timezone: Optional[str], agora_utc: Optional[datetime] = None) -> datetime:
    """O instante atual no fuso da clínica. Fuso ausente ou inválido vira São Paulo.

    `agora_utc` (com tzinfo) existe para o teste fixar o relógio.
    """
    try:
        fuso = pytz.timezone(timezone or FUSO_PADRAO)
    except pytz.UnknownTimeZoneError:
        logger.warning(f"[MesVigente] fuso desconhecido {timezone!r}; usando {FUSO_PADRAO}")
        fuso = pytz.timezone(FUSO_PADRAO)
    return (agora_utc or datetime.now(pytz.utc)).astimezone(fuso)


def janela(agora: datetime) -> Tuple[date, date]:
    """(primeiro, último) dia agendável: de hoje até o último dia do mês."""
    hoje = agora.date()
    ultimo = calendar.monthrange(hoje.year, hoje.month)[1]
    return hoje, hoje.replace(day=ultimo)


def dentro(d: date, agora: datetime) -> bool:
    inicio, fim = janela(agora)
    return inicio <= d <= fim


def proximo_mes_abre_em(agora: datetime) -> date:
    """O dia 1º do mês seguinte - quando a agenda dele aparece no site."""
    _, fim = janela(agora)
    return fim + timedelta(days=1)


def minutos_de_agora(agora: datetime) -> int:
    """Minutos desde a meia-noite, no fuso da clínica - o corte dos horários de hoje.

    Arredonda para cima: às 14h00min30s, 14h00 já passou.
    """
    minutos = agora.hour * 60 + agora.minute
    return minutos + 1 if (agora.second or agora.microsecond) else minutos
