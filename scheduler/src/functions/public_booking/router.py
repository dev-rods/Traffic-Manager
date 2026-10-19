"""
Router unico para os endpoints publicos de agendamento (public_booking/*).

A stack do scheduler ja tem ~65 Lambdas e bateu no limite de 500 recursos por
stack do CloudFormation (cada função Lambda custa ~7-8 recursos: Function,
Version, Role, LogGroup, Permission, Method, Resource). Em vez de 1 função por
endpoint (~7 recursos cada), esta única Lambda atende todas as rotas
públicas via `event['resource']`, delegando para os handlers originais — que
continuam intactos, testáveis e importáveis individualmente.
"""
import logging

from src.functions.public_booking import (
    asaas_webhook,
    availability,
    bootstrap,
    cancel_appointment,
    checkin,
    confirm_otp,
    create_appointment,
    list_appointments,
    quote,
    resolve_domain,
    send_otp,
    slots,
)
from src.utils.http import http_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ROUTES = {
    ("GET", "public/clinics/{clinicId}/bootstrap"): bootstrap.handler,
    ("GET", "public/clinics/{clinicId}/available-slots"): slots.handler,
    ("GET", "public/clinics/{clinicId}/availability"): availability.handler,
    ("POST", "public/clinics/{clinicId}/verify/send"): send_otp.handler,
    ("POST", "public/clinics/{clinicId}/verify/confirm"): confirm_otp.handler,
    ("POST", "public/clinics/{clinicId}/quote"): quote.handler,
    ("POST", "public/clinics/{clinicId}/appointments"): create_appointment.handler,
    ("GET", "public/clinics/{clinicId}/my-appointments"): list_appointments.handler,
    ("POST", "public/clinics/{clinicId}/appointments/{appointmentId}/cancel"): cancel_appointment.handler,
    ("GET", "public/resolve-domain"): resolve_domain.handler,
    # Check-in do iPad (PRD 026): uma rota coringa para todas as sub-rotas,
    # que `checkin.handler` distingue pelo `proxy`.
    **{(m, "public/clinics/{clinicId}/checkin/{proxy+}"): checkin.handler for m in ("GET", "POST")},
    ("POST", "public/asaas/webhook"): asaas_webhook.handler,
}


def handler(event, context):
    method = event.get("httpMethod", "")
    resource = (event.get("resource") or "").lstrip("/")

    route_handler = ROUTES.get((method, resource))
    if not route_handler:
        logger.warning(f"[PublicBookingRouter] Rota nao mapeada: {method} {resource}")
        return http_response(404, {"status": "ERROR", "message": "Rota não encontrada"})

    return route_handler(event, context)
