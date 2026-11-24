# -*- coding: utf-8 -*-
import logging

from src.functions.public_booking.create_appointment import (
    CADASTRO_INCOMPLETO, CPF_EM_USO, MENSAGEM_CADASTRO, MENSAGEM_TOKEN, _cadastro_invalido,
)
from src.services import carrinho
from src.services.cadastro_pelo_site import completa_paciente, conflito_de_cpf, primeiro_nome
from src.services.db.postgres import PostgresService
from src.utils.booking_verification import verify_token
from src.utils.cadastro import cpf_valido, normaliza_cpf, normaliza_data_nascimento, normaliza_email
from src.utils.http import extract_path_param, http_response, parse_body, require_booking_intake_api_key
from src.utils.phone import is_valid_phone, normalize_phone

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    POST /public/clinics/{clinicId}/cadastro  (PRD 061)

    Body:
    {
        "phone": "string",
        "token": "string",          // de /verify/confirm, escopo sessao
        "fullName": "string",       // obrigatorio para celular sem ficha
        "cpf": "000.000.000-00",    // os que faltam no cadastro deste celular
        "birthDate": "YYYY-MM-DD",
        "email": "a@b.com"
    }

    Cria ou completa a ficha do paciente SEM agendamento: o site chama assim
    que a pessoa confirma o codigo, antes de escolher data. Quem abandona
    depois disso fica cadastrado. O preenchimento e o mesmo da criacao
    (`cadastro_pelo_site.completa_paciente`): o que a clinica ja tem nao e
    tocado, so o vazio e preenchido.

    Sem token valido: 401. Faltando campo exigido: 400 `CADASTRO_INCOMPLETO`
    com `faltam`. CPF de outro paciente: 409 `CPF_EM_USO`. Resposta so com o
    primeiro nome e o que ainda falta (nada de CPF, nascimento, e-mail ou id).
    Chamar de novo com os mesmos dados nao muda nada; chamar so com phone e
    token devolve o estado da ficha sem gravar.
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
        if not phone or not is_valid_phone(str(phone)):
            return http_response(400, {"status": "ERROR", "message": "Telefone inválido"})
        phone = normalize_phone(str(phone))

        token = body.get("token")
        if not token or not verify_token(clinic_id, phone, str(token)):
            return http_response(401, {"status": "ERROR", "message": MENSAGEM_TOKEN})

        cpf = normaliza_cpf(body.get("cpf"))
        if cpf is False or (cpf and not cpf_valido(cpf)):
            return _cadastro_invalido("cpf", "CPF inválido")
        birth_date = normaliza_data_nascimento(body.get("birthDate"))
        if birth_date is False:
            return _cadastro_invalido("birth_date", "Data de nascimento inválida")
        email = normaliza_email(body.get("email"))
        if email is False:
            return _cadastro_invalido("email", "E-mail inválido")
        nome = (body.get("fullName") or "").strip() or None

        db = PostgresService()
        clinics = db.execute_query(
            "SELECT clinic_id FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,),
        )
        if not clinics:
            return http_response(404, {"status": "ERROR", "message": "Salão não encontrado"})

        paciente = carrinho.paciente_do_telefone(db, clinic_id, phone)
        so_consulta = not any([nome, cpf, birth_date, email])
        if so_consulta:
            # O site ja tem token guardado e so quer saber quem e: nada a gravar.
            return http_response(200, {"status": "SUCCESS", "paciente": _resposta(paciente)})

        if paciente is None and not nome:
            return http_response(400, {"status": "ERROR", "code": CADASTRO_INCOMPLETO,
                                       "faltam": ["name"], "message": "Digite seu nome completo"})

        informados = {"cpf": cpf, "birth_date": birth_date, "email": email}
        faltam = [c for c in carrinho.cadastro_para_o_site(paciente)["faltam"] if not informados.get(c)]
        if faltam:
            return http_response(400, {"status": "ERROR", "code": CADASTRO_INCOMPLETO,
                                       "faltam": faltam, "message": MENSAGEM_CADASTRO})

        if conflito_de_cpf(db, clinic_id, cpf, paciente["id"] if paciente else None):
            return http_response(409, {
                "status": "ERROR", "code": CPF_EM_USO,
                "message": "Este CPF já está cadastrado com outro celular. Fale com a clínica.",
            })

        ficha = completa_paciente(db, clinic_id, phone, nome, cpf, birth_date, email)
        logger.info(
            f"[PublicBooking][cadastro] {clinic_id} tel=***{phone[-4:]} novo={paciente is None} "
            f"completou={[c for c, v in informados.items() if v]}"
        )
        return http_response(200, {"status": "SUCCESS", "paciente": _resposta(ficha)})

    except Exception as e:
        logger.error(f"Erro no cadastro pelo site: {str(e)}", exc_info=True)
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor"})


def _resposta(paciente):
    """O que o site pode saber da ficha: primeiro nome e o que falta. Ou None."""
    if not paciente:
        return None
    return {"nome": primeiro_nome(paciente.get("name")),
            "faltam": carrinho.cadastro_para_o_site(paciente)["faltam"]}
