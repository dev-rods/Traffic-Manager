import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.utils.booking_verification import confirm_code, InvalidCodeError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/verify/confirm
    Body: { "phone": "string", "code": "string" }

    Valida o código enviado por WhatsApp e devolve um token de sessão
    (15min, assinado) que autoriza criar/listar/cancelar agendamentos
    daquele telefone nesta clínica.
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
        code = body.get("code")
        if not phone or not code:
            return http_response(400, {"status": "ERROR", "message": "phone e code são obrigatórios"})

        token = confirm_code(clinic_id, phone, code)

        return http_response(200, {"status": "SUCCESS", "verified": True, "token": token})

    except InvalidCodeError as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao confirmar código de verificação: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
