"""
Lambda handler para listar leads de um cliente.

Endpoint: GET /leads?clientId={clientId}&startDate={startDate}&endDate={endDate}&limit={limit}
"""
import json
import logging
import os
from typing import Dict, Any, Optional

import boto3
from boto3.dynamodb.conditions import Key, Attr

from src.utils.http import require_api_key, parse_body, http_response, extract_query_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))


def handler(event, context):
    """
    Lambda handler para listar leads de um cliente.

    Query Params:
        clientId (required): ID do cliente
        startDate (optional): Filtrar leads a partir desta data (ISO)
        endDate (optional): Filtrar leads ate esta data (ISO)
        limit (optional): Limite de resultados (default: 100, max: 1000)

    Returns:
        dict: Lista de leads do cliente
    """
    logger.info(f"Iniciando ListLeads com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    start_date = extract_query_param(event, "startDate")
    end_date = extract_query_param(event, "endDate")
    limit_str = extract_query_param(event, "limit")

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio como query parameter"
        })

    # Parse limit
    try:
        limit = min(int(limit_str), 1000) if limit_str else 100
    except ValueError:
        limit = 100

    try:
        # Construir query
        key_condition = Key("clientId").eq(client_id)

        # Adicionar filtro de data se especificado
        if start_date and end_date:
            key_condition = key_condition & Key("createdAt").between(start_date, end_date)
        elif start_date:
            key_condition = key_condition & Key("createdAt").gte(start_date)
        elif end_date:
            key_condition = key_condition & Key("createdAt").lte(end_date)

        query_kwargs = {
            "IndexName": "clientId-createdAt-index",
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": False,  # Mais recentes primeiro
            "Limit": limit
        }

        response = leads_table.query(**query_kwargs)
        items = response.get("Items", [])

        # Converter Decimals para JSON serializable
        leads = [convert_decimal_to_json_serializable(item) for item in items]

        return http_response(200, {
            "status": "SUCCESS",
            "leads": leads,
            "count": len(leads),
            "clientId": client_id
        })

    except Exception as e:
        logger.error(f"Erro ao listar leads: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar leads: {str(e)}"
        })
