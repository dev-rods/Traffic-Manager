"""
Lambda handler para aplicar negative keywords no Google Ads.

Endpoint: POST /keywords/apply-negatives
Body:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios (se omitido, aplica a nivel de campanha)
    - negativeKeywords (required): Lista de keywords a negativar
        - text: Texto da keyword
        - matchType: BROAD, PHRASE ou EXACT (default: BROAD)
"""
import json
import logging
import os
import uuid
from datetime import datetime

import boto3

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))


def _validate_negative_keywords(keywords):
    """Valida a lista de negative keywords."""
    if not keywords or not isinstance(keywords, list):
        return False, "negativeKeywords deve ser uma lista nao vazia"

    for i, kw in enumerate(keywords):
        if not isinstance(kw, dict):
            return False, f"Item {i} deve ser um objeto"
        if not kw.get("text"):
            return False, f"Item {i} deve ter o campo 'text'"

        match_type = kw.get("matchType", "BROAD").upper()
        if match_type not in ["BROAD", "PHRASE", "EXACT"]:
            return False, f"Item {i} tem matchType invalido: {match_type}"

    return True, ""


def handler(event, context):
    """
    Lambda handler para aplicar negative keywords.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()
    stage = 'APPLY_NEGATIVE_KEYWORDS'

    logger.info(f"[traceId: {trace_id}] Iniciando ApplyNegativeKeywords")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    if not body:
        return http_response(400, {
            "status": "ERROR",
            "message": "Request body e obrigatorio"
        })

    # Extrair parametros
    client_id = body.get("clientId")
    campaign_id = body.get("campaignId")
    ad_group_id = body.get("adGroupId")
    negative_keywords = body.get("negativeKeywords", [])

    # Validacoes
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

    is_valid, error_msg = _validate_negative_keywords(negative_keywords)
    if not is_valid:
        return http_response(400, {
            "status": "ERROR",
            "message": error_msg
        })

    try:
        google_ads_service = GoogleAdsClientService()

        # Aplicar negative keywords
        logger.info(f"[traceId: {trace_id}] Aplicando {len(negative_keywords)} negative keywords...")

        result = google_ads_service.add_negative_keywords(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            negative_keywords=negative_keywords
        )

        if not result.get("success"):
            return http_response(400, {
                "status": "ERROR",
                "message": result.get("error", "Erro ao aplicar negative keywords")
            })

        # Registrar no ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'clientId': client_id,
            'campaignId': campaign_id,
            'payload': json.dumps({
                'keywordsApplied': len(negative_keywords),
                'keywords': [kw.get("text") for kw in negative_keywords],
                'level': 'ad_group' if ad_group_id else 'campaign'
            })
        }
        execution_history_table.put_item(Item=execution_record)

        logger.info(f"[traceId: {trace_id}] {len(negative_keywords)} negative keywords aplicadas com sucesso")

        return http_response(200, {
            "status": "SUCCESS",
            "traceId": trace_id,
            "message": f"{len(negative_keywords)} negative keywords aplicadas com sucesso",
            "applied": result.get("applied", []),
            "level": "ad_group" if ad_group_id else "campaign"
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao aplicar negative keywords: {str(e)}", exc_info=True)

        # Registrar erro
        try:
            error_record = {
                'traceId': trace_id,
                'stageTm': f"{stage}#{timestamp}",
                'stage': stage,
                'status': 'ERROR',
                'timestamp': timestamp,
                'clientId': client_id,
                'campaignId': campaign_id,
                'errorMsg': str(e)
            }
            execution_history_table.put_item(Item=error_record)
        except Exception:
            pass

        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao aplicar negative keywords: {str(e)}"
        })
