import os
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

logger = logging.getLogger(__name__)


class ReminderService:

    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        self.table = dynamodb.Table(os.environ["SCHEDULED_REMINDERS_TABLE"])

    def schedule_reminder(self, appointment: Dict[str, Any]) -> Dict[str, Any]:
        reminder_id = str(uuid.uuid4())
        clinic_id = appointment.get("clinic_id", "")
        appointment_id = str(appointment.get("id", ""))

        # Calculate send_at: appointment_date + start_time - 24h
        appt_date = appointment.get("appointment_date")
        appt_time = appointment.get("start_time")

        if isinstance(appt_date, str):
            dt = datetime.strptime(appt_date, "%Y-%m-%d")
        else:
            dt = datetime.combine(appt_date, datetime.min.time())

        if isinstance(appt_time, str):
            parts = appt_time.split(":")
            dt = dt.replace(hour=int(parts[0]), minute=int(parts[1]))
        elif hasattr(appt_time, 'hour'):
            dt = dt.replace(hour=appt_time.hour, minute=appt_time.minute)
        elif isinstance(appt_time, timedelta):
            total_seconds = int(appt_time.total_seconds())
            dt = dt.replace(hour=total_seconds // 3600, minute=(total_seconds % 3600) // 60)

        # 24h before appointment (UTC assumed, timezone should be handled by caller)
        send_at_dt = dt - timedelta(hours=24)
        send_at_iso = send_at_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        # Get patient info
        phone = appointment.get("patient_phone", "")
        patient_name = appointment.get("patient_name", "")

        # If patient info not in appointment dict, try from nested data
        if not phone:
            phone = appointment.get("phone", "")

        item = {
            "pk": f"REMINDER#{reminder_id}",
            "sk": f"SEND_AT#{send_at_iso}",
            "reminderId": reminder_id,
            "appointmentId": appointment_id,
            "clinicId": clinic_id,
            "phoneNumber": phone,
            "patientName": patient_name,
            "reminderType": "REMINDER_24H",
            "status": "PENDING",
            "sendAt": send_at_iso,
            "appointmentDate": str(appt_date),
            "appointmentTime": str(appt_time),
            "createdAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }

        try:
            self.table.put_item(Item=item)
            logger.info(
                f"[ReminderService] Lembrete agendado: id={reminder_id} "
                f"appointmentId={appointment_id} sendAt={send_at_iso}"
            )
        except Exception as e:
            logger.error(f"[ReminderService] Erro ao agendar lembrete: {e}")

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
