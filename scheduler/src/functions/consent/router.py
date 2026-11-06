# -*- coding: utf-8 -*-
"""Termo de consentimento no painel da clínica (PRD 036).

Uma Lambda, uma rota coringa (`clinics/{clinicId}/consents/{proxy+}`, ANY):
a stack está perto do limite de 500 recursos do CloudFormation.

    GET  patients/{patientId}            prontuario.ler    termos da paciente (todas as versões)
    POST patients/{patientId}/paper      agenda.escrever   assinado em papel {signedAt}
    POST appointments/{id}/waive         agenda.escrever   dispensa nesta sessão {reason, note?}
    POST {consentId}/renew               agenda.escrever   pede nova assinatura (PRD 038): o vigente vira REVOKED
    GET  {consentId}/pdf-url             prontuario.ler    URL assinada (5 min) do PDF
    GET  {consentId}/zip-url             prontuario.ler    URL assinada (5 min) do zip de auditoria

Ler o termo é ler documento da paciente, como o histórico (prontuário).
Dispensar e registrar papel são trabalho da recepção, como a baixa em
dinheiro. As permissões valem no servidor; o painel só esconde botões.
"""
import json
import logging
import re
from datetime import date

from src.services import consentimento
from src.services.db.postgres import PostgresService
from src.services.visao_do_staff import para_o_staff
from src.utils.acesso import require_acesso
from src.utils.http import extract_path_param, http_response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

UUID = r"([0-9a-fA-F-]{36})"
POR_PACIENTE = re.compile(r"^patients/{}$".format(UUID))
PAPEL = re.compile(r"^patients/{}/paper$".format(UUID))
DISPENSA = re.compile(r"^appointments/{}/waive$".format(UUID))
PDF = re.compile(r"^{}/pdf-url$".format(UUID))
ZIP = re.compile(r"^{}/zip-url$".format(UUID))
RENOVA = re.compile(r"^{}/renew$".format(UUID))


def _erro(status, mensagem):
    return http_response(status, {"status": "ERROR", "message": mensagem})


def _corpo(event):
    try:
        corpo = json.loads(event.get("body") or "{}")
    except ValueError:
        return None
    return corpo if isinstance(corpo, dict) else None


def _autor(identidade) -> str:
    return (identidade.nome if identidade and identidade.nome else "admin")


def handler(event, context):
    metodo = event.get("httpMethod", "")
    caminho = (extract_path_param(event, "proxy") or "").strip("/")
    clinic_id = extract_path_param(event, "clinicId")
    if not clinic_id:
        return _erro(404, "Rota não encontrada")

    try:
        achou = POR_PACIENTE.match(caminho)
        if metodo == "GET" and achou:
            identidade, erro = require_acesso(event, "prontuario.ler")
            if erro:
                return erro
            termos = consentimento.lista_do_paciente(PostgresService(), clinic_id, achou.group(1))
            return http_response(200, para_o_staff(identidade, {
                "status": "SUCCESS", "consents": termos, "consent_enabled": bool(consentimento.versao()),
                "term_version": consentimento.versao() or None,
            }))

        achou = PAPEL.match(caminho)
        if metodo == "POST" and achou:
            identidade, erro = require_acesso(event, "agenda.escrever")
            if erro:
                return erro
            corpo = _corpo(event)
            if corpo is None:
                return _erro(400, "Corpo inválido")
            try:
                assinado_em = date.fromisoformat(str(corpo.get("signedAt") or ""))
            except ValueError:
                return _erro(400, "signedAt deve ser uma data YYYY-MM-DD")
            termo = consentimento.registra_papel(PostgresService(), clinic_id, achou.group(1),
                                                 assinado_em, _autor(identidade))
            return http_response(201, para_o_staff(identidade, {"status": "SUCCESS", "consent": termo}))

        achou = DISPENSA.match(caminho)
        if metodo == "POST" and achou:
            identidade, erro = require_acesso(event, "agenda.escrever")
            if erro:
                return erro
            corpo = _corpo(event)
            if corpo is None:
                return _erro(400, "Corpo inválido")
            resultado = consentimento.dispensa(PostgresService(), clinic_id, achou.group(1),
                                               str(corpo.get("reason") or ""), corpo.get("note"),
                                               _autor(identidade))
            return http_response(200, para_o_staff(identidade, {"status": "SUCCESS", "appointment": resultado}))

        achou = RENOVA.match(caminho)
        if metodo == "POST" and achou:
            identidade, erro = require_acesso(event, "agenda.escrever")
            if erro:
                return erro
            termo = consentimento.renova(PostgresService(), clinic_id, achou.group(1), _autor(identidade))
            return http_response(200, para_o_staff(identidade, {"status": "SUCCESS", "consent": termo}))

        achou = PDF.match(caminho)
        if metodo == "GET" and achou:
            identidade, erro = require_acesso(event, "prontuario.ler")
            if erro:
                return erro
            return http_response(200, {"status": "SUCCESS",
                                       **consentimento.url_do_pdf(PostgresService(), clinic_id, achou.group(1))})

        achou = ZIP.match(caminho)
        if metodo == "GET" and achou:
            identidade, erro = require_acesso(event, "prontuario.ler")
            if erro:
                return erro
            return http_response(200, {"status": "SUCCESS",
                                       **consentimento.url_do_zip(PostgresService(), clinic_id, achou.group(1))})

        return _erro(404, "Rota não encontrada")

    except consentimento.NaoEncontrado:
        return _erro(404, "Não encontrado")
    except consentimento.ConsentimentoInvalido as e:
        return _erro(400, str(e))
    except Exception as e:
        logger.error(f"[Consentimento] erro em {metodo} {caminho}: {e}", exc_info=True)
        return _erro(500, "Erro interno no servidor")
