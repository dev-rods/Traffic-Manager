# -*- coding: utf-8 -*-
"""Tarefas humanas da clínica: listar e fechar. PRD 020 §3.6.

    GET  /clinics/{clinicId}/tarefas              as abertas
    POST /clinics/{clinicId}/tarefas/{tarefaId}/close   fecha e devolve a conversa ao cooldown

Uma Lambda para as duas rotas, como o site público: o stack tem limite de
recursos e cada função custa quatro.
"""
import logging
import os

import boto3

from src.services import atendimento, tarefas
from src.services.session_store import carrega_sessao, grava_atendimento
from src.utils.http import extract_path_param, http_response, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _tabela():
    return boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])


def listar(event, context):
    from src.services.db.postgres import PostgresService

    clinic_id = extract_path_param(event, "clinicId")
    if not clinic_id:
        return http_response(400, {"status": "ERROR", "message": "clinicId obrigatório"})
    itens = tarefas.abertas(PostgresService(), clinic_id)
    for t in itens:
        if t.get("aberta_em") is not None:
            t["aberta_em"] = t["aberta_em"].isoformat()
    return http_response(200, {"status": "OK", "tarefas": itens, "total": len(itens)})


def fechar(event, context):
    from src.services.db.postgres import PostgresService

    clinic_id = extract_path_param(event, "clinicId")
    tarefa_id = extract_path_param(event, "tarefaId")
    if not clinic_id or not tarefa_id:
        return http_response(400, {"status": "ERROR", "message": "clinicId e tarefaId obrigatórios"})

    db = PostgresService()
    fechada = tarefas.fecha(db, clinic_id, tarefa_id, por=(event.get("requestContext") or {}).get("identity", {}).get("sourceIp", ""))
    if not fechada:
        return http_response(404, {"status": "ERROR", "message": "Tarefa não encontrada ou já fechada"})

    # Fechar a tarefa é o que tira a conversa de HUMAN_PENDING: ela vai para
    # cooldown - o bot responde se a pessoa escrever, mas não inicia nada.
    phone = fechada["phone"]
    tabela = _tabela()
    sessao = carrega_sessao(clinic_id, phone, tabela)
    atendimento.fecha_pendencia(sessao)
    grava_atendimento(tabela, clinic_id, phone, sessao)
    logger.info(f"[Tarefas] {tarefa_id} fechada; conversa de {phone} em {atendimento.estado(sessao)}")
    return http_response(200, {"status": "OK", "phone": phone, "handler": atendimento.estado(sessao)})


ROTAS = {
    ("GET", "clinics/{clinicId}/tarefas"): listar,
    ("POST", "clinics/{clinicId}/tarefas/{tarefaId}/close"): fechar,
}


def handler(event, context):
    _, erro = require_api_key(event)
    if erro:
        return erro
    rota = ROTAS.get((event.get("httpMethod", ""), (event.get("resource") or "").lstrip("/")))
    if not rota:
        return http_response(404, {"status": "ERROR", "message": "Rota não encontrada"})
    return rota(event, context)
