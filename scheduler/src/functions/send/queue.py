import json
import logging

import requests

from src.utils.http import parse_body, http_response, require_api_key, extract_path_param, extract_query_param
from src.services.db.postgres import PostgresService
from src.providers.whatsapp_provider import get_provider

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Handler para consultar fila de mensagens do z-api.

    GET /clinics/{clinicId}/queue?page=1&pageSize=100
    GET /clinics/{clinicId}/queue/count
    """
    try:
        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        if not clinic_id:
            return http_response(400, {"status": "ERROR", "message": "clinicId is required"})

        # Buscar clinica no RDS
        db = PostgresService()
        clinics = db.execute_query(
            "SELECT * FROM scheduler.clinics WHERE clinic_id = %s AND active = TRUE",
            (clinic_id,)
        )

        if not clinics:
            return http_response(404, {"status": "ERROR", "message": f"Clinica '{clinic_id}' nao encontrada"})

        clinic = clinics[0]

        instance_id = clinic.get("zapi_instance_id")
        instance_token = clinic.get("zapi_instance_token")

        if not instance_id or not instance_token:
            return http_response(400, {"status": "ERROR", "message": "Clinica nao possui z-api configurado"})

        # Montar URL do z-api
        base_url = f"https://api.z-api.io/instances/{instance_id}/token/{instance_token}"

        # Verificar se é request de count
        path = event.get("path", "")
        if path.endswith("/count"):
            url = f"{base_url}/queue/count"
            params = {}
        else:
            page = extract_query_param(event, "page") or "1"
            page_size = extract_query_param(event, "pageSize") or "100"
            url = f"{base_url}/queue"
            params = {"page": page, "pageSize": page_size}

        # Buscar client token
        import os
        client_token = os.environ.get("ZAPI_CLIENT_TOKEN", "")

        headers = {
            "Client-Token": client_token,
            "Content-Type": "application/json",
        }

        resp = requests.get(url, params=params, headers=headers, timeout=15)
        data = resp.json() if resp.content else {}

        if resp.status_code == 200:
            return http_response(200, {
                "status": "SUCCESS",
                "data": data
            })
        else:
            return http_response(resp.status_code, {
                "status": "ERROR",
                "message": f"z-api retornou status {resp.status_code}",
                "data": data
            })

    except Exception as e:
        logger.error(f"Erro ao consultar fila: {str(e)}")
        return http_response(500, {"status": "ERROR", "message": str(e)})
