"""
Lambda handler para buscar um lead especifico por ID.

Endpoint: GET /leads/{leadId}
"""
import json
import logging
import os

import boto3

from src.utils.http import require_api_key, parse_body, http_response, extract_path_param
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))


def handler(event, context):
    """
    Lambda handler para buscar um lead especifico.

    Path Params:
        leadId (required): ID unico do lead

    Returns:
        dict: Dados do lead
    """
    logger.info(f"Iniciando GetLead com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair leadId do path
    lead_id = extract_path_param(event, "leadId")

    if not lead_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "leadId e obrigatorio no path"
        })

    try:
        # Buscar lead por ID
        response = leads_table.get_item(Key={"leadId": lead_id})
        item = response.get("Item")

        if not item:
            return http_response(404, {
                "status": "NOT_FOUND",
                "message": "Lead nao encontrado",
                "leadId": lead_id
            })

        # Converter Decimals para JSON serializable
        lead = convert_decimal_to_json_serializable(item)

        return http_response(200, {
            "status": "SUCCESS",
            "lead": lead
        })

    except Exception as e:
        logger.error(f"Erro ao buscar lead: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao buscar lead: {str(e)}"
        })
