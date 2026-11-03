# -*- coding: utf-8 -*-
"""Envio de WhatsApp pelo sistema, fora do agente, com rastro (PRD 034).

O OTP e a confirmação do site e o link de cobrança do check-in saíam direto
pelo provedor. O z-api devolve o eco ao webhook, que não achava o id no
MessageEvents e tratava como atendente digitando no celular: gravava como fala
humana e pausava o bot por 24h. Em outubro de 2026, na Essência, foram 35 OTPs
e 44 confirmações, cerca de 40 conversas caladas logo depois de agendar.

Aqui o envio faz o que o bot faz em `agent_runner`: grava QUEUED, envia, grava
SENT ou FAILED com o id do provedor - e `metadata.origem`, para o painel e o
histórico saberem que foi o sistema, não o bot nem uma pessoa.

O rastro nunca derruba o envio: `MessageTracker.track_outbound` engole a
própria exceção, e a construção do tracker também é protegida. O chamador
recebe o resultado do provedor e decide o que fazer com ele.
"""
import logging
import uuid
from typing import Optional

from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)

SITE_OTP = "SITE_OTP"
SITE_AGENDAMENTO = "SITE_AGENDAMENTO"
CHECKIN = "CHECKIN"
ORIGENS = {SITE_OTP, SITE_AGENDAMENTO, CHECKIN}


def _tracker():
    try:
        from src.services.message_tracker import MessageTracker
        return MessageTracker()
    except Exception as e:
        logger.error(f"[EnvioDoSistema] sem rastro nesta execução: {e}")
        return None


def _final(phone):
    return f"***{str(phone)[-4:]}" if phone else "-"


def envia_texto(clinic: dict, phone: str, content: str, origem: str, *,
                conteudo_registrado: Optional[str] = None, provider=None, tracker=None):
    """Manda `content` para `phone` e grava o evento com `metadata.origem`.

    `conteudo_registrado` é o que vai para o MessageEvents no lugar do texto
    enviado: o OTP é segredo de 5 minutos e o MessageEvents vive 60 dias e
    aparece no painel. `provider` e `tracker` existem para teste e para o
    check-in, que já recebe o provedor de fora.
    """
    if origem not in ORIGENS:
        raise ValueError(f"origem desconhecida: {origem!r}")

    clinic_id = clinic["clinic_id"]
    provider = provider or get_provider(clinic)
    tracker = tracker if tracker is not None else _tracker()
    message_id = str(uuid.uuid4())
    conversation_id = f"{clinic_id}#{phone}"
    registrado = conteudo_registrado if conteudo_registrado is not None else content

    if tracker is not None:
        tracker.track_outbound(
            clinic_id=clinic_id, phone=phone, message_id=message_id,
            conversation_id=conversation_id, message_type="TEXT",
            content=registrado, status="QUEUED", metadata={"origem": origem},
        )

    result = provider.send_text(phone, content)

    if tracker is not None:
        metadata = {"origem": origem}
        if not result.success:
            metadata["error"] = result.error
        tracker.track_outbound(
            clinic_id=clinic_id, phone=phone, message_id=message_id,
            conversation_id=conversation_id, message_type="TEXT",
            content=registrado,
            status="SENT" if result.success else "FAILED",
            provider_message_id=getattr(result, "provider_message_id", "") or "",
            provider_response=getattr(result, "raw_response", None),
            metadata=metadata,
        )

    logger.info(f"[EnvioDoSistema] {origem} {clinic_id} tel={_final(phone)} enviado={bool(result.success)}")
    return result
