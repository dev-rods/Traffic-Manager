"""Faz o ConversationAgent falar primeiro e entrega o que ele escreveu.

Dois caminhos precisam disso: o dispatcher da fila de abordagens ativas e a
retomada de conversa pelo painel. Nos dois, ninguém escreveu nada agora - um
gatilho sintético diz ao agente por que ele está falando, e o texto sai dele,
com o mesmo prompt de quando o lead escreve primeiro.

Manter num lugar só é o que impede os dois de divergirem no que registram: o
rastro no MessageEvents é o que o painel mostra e o que o agente relê depois
para reconstruir a conversa.
"""
import logging
import time
import uuid

from src.providers.whatsapp_provider import IncomingMessage

logger = logging.getLogger(__name__)


def montar_agente(db, provider, tracker):
    """Importes adiados: são pesados e nem todo caminho do lambda usa o agente."""
    from src.services.appointment_service import AppointmentService
    from src.services.availability_engine import AvailabilityEngine
    from src.services.conversation_agent import ConversationAgent
    from src.services.template_service import TemplateService

    return ConversationAgent(
        db=db,
        template_service=TemplateService(db),
        availability_engine=AvailabilityEngine(db),
        appointment_service=AppointmentService(db),
        provider=provider,
        message_tracker=tracker,
    )


def falar(clinic_id, phone, gatilho, *, db, provider, tracker, metadata=None):
    """Roda o agente com um gatilho sintético e envia o que ele escrever.

    O gatilho não entra no MessageEvents como INBOUND: ninguém o escreveu, e
    registrá-lo faria o agente reler o próprio gatilho como fala da pessoa na
    próxima reconstrução de histórico.

    Devolve (enviou_alguma, total_de_mensagens).
    """
    agente = montar_agente(db, provider, tracker)

    entrada = IncomingMessage(
        message_id=str(uuid.uuid4()),
        phone=phone,
        sender_name="",
        timestamp=int(time.time()),
        message_type="TEXT",
        content=gatilho,
    )
    saidas = agente.process_message(clinic_id, entrada)
    if not saidas:
        return False, 0

    conversation_id = f"{clinic_id}#{phone}"
    enviou_alguma = False

    for msg in saidas:
        msg_id = str(uuid.uuid4())
        tracker.track_outbound(
            clinic_id=clinic_id, phone=phone, message_id=msg_id,
            conversation_id=conversation_id, message_type=msg.message_type.upper(),
            content=msg.content, status="QUEUED", metadata=metadata,
        )

        if msg.message_type == "buttons" and msg.buttons:
            response = provider.send_buttons(phone, msg.content, msg.buttons)
        elif msg.message_type == "list" and msg.sections:
            response = provider.send_list(
                phone, msg.content, msg.button_text or "Selecione", msg.sections
            )
        else:
            response = provider.send_text(phone, msg.content)

        tracker.track_outbound(
            clinic_id=clinic_id, phone=phone, message_id=msg_id,
            conversation_id=conversation_id, message_type=msg.message_type.upper(),
            content=msg.content,
            status="SENT" if response.success else "FAILED",
            provider_message_id=getattr(response, "provider_message_id", None),
            provider_response=getattr(response, "raw_response", None),
            metadata=None if response.success else {"error": response.error},
        )
        enviou_alguma = enviou_alguma or response.success

    return enviou_alguma, len(saidas)
