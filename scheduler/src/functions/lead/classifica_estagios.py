# -*- coding: utf-8 -*-
"""Recalcula o estagio de todos os leads (PRD 057). Diario, 7h BRT.

Para cada lead: le a transcricao no MessageEvents, cruza com agenda e espelho
do z-api, aplica `estagio_do_lead.decide`, e so entao pergunta ao modelo o que a
regra nao sabe (triagem de WhatsApp novo; desfecho de quem parou). Grava so o
que mudou. `{"dryRun": true}` calcula e devolve a distribuicao sem escrever.
`{"clinicId": "..."}` limita a uma clinica.
"""
import logging
import os
import uuid
from collections import Counter
from datetime import datetime, timezone
from typing import Dict, List, Optional

from src.services import estagio_do_lead as estagio
from src.services import estagio_repo as repo
from src.services.classificador_de_lead import (
    Classificador,
    TetoAtingido,
    precisa_de_desfecho,
    precisa_de_triagem,
)
from src.services.db.postgres import PostgresService
from src.services.status_da_conversa import conversas_da_clinica
from src.services.transcricao import resumo, ultimas_mensagens
from src.utils.phone import variantes_do_numero

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_tabela = None


def _tabela_de_eventos():
    global _tabela
    if _tabela is None:
        import boto3
        _tabela = boto3.resource("dynamodb").Table(os.environ["MESSAGE_EVENTS_TABLE"])
    return _tabela


def _clinicas(db, clinic_id: Optional[str] = None) -> List[Dict]:
    if clinic_id:
        return db.execute_query("SELECT * FROM scheduler.clinics WHERE clinic_id = %s", (clinic_id,))
    return db.execute_query("SELECT * FROM scheduler.clinics WHERE active = TRUE ORDER BY clinic_id")


def _agendamentos_por_variante(db, clinic_id: str) -> Dict[str, List[Dict]]:
    """Agendamentos da clinica que NAO sao remarcacao (PRD 054), indexados por
    variante do telefone do paciente. Remarcacao = CANCELLED com rescheduled_to_id."""
    linhas = db.execute_query(
        """
        SELECT p.phone, a.status, a.appointment_date, a.start_time
          FROM scheduler.appointments a
          JOIN scheduler.patients p ON p.id = a.patient_id
         WHERE a.clinic_id = %s
           AND a.rescheduled_to_id IS NULL
           AND p.deleted_at IS NULL
        """,
        (clinic_id,),
    )
    por_tel = {}  # type: Dict[str, List[Dict]]
    for linha in linhas:
        for v in variantes_do_numero(linha.get("phone") or ""):
            por_tel.setdefault(v, []).append(linha)
    return por_tel


def _ultimo_status(agendamentos: List[Dict]) -> Optional[str]:
    if not agendamentos:
        return None
    mais_recente = max(agendamentos, key=lambda a: (str(a.get("appointment_date") or ""), str(a.get("start_time") or "")))
    return mais_recente.get("status")


def _sinais(lead: Dict, mensagens, chat: Optional[Dict], agendamentos: List[Dict]) -> estagio.Sinais:
    r = resumo(mensagens)
    return estagio.Sinais(
        stage=lead.get("stage"), stage_source=lead.get("stage_source"), stage_updated_at=lead.get("stage_updated_at"),
        first_contact_at=lead.get("first_contact_at"),
        ultima_mensagem_de=r["ultima_de"], ultima_mensagem_em=r["ultima_em"], lead_ja_falou=r["lead_ja_falou"],
        tem_transcricao=bool(mensagens),
        chat_espelho_em=(chat or {}).get("last_message_at"),
        chat_espelho_nao_lidas=int((chat or {}).get("unread_count") or 0),
        ultimo_agendamento=_ultimo_status(agendamentos),
    )


class _SemModelo:
    """Depois do teto, as regras continuam e o modelo cala."""
    chamadas = 0

    def triagem(self, *_):
        return None

    def desfecho(self, *_):
        return None


