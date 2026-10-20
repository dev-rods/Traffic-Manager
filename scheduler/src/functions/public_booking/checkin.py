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

A baixa em dinheiro é da recepção e mora no painel (`functions/caixa`), não
aqui. Tudo exige a chave do booking-site E o token do código de WhatsApp (o mesmo de "Meus agendamentos"): sem ele, quem digitasse
o número de outra pessoa veria e pagaria a sessão dela.
"""
import logging
import re

from src.providers.payment_provider import ErroDoProvedor, PagamentoIndisponivel, provedor_ativo
from src.services import checkin
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
)


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
        phone = body.get("phone") if metodo == "POST" else extract_query_param(event, "phone")
        token = body.get("token") if metodo == "POST" else extract_query_param(event, "token")
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
    except checkin.CheckinInvalido as e:
        return _erro(400, str(e))
    except PagamentoIndisponivel:
        logger.error(f"[Checkin] sem provedor de pagamento configurado ({clinic_id})")
        return _erro(503, "Pagamento pelo tablet indisponível no momento. Pague na recepção.")
    except ErroDoProvedor as e:
        logger.error(f"[Checkin] provedor recusou ({clinic_id} {nome}): {e}")
        return _erro(502, "Não conseguimos gerar a cobrança agora. Tente de novo ou pague na recepção.")
    except Exception as e:
        logger.error(f"[Checkin] erro em {metodo} {caminho}: {e}", exc_info=True)
        return _erro(500, "Erro interno no servidor")
