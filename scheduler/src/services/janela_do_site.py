# -*- coding: utf-8 -*-
"""Quais datas o site público oferece: as próximas N com horário livre.

N é `clinics.max_future_dates` ("Datas futuras" em Configurações), o mesmo
número que limita quantos dias o bot de WhatsApp lista. Hoje entra na conta,
sem os horários que já passaram; dia fechado ou lotado não conta.

Até 30/10/2026 o site mostrava o mês vigente e abria o seguinte na virada
(decisão de outubro/2026). Uma clínica que abre em 06/11 ficou sem nada para
oferecer no fim de outubro, e a regra passou a contar datas, não meses
(PRD 030). A janela mora inteira aqui: a grade (`availability`) e a criação
(`create_appointment`) perguntam à mesma função, e o front só exibe.

Vale só para o site. Bot e painel marcam para qualquer data.
"""
from datetime import datetime
from typing import Dict

from src.services import relogio
from src.services.availability_engine import AvailabilityEngine, MAX_SEARCH_DAYS, PADRAO_DATAS_FUTURAS


def quantas(clinic) -> int:
    """`max_future_dates` da linha da clínica, com o mesmo padrão do bot."""
    return int(clinic.get("max_future_dates") or PADRAO_DATAS_FUTURAS)


def dias_oferecidos(engine: AvailabilityEngine, clinic_id: str, duracao: int,
                    agora: datetime, max_dates: int) -> Dict[str, dict]:
    """{data: {"status": "AVAILABLE", "slots": [...]}} das próximas `max_dates`
    datas com horário para `duracao`, a partir de hoje (fuso da clínica), em
    ordem. Menos que isso quando a agenda do horizonte não tem tantas."""
    hoje = agora.date()
    corte = {hoje.isoformat(): relogio.minutos_de_agora(agora)}
    oferecidos: Dict[str, dict] = {}
    for data in engine.datas_com_regra(clinic_id, hoje, MAX_SEARCH_DAYS):
        dia = engine.get_days_status(clinic_id, [data], duracao, a_partir_de=corte)[data]
        if dia["status"] != "AVAILABLE":
            continue
        oferecidos[data] = dia
        if len(oferecidos) >= max_dates:
            break
    return oferecidos