def _pergunta_ao_modelo(db, lead, mensagens, decisao, clinic, classificador, agora, dias, dry_run):
    """Triagem e desfecho. Devolve (decisao, descartes)."""
    descartes = 0
    if decisao.stage in estagio.ESTAGIOS_DA_AGENDA or decisao.source == estagio.MANUAL:
        return decisao, descartes
    if precisa_de_triagem(lead, mensagens):
        v = classificador.triagem(mensagens, clinic)
        if v is None:
            descartes += 1
        else:
            if not dry_run:
                repo.marca_triagem(db, str(lead["id"]))
            if v.classe == "NAO_E_LEAD":
                decisao = estagio.Decisao(estagio.NAO_E_LEAD, estagio.MODELO, v.motivo)
    if decisao.stage != estagio.NAO_E_LEAD and precisa_de_desfecho(lead, decisao, mensagens, agora, dias):
        v = classificador.desfecho(mensagens, clinic)
        if v is None:
            descartes += 1
        else:
            if not dry_run:
                repo.marca_desfecho_tentado(db, str(lead["id"]))
            if v.classe == "NAO_AGENDOU":
                decisao = estagio.Decisao(estagio.NAO_AGENDOU, estagio.MODELO, v.motivo)
            elif not dry_run:
                repo.registra_tentativa(db, dict(lead, stage=decisao.stage), "ainda_aberto")
    return decisao, descartes


def processa_clinica(db, tabela_eventos, clinic: Dict, classificador, agora: datetime, dry_run: bool) -> Dict:
    clinic_id = clinic["clinic_id"]
    dias = int(clinic.get("crm_dias_parado") or 7)
    leads = db.execute_query("SELECT * FROM scheduler.leads WHERE clinic_id = %s ORDER BY created_at", (clinic_id,))
    chats = conversas_da_clinica(db, clinic_id)
    agenda = _agendamentos_por_variante(db, clinic_id)
    por_estagio = Counter()  # type: Counter
    mudaram, descartes = 0, 0
    for lead in leads:
        telefone = lead.get("phone") or ""
        variantes = variantes_do_numero(telefone)
        mensagens = ultimas_mensagens(tabela_eventos, clinic_id, telefone)
        chat = next((chats.get(v) for v in variantes if chats.get(v)), None)
        ags = [a for v in variantes for a in agenda.get(v, [])]
        decisao = estagio.decide(_sinais(lead, mensagens, chat, ags), agora, dias)
        try:
            decisao, d = _pergunta_ao_modelo(db, lead, mensagens, decisao, clinic, classificador, agora, dias, dry_run)
            descartes += d
        except TetoAtingido as t:
            logger.warning("[ClassificaLeads] {}: teto do modelo atingido ({}); o resto fica para amanha".format(clinic_id, t))
            classificador = _SemModelo()
        por_estagio[decisao.stage] += 1
        r = resumo(mensagens)
        if dry_run:
            if decisao.stage != lead.get("stage"):
                mudaram += 1
        elif repo.grava_estagio(db, lead, decisao, ultima_em=r["ultima_em"], ultima_de=r["ultima_de"]):
            mudaram += 1
    return {"leads": len(leads), "mudaram": mudaram, "por_estagio": dict(por_estagio),
            "chamadas_modelo": getattr(classificador, "chamadas", 0), "descartes": descartes}


def handler(event, context):
    trace_id = str(uuid.uuid4())
    event = event or {}
    dry_run = bool(event.get("dryRun"))
    agora = datetime.now(timezone.utc)
    logger.info("[traceId: {}] ClassificaLeads inicio{}".format(trace_id, " (dryRun)" if dry_run else ""))
    db = PostgresService()
    tabela = _tabela_de_eventos()
    max_chamadas = int(os.environ.get("CRM_MAX_CHAMADAS_MODELO", "200"))
    saida = {"traceId": trace_id, "dryRun": dry_run, "clinics": 0, "por_clinica": {}}
    for clinic in _clinicas(db, event.get("clinicId")):
        cid = clinic["clinic_id"]
        saida["clinics"] += 1
        try:
            resultado = processa_clinica(db, tabela, clinic, Classificador(max_chamadas=max_chamadas), agora, dry_run)
            saida["por_clinica"][cid] = resultado
            logger.info("[traceId: {}] {}: {}".format(trace_id, cid, resultado))
        except Exception as e:
            logger.error("[traceId: {}] {} falhou: {}".format(trace_id, cid, e))
            saida["por_clinica"][cid] = {"erro": str(e)}
    return saida
