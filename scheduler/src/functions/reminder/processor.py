# -*- coding: utf-8 -*-
"""Entrega os lembretes vencidos da fila (PRD 027).

Acordado por invocacao (botao do painel) e por cron horario (lotes
automaticos). Para cada item: recarrega o agendamento (cancelado e descartado),
confere a porta (bot pausado falha; silencio adia; humano e cooldown
destravam, como o disparo em lote), envia, grava `lembrete_*` no agendamento e
abre a sobreposicao de lembrete na sessao.
"""
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from src.providers.whatsapp_provider import get_provider
from src.services import atendimento, lembrete
from src.services.business_hours import fim_do_silencio
from src.services.db.postgres import PostgresService
from src.services.lembrete_da_agenda import variaveis_do_template
from src.services.message_tracker import MessageTracker
from src.services.porta_do_disparo import MOTIVOS_QUE_O_DISPARO_DESTRAVA, motivo_para_nao_iniciar
from src.services.reminder_service import ReminderService
from src.services.session_store import abre_lembrete, carrega_sessao, grava_atendimento
from src.services.template_service import TemplateService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TEMPLATE = "LEMBRETE_SESSAO"
MOTIVO_LEGIVEL = {"bot_da_clinica_pausado": "bot pausado", "janela_de_silencio": "fora do horário"}


@dataclass
class Deps:
    """O que `entrega` usa. Injetavel para o teste nao subir AWS."""
    db: Any
    reminder_service: Any
    template_service: Any
    tracker: Any
    provider: Any
    tabela_sessoes: Any
    abre_lembrete: Callable = abre_lembrete
    grava_atendimento: Callable = grava_atendimento
    carrega_sessao: Callable = carrega_sessao


def _marca(db, appointment_id: str, status: Optional[str], erro: Optional[str] = None,
           enviado: bool = False) -> None:
    db.execute_write(
        "UPDATE scheduler.appointments SET lembrete_status = %s, lembrete_erro = %s"
        + (", lembrete_enviado_em = NOW()" if enviado else "")
        + ", updated_at = NOW() WHERE id = %s::uuid",
        (status, erro, appointment_id),
    )


def _agendamento(db, appointment_id: str) -> Optional[Dict]:
    linhas = db.execute_query(
        """SELECT a.*, p.phone AS patient_phone, p.name AS patient_name,
                  (SELECT string_agg(asa.area_name, ', ' ORDER BY asa.created_at)
                     FROM scheduler.appointment_service_areas asa
                    WHERE asa.appointment_id = a.id) AS areas
             FROM scheduler.appointments a
             LEFT JOIN scheduler.patients p ON p.id = a.patient_id
            WHERE a.id = %s::uuid""",
        (appointment_id,),
    )
    return linhas[0] if linhas else None


def _rastro(deps: Deps, clinic_id, phone, msg_id, conversation_id, content, status, **extras):
    deps.tracker.track_outbound(
        clinic_id=clinic_id, phone=phone, message_id=msg_id, conversation_id=conversation_id,
        message_type="TEXT", content=content, status=status, **extras,
    )


