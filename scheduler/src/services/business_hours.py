"""Janela de envio derivada do horário comercial cadastrado pela clínica.

Funções puras, sem I/O. O formato de `business_hours` é o JSONB da tabela
`scheduler.clinics`: {"mon": {"start": "07:15", "end": "21:00"}, ...}. Dia ausente
significa fechado, que é como sábado e domingo aparecem hoje na Essência.

Só o contato ativo usa isso. Quando o lead escreve primeiro, o bot responde na
hora: a pessoa está do outro lado esperando, e horário comercial não se aplica.
"""
from datetime import datetime, time as hora_do_dia, timedelta
from typing import Dict, Optional

import pytz

CLINIC_TZ = pytz.timezone("America/Sao_Paulo")

# Janela em que a plataforma NAO inicia conversa, em nenhuma clinica. Decisao
# do Andre em 05/10/2026 (PRD 020 §3.5): vale so para quem INICIA - lembrete,
# abordagem, campanha, retomada. Quem escreve de madrugada e respondido na
# hora. Inclusiva no inicio e exclusiva no fim, como `is_open`: 22:59:00 esta
# em silencio, 04:59:00 nao.
SILENCIO_PADRAO = {"start": "22:59", "end": "04:59"}


def fuso(clinic: Optional[Dict]):
    """O fuso da clinica (`clinics.timezone`), ou o padrao se ausente ou invalido."""
    nome = (clinic or {}).get("timezone")
    if not nome:
        return CLINIC_TZ
    try:
        return pytz.timezone(nome)
    except pytz.UnknownTimeZoneError:
        return CLINIC_TZ


def _hora(texto: str) -> hora_do_dia:
    h, m = (int(p) for p in texto.split(":"))
    return hora_do_dia(h, m)


def _janela_de_silencio(clinic: Optional[Dict]):
    janela = (clinic or {}).get("janela_de_silencio") or SILENCIO_PADRAO
    try:
        return _hora(janela["start"]), _hora(janela["end"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return _hora(SILENCIO_PADRAO["start"]), _hora(SILENCIO_PADRAO["end"])


def em_silencio(clinic: Optional[Dict], agora: datetime) -> bool:
    """A plataforma esta na janela em que nao inicia conversa?

    `agora` tem de ter fuso; e convertido para o da clinica. A janela padrao
    cruza a meia-noite, entao "dentro" e `hora >= inicio OU hora < fim`.
    """
    inicio, fim = _janela_de_silencio(clinic)
    hora = agora.astimezone(fuso(clinic)).time().replace(second=0, microsecond=0)
    if inicio > fim:
        return hora >= inicio or hora < fim
    return inicio <= hora < fim


def fim_do_silencio(clinic: Optional[Dict], agora: datetime) -> datetime:
    """O primeiro instante a partir de `agora` fora da janela. `agora` se ja estiver fora."""
    if not em_silencio(clinic, agora):
        return agora
    _, fim = _janela_de_silencio(clinic)
    tz = fuso(clinic)
    local = agora.astimezone(tz)
    candidato = local.replace(hour=fim.hour, minute=fim.minute, second=0, microsecond=0)
    if candidato <= local:
        candidato = candidato + timedelta(days=1)
    # Relocaliza: somar dias nao ajusta o offset ao cruzar horario de verao.
    return tz.localize(candidato.replace(tzinfo=None))

# datetime.weekday(): 0 = segunda
_DIAS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
_DIAS_NA_SEMANA = 7


def _janela_do_dia(business_hours: Dict, momento: datetime):
    """(abertura, fechamento) do dia de `momento`, ou None se fechado."""
    dia = business_hours.get(_DIAS[momento.weekday()])
    if not dia or not dia.get("start") or not dia.get("end"):
        return None

    abre_h, abre_m = (int(p) for p in dia["start"].split(":"))
    fecha_h, fecha_m = (int(p) for p in dia["end"].split(":"))

    base = momento.replace(hour=0, minute=0, second=0, microsecond=0)
    return base.replace(hour=abre_h, minute=abre_m), base.replace(hour=fecha_h, minute=fecha_m)


def is_open(business_hours: Optional[Dict], moment: datetime) -> bool:
    """A clínica está atendendo neste instante?

    A abertura é inclusiva e o fechamento exclusivo: às 21:00 em ponto já está
    fechada, porque 21:00 é o instante em que encerra.
    """
    janela = _janela_do_dia(business_hours or {}, moment)
    if janela is None:
        return False
    abertura, fechamento = janela
    return abertura <= moment < fechamento


def next_opening(business_hours: Optional[Dict], moment: datetime) -> Optional[datetime]:
    """Primeiro instante a partir de `moment` em que a clínica está aberta.

    Devolve o próprio `moment` se já estiver aberta, e None se nenhum dia da
    semana estiver configurado — sem essa saída a busca não terminaria.
    """
    business_hours = business_hours or {}
    if not any(business_hours.get(dia) for dia in _DIAS):
        return None

    if is_open(business_hours, moment):
        return moment

    # Hoje ainda pode abrir mais tarde; a partir de amanhã, sempre na abertura.
    janela = _janela_do_dia(business_hours, moment)
    if janela is not None and moment < janela[0]:
        return janela[0]

    candidato = moment
    for _ in range(_DIAS_NA_SEMANA):
        candidato = (candidato + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        janela = _janela_do_dia(business_hours, candidato)
        if janela is not None:
            return janela[0]

    return None
