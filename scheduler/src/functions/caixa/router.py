# -*- coding: utf-8 -*-
"""Caixa no painel da clínica (PRD 026, fase 2).

Uma Lambda, uma rota coringa (`clinics/{clinicId}/caixa/{proxy+}`, ANY): a
stack está perto do limite de 500 recursos do CloudFormation.

    GET  resumo?date_from&date_to     admin           previsto, recebido, pendências
    POST pagamentos/{id}/dinheiro     agenda.escrever a recepção recebeu em dinheiro
    POST pagamentos/{id}/estorno      admin           devolve pagamento de sessão cancelada

A baixa em dinheiro é da recepção (é ela quem recebe a nota), por isso usa a
permissão de escrever na agenda e não a chave de admin. O resumo é dinheiro
da clínica inteira: só admin, como os relatórios.
"""
import logging
import re

from src.providers.payment_provider import ErroDoProvedor, PagamentoIndisponivel, provedor_ativo
from src.services import caixa, checkin
from src.services.db.postgres import PostgresService
from src.services.visao_do_staff import para_o_staff
from src.utils.acesso import require_acesso
from src.utils.http import extract_path_param, extract_query_param, http_response, require_api_key

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

DINHEIRO = re.compile(r"^pagamentos/([0-9a-fA-F-]{36})/dinheiro$")
ESTORNO = re.compile(r"^pagamentos/([0-9a-fA-F-]{36})/estorno$")


def _erro(status, mensagem):
    return http_response(status, {"status": "ERROR", "message": mensagem})


def handler(event, context):
    metodo = event.get("httpMethod", "")
    caminho = (extract_path_param(event, "proxy") or "").strip("/")
    clinic_id = extract_path_param(event, "clinicId")
    if not clinic_id:
        return _erro(404, "Rota não encontrada")

    falha_do_provedor = "O Asaas não confirmou a baixa. Tente de novo."
    try:
        if metodo == "GET" and caminho == "resumo":
            _, erro = require_api_key(event)
            if erro:
                return erro
            dados = caixa.resumo(PostgresService(), clinic_id,
                                 extract_query_param(event, "date_from"),
                                 extract_query_param(event, "date_to"))
            return http_response(200, {"status": "SUCCESS", **dados})

        achou = DINHEIRO.match(caminho)
        if metodo == "POST" and achou:
            identidade, erro = require_acesso(event, "agenda.escrever")
            if erro:
                return erro
            pagamento = checkin.marca_recebido_em_dinheiro(
                PostgresService(), provedor_ativo(), clinic_id, achou.group(1))
            return http_response(200, para_o_staff(identidade, {"status": "SUCCESS", "payment": pagamento}))

        achou = ESTORNO.match(caminho)
        if metodo == "POST" and achou:
            # Dinheiro saindo da clínica: só admin (PRD 028, M7).
            _, erro = require_api_key(event)
            if erro:
                return erro
            falha_do_provedor = "O Asaas não aceitou o estorno. Tente de novo."
            pagamento = checkin.estorna(PostgresService(), provedor_ativo(), clinic_id, achou.group(1))
            return http_response(200, {"status": "SUCCESS", "payment": pagamento})

        return _erro(404, "Rota não encontrada")

    except caixa.PeriodoInvalido as e:
        return _erro(400, str(e))
    except checkin.NaoEncontrado:
        return _erro(404, "Pagamento não encontrado")
    except checkin.CheckinInvalido as e:
        return _erro(409, str(e))
    except PagamentoIndisponivel:
        return _erro(503, "Pagamentos indisponíveis neste ambiente")
    except ErroDoProvedor as e:
        logger.error(f"[Caixa] provedor recusou {metodo} {caminho} ({clinic_id}): {e}")
        return _erro(502, falha_do_provedor)
    except Exception as e:
        logger.error(f"[Caixa] erro em {metodo} {caminho}: {e}", exc_info=True)
        return _erro(500, "Erro interno no servidor")
