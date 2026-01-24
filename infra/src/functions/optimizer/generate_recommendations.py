import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal
import boto3
from src.services.client_service import ClientService, build_optimization_config_from_payload
from src.functions.googleads.get_campaign import extract_campaign_params
from src.functions.googleads.utils import validate_client, create_google_ads_client, get_campaigns_from_google_ads, get_campaign_from_google_ads, get_ad_groups_metrics_from_google_ads
from src.utils.http import require_api_key, parse_body, http_response
from src.utils.decimal_utils import convert_dict_to_decimal, convert_to_decimal


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
campaign_metadata_table = dynamodb.Table(os.environ.get("CAMPAIGN_METADATA_TABLE"))


def _get_clients_to_optimize() -> List[Dict[str, Any]]:
    """
    Retorna a lista de clientes ativos que podem ser otimizados.
    """
    service = ClientService()
    result = service.list_clients(active_only=True)
    clients = result.get("clients", [])

    # Por enquanto, qualquer cliente ativo com Google Ads configurado
    eligible = [ c for c in clients if c.get("googleAdsCustomerId") ]

    logger.info(f"Clientes elegíveis para otimização: {len(eligible)}")
    return eligible


def _ensure_optimization_config(client: Dict[str, Any]) -> Dict[str, Any]:
    """
    Garante que o cliente tenha um bloco optimizationConfig consistente.
    Se não existir, constrói a partir dos dados do cliente.
    """
    if "optimizationConfig" in client and isinstance(client["optimizationConfig"], dict):
        cfg = client["optimizationConfig"]
    else:
        cfg = build_optimization_config_from_payload(client)

    # Garante que healthy_cpa esteja presente e consistente
    cfg = build_optimization_config_from_payload(cfg)
    return cfg


def _decide_action(current_cpa: float, healthy_cpa: float) -> str:
    """
    Decide a ação de otimização com base no desvio do CPA em relação à meta.

    Tabela:
      - ≤ 75%: Aumentar CPC em 15%
      - 75–100%: Aumentar CPC em 10%
      - 100–127%: Manter CPC
      - 127–167%: Reduzir CPC em 15%
      - > 167%: Pausar
    """
    if healthy_cpa <= 0 or current_cpa is None or current_cpa <= 0:
        return "NO_DATA"

    ratio = current_cpa / healthy_cpa

    if ratio <= 0.75:
        return "INCREASE_CPC_15"
    if 0.75 < ratio <= 1.0:
        return "INCREASE_CPC_10"
    if 1.0 < ratio <= 1.27:
        return "KEEP_CPC"
    if 1.27 < ratio <= 1.67:
        return "REDUCE_CPC_15"
    return "PAUSE_CAMPAIGN"


def _store_recommendation(
    client_id: str,
    campaign_id: str,
    campaign_name: str,
    optimization_config: Dict[str, Any],
    metrics: Dict[str, Any],
    action: str,
) -> None:
    """
    Salva no DynamoDB a recomendação de otimização para a campanha.
    """
    timestamp = datetime.utcnow().isoformat()
    healthy_cpa = optimization_config.get("healthy_cpa")
    current_cpa = metrics.get("cost_per_conversion")

    # Converter valores numéricos para Decimal (requisito do DynamoDB)
    optimization_config_decimal = convert_dict_to_decimal(optimization_config)
    metrics_decimal = convert_dict_to_decimal(metrics)
    healthy_cpa_decimal = convert_to_decimal(healthy_cpa) if healthy_cpa is not None else None
    current_cpa_decimal = convert_to_decimal(current_cpa) if current_cpa is not None else None

    item = {
        "googleCampaignId": str(campaign_id),
        "clientId": client_id,
        "campaignName": campaign_name,
        "createdAt": timestamp,
        "optimizationConfig": optimization_config_decimal,
        "metrics": metrics_decimal,
        "healthyCpa": healthy_cpa_decimal,
        "currentCpa": current_cpa_decimal,
        "action": action,
        "period": {
            "days": 30,
        },
    }

    logger.info(
        f"[clientId={client_id}][campaignId={campaign_id}] "
        f"Ação recomendada: {action} | CPA atual={current_cpa} | CPA saudável={healthy_cpa}"
    )

    campaign_metadata_table.put_item(Item=item)


def _resolve_targets_from_event(event: Dict[str, Any]) -> (Optional[str], Optional[str], bool):
    """
    Descobre se a chamada veio de API Gateway ou de schedule e
    retorna (client_id, campaign_id, is_api_call).
    """
    is_api_call = "requestContext" in (event or {})

    client_id: Optional[str] = None
    campaign_id: Optional[str] = None

    if is_api_call:
        body = parse_body(event)
        _, error_response = require_api_key(event, body)
        if error_response:
            return None, None, True
        client_id, campaign_id = extract_campaign_params(event, body)
    else:
        client_id = event.get("clientId")
        campaign_id = event.get("campaignId")

    return client_id, campaign_id, is_api_call