def entrega(reminder: Dict, deps: Deps, agora: datetime) -> str:
    """Um lembrete. Devolve "enviado" | "adiado" | "falhou" | "descartado"."""
    rid, aid = reminder.get("reminderId", ""), reminder.get("appointmentId", "")
    clinic_id, phone = reminder.get("clinicId", ""), reminder.get("phoneNumber", "")
    pk, sk = reminder.get("pk", ""), reminder.get("sk", "")
    db, rs = deps.db, deps.reminder_service

    clinicas = db.execute_query(
        "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE", (clinic_id,))
    clinic = clinicas[0] if clinicas else None
    appt = _agendamento(db, aid) if aid else None

    # Cancelado ou remarcado depois de entrar na fila: lembrar alguem de uma
    # sessao que nao existe mais e pior do que nao lembrar.
    if not clinic or not appt or appt.get("status") != "CONFIRMED":
        rs.mark_failed(rid, pk, sk, "agendamento_nao_confirmado")
        if aid:
            db.execute_write(
                "UPDATE scheduler.appointments SET lembrete_status = NULL, updated_at = NOW() WHERE id = %s::uuid",
                (aid,),
            )
        return "descartado"

    sessao = deps.carrega_sessao(clinic_id, phone)
    epoch = int(agora.timestamp())
    motivo = motivo_para_nao_iniciar(clinic, sessao, epoch)
    if motivo == "janela_de_silencio":
        novo = fim_do_silencio(clinic, agora).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        rs.adia(pk, sk, novo, motivo)
        _marca(db, aid, "ADIADO")
        return "adiado"
    if motivo and motivo not in MOTIVOS_QUE_O_DISPARO_DESTRAVA:
        rs.mark_failed(rid, pk, sk, motivo)
        _marca(db, aid, "FALHOU", MOTIVO_LEGIVEL.get(motivo, motivo))
        return "falhou"

    content = deps.template_service.get_and_render(clinic_id, TEMPLATE, variaveis_do_template(appt, clinic))
    msg_id, conversation_id = str(uuid.uuid4()), f"{clinic_id}#{phone}"
    _rastro(deps, clinic_id, phone, msg_id, conversation_id, content, "QUEUED",
            metadata={"reminderType": TEMPLATE, "reminderId": rid, "appointmentId": aid})
    resp = deps.provider.send_text(phone, content)
    if not resp.success:
        _rastro(deps, clinic_id, phone, msg_id, conversation_id, content, "FAILED",
                metadata={"error": resp.error})
        rs.mark_failed(rid, pk, sk, resp.error or "Erro desconhecido")
        _marca(db, aid, "FALHOU", (resp.error or "erro de envio")[:120])
        return "falhou"

    _rastro(deps, clinic_id, phone, msg_id, conversation_id, content, "SENT",
            provider_message_id=resp.provider_message_id, provider_response=resp.raw_response)
    rs.mark_sent(rid, pk, sk)
    _marca(db, aid, "ENVIADO", enviado=True)

    # DEPOIS do envio confirmado, como o disparo em lote: destrava e abre a
    # sobreposicao. Mensagem que nao saiu nao pode deixar o bot esperando.
    if motivo in MOTIVOS_QUE_O_DISPARO_DESTRAVA:
        atendimento.retoma_pelo_painel(sessao)
        sessao["bot_enabled"] = True
        if not deps.grava_atendimento(deps.tabela_sessoes, clinic_id, phone, sessao,
                                      extras={"bot_enabled": True}):
            logger.error(f"[ReminderProcessor] {phone}: lembrete enviado mas NAO destravou ({motivo})")
    if not deps.abre_lembrete(deps.tabela_sessoes, clinic_id, phone, lembrete.abre(appt, clinic, epoch)):
        logger.error(f"[ReminderProcessor] {phone}: lembrete enviado mas a sobreposicao NAO abriu")
    return "enviado"


def handler(event, context):
    trace_id = str(uuid.uuid4())[:8]
    logger.info(f"[traceId: {trace_id}] [ReminderProcessor] inicio")
    import boto3

    db = PostgresService()
    rs = ReminderService()
    agora = datetime.now(timezone.utc)
    pendentes = rs.get_pending_reminders(agora.strftime("%Y-%m-%dT%H:%M:%SZ"))
    tabela = boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])
    contagem = {"enviado": 0, "adiado": 0, "falhou": 0, "descartado": 0}
    providers: Dict[str, Any] = {}

    for r in pendentes:
        rid = r.get("reminderId", "")
        try:
            cid = r.get("clinicId", "")
            if cid not in providers:
                c = db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s", (cid,))
                providers[cid] = get_provider(c[0]) if c else None
            deps = Deps(db=db, reminder_service=rs, template_service=TemplateService(db),
                        tracker=MessageTracker(), provider=providers[cid], tabela_sessoes=tabela)
            resultado = entrega(r, deps, agora)
        except Exception as e:
            logger.error(f"[traceId: {trace_id}] lembrete {rid} falhou: {e}")
            rs.mark_failed(rid, r.get("pk", ""), r.get("sk", ""), str(e)[:200])
            resultado = "falhou"
        contagem[resultado] += 1

    logger.info(f"[traceId: {trace_id}] [ReminderProcessor] {len(pendentes)} processados: {contagem}")
    return {"processed": len(pendentes), **contagem}
