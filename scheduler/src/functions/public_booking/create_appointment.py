import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService, ConflictError, NotFoundError
from src.services.template_service import TemplateService
from src.providers.zapi_provider import ZApiProvider
import os

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result


def _format_date_br(iso_date: str) -> str:
    try:
        y, m, d = iso_date.split("-")
        return f"{d}/{m}/{y}"
    except Exception:
        return iso_date


def _format_price_brl(price_cents):
    if not price_cents:
        return "Consultar"
    return f"R$ {price_cents / 100:.2f}".replace(".", ",")


def _send_confirmation_whatsapp(db: PostgresService, clinic: dict, phone: str, appointment: dict, duration_minutes) -> None:
    """
    Envia a mesma confirmação que o bot de WhatsApp manda ao fechar um
    agendamento (template "BOOKED", customizável por clínica). Falha aqui
    nunca derruba a criação do agendamento — ele já foi persistido.
    """
    try:
        hours, mins = divmod(int(duration_minutes or 0), 60)
        duration_str = f"{hours}h{mins:02d}min" if hours else f"{duration_minutes}min"

        variables = {
            "date": _format_date_br(str(appointment.get("appointment_date", ""))[:10]),
            "time": str(appointment.get("start_time", ""))[:5],
            "duration": duration_str,
            "price": _format_price_brl(appointment.get("final_price_cents")),
        }

        template_service = TemplateService(db)
        content = template_service.get_and_render(clinic["clinic_id"], "BOOKED", variables)

        provider = ZApiProvider(
            instance_id=clinic.get("zapi_instance_id") or "",
            instance_token=clinic.get("zapi_instance_token") or "",
            client_token=os.environ.get("ZAPI_CLIENT_TOKEN", ""),
        )
        result = provider.send_text(phone, content)
        if not result.success:
            logger.error(f"[PublicBooking] Falha ao enviar confirmação por WhatsApp: {result.error}")
    except Exception as e:
        logger.error(f"[PublicBooking] Erro ao montar/enviar confirmação por WhatsApp: {e}", exc_info=True)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/appointments

    Body:
    {
        "phone": "string",
        "fullName": "string",
        "serviceIds": ["uuid", ...], // carrinho — 1+ serviços
        "date": "YYYY-MM-DD",
        "time": "HH:MM",
        "professionalId": "uuid",     // opcional
        "serviceAreaPairs": [          // opcional — quando os serviços têm áreas
            {"serviceId": "uuid", "areaId": "uuid"}
        ]
    }

    Sem verificação por código: o agendamento é criado direto e a confirmação
    chega pelo próprio WhatsApp (mesmo template "BOOKED" do bot) — a posse do
    número não precisa ser confirmada antes de agendar, só de ver/cancelar
    (endpoints /my-appointments e /appointments/{id}/cancel continuam exigindo
    o token de /verify/confirm).
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        body = parse_body(event)
        if not body:
            return http_response(400, {"status": "ERROR", "message": "Corpo da requisição vazio ou inválido"})

        phone = body.get("phone")
        service_ids = body.get("serviceIds")
        appt_date = body.get("date")
        appt_time = body.get("time")
        full_name = body.get("fullName")

        if not all([phone, service_ids, appt_date, appt_time, full_name]):
            return http_response(400, {
                "status": "ERROR",
                "message": "Campos obrigatorios: phone, serviceIds, date, time, fullName",
            })

        raw_pairs = body.get("serviceAreaPairs")
        service_area_pairs = None
        if raw_pairs and isinstance(raw_pairs, list):
            service_area_pairs = [
                {"service_id": p.get("serviceId"), "area_id": p.get("areaId")}
                for p in raw_pairs
                if p.get("serviceId") and p.get("areaId")
            ]

        db = PostgresService()

        clinics = db.execute_query(
            "SELECT clinic_id, zapi_instance_id, zapi_instance_token FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        service = AppointmentService(db)

        result = service.create_appointment(
            clinic_id=clinic_id,
            phone=phone,
            service_id=service_ids[0],
            date=appt_date,
            time=appt_time,
            professional_id=body.get("professionalId"),
            service_ids=service_ids,
            service_area_pairs=service_area_pairs if service_area_pairs else None,
            full_name=full_name,
        )

        _send_confirmation_whatsapp(db, clinics[0], phone, result, result.get("total_duration_minutes"))

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Agendamento criado com sucesso",
            "appointment": _serialize_row(result),
        })

    except ConflictError as e:
        return http_response(409, {"status": "ERROR", "message": str(e)})
    except NotFoundError as e:
        return http_response(404, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao criar agendamento público: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
