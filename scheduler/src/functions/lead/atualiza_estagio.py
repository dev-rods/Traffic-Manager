# -*- coding: utf-8 -*-
"""A atendente corrige o estagio que o modelo (ou a regra) errou (PRD 057).

PATCH /clinics/{clinicId}/leads/{leadId}/stage  {"stage": "...", "reason": "..."}

Grava MANUAL: a regra noturna nao sobrescreve mais, so um fato da agenda
(agendou) ou outra correcao. Fato da agenda nao se edita aqui - vem da agenda.
"""
import logging
from datetime import date, datetime, time
from decimal import Decimal

from src.services import estagio_repo as repo
from src.services.db.postgres import PostgresService
from src.services.estagio_do_lead import Decisao, ESTAGIOS_DA_AGENDA, ESTAGIOS_EDITAVEIS, MANUAL
from src.utils.acesso import require_acesso
from src.utils.http import extract_path_param, http_response, parse_body

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TAMANHO_DO_MOTIVO = 120


def _serializa(valor):
    if isinstance(valor, (datetime, date, time)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def handler(event, context):
    try:
        identidade, erro = require_acesso(event, "crm.escrever")
        if erro:
            return erro

        clinic_id = extract_path_param(event, "clinicId")
        lead_id = extract_path_param(event, "leadId")
        if not clinic_id or not lead_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e leadId sao obrigatorios"})

        body = parse_body(event) or {}
        stage = body.get("stage")
        reason = " ".join(str(body.get("reason") or "").split())[:TAMANHO_DO_MOTIVO] or None
        if stage in ESTAGIOS_DA_AGENDA:
            return http_response(400, {
                "status": "ERROR",
                "message": "Este estagio vem da agenda e nao pode ser editado.",
            })
        if stage not in ESTAGIOS_EDITAVEIS:
            return http_response(400, {
                "status": "ERROR",
                "message": "stage invalido; aceitos: {}".format(", ".join(sorted(ESTAGIOS_EDITAVEIS))),
            })

        db = PostgresService()
        leads = db.execute_query(
            "SELECT * FROM scheduler.leads WHERE id = %s::uuid AND clinic_id = %s", (lead_id, clinic_id))
        if not leads:
            return http_response(404, {"status": "ERROR", "message": "Lead nao encontrado"})
        lead = leads[0]

        repo.grava_estagio(db, lead, Decisao(stage, MANUAL, reason or ""), usuario_id=identidade.user_id,
                           ultima_em=lead.get("ultima_mensagem_em"), ultima_de=lead.get("ultima_mensagem_de"))
        atualizado = dict(lead, stage=stage, stage_source=MANUAL, stage_reason=reason)
        logger.info("[AtualizaEstagio] {} -> {} por {}".format(lead_id, stage, identidade.nome or identidade.user_id or "admin"))
        return http_response(200, {
            "status": "SUCCESS",
            "lead": {k: _serializa(v) for k, v in atualizado.items()},
        })
    except Exception as e:
        logger.error("Erro ao atualizar estagio: {}".format(e))
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
