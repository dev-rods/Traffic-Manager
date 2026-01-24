"""
Lambda handler para criar um novo lead.

Endpoint: POST /leads
Body: {
    "clientId": "string (required)",
    "name": "string (required)",
    "email": "string (required)",
    "phone": "string (optional)",
    "location": "string (optional)",
    "source": "string (optional, default: 'web-form')",
    "metadata": {} (optional)
}
"""
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Dict, Any

import boto3

from src.utils.http import require_api_key, parse_body, http_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))


def _validate_required_fields(body: Dict[str, Any]) -> tuple[bool, str]:
    """Valida campos obrigatorios do lead."""
    required_fields = ["clientId", "name", "email"]
    missing = [field for field in required_fields if not body.get(field)]

    if missing:
        return False, f"Campos obrigatorios ausentes: {', '.join(missing)}"

    return True, ""


def handler(event, context):
    """
    Lambda handler para criar um novo lead.

    Returns:
        dict: Response com leadId criado e dados do lead
    """
    logger.info(f"Iniciando CreateLead com evento: {json.dumps(event)}")

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

    # Validar campos obrigatorios
    is_valid, error_msg = _validate_required_fields(body)
    if not is_valid:
        return http_response(400, {
            "status": "ERROR",
            "message": error_msg
        })

    try:
        # Gerar ID e timestamp
        lead_id = str(uuid.uuid4())
        created_at = datetime.utcnow().isoformat()

        # Construir item do lead
        lead_item = {
            "leadId": lead_id,
            "clientId": body["clientId"],
            "name": body["name"],
            "email": body["email"],
            "phone": body.get("phone", ""),
            "location": body.get("location", ""),
            "source": body.get("source", "web-form"),
            "createdAt": created_at,
            "metadata": body.get("metadata", {})
        }

        # Salvar no DynamoDB
        leads_table.put_item(Item=lead_item)

        logger.info(f"Lead criado com sucesso: leadId={lead_id}, clientId={body['clientId']}")

        return http_response(201, {
            "status": "SUCCESS",
            "message": "Lead registrado com sucesso",
            "leadId": lead_id,
            "lead": lead_item
        })

    except Exception as e:
        logger.error(f"Erro ao criar lead: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao criar lead: {str(e)}"
        })
