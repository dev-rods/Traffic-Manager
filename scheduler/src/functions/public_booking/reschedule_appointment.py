# -*- coding: utf-8 -*-
"""Remarcar pelo site (PRD 035).

Até aqui "Meus agendamentos" só cancelava, e quem queria outro dia cancelava
e marcava de novo: 81% dos cancelamentos vindos do site eram remarcações.
Este endpoint usa o mesmo `reschedule_appointment` do painel e do bot: o
registro é o mesmo, só muda a data. Nenhum CANCELLED nasce.

Mesmo contrato de segurança do cancelar: código OTP válido e o agendamento
precisa ser deste telefone.
"""
import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.booking_verification import verify_token
from src.utils.phone import variantes_do_numero
from src.services import relogio
from src.services.db.postgres import PostgresService
from src.services.appointment_service import (
    AppointmentService, ConflictError, NotFoundError, OptimisticLockError)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

MENSAGEM_CONFLITO = "Esse horário acabou de ser ocupado. Escolha outro."


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _le_data_e_hora(body):
    """("YYYY-MM-DD", "HH:MM") ou (None, None) se ilegível."""
    try:
        dia = datetime.strptime(str(body.get("date") or ""), "%Y-%m-%d").date()
        hora = datetime.strptime(str(body.get("time") or "")[:5], "%H:%M").time()
    except ValueError:
        return None, None
    return dia.isoformat(), hora.strftime("%H:%M")


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/appointments/{appointmentId}/reschedule
    Body: { "phone", "token", "date": "YYYY-MM-DD", "time": "HH:MM" }
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        appointment_id = extract_path_param(event, "appointmentId")
        if not clinic_id or not appointment_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e appointmentId são obrigatórios no path"})

        body = parse_body(event) or {}
        phone = body.get("phone")
        token = body.get("token")
        if not phone or not token:
            return http_response(400, {"status": "ERROR", "message": "phone e token são obrigatórios"})

        nova_data, nova_hora = _le_data_e_hora(body)
        if not nova_data:
            return http_response(400, {"status": "ERROR", "message": "date (YYYY-MM-DD) e time (HH:MM) são obrigatórios"})

        if not verify_token(clinic_id, phone, token):
            return http_response(401, {"status": "ERROR", "message": "Verificação por WhatsApp expirada. Confirme o código novamente."})

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT timezone FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})
        agora = relogio.agora_na_clinica(clinics[0].get("timezone"))
        if datetime.fromisoformat(f"{nova_data}T{nova_hora}") < agora.replace(tzinfo=None):
            return http_response(400, {"status": "ERROR", "message": "Escolha um horário futuro."})

        # As mesmas variantes da listagem: o que "Meus agendamentos" mostra,
        # a pessoa consegue remarcar.
        owned = db.execute_query(
            """
            SELECT a.id FROM scheduler.appointments a
            JOIN scheduler.patients p ON p.id = a.patient_id
            WHERE a.id = %s::uuid AND a.clinic_id = %s AND p.phone = ANY(%s) AND a.status = 'CONFIRMED'
            """,
            (appointment_id, clinic_id, sorted(variantes_do_numero(phone))),
        )
        if not owned:
            return http_response(404, {"status": "ERROR", "message": "Agendamento não encontrado para este telefone"})

        service = AppointmentService.completo(db)
        result = service.reschedule_appointment(appointment_id, nova_data, nova_hora)

        return http_response(200, {
            "status": "SUCCESS",
            "message": "Agendamento remarcado com sucesso",
            "appointment": _serialize_row(result),
        })

    except ConflictError:
        return http_response(409, {"status": "ERROR", "message": MENSAGEM_CONFLITO})
    except OptimisticLockError:
        return http_response(409, {"status": "ERROR", "message": MENSAGEM_CONFLITO})
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao remarcar agendamento público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
