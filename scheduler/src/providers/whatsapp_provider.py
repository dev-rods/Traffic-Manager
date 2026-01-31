from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ProviderResponse:
    success: bool
    provider_message_id: str = ""
    raw_response: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


@dataclass
class IncomingMessage:
    message_id: str
    phone: str
    sender_name: str
    timestamp: int
    message_type: str  # TEXT, BUTTON_RESPONSE, LIST_RESPONSE, IMAGE, AUDIO, VIDEO, DOCUMENT
    content: str = ""
    button_id: Optional[str] = None
    button_text: Optional[str] = None
    reference_message_id: Optional[str] = None
    raw_payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MessageStatusUpdate:
    message_ids: List[str]
    phone: str
    status: str  # SENT, RECEIVED, READ, PLAYED
    timestamp: int
    raw_payload: Dict[str, Any] = field(default_factory=dict)


class WhatsAppProvider(ABC):

    @abstractmethod
    def send_text(self, phone: str, message: str) -> ProviderResponse:
        ...

    @abstractmethod
    def send_buttons(self, phone: str, message: str, buttons: List[Dict[str, str]]) -> ProviderResponse:
        ...

    @abstractmethod
    def send_list(self, phone: str, message: str, button_text: str, sections: List[Dict]) -> ProviderResponse:
        ...

    @abstractmethod
    def parse_incoming_message(self, raw_payload: Dict[str, Any]) -> IncomingMessage:
        ...

    @abstractmethod
    def parse_status_update(self, raw_payload: Dict[str, Any]) -> MessageStatusUpdate:
        ...


def get_provider(clinic: Dict[str, Any]) -> WhatsAppProvider:
    from src.providers.zapi_provider import ZApiProvider
    import os

    return ZApiProvider(
        instance_id=clinic.get("zapi_instance_id", ""),
        instance_token=clinic.get("zapi_instance_token", ""),
        client_token=os.environ.get("ZAPI_CLIENT_TOKEN", ""),
    )
