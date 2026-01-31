import os
import time
import uuid
import logging
from typing import Any, Dict, List, Optional

import boto3
from boto3.dynamodb.conditions import Key

from src.providers.whatsapp_provider import IncomingMessage

logger = logging.getLogger(__name__)


class MessageTracker:

    def __init__(self):
        dynamodb = boto3.resource("dynamodb")
        self.table = dynamodb.Table(os.environ["MESSAGE_EVENTS_TABLE"])

    def track_outbound(
        self,
        clinic_id: str,
        phone: str,
        message_id: str,
        conversation_id: str,
        message_type: str,
        content: str,
        status: str,
        provider: str = "zapi",
        provider_message_id: str = "",
        provider_response: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = int(time.time())
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        item = {
            "pk": f"CLINIC#{clinic_id}#PHONE#{phone}",
            "sk": f"MSG#{timestamp_iso}#{message_id}",
            "clinicId": clinic_id,
            "phone": phone,
            "messageId": message_id,
            "conversationId": conversation_id,
            "direction": "OUTBOUND",
            "messageType": message_type,
            "content": content,
            "status": status,
            "statusTimestamp": f"{status}#{timestamp_iso}",
            "provider": provider,
            "providerMessageId": provider_message_id,
            "createdAt": timestamp_iso,
            "updatedAt": timestamp_iso,
        }

        if provider_response:
            item["providerResponse"] = _sanitize_for_dynamo(provider_response)

        if metadata:
            item["metadata"] = _sanitize_for_dynamo(metadata)

        try:
            self.table.put_item(Item=item)
            logger.info(
                f"[MessageTracker] Tracked OUTBOUND {status} | clinic={clinic_id} phone={phone} msgId={message_id}"
            )
        except Exception as e:
            logger.error(f"[MessageTracker] Erro ao rastrear outbound: {e}")

        return item

    def track_inbound(
        self,
        clinic_id: str,
        phone: str,
        message_id: str,
        conversation_id: str,
        incoming_message: IncomingMessage,
        conversation_state: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = int(time.time())
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))

        item = {
            "pk": f"CLINIC#{clinic_id}#PHONE#{phone}",
            "sk": f"MSG#{timestamp_iso}#{message_id}",
            "clinicId": clinic_id,
            "phone": phone,
            "messageId": message_id,
            "conversationId": conversation_id,
            "direction": "INBOUND",
            "messageType": incoming_message.message_type,
            "content": incoming_message.content,
            "status": "RECEIVED",
            "statusTimestamp": f"RECEIVED#{timestamp_iso}",
            "senderName": incoming_message.sender_name,
            "conversationState": conversation_state,
            "createdAt": timestamp_iso,
            "updatedAt": timestamp_iso,
        }

        if incoming_message.button_id:
            item["buttonId"] = incoming_message.button_id
        if incoming_message.button_text:
            item["buttonText"] = incoming_message.button_text
        if incoming_message.reference_message_id:
            item["referenceMessageId"] = incoming_message.reference_message_id

        if metadata:
            item["metadata"] = _sanitize_for_dynamo(metadata)

        try:
            self.table.put_item(Item=item)
            logger.info(
                f"[MessageTracker] Tracked INBOUND | clinic={clinic_id} phone={phone} msgId={message_id}"
            )
        except Exception as e:
            logger.error(f"[MessageTracker] Erro ao rastrear inbound: {e}")

        return item

    def update_status(
        self,
        clinic_id: str,
        phone: str,
        message_id: str,
        new_status: str,
        timestamp: int = 0,
        raw_payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        now = int(time.time())
        event_time = timestamp if timestamp else now
        timestamp_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(event_time))

        item = {
            "pk": f"CLINIC#{clinic_id}#PHONE#{phone}",
            "sk": f"STATUS#{timestamp_iso}#{message_id}#{new_status}",
            "clinicId": clinic_id,
            "phone": phone,
            "messageId": message_id,
            "direction": "STATUS_UPDATE",
            "status": new_status,
            "statusTimestamp": f"{new_status}#{timestamp_iso}",
            "content": "",
            "createdAt": timestamp_iso,
            "updatedAt": timestamp_iso,
        }

        if raw_payload:
            item["rawPayload"] = _sanitize_for_dynamo(raw_payload)

        try:
            self.table.put_item(Item=item)
            logger.info(
                f"[MessageTracker] Status update {new_status} | clinic={clinic_id} phone={phone} msgId={message_id}"
            )
        except Exception as e:
            logger.error(f"[MessageTracker] Erro ao atualizar status: {e}")

        return item

    def get_conversation_messages(
        self, clinic_id: str, phone: str, limit: int = 50
    ) -> List[Dict[str, Any]]:
        try:
            response = self.table.query(
                KeyConditionExpression=Key("pk").eq(f"CLINIC#{clinic_id}#PHONE#{phone}"),
                ScanIndexForward=True,
                Limit=limit,
            )
            return response.get("Items", [])
        except Exception as e:
            logger.error(f"[MessageTracker] Erro ao buscar mensagens: {e}")
            return []


def _sanitize_for_dynamo(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _sanitize_for_dynamo(v) for k, v in data.items() if v is not None and v != ""}
    elif isinstance(data, list):
        return [_sanitize_for_dynamo(item) for item in data]
    elif isinstance(data, float):
        from decimal import Decimal
        return Decimal(str(data))
    return data
