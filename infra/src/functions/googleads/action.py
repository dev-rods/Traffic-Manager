import json
import boto3
import os
from datetime import datetime
from typing import Optional
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from src.services.google_ads_config import GoogleAdsConfig

dynamodb = boto3.resource("dynamodb")
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))
campaign_metadata_table = dynamodb.Table(os.environ.get("CAMPAIGN_METADATA_TABLE"))
clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))

def handler(event, context):
    trace_id = event.get("traceId", "unknown")
    client_id = event.get("clientId")
    stage = "GOOGLE_ADS_GET_CAMPAIGNS"
    timestamp = datetime.utcnow().isoformat()
    
    print(f"[traceId: {trace_id}] Iniciando busca de campanhas do Google Ads para cliente: {client_id}")
    try:
        if not client_id:
            raise ValueError("clientId é obrigatório")
        
        client_info = get_client_info(client_id)
        if not client_info:
            raise ValueError(f"Customer ID não encontrado para cliente: {client_id}")
        
        print(f"[traceId: {trace_id}] Customer ID encontrado: {client_info['googleAdsCustomerId']}")
        google_ads_customer_id = client_info['googleAdsCustomerId'].replace('-', '')
        googleads_client = create_google_ads_client(google_ads_customer_id)
        campaigns = get_campaigns_from_google_ads(googleads_client, google_ads_customer_id, trace_id)
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
                'campaigns': campaigns[:5]
            })
        }
        execution_history_table.put_item(Item=execution_record)
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'clientId': client_id,
            'googleAdsCustomerId': google_ads_customer_id,
            'stage': stage,
            'status': 'SUCCESS',
            'campaigns': campaigns,
            'total_campaigns': len(campaigns)
        }
        
        print(f"[traceId: {trace_id}] Busca de campanhas concluída com sucesso. Total: {len(campaigns)} campanhas")
        return response
        
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
            'clientId': client_id,
            'errorMsg': error_msg,
            'requestId': ex.request_id,
            'errorCode': ex.error.code().name,
            'payload': json.dumps({'error': error_msg})
        }
        execution_history_table.put_item(Item=error_record)
        return {
            'traceId': trace_id,
            'timestamp': timestamp,
            'status': 'ERROR',
            'error_type': 'GOOGLE_ADS_API_ERROR',
            'error': error_msg,
            'request_id': ex.request_id,
            'error_code': ex.error.code().name
        }
        
    except Exception as e:
        error_msg = str(e)
        print(f"[traceId: {trace_id}] Erro geral: {error_msg}")
        try:
            error_record = {
                'traceId': trace_id,
                'stageTm': f"{stage}#{timestamp}",
                'stage': stage,
                'status': 'ERROR',
                'timestamp': timestamp,
                'clientId': client_id if 'client_id' in locals() else 'unknown',
                'errorMsg': error_msg,
                'payload': json.dumps({'error': error_msg})
            }
            
            execution_history_table.put_item(Item=error_record)
        except Exception as inner_e:
            print(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        return {
            'traceId': trace_id,
            'timestamp': timestamp,
            'status': 'ERROR',
            'error_type': 'GENERAL_ERROR',
            'error': error_msg
        }


def get_client_info(client_id: str) -> Optional[str]:
    try:
        response = clients_table.get_item(Key={"clientId": client_id})
        if "Item" not in response:
            print(f"Cliente não encontrado no DynamoDB: {client_id}")
            return None
        client_data = response["Item"]
        return client_data
    except Exception as e:
        print(f"Erro ao buscar customer_id para cliente {client_id}: {str(e)}")
        return None


def create_google_ads_client(google_ads_customer_id: str) -> GoogleAdsClient:
    print(f"Criando Google Ads Client para cliente: {google_ads_customer_id}")
    ads_config = GoogleAdsConfig()
    config = ads_config.get_google_ads_config()
    try:
        googleads_client = GoogleAdsClient.load_from_dict(config, version="v20")
        
        print(f"Google Ads Client criado com sucesso para cliente: {google_ads_customer_id}")
        return googleads_client
    except Exception as e:
        print(f"Erro ao criar Google Ads Client: {str(e)}")
        raise


def get_campaigns_from_google_ads(client: GoogleAdsClient, customer_id: str, trace_id: str) -> list:
    print(f"[traceId: {trace_id}] Buscando campanhas para customer: {customer_id}")
    ga_service = client.get_service("GoogleAdsService")
    query = """
        SELECT
          campaign.id,
          campaign.name
        FROM campaign
        ORDER BY campaign.id"""
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    campaigns = []
    for batch in stream:
        for row in batch.results:
            campaign_data = {
                'id': row.campaign.id,
                'name': row.campaign.name
            }
            campaigns.append(campaign_data)
    print(f"[traceId: {trace_id}] Total de campanhas encontradas: {len(campaigns)}")
    return campaigns