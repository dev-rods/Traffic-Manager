import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any, Optional
from google.ads.googleads.errors import GoogleAdsException
from src.functions.googleads.utils import validate_client, create_google_ads_client, get_campaign_from_google_ads, get_ad_groups_metrics_from_google_ads, extract_client_id
from src.utils.http import require_api_key, parse_body, extract_path_param, extract_query_param, http_response


dynamodb = boto3.resource("dynamodb")
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))


def handler(event, context) -> Dict[str, Any]:
    trace_id = event.get("requestContext", {}).get("requestId", f"get-campaign-{datetime.utcnow().isoformat()}")
    stage = "GOOGLE_ADS_GET_CAMPAIGN"
    timestamp = datetime.utcnow().isoformat()
    try:
        print(f"Requisição recebida para buscar campanha: {json.dumps(event)}")
        body = parse_body(event)
        
        _, error_response = require_api_key(event, body)
        if error_response:
            print("API key inválida ou não fornecida")
            return error_response
        
        client_id, campaign_id = extract_campaign_params(event, body)
        if not client_id or not campaign_id:
            raise ValueError("clientId e campaignId são obrigatórios")        
        
        print(f"[traceId: {trace_id}] Iniciando busca de campanha {campaign_id} do Google Ads para cliente: {client_id}")
        
        # Validação do cliente
        client_info = validate_client(client_id)
        
        
        try:
            campaign_id_int = int(campaign_id)
        except (ValueError, TypeError):
            raise ValueError(f"campaignId deve ser um número válido: {campaign_id}")
        
        google_ads_customer_id = client_info['googleAdsCustomerId'].replace('-', '')
        print(f"[traceId: {trace_id}] Customer ID encontrado: {google_ads_customer_id}")
        
        # Criar cliente do Google Ads
        googleads_client = create_google_ads_client()
        
        # Buscar campanha específica com métricas
        campaign = get_campaign_from_google_ads(googleads_client, google_ads_customer_id, campaign_id_int, trace_id)
        
        if not campaign:
            raise ValueError(f"Campanha {campaign_id} não encontrada para o cliente {client_id}")
        
        # Buscar métricas dos grupos de anúncios
        ad_groups_metrics = get_ad_groups_metrics_from_google_ads(googleads_client, google_ads_customer_id, campaign_id_int, trace_id)
        
        # Adicionar grupos de anúncios com métricas à resposta da campanha
        campaign['ad_groups'] = ad_groups_metrics
        
        # Registrar execução no histórico
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'clientId': client_id,
            'googleAdsCustomerId': google_ads_customer_id,
            'payload': json.dumps({
                'campaign_id': campaign_id,
                'campaign': campaign
            })
        }
        execution_history_table.put_item(Item=execution_record)
        
        print(f"[traceId: {trace_id}] Campanha recuperada com sucesso: {campaign['name']} - {len(ad_groups_metrics)} grupos de anúncios")
        
        # Retornar resposta HTTP
        return http_response(200, {
            'traceId': trace_id,
            'timestamp': timestamp,
            'clientId': client_id,
            'googleAdsCustomerId': google_ads_customer_id,
            'status': 'SUCCESS',
            'campaign': campaign
        })
        
    except ValueError as ve:
        error_msg = str(ve)
        print(f"[traceId: {trace_id}] Erro de validação: {error_msg}")
        error_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'VALIDATION_ERROR',
            'timestamp': timestamp,
            'clientId': client_id if client_id else 'unknown',
            'errorMsg': error_msg,
            'payload': json.dumps({'error': error_msg})
        }
        
        try:
            execution_history_table.put_item(Item=error_record)
        except Exception as inner_e:
            print(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        return http_response(400, {
            'traceId': trace_id,
            'timestamp': timestamp,
            'status': 'ERROR',
            'error_type': 'VALIDATION_ERROR',
            'error': error_msg
        })
        
    except GoogleAdsException as ex:
        error_msg = f'Request with ID "{ex.request_id}" failed with status "{ex.error.code().name}"'
        if ex.failure and ex.failure.errors:
            error_details = []
            for error in ex.failure.errors:
                error_detail = f'Error with message "{error.message}"'
                if error.location:
                    for field_path_element in error.location.field_path_elements:
                        error_detail += f' On field: {field_path_element.field_name}'
                error_details.append(error_detail)
            error_msg += f" Errors: {'; '.join(error_details)}"
        
        print(f"[traceId: {trace_id}] Google Ads API Error: {error_msg}")
        
        error_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'GOOGLE_ADS_ERROR',
            'timestamp': timestamp,
            'clientId': client_id if client_id else 'unknown',
            'errorMsg': error_msg,
            'requestId': ex.request_id,
            'errorCode': ex.error.code().name,
            'payload': json.dumps({'error': error_msg})
        }
        
        try:
            execution_history_table.put_item(Item=error_record)
        except Exception as inner_e:
            print(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        return http_response(500, {
            'traceId': trace_id,
            'timestamp': timestamp,
            'status': 'ERROR',
            'error_type': 'GOOGLE_ADS_API_ERROR',
            'error': error_msg,
            'request_id': ex.request_id,
            'error_code': ex.error.code().name
        })
        
    except Exception as e:
        error_msg = str(e)
        print(f"[traceId: {trace_id}] Erro geral: {error_msg}")
        
        error_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'ERROR',
            'timestamp': timestamp,
            'clientId': client_id if client_id else 'unknown',
            'errorMsg': error_msg,
            'payload': json.dumps({'error': error_msg})
        }
        
        try:
            execution_history_table.put_item(Item=error_record)
        except Exception as inner_e:
            print(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        return http_response(500, {
            'traceId': trace_id,
            'timestamp': timestamp,
            'status': 'ERROR',
            'error_type': 'GENERAL_ERROR',
            'error': error_msg
        })


def extract_campaign_params(event: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> tuple:
    client_id = extract_client_id(event, body)
    
    campaign_id = extract_path_param(event, "campaignId")
    if not campaign_id:
        campaign_id = extract_query_param(event, "campaignId")
    if body and isinstance(body, dict) and "campaignId" in body and not campaign_id:
        campaign_id = body["campaignId"]
    
    return client_id, campaign_id

