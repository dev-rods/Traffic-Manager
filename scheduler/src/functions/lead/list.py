"""
Lambda handler to list leads for a clinic.

GET /clinics/{clinicId}/leads?startDate=&endDate=&booked=true&excludeSource=whatsapp&limit=50&offset=0
"""
import logging
from datetime import datetime, date, time
from decimal import Decimal

from src.utils.http import http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.services.lead_service import LeadService
from src.services.status_da_conversa import (
    conversas_da_clinica,
    enriquece,
    sessoes_por_telefone,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

_sessions_table = None


def _get_sessions_table():
    global _sessions_table
    if _sessions_table is None:
        import os
        import boto3
        _sessions_table = boto3.resource("dynamodb").Table(
            os.environ["CONVERSATION_SESSIONS_TABLE"]
        )
    return _sessions_table


def _serialize_row(row):
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime, date, time)):
            result[key] = value.isoformat()
        elif isinstance(value, Decimal):
            result[key] = float(value)
        else:
            result[key] = value
    return result


def _data_ou_nada(valor):
    """Devolve a data em ISO, ou None. Recusa qualquer outra coisa.

    O MAX() de uma tabela vazia e NULL, e o campo pode simplesmente nao existir
    ainda. Um valor de outro tipo chegaria ate o json.dumps e derrubaria a
    listagem inteira com 500 - por causa de um numero decorativo no topo da
    tela. Aqui ele vira excecao, que o chamador trata mostrando os leads sem os
    contadores.
    """
    if valor is None:
        return None
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    raise TypeError(f"ultimo_envio deveria ser data, veio {type(valor).__name__}")


def handler(event, context):
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId e obrigatorio"})

        start_date = extract_query_param(event, "startDate")
        end_date = extract_query_param(event, "endDate")
        booked_param = extract_query_param(event, "booked")
        limit = int(extract_query_param(event, "limit") or "50")
        offset = int(extract_query_param(event, "offset") or "0")

        booked = None
        if booked_param is not None:
            booked = booked_param.lower() in ("true", "1", "yes")

        # excludeSource=whatsapp,outra - origens a tirar do resultado.
        exclude_param = extract_query_param(event, "excludeSource")
        exclude_sources = [
            s.strip() for s in (exclude_param or "").split(",") if s.strip()
        ]

        db = PostgresService()
        clinicas = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,))
        clinic = clinicas[0] if clinicas else None
        lead_service = LeadService(db)
        leads = lead_service.list_leads(
            clinic_id=clinic_id,
            start_date=start_date,
            end_date=end_date,
            booked=booked,
            exclude_sources=exclude_sources,
            limit=limit,
            offset=offset,
        )

        # Status da conversa vem das fontes, nao de coluna copiada no lead.
        # Foi exatamente um campo denormalizado que mostrou "sem contato" para
        # quem tinha conversa desenvolvida no WhatsApp.
        try:
            leads = enriquece(
                leads,
                sessoes_por_telefone(_get_sessions_table(), clinic_id,
                                     [l.get("phone") for l in leads]),
                conversas_da_clinica(db, clinic_id),
                clinic=clinic,
            )
        except Exception as e:
            # A listagem nao pode cair por causa do enriquecimento: sem ele o
            # painel mostra os leads como mostrava antes.
            logger.error(f"Falha ao enriquecer status da conversa: {e}")

        # Totais e conversao nao podem derrubar a listagem: sem eles o painel
        # mostra os leads como mostrava antes, com os contadores zerados.
        totais = {"total": len(leads), "convertidos": 0, "nao_convertidos": 0}
        conversoes = None
        try:
            # As chaves sao nomeadas uma a uma, e nao copiadas do retorno, para
            # que um retorno em formato inesperado caia no except em vez de
            # virar um dict vazio que estoura la embaixo no json.dumps - que e
            # justamente o 500 que este fallback existe para evitar.
            contagem = lead_service.contar_leads(
                clinic_id=clinic_id,
                start_date=start_date,
                end_date=end_date,
                exclude_sources=exclude_sources,
            )
            totais = {
                "total": int(contagem["total"]),
                "convertidos": int(contagem["convertidos"]),
                "nao_convertidos": int(contagem["nao_convertidos"]),
            }
            resumo = lead_service.resumo_de_conversoes(clinic_id)
            conversoes = {
                "aguardando": int(resumo["aguardando"]),
                "aguardando_cents": int(resumo["aguardando_cents"]),
                "enviadas": int(resumo["enviadas"]),
                "enviadas_cents": int(resumo["enviadas_cents"]),
                "retratadas": int(resumo["retratadas"]),
                "canceladas": int(resumo["canceladas"]),
                "ultimo_envio": _data_ou_nada(resumo["ultimo_envio"]),
            }
            estados = lead_service.conversoes_por_lead(
                clinic_id, [l.get("id") for l in leads])
            for l in leads:
                l["conversion_status"] = estados.get(str(l.get("id")))
        except Exception as e:
            logger.error(f"Falha ao montar totais/conversoes dos leads: {e}")

        return http_response(200, {
            "status": "SUCCESS",
            "clinicId": clinic_id,
            "leads": [_serialize_row(r) for r in leads],
            # `total` e o conjunto INTEIRO, nao a pagina. Era len(leads), e o
            # painel mostrava "50 leads" numa clinica com 77.
            "total": totais["total"],
            "totals": totais,
            "conversions": _serialize_row(conversoes) if conversoes else None,
        })

    except Exception as e:
        logger.error(f"Erro ao listar leads: {e}")
        return http_response(500, {"status": "ERROR", "message": "Erro interno no servidor", "error": str(e)})
