import json
import os
import uuid
import logging
from datetime import datetime, date

import boto3

from src.utils.http import parse_body, http_response, require_api_key
from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker
from src.providers.whatsapp_provider import get_provider
from src.services.campanha import DURACAO_PADRAO_DIAS, MAX_DATAS, abre
from src.services.session_store import abre_campanha

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _tabela_de_sessoes():
    return boto3.resource("dynamodb").Table(
        os.environ.get("CONVERSATION_SESSIONS_TABLE", "")
    )


def handler(event, context):
    """
    Handler para envio de mensagens WhatsApp.

    POST /send
    Body esperado:
    {
        "clinicId": "laser-beauty-sp-abc123",
        "phone": "5511999999999",
        "type": "text" | "buttons" | "list",
        "content": "Texto da mensagem",
        "buttons": [                         (obrigatorio se type=buttons)
            {"id": "btn_1", "label": "Opcao 1"},
            {"id": "btn_2", "label": "Opcao 2"}
        ],
        "sections": [                        (obrigatorio se type=list)
            {"title": "Secao", "rows": [{"id": "r1", "title": "Item 1"}]}
        ],
        "buttonText": "Selecione",           (opcional, para type=list)
        "conversationId": "conv-uuid",       (opcional)
        "metadata": {}                       (opcional)
    }
    """
    try:
        logger.info(f"Requisicao recebida para envio de mensagem")

        # 1. Validar API key
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        # 2. Parse body
        body = parse_body(event)
        if not body:
            return http_response(400, {
                "status": "ERROR",
                "message": "Corpo da requisição vazio ou inválido"
            })

        # 3. Validar campos obrigatorios
        clinic_id = body.get("clinicId")
        phone = body.get("phone")
        msg_type = body.get("type", "text")
        content = body.get("content", "")

        if not clinic_id or not phone:
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: clinicId, phone"
            })

        if not content and msg_type == "text":
            return http_response(400, {
                "status": "ERROR",
                "message": "Campo 'content' e obrigatorio para type=text"
            })

        if msg_type == "buttons" and not body.get("buttons"):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campo 'buttons' e obrigatorio para type=buttons"
            })

        if msg_type == "list" and not body.get("sections"):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campo 'sections' e obrigatorio para type=list"
            })

        # Campanha de reagendamento: campo OPCIONAL. Ausente - que e o caso de
        # toda mensagem manual da atendente - nada muda neste handler.
        campanha_pedida = body.get("campanha")
        if campanha_pedida is not None:
            if not isinstance(campanha_pedida, dict) or not campanha_pedida.get("datas"):
                return http_response(400, {
                    "status": "ERROR",
                    "message": "campanha requer 'datas' com pelo menos uma data",
                })
            if len(campanha_pedida["datas"]) > MAX_DATAS:
                return http_response(400, {
                    "status": "ERROR",
                    "message": f"campanha aceita no maximo {MAX_DATAS} datas",
                })

        # 4. Buscar clinica no RDS
        db = PostgresService()
        clinics = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,)
        )

        if not clinics:
            return http_response(404, {
                "status": "ERROR",
                "message": f"Clinica '{clinic_id}' não encontrada"
            })

        clinic = clinics[0]

        # A campanha so existe no ConversationAgent: o bloco de modo e montado
        # la. Numa clinica que ainda roda a ConversationEngine antiga o disparo
        # sairia, a campanha seria gravada, e a paciente receberia o fluxo de
        # lead - boas-vindas e pedido de CPF de quem ja e cadastrada. Barrado
        # aqui, na origem, em vez de virar log que ninguem le.
        if campanha_pedida is not None and not clinic.get("use_agent"):
            return http_response(400, {
                "status": "ERROR",
                "message": "campanha exige a clinica com use_agent ativo",
            })

        # 5. Instanciar provider
        provider = get_provider(clinic)

        # 6. Gerar message_id e track QUEUED
        message_id = str(uuid.uuid4())
        conversation_id = body.get("conversationId", str(uuid.uuid4()))
        tracker = MessageTracker()

        tracker.track_outbound(
            clinic_id=clinic_id,
            phone=phone,
            message_id=message_id,
            conversation_id=conversation_id,
            message_type=msg_type.upper(),
            content=content,
            status="QUEUED",
            metadata=body.get("metadata"),
        )

        logger.info(f"Mensagem {message_id} enfileirada para {phone} (clinica={clinic_id})")

        # 7. Enviar via provider
        if msg_type == "buttons":
            response = provider.send_buttons(phone, content, body["buttons"])
        elif msg_type == "list":
            button_text = body.get("buttonText", "Selecione")
            response = provider.send_list(phone, content, button_text, body["sections"])
        else:
            response = provider.send_text(phone, content)

        # 8. Track resultado
        if response.success:
            tracker.track_outbound(
                clinic_id=clinic_id,
                phone=phone,
                message_id=message_id,
                conversation_id=conversation_id,
                message_type=msg_type.upper(),
                content=content,
                status="SENT",
                provider_message_id=response.provider_message_id,
                provider_response=response.raw_response,
            )

            # Update last_message_at on patient record (skip soft-deleted).
            # execute_write, not execute_query — the latter calls fetchall() and never
            # commits, so every UPDATE raised "no results to fetch" into the except below
            # and last_message_at stayed NULL for every patient.
            try:
                db.execute_write(
                    """UPDATE scheduler.patients
                       SET last_message_at = NOW(), updated_at = NOW()
                       WHERE clinic_id = %s AND phone = %s AND deleted_at IS NULL""",
                    (clinic_id, phone),
                )
            except Exception as e:
                logger.warning(f"Falha ao atualizar last_message_at para {phone}: {e}")

            # Campanha so DEPOIS do envio confirmado. Invertida a ordem, uma
            # falha de entrega deixaria o bot esperando resposta de uma
            # mensagem que ninguem recebeu.
            campanha_aberta = None
            if campanha_pedida is not None:
                campanha_aberta = abre_campanha(
                    _tabela_de_sessoes(), clinic_id, phone,
                    abre(campanha_pedida["datas"],
                         dias=int(campanha_pedida.get("dias") or DURACAO_PADRAO_DIAS)),
                )
                if not campanha_aberta:
                    # Nao derruba o envio - a mensagem ja saiu. Mas volta na
                    # resposta: a paciente recebeu as datas e o bot NAO vai
                    # responder, entao alguem precisa saber disso.
                    logger.error(
                        f"[Send] Mensagem enviada para {phone} mas a campanha nao abriu; "
                        f"o bot nao respondera esta conversa"
                    )

            logger.info(f"Mensagem {message_id} enviada com sucesso. Provider ID: {response.provider_message_id}")

            corpo = {
                "status": "SUCCESS",
                "message": "Mensagem enviada com sucesso",
                "messageId": message_id,
                "providerMessageId": response.provider_message_id,
                "messageStatus": "SENT",
            }
            if campanha_aberta is not None:
                corpo["campanhaAberta"] = campanha_aberta
            return http_response(200, corpo)
        else:
            tracker.track_outbound(
                clinic_id=clinic_id,
                phone=phone,
                message_id=message_id,
                conversation_id=conversation_id,
                message_type=msg_type.upper(),
                content=content,
                status="FAILED",
                provider_response=response.raw_response,
                metadata={"error": response.error},
            )

            logger.error(f"Falha ao enviar mensagem {message_id}: {response.error}")

            return http_response(502, {
                "status": "ERROR",
                "message": "Falha ao enviar mensagem via provider",
                "messageId": message_id,
                "messageStatus": "FAILED",
                "error": response.error,
            })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro ao enviar mensagem: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno no servidor",
            "error": error_msg,
        })
