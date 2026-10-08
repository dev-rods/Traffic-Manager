# -*- coding: utf-8 -*-
"""Cron: atendimentos humanos vencidos. PRD 020 §3.3 e §3.7.

A cada 60 minutos, lê no índice `handler-humanUntil-index` as conversas com
`handler = HUMAN_ACTIVE` e `humanUntil <= agora`, e para cada uma decide:

  pendente  há pending_intent ou tarefa aberta  -> HUMAN_PENDING (a fila mostra)
  retomar   as guardas de retomada passam        -> responde UMA vez, depois COOLDOWN
  calar     alguma guarda falha                  -> COOLDOWN; se a última fala era
                                                    do cliente, marca alerta

O estado efetivo já é derivado sem cron (`atendimento.estado`): quem lê a
sessão vê COOLDOWN ou HUMAN_PENDING mesmo que esta função nunca rode. O que
só ela faz é a retomada e a materialização, que é o que a fila e o índice
precisam.

Lote pequeno (50) e escrita condicional: conflito pula o item, a próxima
execução o pega.
"""
import logging
import os
import time
import uuid

import boto3
from boto3.dynamodb.conditions import Key

from src.services import atendimento, retomada, tarefas
from src.services.session_store import grava_atendimento

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

LOTE = 50
INDICE = "handler-humanUntil-index"


def _tabela():
    return boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])


def _agora():
    """Epoch UTC. Funcao propria para o teste fixar o relogio sem mexer no
    `time` global - mexer nele fez a suite inteira dormir."""
    return int(time.time())


def vencidas(table, agora):
    r = table.query(
        IndexName=INDICE,
        KeyConditionExpression=Key("handler").eq(atendimento.HUMAN_ACTIVE) & Key("humanUntil").lte(agora),
        Limit=LOTE,
    )
    return r.get("Items", [])


def handler(event, context):
    trace = str(uuid.uuid4())[:8]
    agora = _agora()
    table = _tabela()
    itens = vencidas(table, agora)
    logger.info(f"[traceId: {trace}] [ExpiraAtendimentos] {len(itens)} atendimento(s) vencido(s)")

    resultado = {"vencidos": len(itens), "pendentes": 0, "retomados": 0, "calados": 0, "conflitos": 0}
    if not itens:
        return resultado

    from src.services.db.postgres import PostgresService
    from src.services.message_tracker import MessageTracker

    db = PostgresService()
    tracker = MessageTracker()
    clinicas = {}

    for item in itens:
        clinic_id = item.get("clinicId") or str(item.get("pk", "")).replace("CLINIC#", "")
        phone = item.get("phone") or str(item.get("sk", "")).replace("PHONE#", "")
        prefixo = f"[traceId: {trace}] [ExpiraAtendimentos] {phone}"
        try:
            sessao = dict((table.get_item(Key={"pk": item["pk"], "sk": item["sk"]}).get("Item") or {}).get("session") or {})
            if clinic_id not in clinicas:
                linhas = db.execute_query(
                    "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE", (clinic_id,)
                )
                clinicas[clinic_id] = linhas[0] if linhas else {}
            clinic = clinicas[clinic_id]

            sessao, acao = atendimento.avalia_vencimento(sessao, agora)
            if acao == atendimento.ACAO_PENDENTE:
                b = atendimento.bloco(sessao)
                if not b.get("pending_task_id"):
                    tarefa = tarefas.abre(db, clinic_id, phone, b.get("pending_intent") or "", b.get("handoff_reason") or "")
                    if tarefa:
                        atendimento.vincula_tarefa(sessao, tarefa)
                resultado["pendentes"] += 1
                logger.info(f"{prefixo}: pendencia {b.get('pending_intent')!r}, fica com uma pessoa")
            else:
                eventos = tracker.get_conversation_messages(clinic_id, phone, limit=retomada.EVENTOS_PARA_CONTEXTO)
                fala = retomada.ultima_fala(eventos)
                efeitos = _efeitos_depois(db, clinic_id, phone, fala)
                pode, motivo = retomada.pode_retomar(sessao, eventos, efeitos, clinic, phone, agora)
                if pode:
                    retomou = _retoma(db, clinic, clinic_id, phone, sessao, eventos, fala, agora, tracker, prefixo)
                    resultado["retomados" if retomou else "calados"] += 1
                else:
                    if fala is not None and fala.get("direction") == "INBOUND":
                        atendimento.marca_alerta(sessao, motivo)
                    resultado["calados"] += 1
                    logger.info(f"{prefixo}: cala ({motivo}), vai para cooldown")
                # Respondeu ou calou, o atendimento humano ACABOU: o bloco (e o
                # espelho `handler`/`humanUntil` que a GSI le) sai de
                # HUMAN_ACTIVE. Sem isto a mesma conversa voltava a cada ciclo.
                atendimento.encerra_atendimento_humano(sessao, agora)

            if not grava_atendimento(table, clinic_id, phone, sessao):
                resultado["conflitos"] += 1
        except Exception as e:
            logger.error(f"{prefixo}: falha ao avaliar vencimento: {e}")

    logger.info(f"[traceId: {trace}] [ExpiraAtendimentos] {resultado}")
    return resultado


