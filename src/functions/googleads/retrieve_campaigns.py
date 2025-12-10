import json
import os
import boto3
from datetime import datetime
from typing import Dict, Any
from google.ads.googleads.errors import GoogleAdsException
from src.functions.googleads.utils import validate_client, create_google_ads_client, get_campaigns_from_google_ads, extract_client_id
from src.utils.http import require_api_key, parse_body, http_response

dynamodb = boto3.resource("dynamodb")
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))


def handler(event, context) -> Dict[str, Any]:
    try:
        print(f"Requisição recebida para recuperar campanhas: {json.dumps(event)}")        
        body = parse_body(event)        
        _, error_response = require_api_key(event, body)
        if error_response:
            print("API key inválida ou não fornecida")
            return error_response
        
        client_id = extract_client_id(event, body)
        trace_id = event.get("requestContext", {}).get("requestId", f"retrieve-campaigns-{datetime.utcnow().isoformat()}")
        stage = "GOOGLE_ADS_RETRIEVE_CAMPAIGNS"
        timestamp = datetime.utcnow().isoformat()
        
        print(f"[traceId: {trace_id}] Iniciando recuperação de campanhas do Google Ads para cliente: {client_id}")
        
        # Validação do cliente
        client_info = validate_client(client_id)
        
        google_ads_customer_id = client_info['googleAdsCustomerId'].replace('-', '')
        print(f"[traceId: {trace_id}] Customer ID encontrado: {google_ads_customer_id}")
        
        # Criar cliente do Google Ads
        googleads_client = create_google_ads_client()
        
        # Buscar campanhas
        campaigns = get_campaigns_from_google_ads(googleads_client, google_ads_customer_id, trace_id)
        
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
                'campaigns_found': len(campaigns),
                'campaigns': campaigns[:5]  # Primeiras 5 para o log
            })
        }
        execution_history_table.put_item(Item=execution_record)
        
        
        print(f"[traceId: {trace_id}] Recuperação de campanhas concluída com sucesso. Total: {len(campaigns)} campanhas")
        
        return http_response(200, {
            'traceId': trace_id,
            'timestamp': timestamp,
            'clientId': client_id,
            'googleAdsCustomerId': google_ads_customer_id,
            'status': 'SUCCESS',
            'campaigns': campaigns,
            'total_campaigns': len(campaigns)
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

