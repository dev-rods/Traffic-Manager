"""
Lambda handler para listar negative keywords existentes.

Endpoint: GET /keywords/negatives
Query Params:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios
"""
import logging
import uuid

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response, extract_query_param

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda handler para listar negative keywords.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    logger.info(f"[traceId: {trace_id}] Iniciando ListNegativeKeywords")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    campaign_id = extract_query_param(event, "campaignId")
    ad_group_id = extract_query_param(event, "adGroupId")

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

    try:
        google_ads_service = GoogleAdsClientService()
        negative_keywords = google_ads_service.get_negative_keywords(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id
        )

        logger.info(f"[traceId: {trace_id}] Encontradas {len(negative_keywords)} negative keywords")

        return http_response(200, {
            "status": "SUCCESS",
            "negativeKeywords": negative_keywords,
            "count": len(negative_keywords),
            "filters": {
                "clientId": client_id,
                "campaignId": campaign_id,
                "adGroupId": ad_group_id
            }
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao listar negative keywords: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar negative keywords: {str(e)}"
        })