def _efeitos_depois(db, clinic_id, phone, fala):
    """Agendamentos da pessoa criados ou alterados DEPOIS da última fala dela."""
    if not fala:
        return 0
    quando = retomada._instante(fala)
    if quando is None:
        return 0
    try:
        from src.utils.phone import variantes_do_numero

        linhas = db.execute_query(
            "SELECT COUNT(*) AS n FROM scheduler.appointments a "
            "JOIN scheduler.patients p ON p.id = a.patient_id "
            "WHERE a.clinic_id = %s AND p.phone = ANY(%s) "
            "AND GREATEST(a.created_at, a.updated_at) > to_timestamp(%s)",
            (clinic_id, sorted(variantes_do_numero(phone)), quando),
        )
        return int(linhas[0]["n"]) if linhas else 0
    except Exception as e:
        logger.error(f"[ExpiraAtendimentos] {phone}: nao li efeitos depois da fala: {e}")
        # Falha fechada: sem saber, assume que alguem resolveu.
        return 1


def _retoma(db, clinic, clinic_id, phone, sessao, eventos, fala, agora, tracker, prefixo):
    """Classifica e responde uma vez. Quem encerra em cooldown e o handler."""
    from src.providers.whatsapp_provider import get_provider
    from src.services.agent_runner import falar
    from src.services.anthropic_service import AnthropicService
    from src.services.conversation_resume import GATILHO_RETOMADA

    veredito = retomada.classifica(AnthropicService(), eventos)
    atendimento.marca_retomada(sessao, agora)  # uma vez por pendencia, mesmo se calar
    if not veredito["pendente"]:
        atendimento.marca_alerta(sessao, retomada.MODELO_DISSE_NAO)
        logger.info(f"{prefixo}: o classificador disse que nao ha pendencia, cala")
        return False

    horas = max(1, int((agora - (retomada._instante(fala) or agora)) // 3600))
    atendimento.poe_contexto_de_retomada(sessao, retomada.bloco_de_contexto(horas, veredito["o_que"]))
    # O contexto precisa estar na sessao ANTES de o agente rodar, porque ele
    # recarrega a sessao do banco.
    grava_atendimento(_tabela(), clinic_id, phone, sessao)

    enviou, quantas = falar(
        clinic_id, phone, GATILHO_RETOMADA,
        db=db, provider=get_provider(clinic), tracker=tracker,
        metadata={"kind": "retomada_por_vencimento"},
    )
    # O agente gravou a sessao dele; recarrega para nao sobrescrever.
    item = _tabela().get_item(Key={"pk": f"CLINIC#{clinic_id}", "sk": f"PHONE#{phone}"}).get("Item") or {}
    sessao.clear(); sessao.update(item.get("session") or {})
    atendimento.limpa_contexto_de_retomada(sessao)
    atendimento.marca_retomada(sessao, agora)
    logger.info(f"{prefixo}: retomada {'enviada' if enviou else 'FALHOU'} ({quantas} msg)")
    return enviou
