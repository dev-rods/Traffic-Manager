# -*- coding: utf-8 -*-
"""Reagendamento não é cancelamento (PRD 035).

Reagendado é `CANCELLED` com `rescheduled_to_id`; cancelado de verdade é
`CANCELLED` sem vínculo; falta é `NO_SHOW`. Não há um quarto status, porque
`status` governa motor de horários, lembretes e uploader, e todos leem o valor
puro. Quem conta cancelamento usa os fragmentos daqui, num lugar só.

O vínculo nasce em `AppointmentService.create_appointment`, por
`vincula_antecessor`: ao criar para um paciente que teve um cancelamento na
mesma clínica dentro da janela, o antigo passa a apontar para o novo. Isso
cobre painel, site e bot sem que nenhum chamador conheça a regra. Medido em
prod em 01/11/2026: dos 37 pares reais, todos caíram entre -7 e +8 minutos,
e os que passaram disso eram remarcações em dois tempos no mesmo dia.

Funções puras de SQL; o I/O é o `db` que chega por parâmetro.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

JANELA_DE_VINCULO_MIN = 30
# Quem cria o novo primeiro e cancela o antigo em seguida (pares com delta
# negativo na medição) também é remarcação.
FOLGA_DEPOIS_MIN = 10

# Fragmentos para FILTER (...) e WHERE. `{a}` é o alias da tabela.
E_REAGENDADO = "({a}.status = 'CANCELLED' AND {a}.rescheduled_to_id IS NOT NULL)"
E_CANCELADO_DE_VERDADE = "({a}.status = 'CANCELLED' AND {a}.rescheduled_to_id IS NULL)"

_VINCULA = """
UPDATE scheduler.appointments a
   SET rescheduled_to_id = %(novo)s::uuid, updated_at = NOW()
 WHERE a.id = (
   SELECT c.id FROM scheduler.appointments c
    WHERE c.clinic_id = %(clinic)s AND c.patient_id = %(patient)s::uuid
      AND c.status = 'CANCELLED' AND c.rescheduled_to_id IS NULL
      AND c.id <> %(novo)s::uuid
      AND c.updated_at >= %(criado_em)s - make_interval(mins => %(janela)s)
      AND c.updated_at <= %(criado_em)s + make_interval(mins => %(folga)s)
    ORDER BY c.updated_at DESC LIMIT 1)
RETURNING a.id
"""

_CANDIDATO = """
   SELECT c.id, c.appointment_date, c.updated_at
     FROM scheduler.appointments c
    WHERE c.clinic_id = %(clinic)s AND c.patient_id = %(patient)s::uuid
      AND c.status = 'CANCELLED' AND c.rescheduled_to_id IS NULL
      AND c.id <> %(novo)s::uuid
      AND c.updated_at >= %(criado_em)s - make_interval(mins => %(janela)s)
      AND c.updated_at <= %(criado_em)s + make_interval(mins => %(folga)s)
    ORDER BY c.updated_at DESC LIMIT 1
"""


def _params(novo: Dict[str, Any], janela_min: int) -> Optional[Dict[str, Any]]:
    if not novo.get("patient_id"):
        return None
    criado_em = novo.get("created_at") or datetime.now()
    return {
        "novo": str(novo["id"]),
        "clinic": novo["clinic_id"],
        "patient": str(novo["patient_id"]),
        "criado_em": criado_em,
        "janela": int(janela_min),
        "folga": FOLGA_DEPOIS_MIN,
    }


def vincula_antecessor(db, novo: Dict[str, Any],
                       janela_min: int = JANELA_DE_VINCULO_MIN) -> Optional[str]:
    """Liga ao `novo` o cancelamento mais recente do mesmo paciente na mesma
    clínica dentro da janela. Devolve o id do antecessor ou None.

    Um UPDATE só, com `rescheduled_to_id IS NULL` no WHERE: idempotente, e
    duas criações simultâneas não disputam o mesmo antecessor. A referência de
    tempo é o `created_at` do novo, não NOW(), para o backfill reusar isto
    com registros antigos.
    """
    params = _params(novo, janela_min)
    if not params:
        return None
    linha = db.execute_write_returning(_VINCULA, params)
    if not linha:
        return None
    antecessor = str(linha["id"])
    logger.info(
        f"[Reagendamento] antecessor={antecessor} novo={params['novo']} "
        f"clinic={params['clinic']}")
    return antecessor


def candidato_a_antecessor(db, novo: Dict[str, Any],
                           janela_min: int = JANELA_DE_VINCULO_MIN) -> Optional[Dict[str, Any]]:
    """O que `vincula_antecessor` ligaria, sem escrever. Para o dry-run."""
    params = _params(novo, janela_min)
    if not params:
        return None
    linhas = db.execute_query(_CANDIDATO, params)
    return linhas[0] if linhas else None
