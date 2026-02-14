import json
import uuid
import logging
from datetime import datetime, date

from src.utils.http import parse_body, http_response, require_api_key
from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker
from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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

            logger.info(f"Mensagem {message_id} enviada com sucesso. Provider ID: {response.provider_message_id}")

            return http_response(200, {
                "status": "SUCCESS",
                "message": "Mensagem enviada com sucesso",
                "messageId": message_id,
                "providerMessageId": response.provider_message_id,
                "messageStatus": "SENT",
            })
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
