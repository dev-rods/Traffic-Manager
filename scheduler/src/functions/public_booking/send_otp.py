import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.phone import is_valid_br_phone
from src.services.db.postgres import PostgresService
from src.utils.booking_verification import generate_and_send_code, RateLimitedError, SendFailedError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/verify/send
    Body: { "phone": "string" }

    Gera um código de 6 dígitos e envia por WhatsApp (z-api) para confirmar
    a posse do número antes de criar/listar/cancelar um agendamento.
    """
    try:
        api_key, error_response = require_booking_intake_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId não fornecido no path"})

        body = parse_body(event) or {}
        phone = body.get("phone")
        if not phone or not is_valid_br_phone(phone):
            return http_response(400, {"status": "ERROR", "message": "Celular inválido"})

        db = PostgresService()
        clinics = db.execute_query(
            "SELECT clinic_id, zapi_instance_id, zapi_instance_token FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        generate_and_send_code(clinics[0], phone)

        return http_response(200, {"status": "SUCCESS", "message": "Código enviado por WhatsApp"})

    except RateLimitedError as e:
        return http_response(429, {"status": "ERROR", "message": str(e)})
    except SendFailedError as e:
        return http_response(502, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao enviar código de verificação: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
