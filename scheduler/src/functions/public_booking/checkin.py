# -*- coding: utf-8 -*-
"""Check-in de autoatendimento no iPad da recepção (PRD 026).

Uma rota coringa (`public/clinics/{clinicId}/checkin/{proxy+}`, ANY) atende
todas as sub-rotas abaixo. A stack do scheduler está em 438 de 500 recursos
do CloudFormation e cada rota HTTP custa ~4; a coringa custa ~4 no total.

    GET  appointments                     ?phone&token
    POST appointments/{id}/confirm        {phone, token}
    POST appointments/{id}/payments       {phone, token, method, cpf?}
    GET  payments/{id}                    ?phone&token
    POST payments/{id}/simulate           {phone, token}       só provedor simulado (dev)
    POST appointments/{id}/anamnesis      {phone, token, screen, answers}   ficha (PRD 038)
    POST appointments/{id}/consent        {phone, token, fullName, cpf?, birthDate, email,
                                           imageAuthorized, guardian?}   termo (PRD 036)
    GET  consents/{id}                    ?phone&token
    POST consents/{id}/simulate           {phone, token}       só provedor simulado (dev)

A baixa em dinheiro é da recepção e mora no painel (`functions/caixa`), não
aqui. Tudo exige a chave do booking-site E o token do código de WhatsApp (o mesmo de "Meus agendamentos"): sem ele, quem digitasse
o número de outra pessoa veria e pagaria a sessão dela.
"""
import logging
import re

