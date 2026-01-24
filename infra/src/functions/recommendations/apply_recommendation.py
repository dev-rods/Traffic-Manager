"""
Lambda handler para aplicar uma recomendacao de otimizacao.

Endpoint: POST /recommendations/{recommendationId}/apply
Body: { "clientId": "string", "campaignId": "string" }
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
from src.utils.decimal_utils import convert_decimal_to_json_serializable


logger = logging.getLogger()
logger.setLevel(logging.INFO)


dynamodb = boto3.resource("dynamodb")
recommendations_table = dynamodb.Table(os.environ.get("RECOMMENDATIONS_TABLE"))
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))


# Mapeamento de acoes para multiplicadores de CPC
ACTION_CPC_MULTIPLIERS = {
    "INCREASE_CPC_15": 1.15,
    "INCREASE_CPC_10": 1.10,
    "KEEP_CPC": 1.0,
    "REDUCE_CPC_15": 0.85,
}


def _get_recommendation(recommendation_id: str) -> Optional[Dict[str, Any]]:
    """Busca recomendacao por ID."""
    try:
        response = recommendations_table.get_item(
            Key={"recommendationId": recommendation_id}
        )
        return response.get("Item")
    except Exception as e:
        logger.error(f"Erro ao buscar recomendacao {recommendation_id}: {str(e)}")
        return None


def _update_recommendation_status(
    recommendation_id: str,
    status: str,
    application_result: Dict[str, Any]
) -> None:
    """Atualiza status da recomendacao apos aplicacao."""
    try:
        update_expr = "SET #status = :status, appliedAt = :appliedAt, applicationResult = :result"
        recommendations_table.update_item(
            Key={"recommendationId": recommendation_id},
            UpdateExpression=update_expr,
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":status": status,
                ":appliedAt": datetime.utcnow().isoformat(),
                ":result": application_result
            }
        )
        logger.info(f"Recomendacao {recommendation_id} atualizada para status {status}")
    except Exception as e:
        logger.error(f"Erro ao atualizar recomendacao: {str(e)}")


def _log_execution(
    trace_id: str,
    client_id: str,
    campaign_id: str,
    recommendation_id: str,
    action: str,
    operations: List[Dict],
    dry_run: bool,
    status: str
) -> None:
    """Registra a execucao na tabela de historico."""
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
                "recommendationId": recommendation_id,
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
    """Aplica acao de pausar campanha."""
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
    """Aplica ajuste de CPC em todos os ad groups."""
    operations = []

    for ad_group in ad_groups:
        ad_group_id = ad_group.get("id") or ad_group.get("ad_group_id")
        current_cpc = ad_group.get("cpc_bid_micros") or ad_group.get("cpc_micros", 0)

        if not ad_group_id:
            continue

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
    Lambda handler para aplicar uma recomendacao especifica.

    Endpoint: POST /recommendations/{recommendationId}/apply
    Body: { "clientId": "string", "campaignId": "string", "dryRun": bool }
    """
    logger.info(f"Iniciando ApplyRecommendation com evento: {json.dumps(event)}")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    recommendation_id = extract_path_param(event, "recommendationId")
    if not recommendation_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "recommendationId e obrigatorio no path"
        })

    request_client_id = (body or {}).get("clientId")
    request_campaign_id = (body or {}).get("campaignId")
    dry_run = (body or {}).get("dryRun", False)

    if not request_client_id or not request_campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e campaignId sao obrigatorios no body"
        })

    # Buscar recomendacao
    recommendation = _get_recommendation(recommendation_id)
    if not recommendation:
        return http_response(404, {
            "status": "NOT_FOUND",
            "recommendationId": recommendation_id,
            "message": "Recomendacao nao encontrada"
        })

    # Validar que clientId e campaignId correspondem
    rec_client_id = recommendation.get("clientId")
    rec_campaign_id = recommendation.get("campaignId")

    if rec_client_id != request_client_id or rec_campaign_id != request_campaign_id:
        return http_response(400, {
            "status": "MISMATCH",
            "message": "clientId ou campaignId nao correspondem a recomendacao"
        })

    # Verificar se ja foi aplicada
    if recommendation.get("status") == "APPLIED" and not dry_run:
        return http_response(409, {
            "status": "ALREADY_APPLIED",
            "recommendationId": recommendation_id,
            "appliedAt": recommendation.get("appliedAt"),
            "message": "Esta recomendacao ja foi aplicada"
        })

    # Extrair dados da recomendacao
    action = recommendation.get("action")
    metrics = recommendation.get("metrics", {})
    ad_groups = metrics.get("ad_groups", [])
    campaign_name = recommendation.get("campaignName", "")

    if not action:
        return http_response(400, {
            "status": "ERROR",
            "message": "action nao encontrada na recomendacao"
        })

    # Gerar trace ID
    trace_id = f"apply-rec-{recommendation_id[:8]}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    logger.info(f"[traceId: {trace_id}] Aplicando recomendacao {recommendation_id}, acao={action}, dryRun={dry_run}")

    # Inicializar servico do Google Ads
    service = GoogleAdsClientService()
    operations = []

    try:
        if action == "PAUSE_CAMPAIGN":
            operation_result = _apply_pause_campaign(
                service, rec_client_id, rec_campaign_id, dry_run
            )
            operations.append(operation_result)

        elif action == "KEEP_CPC":
            operations.append({
                "type": "KEEP_CPC",
                "success": True,
                "dryRun": dry_run,
                "details": {"message": "CPC mantido conforme recomendacao"}
            })

        elif action in ACTION_CPC_MULTIPLIERS:
            multiplier = ACTION_CPC_MULTIPLIERS[action]

            if not ad_groups:
                ad_groups = service.get_ad_groups(rec_client_id, campaign_id=rec_campaign_id)

            if ad_groups:
                cpc_operations = _apply_cpc_update(
                    service, rec_client_id, ad_groups, multiplier, dry_run
                )
                operations.extend(cpc_operations)
            else:
                operations.append({
                    "type": "UPDATE_CPC",
                    "success": False,
                    "dryRun": dry_run,
                    "details": {"message": "Nenhum ad group encontrado para atualizar CPC"}
                })

        else:
            return http_response(400, {
                "status": "ERROR",
                "message": f"Acao desconhecida: {action}"
            })

        # Verificar sucesso
        all_success = all(op.get("success", False) for op in operations)
        status = "SUCCESS" if all_success else "PARTIAL_SUCCESS"

        # Atualizar status da recomendacao (se nao for dry run)
        if not dry_run and all_success:
            _update_recommendation_status(
                recommendation_id,
                "APPLIED",
                {"operations": operations, "traceId": trace_id}
            )

        # Registrar execucao
        _log_execution(
            trace_id=trace_id,
            client_id=rec_client_id,
            campaign_id=rec_campaign_id,
            recommendation_id=recommendation_id,
            action=action,
            operations=operations,
            dry_run=dry_run,
            status=status
        )

        response_data = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "recommendationId": recommendation_id,
            "clientId": rec_client_id,
            "campaignId": rec_campaign_id,
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

        _log_execution(
            trace_id=trace_id,
            client_id=rec_client_id,
            campaign_id=rec_campaign_id,
            recommendation_id=recommendation_id,
            action=action,
            operations=operations,
            dry_run=dry_run,
            status="ERROR"
        )

        return http_response(500, {
            "status": "ERROR",
            "recommendationId": recommendation_id,
            "message": f"Erro ao aplicar recomendacao: {error_msg}"
        })
