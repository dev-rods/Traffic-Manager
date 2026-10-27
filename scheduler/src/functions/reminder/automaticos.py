# -*- coding: utf-8 -*-
"""Lotes automaticos de lembrete (PRD 027). Horario.

Para cada clinica com `lembrete_automatico`, olha hoje+1..hoje+3 e dispara o
dia inteiro quando `agora >= primeiro horario - antecedencia`. A selecao e por
agendamento sem lembrete, entao um encaixe de ultima hora e pego na proxima
rodada, e um dia ja lembrado nao repete.
"""
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

from src.services.business_hours import fim_do_silencio, fuso
from src.services.db.postgres import PostgresService
from src.services.lembrete_da_agenda import enfileira, inicio_da_agenda
from src.services.reminder_service import ReminderService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DIAS_A_FRENTE = 3


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def send_at_se_vencido(clinic: Dict, dia: str, appointments: List[Dict], agora: datetime) -> Optional[datetime]:
    """O instante de envio do lote do `dia`, se ja chegou a hora; None se ainda
    nao, ou se nao ha o que lembrar. Dentro do silencio, vai para o fim dele."""
    pendentes = [a for a in appointments
                 if a.get("status") == "CONFIRMED" and not a.get("lembrete_enviado_em")
                 and a.get("lembrete_status") != "ENFILEIRADO"]
    inicio = inicio_da_agenda(pendentes)
    if inicio is None:
        return None
    tz = fuso(clinic)
    primeiro = tz.localize(datetime.combine(datetime.strptime(dia, "%Y-%m-%d").date(), inicio))
    send_at = primeiro - timedelta(hours=int(clinic.get("lembrete_antecedencia_horas") or 24))
    if agora < send_at:
        return None
    return fim_do_silencio(clinic, agora)


def handler(event, context):
    trace_id = str(uuid.uuid4())[:8]
    db = PostgresService()
    rs = ReminderService()
    agora = _agora()
    lotes = 0
    clinicas = db.execute_query(
        "SELECT * FROM scheduler.clinics WHERE active = TRUE AND lembrete_automatico = TRUE")
    for clinic in clinicas:
        tz = fuso(clinic)
        hoje = agora.astimezone(tz).date()
        for n in range(1, DIAS_A_FRENTE + 1):
            dia = (hoje + timedelta(days=n)).isoformat()
            try:
                appts = db.execute_query(
                    """SELECT a.id, a.status, a.start_time, a.lembrete_enviado_em, a.lembrete_status,
                              p.phone AS patient_phone
                         FROM scheduler.appointments a
                         LEFT JOIN scheduler.patients p ON p.id = a.patient_id
                        WHERE a.clinic_id = %s AND a.appointment_date = %s AND a.status = 'CONFIRMED'""",
                    (clinic["clinic_id"], dia))
                send_at = send_at_se_vencido(clinic, dia, appts, agora)
                if send_at is None:
                    continue
                r = enfileira(db, rs, clinic, dia, send_at)
                lotes += 1 if r["enfileirados"] else 0
                logger.info(f"[traceId: {trace_id}] {clinic['clinic_id']} {dia}: {r}")
            except Exception as e:
                logger.error(f"[traceId: {trace_id}] {clinic['clinic_id']} {dia} falhou: {e}")
    logger.info(f"[traceId: {trace_id}] [LembretesAutomaticos] {len(clinicas)} clinicas, {lotes} lotes")
    return {"traceId": trace_id, "clinicas": len(clinicas), "lotes": lotes}