from src.providers.payment_provider import ErroDoProvedor, PagamentoIndisponivel, provedor_ativo
from src.providers.signature_provider import (
    AssinaturaIndisponivel, ErroDoProvedor as ErroDeAssinatura, provedor_ativo as provedor_de_assinatura,
)
from src.services import checkin, consentimento
from src.services.db.postgres import PostgresService
from src.utils.booking_verification import verify_token
from src.utils.http import (
    extract_path_param, extract_query_param, http_response, parse_body,
    require_booking_intake_api_key,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

UUID = r"[0-9a-fA-F-]{36}"
ROTAS = (
    ("GET", re.compile(r"^appointments$"), "lista"),
    ("POST", re.compile(rf"^appointments/({UUID})/confirm$"), "confirma"),
    ("POST", re.compile(rf"^appointments/({UUID})/payments$"), "cobra"),
    ("GET", re.compile(rf"^payments/({UUID})$"), "status"),
    ("POST", re.compile(rf"^payments/({UUID})/simulate$"), "simula"),
    ("POST", re.compile(rf"^appointments/({UUID})/anamnesis$"), "anamnesis"),
    ("POST", re.compile(rf"^appointments/({UUID})/consent$"), "consent"),
    ("GET", re.compile(rf"^consents/({UUID})$"), "consent_status"),
    ("POST", re.compile(rf"^consents/({UUID})/simulate$"), "consent_simula"),
)
CONSENTIMENTO = ("anamnesis", "consent", "consent_status", "consent_simula")


def _rota(metodo, caminho):
    for m, padrao, nome in ROTAS:
        achou = padrao.match(caminho)
        if m == metodo and achou:
            return nome, (achou.group(1) if achou.groups() else None)
    return None, None


def _erro(status, mensagem):
    return http_response(status, {"status": "ERROR", "message": mensagem})


def handler(event, context):
    metodo = event.get("httpMethod", "")
    caminho = (extract_path_param(event, "proxy") or "").strip("/")
    clinic_id = extract_path_param(event, "clinicId")
    nome, recurso_id = _rota(metodo, caminho)
    if not nome or not clinic_id:
        return _erro(404, "Rota não encontrada")

    body = parse_body(event) or {}

    try:
        db = PostgresService()

        _, erro = require_booking_intake_api_key(event, body)
        if erro:
            return erro
        phone = body.get("phone") if metodo in ("POST", "PUT") else extract_query_param(event, "phone")
        token = body.get("token") if metodo in ("POST", "PUT") else extract_query_param(event, "token")
        if not phone or not token:
            return _erro(400, "phone e token são obrigatórios")
        if not verify_token(clinic_id, phone, token):
            return _erro(401, "Sua sessão expirou. Confirme o código de novo.")

        if nome == "lista":
            return http_response(200, {
                "status": "SUCCESS",
                "appointments": checkin.agendamentos_do_numero(db, clinic_id, phone),
            })
        if nome == "confirma":
            return http_response(200, {"status": "SUCCESS", **checkin.confirma(db, clinic_id, phone, recurso_id)})

        if nome in CONSENTIMENTO:
            # O provedor de assinatura só é exigido aqui: lista e confirma não
            # dependem de chave da ClickSign.
            assinatura = provedor_de_assinatura()
            if nome == "anamnesis":
                return http_response(200, {"status": "SUCCESS", **consentimento.guarda_respostas(
                    db, assinatura, clinic_id, phone, recurso_id, body.get("screen"), body.get("answers"))})
            if nome == "consent":
                return http_response(201, {"status": "SUCCESS", **consentimento.inicia(
                    db, assinatura, clinic_id, phone, recurso_id, body)})
            if nome == "consent_status":
                return http_response(200, {"status": "SUCCESS", **consentimento.status(
                    db, assinatura, clinic_id, phone, recurso_id)})
            return http_response(200, {"status": "SUCCESS", **consentimento.simula(
                db, assinatura, clinic_id, phone, recurso_id)})

        provider = provedor_ativo()
        if nome == "cobra":
            pagamento = checkin.cobra(db, provider, clinic_id, phone, recurso_id,
                                      body.get("method"), body.get("cpf"))
            return http_response(201, {"status": "SUCCESS", "payment": pagamento})
        if nome == "status":
            return http_response(200, {"status": "SUCCESS",
                                       "payment": checkin.status(db, provider, clinic_id, phone, recurso_id)})
        if nome == "simula":
            return http_response(200, {"status": "SUCCESS",
                                       "payment": checkin.simula_pagamento(db, provider, clinic_id, phone, recurso_id)})
        return _erro(404, "Rota não encontrada")

    except checkin.NaoEncontrado:
        return _erro(404, "Agendamento não encontrado")
    except consentimento.NaoEncontrado:
        return _erro(404, "Termo não encontrado")
    except consentimento.AnamneseInvalida as e:
        return http_response(400, {"status": "ERROR", "message": str(e), "field": e.campo})
    except (checkin.CheckinInvalido, consentimento.ConsentimentoInvalido) as e:
        return _erro(400, str(e))
    except AssinaturaIndisponivel:
        logger.error(f"[Checkin] sem provedor de assinatura configurado ({clinic_id})")
        return _erro(503, "Assinatura indisponível no momento. Chame a recepção.")
    except ErroDeAssinatura as e:
        logger.error(f"[Checkin] ClickSign recusou ({clinic_id} {nome}): {e}")
        return _erro(502, "Não conseguimos preparar o termo agora. Tente de novo ou chame a recepção.")
    except PagamentoIndisponivel:
        logger.error(f"[Checkin] sem provedor de pagamento configurado ({clinic_id})")
        return _erro(503, "Pagamento pelo tablet indisponível no momento. Pague na recepção.")
    except ErroDoProvedor as e:
        logger.error(f"[Checkin] provedor recusou ({clinic_id} {nome}): {e}")
        if nome == "simula":
            return _erro(502, "O Asaas não confirmou o pagamento de teste. Tente de novo.")
        return _erro(502, "Não conseguimos gerar a cobrança agora. Tente de novo ou pague na recepção.")
    except Exception as e:
        logger.error(f"[Checkin] erro em {metodo} {caminho}: {e}", exc_info=True)
        return _erro(500, "Erro interno no servidor")
