import os
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)

# A fila de ENTREGA dos lembretes de sessao (PRD 027). Quem decide QUANDO e o
# chamador (`lembrete_da_agenda`): o botao do painel manda "agora", o lote
# automatico manda "primeiro horario do dia menos a antecedencia". Ate 27/10/2026
# este arquivo calculava "24h antes de cada sessao" e nunca foi ligado em
# producao; o calculo saiu daqui porque o lembrete e por DIA, nao por sessao.


class ReminderService:

    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        self.table = dynamodb.Table(os.environ["SCHEDULED_REMINDERS_TABLE"])

    def agenda_lembrete(self, appointment: Dict[str, Any], clinic: Dict[str, Any],
                        send_at: datetime) -> Dict[str, Any]:
        """Um item na fila com o `sendAt` do LOTE. `send_at` tem fuso; e gravado
        em UTC porque e com o relogio UTC que o processador compara."""
        reminder_id = str(uuid.uuid4())
        send_at_iso = send_at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        item = {
            "pk": f"REMINDER#{reminder_id}",
            "sk": f"SEND_AT#{send_at_iso}",
            "reminderId": reminder_id,
            "appointmentId": str(appointment.get("id", "")),
            "clinicId": appointment.get("clinic_id") or clinic.get("clinic_id", ""),
            "phoneNumber": appointment.get("patient_phone") or appointment.get("phone") or "",
            # O nome digitado neste agendamento: o mesmo telefone pode agendar
            # para mais de uma pessoa, e o cadastro guarda um nome so.
            "patientName": appointment.get("full_name") or appointment.get("patient_name") or "",
            "reminderType": "LEMBRETE_SESSAO",
            "status": "PENDING",
            "sendAt": send_at_iso,
            "appointmentDate": str(appointment.get("appointment_date")),
            "appointmentTime": str(appointment.get("start_time")),
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        self.table.put_item(Item=item)
        logger.info(
            f"[ReminderService] Lembrete enfileirado: {reminder_id} "
            f"appointment={item['appointmentId']} sendAt={send_at_iso}"
        )
        return item

    def cancel_reminder(self, appointment_id: str) -> int:
        cancelled_count = 0
        try:
            # Scan for reminders by appointmentId (limited scan is acceptable
            # since reminders per appointment is low — typically 1)
            response = self.table.scan(
                FilterExpression=Attr("appointmentId").eq(appointment_id) & Attr("status").eq("PENDING"),
                Limit=10,
            )

            for item in response.get("Items", []):
                self.table.update_item(
                    Key={"pk": item["pk"], "sk": item["sk"]},
                    UpdateExpression="SET #s = :s, updatedAt = :u",
                    ExpressionAttributeNames={"#s": "status"},
                    ExpressionAttributeValues={
                        ":s": "CANCELLED",
                        ":u": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    },
                )
                cancelled_count += 1

            logger.info(
                f"[ReminderService] {cancelled_count} lembrete(s) cancelado(s) para appointmentId={appointment_id}"
            )
        except Exception as e:
            logger.error(f"[ReminderService] Erro ao cancelar lembretes: {e}")

        return cancelled_count

    def get_pending_reminders(self, now: str) -> List[Dict[str, Any]]:
        try:
            response = self.table.query(
                IndexName="status-sendAt-index",
                KeyConditionExpression=Key("status").eq("PENDING") & Key("sendAt").lte(now),
            )
            items = response.get("Items", [])
            logger.info(f"[ReminderService] {len(items)} lembrete(s) pendente(s) encontrado(s)")
            return items
        except Exception as e:
            logger.error(f"[ReminderService] Erro ao buscar lembretes pendentes: {e}")
            return []

    def mark_sent(self, reminder_id: str, pk: str, sk: str) -> None:
        try:
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression="SET #s = :s, sentAt = :t, updatedAt = :u",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={
                    ":s": "SENT",
                    ":t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    ":u": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
        except Exception as e:
            logger.error(f"[ReminderService] Erro ao marcar como enviado: {e}")

    def adia(self, pk: str, sk: str, novo_send_at: str, motivo: str) -> None:
        """Deixa PENDING e empurra o `sendAt`. Adiar, nao falhar: FAILED e
        terminal, e um lembrete que caiu na janela de silencio ainda tem de
        sair - as 05:00. So o atributo muda; o `sk` carrega o horario antigo
        mas nada consulta por ele, e o indice le `sendAt`."""
        try:
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression="SET sendAt = :s, adiadoPor = :m, updatedAt = :u",
                ExpressionAttributeValues={
                    ":s": novo_send_at,
                    ":m": motivo,
                    ":u": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
        except Exception as e:
            logger.error(f"[ReminderService] Erro ao adiar lembrete: {e}")

    def mark_failed(self, reminder_id: str, pk: str, sk: str, error: str) -> None:
        try:
            self.table.update_item(
                Key={"pk": pk, "sk": sk},
                UpdateExpression="SET #s = :s, #e = :e, updatedAt = :u",
                ExpressionAttributeNames={"#s": "status", "#e": "error"},
                ExpressionAttributeValues={
                    ":s": "FAILED",
                    ":e": error,
                    ":u": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                },
            )
        except Exception as e:
            logger.error(f"[ReminderService] Erro ao marcar como falha: {e}")
