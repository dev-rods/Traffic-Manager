# -*- coding: utf-8 -*-
"""A atendente manda o bot abrir conversa com um lead.

POST /leads/{leadId}/iniciar-pelo-bot

Substitui o disparo automático no cadastro, removido em 05/09/2026. A razão não
foi técnica: não há como saber por API que a atendente já falou com quem nunca
respondeu, então a decisão voltou para quem sabe.
"""
import logging
import os

import boto3

from src.services.db.postgres import PostgresService
from src.services.elegibilidade_do_bot import motivo_legivel, por_que_nao_pode
from src.services.outbound_queue import OutboundQueueService
from src.services.status_da_conversa import conversas_da_clinica, enriquece
from src.utils.http import extract_path_param, http_response, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _acorda_o_dispatcher():
    """Chama o processor agora em vez de esperar o cron.

    O cron roda a cada 10 minutos. A atendente clica e olha a tela: dez minutos
    de "na fila" parado parece defeito. O cron continua como rede para o que for
    adiado por horário ou política.
    """
    try:
        nome = os.environ.get("OUTBOUND_PROCESSOR_FUNCTION")
        if not nome:
            return
        boto3.client("lambda").invoke(
            FunctionName=nome, InvocationType="Event", Payload=b"{}"
        )
    except Exception as e:
        # O cron pega em ate 10 minutos: falhar aqui atrasa, nao perde.
        logger.warning(f"[IniciarBot] Nao consegui acordar o dispatcher: {e}")


def handler(event, context):
    try:
        _, erro = require_api_key(event)
        if erro:
            return erro

        lead_id = extract_path_param(event, "leadId")
        if not lead_id:
            return http_response(400, {"status": "ERROR", "message": "leadId e obrigatorio"})

        db = PostgresService()
        leads = db.execute_query(
            "SELECT * FROM scheduler.leads WHERE id = %s::uuid", (lead_id,)
        )
        if not leads:
            return http_response(404, {"status": "ERROR", "message": "Lead nao encontrado"})
        lead = leads[0]

        clinics = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (lead["clinic_id"],),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Clinica nao encontrada"})
        clinic = clinics[0]

        # Revalida com a MESMA função que desenhou o botão. Botão habilitado numa
        # aba aberta há uma hora não é autorização: entre o render e o clique a
        # pessoa pode ter escrito, ou outra atendente pode ter marcado.
        lead = enriquece([lead], {}, conversas_da_clinica(db, lead["clinic_id"]))[0]
        motivo = por_que_nao_pode(lead, clinic)
        if motivo:
            logger.info(f"[IniciarBot] {lead_id} recusado: {motivo}")
            return http_response(409, {
                "status": "ERROR", "reason": motivo, "message": motivo_legivel(motivo)})

        # Marca ANTES de enfileirar, e só se ninguém marcou. É o que torna o
        # clique duplo inofensivo: a segunda chamada não acha linha para
        # atualizar e sai sem enfileirar nada.
        marcado = db.execute_write_returning(
            "UPDATE scheduler.leads SET first_contact_status = 'QUEUED', "
            "first_contact_channel = 'BOT', updated_at = NOW() "
            "WHERE id = %s::uuid AND first_contact_status IS NULL "
            "AND first_contact_at IS NULL RETURNING id",
            (lead_id,),
        )
        if not marcado:
            return http_response(409, {
                "status": "ERROR", "reason": "JA_CONTATADA",
                "message": motivo_legivel("JA_CONTATADA")})

        item = OutboundQueueService().enqueue(
            lead["clinic_id"], lead["phone"], lead_id=lead_id,
            business_hours=clinic.get("business_hours") or {},
            # A atendente decidiu agora. A espera de 10 minutos existia para dar
            # chance de a pessoa escrever primeiro, e aqui alguém já olhou isso.
            atraso_minutos=0,
        )
        if not item:
            # Sem horário configurado não há quando enviar. Desfaz a marca para
            # a atendente tentar de novo depois de configurar.
            db.execute_write(
                "UPDATE scheduler.leads SET first_contact_status = NULL, "
                "first_contact_channel = NULL WHERE id = %s::uuid",
                (lead_id,),
            )
            return http_response(409, {
                "status": "ERROR", "reason": "SEM_HORARIO",
                "message": "Clinica sem horario de atendimento configurado."})

        _acorda_o_dispatcher()
        logger.info(f"[IniciarBot] {lead_id} enfileirado ({item['messageId']})")
        return http_response(200, {
            "status": "SUCCESS", "leadId": lead_id,
            "first_contact_status": "QUEUED", "first_contact_channel": "BOT"})

    except Exception as e:
        logger.error(f"[IniciarBot] Erro: {e}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
