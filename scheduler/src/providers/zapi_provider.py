import logging
from typing import Any, Dict, List, Optional

import requests

from src.providers.whatsapp_provider import (
    WhatsAppProvider,
    ProviderResponse,
    IncomingMessage,
    MessageStatusUpdate,
    is_phone_allowed,
)

logger = logging.getLogger(__name__)


class ZApiProvider(WhatsAppProvider):

    def __init__(self, instance_id: str, instance_token: str, client_token: str):
        self.instance_id = instance_id
        self.instance_token = instance_token
        self.client_token = client_token
        self.base_url = f"https://api.z-api.io/instances/{instance_id}/token/{instance_token}"
        self.headers = {
            "Client-Token": client_token,
            "Content-Type": "application/json",
        }

    def _check_allowlist(self, phone: str) -> Optional[ProviderResponse]:
        if not is_phone_allowed(phone):
            masked = phone[-4:] if len(phone) >= 4 else phone
            logger.warning(f"Message blocked by allowlist — phone ending in ***{masked}")
            return ProviderResponse(
                success=True,
                provider_message_id="blocked-by-allowlist",
                raw_response={"blocked": True, "reason": "phone_not_in_allowlist"},
            )
        return None

    def send_text(self, phone: str, message: str) -> ProviderResponse:
        blocked = self._check_allowlist(phone)
        if blocked:
            return blocked

        url = f"{self.base_url}/send-text"
        payload = {"phone": phone, "message": message}

        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = resp.json() if resp.content else {}

            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    provider_message_id=data.get("zaapId", data.get("messageId", "")),
                    raw_response=data,
                )
            else:
                return ProviderResponse(
                    success=False,
                    raw_response=data,
                    error=f"z-api status {resp.status_code}: {data}",
                )
        except Exception as e:
            logger.error(f"Erro ao enviar texto via z-api: {e}")
            return ProviderResponse(success=False, error=str(e))

    def send_buttons(self, phone: str, message: str, buttons: List[Dict[str, str]]) -> ProviderResponse:
        blocked = self._check_allowlist(phone)
        if blocked:
            return blocked

        url = f"{self.base_url}/send-button-list"
        payload = {
            "phone": phone,
            "message": message,
            "buttonList": {
                "buttons": [{"id": b["id"], "label": b["label"]} for b in buttons]
            },
        }

        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=15)
            data = resp.json() if resp.content else {}

            if resp.status_code == 200:
                return ProviderResponse(
                    success=True,
                    provider_message_id=data.get("zaapId", data.get("messageId", "")),
                    raw_response=data,
                )
            else:
                logger.warning(f"Botões falharam (status {resp.status_code}), usando fallback texto numerado")
                return self._send_numbered_fallback(phone, message, buttons)
        except Exception as e:
            logger.warning(f"Botões falharam ({e}), usando fallback texto numerado")
            return self._send_numbered_fallback(phone, message, buttons)

    def send_list(self, phone: str, message: str, button_text: str, sections: List[Dict]) -> ProviderResponse:
        blocked = self._check_allowlist(phone)
        if blocked:
            return blocked

        # z-api list support can be unstable, use numbered fallback
        lines = [message, ""]
        idx = 1
        for section in sections:
            for row in section.get("rows", []):
                lines.append(f"{idx} - {row.get('title', row.get('label', ''))}")
                idx += 1

        return self.send_text(phone, "\n".join(lines))

    def parse_incoming_message(self, raw_payload: Dict[str, Any]) -> IncomingMessage:
        message_type = "TEXT"
        content = ""
        button_id = None
        button_text = None
        reference_message_id = None

        # Button response
        if "buttonsResponseMessage" in raw_payload:
            message_type = "BUTTON_RESPONSE"
            btn = raw_payload["buttonsResponseMessage"]
            button_id = btn.get("buttonId", "")
            button_text = btn.get("message", "")
            content = button_text
            reference_message_id = raw_payload.get("referenceMessageId")

        # List response
        elif "listResponseMessage" in raw_payload:
            message_type = "LIST_RESPONSE"
            lst = raw_payload["listResponseMessage"]
            button_id = lst.get("selectedRowId", "")
            button_text = lst.get("title", "")
            content = button_text
            reference_message_id = raw_payload.get("referenceMessageId")

        # Text message
        elif "text" in raw_payload:
            message_type = "TEXT"
            content = raw_payload["text"].get("message", "")

        # Image
        elif "image" in raw_payload:
            message_type = "IMAGE"
            content = raw_payload["image"].get("caption", "")

        # Audio
        elif "audio" in raw_payload:
            message_type = "AUDIO"

        # Video
        elif "video" in raw_payload:
            message_type = "VIDEO"
            content = raw_payload["video"].get("caption", "")

        # Document
        elif "document" in raw_payload:
            message_type = "DOCUMENT"
            content = raw_payload["document"].get("title", "")

        return IncomingMessage(
            message_id=raw_payload.get("messageId", ""),
            phone=raw_payload.get("phone", ""),
            sender_name=raw_payload.get("senderName", ""),
            timestamp=raw_payload.get("momment", 0),
            message_type=message_type,
            content=content,
            button_id=button_id,
            button_text=button_text,
            reference_message_id=reference_message_id,
            raw_payload=raw_payload,
        )

    def parse_status_update(self, raw_payload: Dict[str, Any]) -> MessageStatusUpdate:
        return MessageStatusUpdate(
            message_ids=raw_payload.get("ids", []),
            phone=raw_payload.get("phone", ""),
            status=raw_payload.get("status", ""),
            timestamp=raw_payload.get("momment", 0),
            raw_payload=raw_payload,
        )

    def _send_numbered_fallback(self, phone: str, message: str, buttons: List[Dict[str, str]]) -> ProviderResponse:
        lines = [message, ""]
        for i, btn in enumerate(buttons, 1):
            lines.append(f"{i} - {btn['label']}")

        return self.send_text(phone, "\n".join(lines))
