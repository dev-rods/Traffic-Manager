"""
Lambda handler para aplicar recomendacoes de otimizacao no Google Ads

Este endpoint aplica as recomendacoes geradas pelo generate_recommendations.py,
executando acoes como pausar campanhas ou ajustar CPC de ad groups.
"""
import json
import logging
import os
from datetime import datetime
from typing import Dict, Any, List, Optional
from decimal import Decimal
import boto3

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response, extract_path_param


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
campaign_metadata_table = dynamodb.Table(os.environ.get("CAMPAIGN_METADATA_TABLE"))
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))


# Mapeamento de acoes para multiplicadores de CPC
ACTION_CPC_MULTIPLIERS = {
    "INCREASE_CPC_15": 1.15,
    "INCREASE_CPC_10": 1.10,
    "KEEP_CPC": 1.0,
    "REDUCE_CPC_15": 0.85,
}


def _get_recommendation(google_campaign_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca a recomendacao de otimizacao para uma campanha.

    Args:
        google_campaign_id: ID da campanha no Google Ads

    Returns:
        dict: Dados da recomendacao ou None se nao encontrada
    """
    try:
        response = campaign_metadata_table.get_item(
            Key={"googleCampaignId": str(google_campaign_id)}
        )
        return response.get("Item")
    except Exception as e:
        logger.error(f"Erro ao buscar recomendacao para campanha {google_campaign_id}: {str(e)}")
        return None


def _mark_recommendation_as_applied(google_campaign_id: str, operations: List[Dict]) -> None:
    """
    Marca a recomendacao como aplicada no DynamoDB.

    Args:
        google_campaign_id: ID da campanha no Google Ads
        operations: Lista de operacoes realizadas
    """
    try:
        campaign_metadata_table.update_item(
            Key={"googleCampaignId": str(google_campaign_id)},
            UpdateExpression="SET appliedAt = :appliedAt, appliedOperations = :operations",
            ExpressionAttributeValues={
                ":appliedAt": datetime.utcnow().isoformat(),
                ":operations": operations
            }
        )
        logger.info(f"Recomendacao para campanha {google_campaign_id} marcada como aplicada")
    except Exception as e:
        logger.error(f"Erro ao marcar recomendacao como aplicada: {str(e)}")


def _log_execution(
    trace_id: str,
    client_id: str,
    campaign_id: str,
    action: str,
    operations: List[Dict],
    dry_run: bool,
    status: str
) -> None:
    """
    Registra a execucao na tabela de historico.

    Args:
        trace_id: ID de rastreamento
        client_id: ID do cliente
        campaign_id: ID da campanha
        action: Acao recomendada
        operations: Operacoes realizadas
        dry_run: Se foi execucao de teste
        status: Status da execucao (SUCCESS, ERROR)
    """
    try:
        timestamp = datetime.utcnow().isoformat()
        execution_record = {
            "traceId": trace_id,
            "stageTm": f"APPLY_RECOMMENDATION#{timestamp}",
            "stage": "APPLY_RECOMMENDATION",
            "status": status,
            "timestamp": timestamp,
            "clientId": client_id,
            "campaignId": campaign_id,
            "payload": json.dumps({
                "action": action,
                "operations": operations,
                "dryRun": dry_run
            })
        }
        execution_history_table.put_item(Item=execution_record)
        logger.info(f"[traceId: {trace_id}] Execucao registrada com status {status}")
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao registrar execucao: {str(e)}")


def _apply_pause_campaign(
    service: GoogleAdsClientService,
    client_id: str,
    campaign_id: str,
    dry_run: bool
) -> Dict[str, Any]:
    """
    Aplica acao de pausar campanha.

    Args:
        service: Instancia do GoogleAdsClientService
        client_id: ID do cliente
        campaign_id: ID da campanha
        dry_run: Se deve simular sem executar

    Returns:
        dict: Resultado da operacao
    """
    if dry_run:
        return {
            "type": "PAUSE_CAMPAIGN",
            "success": True,
            "dryRun": True,
            "details": {
                "campaign_id": campaign_id,
                "message": "Campanha seria pausada (dry run)"
            }
        }

    result = service.pause_campaign(client_id, campaign_id)

    return {
        "type": "PAUSE_CAMPAIGN",
        "success": result.get("success", False),
        "dryRun": False,
        "details": result
    }


def _apply_cpc_update(
    service: GoogleAdsClientService,
    client_id: str,
    ad_groups: List[Dict],
    multiplier: float,
    dry_run: bool
) -> List[Dict[str, Any]]:
    """
    Aplica ajuste de CPC em todos os ad groups.

    Args:
        service: Instancia do GoogleAdsClientService
        client_id: ID do cliente
        ad_groups: Lista de ad groups com metricas
        multiplier: Multiplicador de CPC (ex: 1.15 para +15%)
        dry_run: Se deve simular sem executar

    Returns:
        list: Lista de resultados das operacoes
    """
    operations = []

    for ad_group in ad_groups:
        ad_group_id = ad_group.get("id") or ad_group.get("ad_group_id")
        current_cpc = ad_group.get("cpc_bid_micros") or ad_group.get("cpc_micros", 0)

        if not ad_group_id:
            continue

        # Converter Decimal para int se necessario
        if isinstance(current_cpc, Decimal):
            current_cpc = int(current_cpc)

        new_cpc = int(current_cpc * multiplier)

        if dry_run:
            operations.append({
                "type": "UPDATE_CPC",
                "success": True,
                "dryRun": True,
                "details": {
                    "ad_group_id": str(ad_group_id),
                    "current_cpc_micros": current_cpc,
                    "new_cpc_micros": new_cpc,
                    "multiplier": multiplier,
                    "message": f"CPC seria atualizado de {current_cpc} para {new_cpc} micros (dry run)"
                }
            })
        else:
            result = service.update_ad_group_cpc(client_id, str(ad_group_id), new_cpc)
            operations.append({
                "type": "UPDATE_CPC",
                "success": result.get("success", False),
                "dryRun": False,
                "details": {
                    **result,
                    "previous_cpc_micros": current_cpc,
                    "multiplier": multiplier
                }
            })

    return operations


def handler(event, context):
    """
    Lambda handler para aplicar recomendacoes de otimizacao.

    Endpoint: POST /optimizer/apply/{googleCampaignId}

    Args:
        event: Evento HTTP do API Gateway
        context: Contexto Lambda

    Returns:
        dict: Resposta HTTP com resultado da aplicacao
    """
    logger.info(f"Iniciando ApplyRecommendations com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    google_campaign_id = extract_path_param(event, "googleCampaignId")
    if not google_campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "googleCampaignId e obrigatorio no path"
        })

    dry_run = (body or {}).get("dryRun", False)

    # Gerar trace ID
    trace_id = f"apply-rec-{google_campaign_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"[traceId: {trace_id}] Processando campanha {google_campaign_id}, dryRun={dry_run}")

    # Buscar recomendacao
    recommendation = _get_recommendation(google_campaign_id)
    if not recommendation:
        logger.warning(f"[traceId: {trace_id}] Recomendacao nao encontrada para campanha {google_campaign_id}")
        return http_response(404, {
            "status": "NOT_FOUND",
            "timestamp": datetime.utcnow().isoformat(),
            "googleCampaignId": google_campaign_id,
            "message": "Recomendacao nao encontrada para esta campanha"
        })

    # Verificar se ja foi aplicada
    if recommendation.get("appliedAt") and not dry_run:
        logger.info(f"[traceId: {trace_id}] Recomendacao ja aplicada em {recommendation.get('appliedAt')}")
        return http_response(400, {
            "status": "ALREADY_APPLIED",
            "timestamp": datetime.utcnow().isoformat(),
            "googleCampaignId": google_campaign_id,
            "appliedAt": recommendation.get("appliedAt"),
            "message": "Esta recomendacao ja foi aplicada"
        })

    client_id = recommendation.get("clientId")
    campaign_name = recommendation.get("campaignName", "")
    action = recommendation.get("action")
    metrics = recommendation.get("metrics", {})
    ad_groups = metrics.get("ad_groups", [])

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId nao encontrado na recomendacao"
        })

    if not action:
        return http_response(400, {
            "status": "ERROR",
            "message": "action nao encontrada na recomendacao"
        })

    logger.info(f"[traceId: {trace_id}] Acao a aplicar: {action} para cliente {client_id}")

    # Inicializar servico do Google Ads
    service = GoogleAdsClientService()
    operations = []

    try:
        if action == "PAUSE_CAMPAIGN":
            # Pausar campanha
            operation_result = _apply_pause_campaign(
                service, client_id, google_campaign_id, dry_run
            )
            operations.append(operation_result)

        elif action == "KEEP_CPC":
            # Nenhuma acao necessaria
            operations.append({
                "type": "KEEP_CPC",
                "success": True,
                "dryRun": dry_run,
                "details": {
                    "message": "CPC mantido conforme recomendacao"
                }
            })

        elif action in ACTION_CPC_MULTIPLIERS:
            # Ajustar CPC dos ad groups
            multiplier = ACTION_CPC_MULTIPLIERS[action]

            if not ad_groups:
                # Buscar ad groups se nao estiverem na recomendacao
                ad_groups = service.get_ad_groups(client_id, campaign_id=google_campaign_id)

            if ad_groups:
                cpc_operations = _apply_cpc_update(
                    service, client_id, ad_groups, multiplier, dry_run
                )
                operations.extend(cpc_operations)
            else:
                operations.append({
                    "type": "UPDATE_CPC",
                    "success": False,
                    "dryRun": dry_run,
                    "details": {
                        "message": "Nenhum ad group encontrado para atualizar CPC"
                    }
                })

        else:
            return http_response(400, {
                "status": "ERROR",
                "message": f"Acao desconhecida: {action}"
            })

        # Verificar se todas operacoes foram bem sucedidas
        all_success = all(op.get("success", False) for op in operations)
        status = "SUCCESS" if all_success else "PARTIAL_SUCCESS"

        # Marcar como aplicada (apenas se nao for dry run e teve sucesso)
        if not dry_run and all_success:
            _mark_recommendation_as_applied(google_campaign_id, operations)

        # Registrar execucao
        _log_execution(
            trace_id=trace_id,
            client_id=client_id,
            campaign_id=google_campaign_id,
            action=action,
            operations=operations,
            dry_run=dry_run,
            status=status
        )

        response_data = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "googleCampaignId": google_campaign_id,
            "clientId": client_id,
            "campaignName": campaign_name,
            "action": action,
            "dryRun": dry_run,
            "operations": operations
        }

        logger.info(f"[traceId: {trace_id}] Aplicacao concluida com status {status}")
        return http_response(200, response_data)

    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id}] Erro ao aplicar recomendacao: {error_msg}", exc_info=True)

        # Registrar erro
        _log_execution(
            trace_id=trace_id,
            client_id=client_id,
            campaign_id=google_campaign_id,
            action=action,
            operations=operations,
            dry_run=dry_run,
            status="ERROR"
        )

        return http_response(500, {
            "status": "ERROR",
            "timestamp": datetime.utcnow().isoformat(),
            "googleCampaignId": google_campaign_id,
            "message": f"Erro ao aplicar recomendacao: {error_msg}"
        })
