# -*- coding: utf-8 -*-
"""O relógio da clínica: que dia e que hora são AGORA no fuso dela.

O "hoje" é o da clínica, não o do servidor (UTC) nem o do navegador: às 23h30
de 31/10 em São Paulo ainda é dia 31, mesmo com a Lambda já em novembro. Caixa,
check-in e o site público perguntam aqui.
"""
import logging
from datetime import datetime
from typing import Optional

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
        logger.warning(f"[Relogio] fuso desconhecido {timezone!r}; usando {FUSO_PADRAO}")
        fuso = pytz.timezone(FUSO_PADRAO)
    return (agora_utc or datetime.now(pytz.utc)).astimezone(fuso)


def minutos_de_agora(agora: datetime) -> int:
    """Minutos desde a meia-noite, no fuso da clínica - o corte dos horários de hoje.

    Arredonda para cima: às 14h00min30s, 14h00 já passou.
    """
    minutos = agora.hour * 60 + agora.minute
    return minutos + 1 if (agora.second or agora.microsecond) else minutos
