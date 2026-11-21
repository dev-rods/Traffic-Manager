# -*- coding: utf-8 -*-
"""O desfecho de um agendamento que nao acontece como marcado (PRD 054).

Cancelar com 24 h ou mais de antecedencia e CANCELAMENTO; com menos, FALTA.
A antecedencia e contada ate a ABERTURA DA AGENDA no dia da sessao (o
`start_time` cadastrado em "Horarios" para aquele dia), nao ate a hora da
sessao - decisao do Andre em 20/11/2026. Sessao as 15h num dia em que a
agenda abre as 9h: cancelar ate as 9h do dia anterior e cancelamento; depois,
falta. Sem regra para o dia, vale a hora da sessao.

Uma funcao so, chamada por `AppointmentService.cancel_appointment`, para
painel, bot e site darem o mesmo desfecho. Ate 20/11/2026 nao havia regra de
antecedencia em porta nenhuma (ver a docstring de `marca_no_show`, que
registra a decisao anterior e a reversao).
"""
import logging
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, Optional

from src.services import relogio

logger = logging.getLogger(__name__)

LIMITE = timedelta(hours=24)
CANCELADO = "CANCELLED"
FALTA = "NO_SHOW"
DESFECHOS = (CANCELADO, FALTA)


class DesfechoInvalido(ValueError):
    """Sobrepor o desfecho automatico exige motivo; so o painel pode."""


def abertura_da_agenda(db, clinic_id: str, dia: date, hora_da_sessao: time) -> time:
    """O `start_time` mais cedo das regras ativas do dia. Regra de data fixa
    vence a recorrente; SPECIAL_HOURS da excecao vence tudo; BLOCKED ou dia
    sem regra caem na hora da sessao (nao ha agenda para abrir)."""
    day_of_week = dia.isoweekday() % 7
    regras = db.execute_query(
        """
        SELECT start_time, rule_date FROM scheduler.availability_rules
        WHERE clinic_id = %s AND active = TRUE
          AND (day_of_week = %s OR rule_date = %s)
        """,
        (clinic_id, day_of_week, dia),
    ) or []
    fixas = [r for r in regras if r.get("rule_date")]
    if fixas:
        regras = fixas
    excecoes = db.execute_query(
        """
        SELECT exception_type, start_time FROM scheduler.availability_exceptions
        WHERE clinic_id = %s AND exception_date = %s
        """,
        (clinic_id, dia),
    ) or []
    for exc in excecoes:
        if exc.get("exception_type") == "BLOCKED":
            return hora_da_sessao
        if exc.get("exception_type") == "SPECIAL_HOURS" and exc.get("start_time"):
            return _hora(exc["start_time"])
    horas = [_hora(r["start_time"]) for r in regras if r.get("start_time")]
    return min(horas) if horas else hora_da_sessao


def classifica(abertura: datetime, agora: datetime) -> str:
    """CANCELLED se ainda faltam 24 h ou mais para a abertura; senao NO_SHOW.
    Sessao ja passada tambem e falta."""
    return CANCELADO if agora <= abertura - LIMITE else FALTA


def desfecho_do_agendamento(db, appointment: Dict[str, Any],
                            agora: Optional[datetime] = None) -> str:
    """Le o fuso da clinica, a abertura do dia e classifica."""
    clinic_id = appointment["clinic_id"]
    fuso = _fuso(db, clinic_id)
    agora_local = agora or relogio.agora_na_clinica(fuso)
    dia = _dia(appointment["appointment_date"])
    hora = _hora(appointment["start_time"])
    abertura = datetime.combine(dia, abertura_da_agenda(db, clinic_id, dia, hora))
    desfecho = classifica(abertura, agora_local.replace(tzinfo=None))
    logger.info(
        f"[Desfecho] {appointment.get('id')}: {desfecho} "
        f"(abertura={abertura.isoformat()} agora={agora_local.isoformat()})"
    )
    return desfecho


def _fuso(db, clinic_id: str) -> Optional[str]:
    try:
        linhas = db.execute_query(
            "SELECT timezone FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))
        return (linhas or [{}])[0].get("timezone")
    except Exception as e:  # pragma: no cover - falha de leitura vira fuso padrao
        logger.warning(f"[Desfecho] nao li o fuso de {clinic_id}: {e}")
        return None


def _dia(valor) -> date:
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    return datetime.strptime(str(valor)[:10], "%Y-%m-%d").date()


def _hora(valor) -> time:
    if isinstance(valor, time):
        return valor.replace(tzinfo=None)
    if isinstance(valor, datetime):
        return valor.time()
    texto = str(valor)[:8]
    for formato in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(texto, formato).time()
        except ValueError:
            continue
    raise ValueError(f"hora ilegivel: {valor!r}")
