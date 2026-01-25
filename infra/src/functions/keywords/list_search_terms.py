"""
Lambda handler para listar termos de pesquisa com metricas.

Endpoint: GET /keywords/search-terms
Query Params:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios
    - minImpressions (optional): Minimo de impressoes (default: 10)
    - days (optional): Periodo em dias (default: 30)
    - limit (optional): Limite de resultados (default: 500)
"""
import json
import logging
import uuid

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response, extract_query_param

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda handler para listar termos de pesquisa.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    logger.info(f"[traceId: {trace_id}] Iniciando ListSearchTerms")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    campaign_id = extract_query_param(event, "campaignId")
    ad_group_id = extract_query_param(event, "adGroupId")
    min_impressions_str = extract_query_param(event, "minImpressions")
    days_str = extract_query_param(event, "days")
    limit_str = extract_query_param(event, "limit")

    # Validar campos obrigatorios
    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio"
        })

    if not campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "campaignId e obrigatorio"
        })

    # Parse parametros opcionais
    try:
        min_impressions = int(min_impressions_str) if min_impressions_str else 10
        days = int(days_str) if days_str else 30
        limit = min(int(limit_str), 500) if limit_str else 500
    except ValueError:
        min_impressions, days, limit = 10, 30, 500

    try:
        # Buscar termos de pesquisa
        google_ads_service = GoogleAdsClientService()
        search_terms = google_ads_service.get_search_terms(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            days=days,
            min_impressions=min_impressions,
            limit=limit
        )

        logger.info(f"[traceId: {trace_id}] Encontrados {len(search_terms)} termos de pesquisa")

        return http_response(200, {
            "status": "SUCCESS",
            "searchTerms": search_terms,
            "count": len(search_terms),
            "filters": {
                "clientId": client_id,
                "campaignId": campaign_id,
                "adGroupId": ad_group_id,
                "minImpressions": min_impressions,
                "days": days
            }
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao listar search terms: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar termos de pesquisa: {str(e)}"
        })
