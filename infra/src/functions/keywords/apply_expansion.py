"""
Lambda handler para aplicar keywords de expansao no Google Ads.

Endpoint: POST /keywords/apply-expansion
Body:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (required): ID do grupo de anuncios
    - keywords (required): Lista de keywords a adicionar
        - text: Texto da keyword
        - matchType: EXACT, PHRASE ou BROAD (default: PHRASE)
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


def _validate_keywords(keywords):
    """Valida a lista de keywords."""
    if not keywords or not isinstance(keywords, list):
        return False, "keywords deve ser uma lista nao vazia"

    for i, kw in enumerate(keywords):
        if not isinstance(kw, dict):
            return False, f"Item {i} deve ser um objeto"
        if not kw.get("text"):
            return False, f"Item {i} deve ter o campo 'text'"

        match_type = kw.get("matchType", "PHRASE").upper()
        if match_type not in ["EXACT", "PHRASE", "BROAD"]:
            return False, f"Item {i} tem matchType invalido: {match_type}"

    return True, ""


def handler(event, context):
    """
    Lambda handler para aplicar keywords de expansao.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()
    stage = 'APPLY_KEYWORD_EXPANSION'

    logger.info(f"[traceId: {trace_id}] Iniciando ApplyKeywordExpansion")

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
    keywords = body.get("keywords", [])

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

    if not ad_group_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "adGroupId e obrigatorio para adicionar keywords"
        })

    is_valid, error_msg = _validate_keywords(keywords)
    if not is_valid:
        return http_response(400, {
            "status": "ERROR",
            "message": error_msg
        })

    try:
        google_ads_service = GoogleAdsClientService()

        # Adicionar keywords
        logger.info(f"[traceId: {trace_id}] Adicionando {len(keywords)} keywords...")

        result = google_ads_service.add_keywords(
            client_id=client_id,
            ad_group_id=ad_group_id,
            keywords=keywords
        )

        if not result.get("success"):
            return http_response(400, {
                "status": "ERROR",
                "message": result.get("error", "Erro ao adicionar keywords"),
                "errors": result.get("errors")
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
            'adGroupId': ad_group_id,
            'payload': json.dumps({
                'keywordsAdded': len(keywords),
                'keywords': [kw.get("text") for kw in keywords]
            })
        }
        execution_history_table.put_item(Item=execution_record)

        logger.info(f"[traceId: {trace_id}] {len(keywords)} keywords adicionadas com sucesso")

        return http_response(200, {
            "status": "SUCCESS",
            "traceId": trace_id,
            "message": f"{len(keywords)} keywords adicionadas com sucesso",
            "added": result.get("added", []),
            "adGroupId": ad_group_id
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao adicionar keywords: {str(e)}", exc_info=True)

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
            "message": f"Erro ao adicionar keywords: {str(e)}"
        })
