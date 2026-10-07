"""
Verificação de posse do número de WhatsApp para o site público de agendamento
(booking-site). Substitui o SMS OTP do site de referência por um código de
6 dígitos enviado via WhatsApp (mesma integração z-api já usada pelo bot),
já que o campo do formulário sempre foi "Celular (WhatsApp)".

Fluxo:
  1. generate_and_send_code(clinic, phone) -> guarda o código no DynamoDB
     (TTL 5min) e envia por WhatsApp.
  2. confirm_code(clinic_id, phone, code) -> valida o código e devolve um
     token de sessão assinado (HMAC, 15min), escopado a (clinic_id, phone).
  3. verify_token(clinic_id, phone, token) -> valida o token nas chamadas
     que exigem posse do telefone (criar/listar/cancelar agendamento).

O token é stateless (não precisa de tabela própria): carrega
clinic_id|phone|expires_at|assinatura e é validado por comparação
constante (hmac.compare_digest).
"""
import base64
import hashlib
import hmac
import logging
import os
import random
import time

import boto3

from src.providers.zapi_provider import ZApiProvider
from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

CODE_TTL_SECONDS = 5 * 60
MAX_SEND_PER_WINDOW = 3
SEND_WINDOW_SECONDS = 15 * 60
MAX_VERIFY_ATTEMPTS = 5
TOKEN_TTL_SECONDS = 15 * 60


class RateLimitedError(Exception):
    pass


class InvalidCodeError(Exception):
    pass


class SendFailedError(Exception):
    pass


def _table():
    return boto3.resource("dynamodb").Table(os.environ["BOOKING_OTP_TABLE"])


def _item_key(clinic_id: str, phone: str) -> str:
    return f"{clinic_id}#{normalize_phone(phone)}"


def generate_and_send_code(clinic: dict, phone: str) -> None:
    """Gera um código de 6 dígitos, persiste com TTL e envia por WhatsApp.

    Levanta RateLimitedError se o (clinic_id, phone) excedeu o limite de
    envios na janela atual, ou SendFailedError se o z-api falhar.
    """
    clinic_id = clinic["clinic_id"]
    phone = normalize_phone(phone)
    table = _table()
    pk = _item_key(clinic_id, phone)
    now = int(time.time())

    item = table.get_item(Key={"clinic_phone": pk}).get("Item")
    if item and int(item.get("window_started_at", 0)) > now - SEND_WINDOW_SECONDS:
        if int(item.get("send_count", 0)) >= MAX_SEND_PER_WINDOW:
            logger.warning(f"[BookingVerification] Rate limit atingido: clinic={clinic_id}")
            raise RateLimitedError("Muitos códigos solicitados. Tente novamente em alguns minutos.")
        send_count = int(item["send_count"]) + 1
        window_started_at = int(item["window_started_at"])
    else:
        send_count = 1
        window_started_at = now

    code = f"{random.randint(0, 999999):06d}"
    table.put_item(
        Item={
            "clinic_phone": pk,
            "code": code,
            "attempts": 0,
            "verified": False,
            "created_at": now,
            "expires_at": now + CODE_TTL_SECONDS,
            "send_count": send_count,
            "window_started_at": window_started_at,
        }
    )

    provider = ZApiProvider(
        instance_id=clinic.get("zapi_instance_id") or "",
        instance_token=clinic.get("zapi_instance_token") or "",
        client_token=os.environ.get("ZAPI_CLIENT_TOKEN", ""),
    )
    message = f"Seu código de confirmação é {code}. Ele expira em 5 minutos."
    result = provider.send_text(phone, message)
    if not result.success:
        logger.error(f"[BookingVerification] Falha ao enviar código via WhatsApp: {result.error}")
        raise SendFailedError("Não foi possível enviar o código por WhatsApp. Tente novamente.")

    logger.info(f"[BookingVerification] Código enviado: clinic={clinic_id} sendCount={send_count}")


def confirm_code(clinic_id: str, phone: str, code: str) -> str:
    """Valida o código digitado e devolve um token de sessão assinado."""
    phone = normalize_phone(phone)
    table = _table()
    pk = _item_key(clinic_id, phone)
    now = int(time.time())

    item = table.get_item(Key={"clinic_phone": pk}).get("Item")
    if not item or int(item.get("expires_at", 0)) < now:
        raise InvalidCodeError("Código expirado ou inexistente. Solicite um novo.")

    if int(item.get("attempts", 0)) >= MAX_VERIFY_ATTEMPTS:
        raise InvalidCodeError("Número de tentativas excedido. Solicite um novo código.")

    if str(item.get("code")) != str(code).strip():
        table.update_item(
            Key={"clinic_phone": pk},
            UpdateExpression="SET attempts = attempts + :one",
            ExpressionAttributeValues={":one": 1},
        )
        raise InvalidCodeError("Código inválido.")

    table.update_item(
        Key={"clinic_phone": pk},
        UpdateExpression="SET verified = :v",
        ExpressionAttributeValues={":v": True},
    )

    logger.info(f"[BookingVerification] Código confirmado: clinic={clinic_id}")
    return _issue_token(clinic_id, phone)


def _issue_token(clinic_id: str, phone: str) -> str:
    expires_at = int(time.time()) + TOKEN_TTL_SECONDS
    payload = f"{clinic_id}|{normalize_phone(phone)}|{expires_at}"
    secret = os.environ.get("BOOKING_VERIFICATION_SECRET", "")
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    raw = f"{payload}|{signature}"
    return base64.urlsafe_b64encode(raw.encode()).decode()


def verify_token(clinic_id: str, phone: str, token: str) -> bool:
    """Valida um token de sessão emitido por confirm_code."""
    try:
        if not token:
            return False
        raw = base64.urlsafe_b64decode(token.encode()).decode()
        parts = raw.split("|")
        if len(parts) != 4:
            return False
        token_clinic_id, token_phone, expires_at_str, signature = parts

        payload = f"{token_clinic_id}|{token_phone}|{expires_at_str}"
        secret = os.environ.get("BOOKING_VERIFICATION_SECRET", "")
        expected_signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return False

        if token_clinic_id != clinic_id or token_phone != normalize_phone(phone):
            return False

        if int(expires_at_str) < int(time.time()):
            return False

        return True
    except Exception as e:
        logger.warning(f"[BookingVerification] Token inválido: {e}")
        return False
