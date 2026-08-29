"""Dispatcher da fila de abordagens ativas.

Roda a cada 15 minutos e envia no máximo uma mensagem por clínica por execução.
Esse limite é a proteção contra bloqueio do número: o provider é o z-api, que é
não-oficial, e a linha é compartilhada com os atendentes humanos, então um
bloqueio derruba a operação inteira e não só o bot. O próprio intervalo do cron é
o limitador — não precisa de contador distribuído nem lock.

O texto não vem da fila: é o ConversationAgent que escreve, com o mesmo prompt
usado quando o lead escreve primeiro. A fila guarda só a intenção de falar.
"""
import logging
import time
import uuid
from datetime import datetime, timezone

import os

import boto3

from src.providers.whatsapp_provider import IncomingMessage, get_provider
from src.services.bot_policy import should_bot_reply
from src.services.business_hours import CLINIC_TZ, is_open
from src.services.db.postgres import PostgresService
from src.services.message_tracker import MessageTracker
from src.services.outbound_queue import OutboundQueueService
from src.services.session_store import mark_conversation_eligible

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MAX_ENVIOS_POR_CLINICA_POR_EXECUCAO = 1

# Mensagem sintética que faz o agente abrir a conversa. Não é registrada como
# INBOUND: ninguém escreveu isso, é só o gatilho. O AI_SYSTEM_PROMPT tem uma
# seção ensinando o agente a reconhecê-la.
GATILHO_ABERTURA = "__INICIAR_CONVERSA__"


def _sessions_table():
    return boto3.resource("dynamodb").Table(os.environ["CONVERSATION_SESSIONS_TABLE"])


def _monta_agente(db, provider, tracker):
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


def handler(event, context):
    trace_id = str(uuid.uuid4())[:8]
    prefixo = f"[OutboundProcessor][trace:{trace_id}]"
    logger.info(f"{prefixo} Iniciando drenagem da fila")

    queue = OutboundQueueService()
    tracker = MessageTracker()
    db = PostgresService()

    agora_utc = datetime.now(timezone.utc)
    pendentes = queue.pending_due(agora_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))

    enviados_por_clinica = {}
    sent = skipped = failed = 0
    clinic_cache = {}

    for item in pendentes:
        clinic_id = item.get("clinicId", "")
        message_id = item.get("messageId", "")
        phone = item.get("phone", "")

        if enviados_por_clinica.get(clinic_id, 0) >= MAX_ENVIOS_POR_CLINICA_POR_EXECUCAO:
            skipped += 1
            continue

        try:
            if clinic_id not in clinic_cache:
                clinicas = db.execute_query(
                    "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
                    (clinic_id,),
                )
                clinic_cache[clinic_id] = clinicas[0] if clinicas else None
            clinic = clinic_cache[clinic_id]

            if not clinic:
                queue.mark_failed(message_id, item["pk"], item["sk"], "Clínica não encontrada")
                failed += 1
                continue

            # A política é reconferida no envio, não só no enfileiramento: o piloto
            # pode ter mudado depois que o item entrou na fila, e ninguém deve
            # receber abordagem de uma clínica que voltou atrás.
            #
            # bot_enabled=True porque a elegibilidade já foi estabelecida no
            # enfileiramento (origem landing-page + as quatro guardas). A sessão
            # ainda não existe: é este envio que vai criá-la. Passar sessão vazia
            # fazia LEADS_ONLY recusar todo item — o cenário de abordagem ativa
            # nunca enviava nada.
            if clinic.get("bot_paused", False) or not should_bot_reply(
                clinic, {"bot_enabled": True}, phone
            ):
                logger.info(
                    f"{prefixo} Política não permite falar com {phone}, descartando {message_id}"
                )
                queue.mark_failed(message_id, item["pk"], item["sk"], "politica_nao_permite")
                skipped += 1
                continue

            # Horário reconferido: a clínica pode ter mudado os horários depois.
            if not is_open(clinic.get("business_hours") or {}, agora_utc.astimezone(CLINIC_TZ)):
                logger.info(f"{prefixo} Clínica {clinic_id} fechada agora, adiando {message_id}")
                skipped += 1
                continue

            provider = get_provider(clinic)
            agente = _monta_agente(db, provider, tracker)

            abertura = IncomingMessage(
                message_id=str(uuid.uuid4()),
                phone=phone,
                sender_name="",
                timestamp=int(time.time()),
                message_type="TEXT",
                content=GATILHO_ABERTURA,
            )
            saidas = agente.process_message(clinic_id, abertura)

            if not saidas:
                logger.error(f"{prefixo} Agente não gerou texto para {phone} ({message_id})")
                queue.mark_failed(message_id, item["pk"], item["sk"], "agente_nao_gerou_texto")
                failed += 1
                continue

            conversation_id = f"{clinic_id}#{phone}"
            enviou_alguma = False
            for msg in saidas:
                msg_id = str(uuid.uuid4())
                tracker.track_outbound(
                    clinic_id=clinic_id, phone=phone, message_id=msg_id,
                    conversation_id=conversation_id, message_type=msg.message_type.upper(),
                    content=msg.content, status="QUEUED",
                    metadata={"kind": item.get("kind"), "leadId": item.get("leadId")},
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

            if not enviou_alguma:
                queue.mark_failed(message_id, item["pk"], item["sk"], "provider_recusou_envio")
                failed += 1
                continue

            queue.mark_sent(message_id, item["pk"], item["sk"])

            # A conversa nasce elegível: quem foi abordado pela clínica tem direito
            # a resposta automática mesmo com a política LEADS_ONLY.
            mark_conversation_eligible(_sessions_table(), clinic_id, phone, item.get("leadId"))

            enviados_por_clinica[clinic_id] = enviados_por_clinica.get(clinic_id, 0) + 1
            sent += 1
            logger.info(f"{prefixo} Conversa aberta com {phone} ({message_id})")

            # Depois deste ponto a mensagem já saiu: uma falha aqui não pode
            # marcar o item como FAILED, senão o log diz que não enviou quando
            # enviou. execute_write, não execute_query: query espera SELECT e
            # levanta "no results to fetch" num UPDATE.
            if item.get("leadId"):
                try:
                    db.execute_write(
                        "UPDATE scheduler.leads SET first_contact_status = 'SENT', "
                        "first_contact_at = NOW(), updated_at = NOW() WHERE id = %s::uuid",
                        (item["leadId"],),
                    )
                except Exception as e:
                    logger.error(f"{prefixo} Mensagem enviada, mas falhou ao marcar o lead: {e}")

        except Exception as e:
            logger.error(f"{prefixo} Erro ao processar {message_id}: {e}", exc_info=True)
            queue.mark_failed(message_id, item["pk"], item["sk"], str(e))
            failed += 1

    logger.info(
        f"{prefixo} Concluído: {len(pendentes)} pendentes, {sent} enviados, "
        f"{skipped} adiados, {failed} falhas"
    )
    return {"processed": len(pendentes), "sent": sent, "skipped": skipped, "failed": failed}
