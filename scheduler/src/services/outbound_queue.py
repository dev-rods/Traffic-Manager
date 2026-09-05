"""Fila de abordagens ativas, drenada pelo dispatcher em cron.

Existe porque o disparo não pode ser síncrono ao cadastro do lead: precisa
respeitar o horário comercial da clínica e um limite de taxa que protege o número
contra bloqueio no provider.

A fila guarda a INTENÇÃO de falar, não o texto. Quem escreve é o
ConversationAgent no momento do envio, com o mesmo prompt usado quando o lead
escreve primeiro — assim não existe uma segunda mensagem de boas-vindas que
diverge do AI_SYSTEM_PROMPT com o tempo.
"""
import logging
import os
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.services.business_hours import CLINIC_TZ, next_opening

logger = logging.getLogger(__name__)

TTL_DIAS = 30

# Espera antes de abordar um lead recém-cadastrado. Boa parte procura a clínica
# por conta própria logo depois de preencher o formulário; abordar na hora
# atropelaria essa conversa. Passado esse tempo sem contato, o bot inicia.
ATRASO_PRIMEIRO_CONTATO_MINUTOS = 10

# Medido em 05/09/2026 nos 34 leads da landing page: dos 3 que escreveram
# sozinhos, TODOS escreveram em menos de 1 minuto, e ninguem escreveu entre 1
# minuto e 24 horas. Os 10 minutos cobrem 100% de quem se autoinicia com folga
# larga, ao custo de 10 minutos de atraso para os outros 91%.

# Prazo de validade da abordagem. Uma tentativa que fica adiando - clinica
# fechada, piloto ligado, provider fora - nao pode virar um "oi" de duas semanas
# atras chegando do nada. Passado o prazo, desiste e grava o motivo.
VALIDADE_HORAS = 72


class OutboundQueueService:

    def __init__(self):
        self.table = boto3.resource("dynamodb").Table(os.environ["OUTBOUND_QUEUE_TABLE"])

    def enqueue(
        self,
        clinic_id: str,
        phone: str,
        *,
        lead_id: Optional[str] = None,
        kind: str = "FIRST_CONTACT",
        business_hours: Optional[Dict] = None,
        now: Optional[datetime] = None,
        atraso_minutos: int = ATRASO_PRIMEIRO_CONTATO_MINUTOS,
    ) -> Optional[Dict]:
        """Enfileira uma abordagem para depois do atraso, dentro do horário de atendimento.

        O atraso vem primeiro e a janela comercial depois: o instante de saída é a
        próxima abertura contada a partir de `agora + atraso`, nunca antes disso.

        Devolve None quando a clínica não tem nenhum dia configurado: sem janela
        não há quando enviar, e enfileirar criaria um item que nunca sai.
        """
        agora = now or datetime.now(timezone.utc)
        # O horário comercial é expresso no fuso da clínica, então o instante tem
        # que chegar em CLINIC_TZ. Passar UTC faz next_opening ler o dia da semana
        # e montar a abertura no fuso errado: um lead de sábado 16:32 saía "segunda
        # 07:15" que na verdade era 04:15 da manhã em Brasília.
        elegivel_a_partir_de = (agora + timedelta(minutes=atraso_minutos)).astimezone(CLINIC_TZ)
        saida = next_opening(business_hours or {}, elegivel_a_partir_de)
        if saida is None:
            logger.warning(
                f"[OutboundQueue] Clínica {clinic_id} sem horário comercial configurado, "
                f"abordagem não enfileirada"
            )
            return None

        send_after = saida.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        message_id = str(uuid.uuid4())
        item = {
            "pk": f"CLINIC#{clinic_id}",
            "sk": f"OUT#{send_after}#{message_id}",
            "messageId": message_id,
            "clinicId": clinic_id,
            "phone": phone,
            "leadId": lead_id,
            "kind": kind,
            "status": "PENDING",
            "sendAfter": send_after,
            "attempts": 0,
            "createdAt": agora.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "expiresAt": (agora + timedelta(hours=VALIDADE_HORAS)).astimezone(
                timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "ttl": int(time.time()) + TTL_DIAS * 24 * 60 * 60,
        }
        self.table.put_item(Item=item)
        logger.info(
            f"[OutboundQueue] {message_id} enfileirado para {clinic_id}, "
            f"sai a partir de {send_after}"
        )
        return item

    def pending_due(self, now_iso: str, limit: int = 50) -> List[Dict]:
        """Itens PENDING cujo sendAfter já passou, mais antigos primeiro."""
        response = self.table.query(
            IndexName="status-sendAfter-index",
            KeyConditionExpression=Key("status").eq("PENDING") & Key("sendAfter").lte(now_iso),
            Limit=limit,
        )
        return response.get("Items", [])

    def mark_sent(self, message_id: str, pk: str, sk: str) -> None:
        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET #s = :status, sentAt = :sent_at, attempts = attempts + :one",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":status": "SENT",
                ":sent_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                ":one": 1,
            },
        )

    def adia(self, message_id: str, pk: str, sk: str, motivo: str) -> None:
        """Continua PENDING: a proxima execucao do cron tenta de novo.

        Separar isto de `mark_failed` e o ponto do retry. Antes, "politica nao
        permite" marcava FAILED terminal - e 3 leads de 02/09/2026 ficaram
        parados para sempre porque o piloto estava ligado no momento do disparo.
        Desligar o piloto nao os traz de volta; nada os traz.

        O backoff e o proprio cron de 10 minutos. Quem para a repeticao e o
        `expiresAt`, nao um contador de tentativas: o que importa nao e quantas
        vezes tentamos, e ha quanto tempo a pessoa se cadastrou.
        """
        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET ultimoMotivo = :motivo ADD attempts :one",
            ExpressionAttributeValues={":motivo": motivo, ":one": 1},
        )

    def mark_expired(self, message_id: str, pk: str, sk: str, motivo: str) -> None:
        """Terminal por prazo. Estado proprio para nao se confundir com falha:
        no relatorio, "ninguem estava disponivel por 72h" e outra coisa de
        "o envio quebrou"."""
        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET #s = :status, #e = :error",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
            ExpressionAttributeValues={":status": "EXPIRED", ":error": motivo},
        )

    def mark_failed(self, message_id: str, pk: str, sk: str, error: str) -> None:
        self.table.update_item(
            Key={"pk": pk, "sk": sk},
            UpdateExpression="SET #s = :status, #e = :error, attempts = attempts + :one",
            ExpressionAttributeNames={"#s": "status", "#e": "error"},
            ExpressionAttributeValues={":status": "FAILED", ":error": error, ":one": 1},
        )
