import json
from typing import Dict, Any, Optional

from src.utils.auth import ClientAuth
from src.services.client_service import ClientService, build_optimization_config_from_payload
from src.utils.http import require_api_key,  parse_body, http_response
from src.functions.googleads.utils import extract_client_id

def handler(event, context):
    """
    Handler para edição de parâmetros econômicos do cliente via API.

    Path:
      - /clients/{clientId}

    Body esperado (qualquer combinação dos campos abaixo):
    {
        "average_ticket": 270.0,
        "ltv_months": 6,
        "net_margin": 0.6,
        "lead_to_sale_conversion_rate": 0.2,
        "safety_factor": 0.7
    }

    Regras:
      - Somente os campos enviados serão considerados como novos valores.
      - Os demais permanecem com o valor atual do cliente (se existir).
      - Caso o cliente ainda não tenha `optimizationConfig`, será criado.
    """
    try:
        print(f"Requisição recebida para edição de cliente: {json.dumps(event)}")

        body = parse_body(event)

        _, error_response = require_api_key(event, body)
        if error_response:
            print("API key inválida ou não fornecida")
            return error_response

        # Obter clientId (path param tem prioridade)
        client_id = extract_client_id(event, body)
        if not client_id:
            return http_response(400, {"message": "clientId é obrigatório (path ou body)"})

        client_service = ClientService()
        client = client_service.get_client(client_id)
        if not client:
            return http_response(404, {"message": f"Cliente {client_id} não encontrado"})

        # Campos econômicos enviados no body
        economic_fields = {
            "average_ticket",
            "ltv_months",
            "net_margin",
            "lead_to_sale_conversion_rate",
            "safety_factor",
            # Aceitar também algumas variações de nome
            "averageTicket",
            "ticket_medio",
            "ltvMonths",
            "ltv",
            "netMargin",
            "margem_liquida",
            "leadToSaleConversionRate",
            "taxa_conversao_lead",
            "safetyFactor",
            "fator_seguranca",
        }

        received_economic_data: Dict[str, Any] = {
            k: v for k, v in (body or {}).items() if k in economic_fields
        }

        if not received_economic_data:
            return http_response(
                400,
                {
                    "message": "Nenhum campo econômico fornecido. "
                    "Envie pelo menos um de: average_ticket, ltv_months, net_margin, "
                    "lead_to_sale_conversion_rate, safety_factor",
                },
            )

        # Base para o cálculo: config atual (se existir) + novos valores
        current_cfg = client.get("optimizationConfig") or {}
        merged_payload = {**current_cfg, **received_economic_data}

        new_cfg = build_optimization_config_from_payload(merged_payload)

        # Atualizar cliente
        updated = client_service.update_client(
            client_id,
            {
                "optimizationConfig": new_cfg,
            },
        )

        if not updated:
            return http_response(500, {"message": "Falha ao atualizar cliente"})

        # Buscar cliente atualizado para retornar
        updated_client = client_service.get_client(client_id) or {}

        return http_response(
            200,
            {
                "message": "Cliente atualizado com sucesso",
                "clientId": client_id,
                "optimizationConfig": updated_client.get("optimizationConfig", new_cfg),
            },
        )

    except Exception as e:
        error_msg = str(e)
        print(f"Erro no processamento da edição de cliente: {error_msg}")
        return http_response(500, {"message": "Erro interno no servidor", "error": error_msg})
