"""
Lambda handler para listar recomendacoes de otimizacao.

Endpoint: GET /recommendations?clientId={clientId}&campaignId={campaignId}&status={status}
"""
import json
import logging
import os
from decimal import Decimal
import boto3
from boto3.dynamodb.conditions import Key, Attr

from src.utils.http import require_api_key, parse_body, http_response, extract_query_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
recommendations_table = dynamodb.Table(os.environ.get("RECOMMENDATIONS_TABLE"))


def handler(event, context):
    """
    Lambda handler para listar recomendacoes.

    Query Params:
        clientId (required): ID do cliente
        campaignId (optional): Filtrar por campanha especifica
        status (optional): Filtrar por status (PENDING, APPLIED, SKIPPED)

    Returns:
        dict: Lista de recomendacoes
    """
    logger.info(f"Iniciando ListRecommendations com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    campaign_id = extract_query_param(event, "campaignId")
    status_filter = extract_query_param(event, "status")

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio como query parameter"
        })

    try:
        # Query usando GSI
        key_condition = Key("clientId").eq(client_id)

        if campaign_id:
            # Filtrar por campaignId usando begins_with no sort key composto
            key_condition = key_condition & Key("campaignIdCreatedAt").begins_with(f"{campaign_id}#")

        query_kwargs = {
            "IndexName": "clientId-campaignId-index",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": False  # Mais recentes primeiro
        }

        # Adicionar filtro de status se especificado
        if status_filter:
            query_kwargs["FilterExpression"] = Attr("status").eq(status_filter)

        response = recommendations_table.query(**query_kwargs)
        items = response.get("Items", [])

        # Converter Decimals para JSON serializable
        recommendations = [convert_decimal_to_json_serializable(item) for item in items]

        return http_response(200, {
            "status": "SUCCESS",
            "recommendations": recommendations,
            "count": len(recommendations)
        })

    except Exception as e:
        logger.error(f"Erro ao listar recomendacoes: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar recomendacoes: {str(e)}"
        })
