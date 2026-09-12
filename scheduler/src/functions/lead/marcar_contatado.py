# -*- coding: utf-8 -*-
"""A atendente registra que ELA já iniciou a conversa - ou desfaz o registro.

POST /leads/{leadId}/marcar-contatado

Este botão existe porque a API não enxerga o que ele registra. Quando a
atendente escreve para alguém que nunca respondeu, a mensagem chega ao nosso
webhook como LID sem telefone e é descartada; o z-api também não resolve
(testado em 05/09/2026: 4 de 27 LIDs, e os 4 já estavam na agenda do aparelho).
O contato existe e é invisível para qualquer consulta que a gente faça. Aqui a
pessoa que sabe conta para o sistema.

Alterna: chamar de novo desmarca. Só desfaz o que uma PESSOA marcou - se o bot
enviou, a mensagem está no WhatsApp de alguém e desmarcar seria mentira, além de
reabrir o botão para uma segunda.
"""
import logging

from src.services.db.postgres import PostgresService
from src.services.elegibilidade_do_bot import pode_desmarcar
from src.utils.http import extract_path_param, http_response, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

        if pode_desmarcar(lead):
            db.execute_write(
                "UPDATE scheduler.leads SET first_contact_status = NULL, "
                "first_contact_at = NULL, first_contact_channel = NULL, "
                "updated_at = NOW() WHERE id = %s::uuid",
                (lead_id,),
            )
            logger.info(f"[MarcarContatado] {lead_id} desmarcado")
            return http_response(200, {
                "status": "SUCCESS", "leadId": lead_id, "first_contact_channel": None})

        # Marcar so vale enquanto ninguem contatou. Se o BOT ja enviou, marcar
        # como humano apagaria o registro de uma mensagem que existe de verdade.
        #
        # A condicao olha `first_contact_status` E o canal. So o canal nao basta:
        # os leads do fluxo automatico antigo tem status QUEUED ou SENT com canal
        # NULL - 5 deles em producao - e um clique aqui os reescreveria como
        # HUMANO, apagando o registro de um envio que foi do bot.
        marcado = db.execute_write_returning(
            "UPDATE scheduler.leads SET first_contact_status = 'SENT', "
            "first_contact_at = NOW(), first_contact_channel = 'HUMANO', "
            "updated_at = NOW() "
            "WHERE id = %s::uuid AND first_contact_channel IS NULL "
            "AND first_contact_status IS NULL RETURNING id",
            (lead_id,),
        )
        if not marcado:
            return http_response(409, {
                "status": "ERROR", "reason": "INICIADA_PELO_BOT",
                "message": "Esta conversa ja foi iniciada pelo bot."})

        logger.info(f"[MarcarContatado] {lead_id} marcado como iniciado por humano")
        return http_response(200, {
            "status": "SUCCESS", "leadId": lead_id, "first_contact_channel": "HUMANO"})

    except Exception as e:
        logger.error(f"[MarcarContatado] Erro: {e}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})
