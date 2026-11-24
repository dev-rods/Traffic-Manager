import logging

from src.utils.http import http_response, require_booking_intake_api_key, extract_path_param, parse_body
from src.services import carrinho
from src.services.cadastro_pelo_site import primeiro_nome
from src.services.db.postgres import PostgresService
from src.utils.booking_verification import SESSAO, TTL_POR_ESCOPO, confirm_code, InvalidCodeError
from src.utils.phone import normalize_phone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/verify/confirm
    Body: { "phone": "string", "code": "string", "scope"?: "sessao" | "documentos" }

    Valida o código enviado por WhatsApp e devolve um token de sessão
    assinado que autoriza criar/listar/cancelar agendamentos daquele
    telefone nesta clínica (30 min desde o PRD 061; eram 15). No escopo de
    sessão devolve também `paciente` ({nome, faltam} ou null): o site
    pergunta "Olá, {nome}, é você?" e pede só o que falta (PRD 061). Com `scope: "documentos"` (PRD 048) o
    token dura 2 h e só serve à ficha e à assinatura no check-in.
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

        scope = body.get("scope") or SESSAO
        if scope not in TTL_POR_ESCOPO:
            return http_response(400, {"status": "ERROR", "message": "scope inválido"})

        token = confirm_code(clinic_id, phone, code, scope)

        resposta = {"status": "SUCCESS", "verified": True, "token": token}
        if scope == SESSAO:
            # PRD 061: so DEPOIS do codigo o site fica sabendo quem e o dono do
            # numero (primeiro nome e o que falta no cadastro). Antes dele a
            # cotacao publica nunca devolve nome. Escopo documentos nao precisa.
            paciente = carrinho.paciente_do_telefone(PostgresService(), clinic_id, normalize_phone(str(phone)))
            resposta["paciente"] = _paciente_para_o_site(paciente)

        return http_response(200, resposta)

    except InvalidCodeError as e:
        return http_response(400, {"status": "ERROR", "message": str(e)})
    except Exception as e:
        logger.error(f"Erro ao confirmar código de verificação: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})


def _paciente_para_o_site(paciente):
    if not paciente:
        return None
    return {"nome": primeiro_nome(paciente.get("name")),
            "faltam": carrinho.cadastro_para_o_site(paciente)["faltam"]}