def handler(event, context):
    """
    Lambda executada diariamente (cron) para gerar recomendações de otimização
    de campanhas para cada cliente.

    Por segurança, esta função **não aplica** mudanças no Google Ads.
    Ela apenas calcula o desvio de CPA x meta e grava a recomendação
    na tabela de metadados de campanha.
    """
    logger.info(f"Iniciando GenerateRecommendations com evento: {json.dumps(event)}")

    target_client_id, target_campaign_id, is_api_call = _resolve_targets_from_event(event or {})

    client_service = ClientService()
    if target_client_id:
        client = client_service.get_client(target_client_id)
        clients = [client] if client else []
    else:
        clients = _get_clients_to_optimize()

    recommendations: List[Dict[str, Any]] = []

    for client in clients:
        client_id = client.get("clientId")
        if not client_id:
            continue

        try:
            optimization_cfg = _ensure_optimization_config(client)
            healthy_cpa_value = optimization_cfg.get("healthy_cpa", 0)
            # Converter Decimal para float para cálculos
            healthy_cpa = float(healthy_cpa_value) if isinstance(healthy_cpa_value, Decimal) else healthy_cpa_value

            try:
                client_info = validate_client(client_id)
            except ValueError as ve:
                logger.warning(f"Cliente {client_id} inválido: {str(ve)}. Pulando.")
                continue

            google_ads_customer_id = client_info['googleAdsCustomerId'].replace('-', '')
            trace_id = f"optimizer-{client_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"

            # Criar cliente do Google Ads
            googleads_client = create_google_ads_client()

            # Buscar campanhas usando métodos existentes
            if target_campaign_id:
                # Buscar apenas a campanha específica usando método existente
                try:
                    campaign_id_int = int(target_campaign_id)
                    campaign_data = get_campaign_from_google_ads(
                        googleads_client,
                        google_ads_customer_id,
                        campaign_id_int,
                        trace_id
                    )
                    campaigns = [campaign_data] if campaign_data else []
                except (TypeError, ValueError):
                    logger.warning(f"campaignId inválido recebido: {target_campaign_id}")
                    continue
            else:
                # Buscar todas as campanhas usando método existente do utils
                campaigns = get_campaigns_from_google_ads(
                    googleads_client,
                    google_ads_customer_id,
                    trace_id
                )
                # Filtrar apenas campanhas não removidas (o método não filtra por status)
                campaigns = [
                    c for c in campaigns
                    if c.get('status') and c.get('status') != 'REMOVED'
                ]

            for campaign_data in campaigns:
                campaign_id = campaign_data.get('id')
                campaign_name = campaign_data.get('name')

                if not campaign_id:
                    continue

                current_cpa = campaign_data.get('cpa')
                try:
                    campaign_id_int = int(campaign_id)
                    ad_groups_metrics = get_ad_groups_metrics_from_google_ads(
                        googleads_client,
                        google_ads_customer_id,
                        campaign_id_int,
                        trace_id
                    )
                except (TypeError, ValueError):
                    logger.warning(f"Erro ao buscar métricas de ad groups para campanha {campaign_id}")
                    ad_groups_metrics = []

                # Construir objeto de métricas compatível com o formato esperado
                metrics = {
                    "cost_per_conversion": current_cpa,
                    "average_cpc": campaign_data.get('cpc'),
                    "ad_groups": ad_groups_metrics,
                    "campaign_id": campaign_id,
                    "campaign_name": campaign_name,
                }

                print(f"[traceId: {trace_id}] Métricas: {metrics}", "current_cpa: {current_cpa}", "healthy_cpa: {healthy_cpa}")
                action = _decide_action(current_cpa, healthy_cpa)
                print(f"[traceId: {trace_id}] Ação: {action}")

                _store_recommendation(
                    client_id=client_id,
                    campaign_id=campaign_id,
                    campaign_name=campaign_name,
                    optimization_config=optimization_cfg,
                    metrics=metrics,
                    action=action,
                )

                recommendations.append(
                    {
                        "clientId": client_id,
                        "campaignId": str(campaign_id),
                        "campaignName": campaign_name,
                        "action": action,
                        "currentCpa": current_cpa,
                        "healthyCpa": healthy_cpa,
                    }
                )

        except Exception as e:
            logger.error(
                f"Erro ao processar cliente {client_id}: {str(e)}",
                exc_info=True,
            )

    logger.info("Execução do GenerateRecommendations concluída com sucesso.")

    if is_api_call:
        return http_response(
            200,
            {
                "status": "SUCCESS",
                "timestamp": datetime.utcnow().isoformat(),
                "totalRecommendations": len(recommendations),
                "recommendations": recommendations,
            },
        )

