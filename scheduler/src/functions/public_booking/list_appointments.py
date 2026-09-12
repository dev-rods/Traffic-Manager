import logging
from datetime import datetime, date, time

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, extract_query_param
from src.utils.booking_verification import verify_token
from src.services.db.postgres import PostgresService
from src.services.appointment_service import AppointmentService

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


def handler(event, context):
    """
    GET /public/clinics/{clinicId}/my-appointments?phone=&token=

    Lista os agendamentos futuros confirmados do telefone (tela "Meus
    agendamentos"). Exige token emitido por /verify/confirm — o site de
    referência não confirmava posse do número antes de listar; aqui exigimos
    para não vazar a agenda de terceiros para quem digitar o número alheio.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        phone = extract_query_param(event, "phone")
        token = extract_query_param(event, "token")
        if not phone or not token:
            return http_response(400, {"status": "ERROR", "message": "phone e token são obrigatórios"})

        if not verify_token(clinic_id, phone, token):
            return http_response(401, {"status": "ERROR", "message": "Verificação por WhatsApp expirada. Confirme o código novamente."})

        db = PostgresService()
        service = AppointmentService(db)
        appointments = service.get_active_appointments_by_phone(clinic_id, phone)

        return http_response(200, {
            "status": "SUCCESS",
            "appointments": [_serialize_row(r) for r in appointments],
        })

    except Exception as e:
        logger.error(f"Erro ao listar agendamentos públicos: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
