"""
Lambda handler para criar um novo lead.

Endpoint: POST /leads
Body: {
    "clientId": "string (required)",
    "name": "string (required)",
    "phone": "string (required)",
    "email": "string (optional)",
    "location": "string (optional)",
    "source": "string (optional, default: 'web-form')",
    "clinicId": "string (optional, triggers WhatsApp welcome)",
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

from src.utils.http import parse_body, http_response


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
leads_table = dynamodb.Table(os.environ.get("LEADS_TABLE"))
lambda_client = boto3.client("lambda")
ssm_client = boto3.client("ssm")

_scheduler_api_key_cache = None


def _validate_required_fields(body: Dict[str, Any]) -> tuple[bool, str]:
    """Valida campos obrigatorios do lead."""
    required_fields = ["clientId", "name", "phone"]
    missing = [field for field in required_fields if not body.get(field)]

    if missing:
        return False, f"Campos obrigatorios ausentes: {', '.join(missing)}"

    return True, ""


def _get_scheduler_api_key() -> str:
    """Busca e cacheia o SCHEDULER_API_KEY do SSM."""
    global _scheduler_api_key_cache
    if _scheduler_api_key_cache:
        return _scheduler_api_key_cache

    stage = os.environ.get("STAGE", "dev")
    response = ssm_client.get_parameter(
        Name=f"/{stage}/SCHEDULER_API_KEY",
        WithDecryption=True
    )
    _scheduler_api_key_cache = response["Parameter"]["Value"]
    return _scheduler_api_key_cache


def _send_whatsapp_welcome(phone: str, name: str, clinic_id: str) -> dict:
    """Constroi evento API Gateway e invoca SendMessage do scheduler."""
    api_key = _get_scheduler_api_key()
    message = f"Ola {name}! Obrigado pelo seu interesse. Em breve entraremos em contato!"

    payload = {
        "httpMethod": "POST",
        "path": "/send",
        "headers": {
            "Content-Type": "application/json",
            "x-api-key": api_key
        },
        "body": json.dumps({
            "clinicId": clinic_id,
            "phone": phone,
            "type": "text",
            "content": message
        })
    }

    function_name = os.environ.get("SCHEDULER_SEND_FUNCTION")
    response = lambda_client.invoke(
        FunctionName=function_name,
        InvocationType="RequestResponse",
        Payload=json.dumps(payload).encode()
    )

    result = json.loads(response["Payload"].read().decode())
    return result


def handler(event, context):
    """
    Lambda handler para criar um novo lead.

    Returns:
        dict: Response com leadId criado e dados do lead
    """
    logger.info(f"Iniciando CreateLead com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)

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
            "phone": body["phone"],
            "email": body.get("email", ""),
            "location": body.get("location", ""),
            "source": body.get("source", "web-form"),
            "createdAt": created_at,
            "metadata": body.get("metadata", {})
        }

        # Salvar no DynamoDB
        leads_table.put_item(Item=lead_item)

        logger.info(f"Lead criado com sucesso: leadId={lead_id}, clientId={body['clientId']}")

        # Enviar WhatsApp welcome (best-effort)
        clinic_id = body.get("clinicId")
        if clinic_id and body.get("phone"):
            try:
                result = _send_whatsapp_welcome(body["phone"], body["name"], clinic_id)
                result_body = json.loads(result.get("body", "{}"))

                whatsapp_fields = {
                    "clinicId": clinic_id,
                    "whatsappStatus": "SENT" if result.get("statusCode") == 200 else "FAILED",
                    "whatsappSentAt": datetime.utcnow().isoformat(),
                }

                if result_body.get("messageId"):
                    whatsapp_fields["whatsappMessageId"] = result_body["messageId"]

                if result.get("statusCode") != 200:
                    whatsapp_fields["whatsappError"] = result_body.get("error", result_body.get("message", "Unknown error"))

                # Update lead with whatsapp fields
                update_expr = "SET " + ", ".join(f"#{k} = :{k}" for k in whatsapp_fields)
                leads_table.update_item(
                    Key={"leadId": lead_id},
                    UpdateExpression=update_expr,
                    ExpressionAttributeNames={f"#{k}": k for k in whatsapp_fields},
                    ExpressionAttributeValues={f":{k}": v for k, v in whatsapp_fields.items()},
                )

                lead_item.update(whatsapp_fields)
                logger.info(f"WhatsApp welcome enviado para lead {lead_id}: status={whatsapp_fields['whatsappStatus']}")

            except Exception as e:
                logger.error(f"Falha ao enviar WhatsApp welcome para lead {lead_id}: {str(e)}")
                lead_item["whatsappStatus"] = "FAILED"
                lead_item["whatsappError"] = str(e)

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
