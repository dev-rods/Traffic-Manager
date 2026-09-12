"""
Router unico para os endpoints publicos de agendamento (public_booking/*).

A stack do scheduler ja tem ~65 Lambdas e bateu no limite de 500 recursos por
stack do CloudFormation (cada função Lambda custa ~7-8 recursos: Function,
Version, Role, LogGroup, Permission, Method, Resource). Em vez de 1 função por
endpoint (7 novas = ~35+ recursos), esta única Lambda atende as 7 rotas
públicas via `event['resource']`, delegando para os handlers originais — que
continuam intactos, testáveis e importáveis individualmente.
"""
import logging

from src.functions.public_booking import (
    availability,
    bootstrap,
    cancel_appointment,
    confirm_otp,
    create_appointment,
    list_appointments,
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
    ("POST", "public/clinics/{clinicId}/appointments"): create_appointment.handler,
    ("GET", "public/clinics/{clinicId}/my-appointments"): list_appointments.handler,
    ("POST", "public/clinics/{clinicId}/appointments/{appointmentId}/cancel"): cancel_appointment.handler,
}


def handler(event, context):
    method = event.get("httpMethod", "")
    resource = (event.get("resource") or "").lstrip("/")

    route_handler = ROUTES.get((method, resource))
    if not route_handler:
        logger.warning(f"[PublicBookingRouter] Rota nao mapeada: {method} {resource}")
        return http_response(404, {"status": "ERROR", "message": "Rota não encontrada"})

    return route_handler(event, context)
