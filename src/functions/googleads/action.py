"""
Google Ads Action Handler
Este módulo implementa as ações do Google Ads seguindo exatamente a documentação oficial:
https://github.com/googleads/google-ads-python/tree/1d2434e452e1c8f4e356ae2c8b0e261aaa5da640
Baseado no exemplo: get_campaigns.py da documentação oficial
"""

import json
import boto3
import os
from datetime import datetime
from typing import Optional
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from src.services.google_ads_config import GoogleAdsConfig

# Configurar logging seguindo a documentação do Google Ads
# DynamoDB resources
dynamodb = boto3.resource("dynamodb")
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))
campaign_metadata_table = dynamodb.Table(os.environ.get("CAMPAIGN_METADATA_TABLE"))
clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))

def handler(event, context):
    """
    Handler principal seguindo a documentação do Google Ads
    
    Este handler implementa o padrão da documentação oficial:
    1. Obter dados do cliente do event
    2. Configurar credenciais do Google Ads
    3. Criar cliente GoogleAds 
    4. Executar get_campaigns seguindo o exemplo da documentação
    
    Args:
        event: Evento Lambda contendo clientId e customerIds
        context: Contexto da execução Lambda
        
    Returns:
        dict: Resposta com campanhas encontradas
    """
    
    trace_id = event.get("traceId", "unknown")
    client_id = event.get("clientId")
    stage = "GOOGLE_ADS_GET_CAMPAIGNS"
    timestamp = datetime.utcnow().isoformat()
    
    print(f"[traceId: {trace_id}] Iniciando busca de campanhas do Google Ads para cliente: {client_id}")
    
    try:
        # Validar parâmetros obrigatórios
        if not client_id:
            raise ValueError("clientId é obrigatório")
        
        # Obter customer_id do cliente no DynamoDB
        client_info = get_client_info(client_id)
        if not client_info:
            raise ValueError(f"Customer ID não encontrado para cliente: {client_id}")
        
        print(f"[traceId: {trace_id}] Customer ID encontrado: {client_info['googleAdsCustomerId']}")
        # Remover hífens do customer ID se existirem (formato: 157-093-2315 -> 1570932315)
        google_ads_customer_id = client_info['googleAdsCustomerId'].replace('-', '')

        # Configurar Google Ads Client seguindo a documentação
        googleads_client = create_google_ads_client(google_ads_customer_id)
        
        # Executar get_campaigns seguindo exatamente o exemplo da documentação
        campaigns = get_campaigns_from_google_ads(googleads_client, google_ads_customer_id, trace_id)
        
        # Registrar execução bem-sucedida
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
        
        # Preparar resposta
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
        # Tratamento específico para erros do Google Ads (seguindo documentação)
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
        
        # Registrar erro específico do Google Ads
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
        
        # Registrar erro geral
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
    """
    Cria um cliente Google Ads seguindo exatamente a documentação oficial
    
    Equivalente ao exemplo:
    googleads_client = GoogleAdsClient.load_from_storage()
    
    Mas usando nossas configurações do SSM/DynamoDB
    
    Args:
        client_id (str): ID do cliente no sistema
        
    Returns:
        GoogleAdsClient: Cliente autenticado
        
    Raises:
        ValueError: Se configuração inválida
        GoogleAdsException: Se erro de autenticação
    """
    
    print(f"Criando Google Ads Client para cliente: {google_ads_customer_id}")
    
    # Usar nossa classe de configuração
    ads_config = GoogleAdsConfig()
    config = ads_config.get_google_ads_config(google_ads_customer_id)
    
    try:
        # Criar cliente seguindo a documentação
        # Equivalente a: GoogleAdsClient.load_from_storage() usando a versão padrão instalada
        googleads_client = GoogleAdsClient.load_from_dict(config, version="v20")
        
        print(f"Google Ads Client criado com sucesso para cliente: {google_ads_customer_id}")
        return googleads_client
        
    except Exception as e:
        print(f"Erro ao criar Google Ads Client: {str(e)}")
        raise


def get_campaigns_from_google_ads(client: GoogleAdsClient, customer_id: str, trace_id: str) -> list:
    """
    Busca campanhas seguindo EXATAMENTE o exemplo da documentação oficial
    
    Baseado em: 
    https://github.com/googleads/google-ads-python/blob/main/examples/basic_operations/get_campaigns.py
    
    Args:
        client (GoogleAdsClient): Cliente autenticado
        customer_id (str): ID do customer
        trace_id (str): ID de rastreamento
        
    Returns:
        list: Lista de campanhas encontradas
    """
    
    print(f"[traceId: {trace_id}] Buscando campanhas para customer: {customer_id}")
    
    # [START get_campaigns] - Seguindo exatamente a documentação
    ga_service = client.get_service("GoogleAdsService")

    query = """
        SELECT
          campaign.id,
          campaign.name
        FROM campaign
        ORDER BY campaign.id"""

    # Issues a search request using streaming. - Exatamente como na documentação
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    
    campaigns = []
    
    for batch in stream:
        for row in batch.results:
            # Log seguindo o formato da documentação
            print(
                f"Campaign with ID {row.campaign.id} and name "
                f'"{row.campaign.name}" was found.'
            )
            
            # Adicionar à lista de retorno
            campaign_data = {
                'id': row.campaign.id,
                'name': row.campaign.name
            }
            campaigns.append(campaign_data)
    # [END get_campaigns]
    
    print(f"[traceId: {trace_id}] Total de campanhas encontradas: {len(campaigns)}")
    return campaigns   