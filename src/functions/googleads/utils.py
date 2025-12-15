"""
Funções utilitárias compartilhadas para operações do Google Ads
"""
import os
import boto3
from typing import Optional, Dict, Any
from google.ads.googleads.client import GoogleAdsClient
from src.services.google_ads_config import GoogleAdsConfig
from src.utils.http import extract_path_param, extract_query_param, parse_body

dynamodb = boto3.resource("dynamodb")
clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))


def get_client_info(client_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca informações do cliente no DynamoDB
    
    Args:
        client_id: ID do cliente no sistema
        
    Returns:
        Dicionário com informações do cliente ou None se não encontrado
    """
    try:
        response = clients_table.get_item(Key={"clientId": client_id})
        if "Item" not in response:
            print(f"Cliente não encontrado no DynamoDB: {client_id}")
            return None
        client_data = response["Item"]
        return client_data
    except Exception as e:
        print(f"Erro ao buscar informações do cliente {client_id}: {str(e)}")
        return None


def validate_client(client_id: str) -> Dict[str, Any]:
    """
    Valida se o cliente existe e tem configuração do Google Ads
    
    Args:
        client_id: ID do cliente no sistema
        
    Returns:
        Dicionário com status da validação e dados do cliente se válido
        
    Raises:
        ValueError: Se o cliente não for encontrado ou não tiver configuração
    """
    if not client_id:
        raise ValueError("clientId é obrigatório")
    
    client_info = get_client_info(client_id)
    if not client_info:
        raise ValueError(f"Cliente não encontrado: {client_id}")
    
    if "googleAdsCustomerId" not in client_info or not client_info["googleAdsCustomerId"]:
        raise ValueError(f"Cliente {client_id} não possui Google Ads Customer ID configurado")
    
    return client_info


def create_google_ads_client() -> GoogleAdsClient:
    """
    Cria um cliente do Google Ads
    
    Returns:
        Instância do GoogleAdsClient
        
    Raises:
        Exception: Se houver erro ao criar o cliente
    """
    print(f"Criando Google Ads Client")
    ads_config = GoogleAdsConfig()
    config = ads_config.get_google_ads_config()
    
    try:
        googleads_client = GoogleAdsClient.load_from_dict(config, version="v20")
        print(f"Google Ads Client criado com sucesso")
        return googleads_client
    except Exception as e:
        print(f"Erro ao criar Google Ads Client: {str(e)}")
        raise


def get_campaigns_from_google_ads(client: GoogleAdsClient, customer_id: str, trace_id: str) -> list:
    """
    Busca todas as campanhas de um cliente do Google Ads
    
    Args:
        client: Instância do GoogleAdsClient
        customer_id: ID do cliente do Google Ads (sem hífens)
        trace_id: ID de rastreamento para logs
        
    Returns:
        Lista de dicionários com informações das campanhas
    """
    print(f"[traceId: {trace_id}] Buscando campanhas para customer: {customer_id}")
    ga_service = client.get_service("GoogleAdsService")
    query = """
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign.start_date,
          campaign.end_date
        FROM campaign
        ORDER BY campaign.id"""
    
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    campaigns = []
    for batch in stream:
        for row in batch.results:
            campaign_data = {
                'id': row.campaign.id,
                'name': row.campaign.name,
                'status': row.campaign.status.name if row.campaign.status else None,
                'advertising_channel_type': row.campaign.advertising_channel_type.name if row.campaign.advertising_channel_type else None,
                'start_date': row.campaign.start_date if hasattr(row.campaign, 'start_date') and row.campaign.start_date else None,
                'end_date': row.campaign.end_date if hasattr(row.campaign, 'end_date') and row.campaign.end_date else None
            }
            campaigns.append(campaign_data)
    
    print(f"[traceId: {trace_id}] Total de campanhas encontradas: {len(campaigns)}")
    return campaigns


def get_campaign_from_google_ads(client: GoogleAdsClient, customer_id: str, campaign_id: int, trace_id: str) -> Optional[Dict[str, Any]]:
    """
    Busca uma campanha específica com métricas de CPA e CPC
    
    Args:
        client: Instância do GoogleAdsClient
        customer_id: ID do cliente do Google Ads (sem hífens)
        campaign_id: ID da campanha
        trace_id: ID de rastreamento para logs
        
    Returns:
        Dicionário com informações da campanha incluindo métricas de CPA e CPC
    """
    print(f"[traceId: {trace_id}] Buscando campanha {campaign_id} para customer: {customer_id}")
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
          campaign.id,
          campaign.name,
          campaign.status,
          campaign.advertising_channel_type,
          campaign.start_date,
          campaign.end_date,
          metrics.cost_per_conversion,
          metrics.average_cpc
        FROM campaign
        WHERE campaign.id = {campaign_id}"""
    
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    for batch in stream:
        for row in batch.results:
            # Converter micros para valores decimais
            cost_per_conversion = None
            if hasattr(row, 'metrics') and hasattr(row.metrics, 'cost_per_conversion'):
                if row.metrics.cost_per_conversion is not None:
                    cost_per_conversion = float(row.metrics.cost_per_conversion) / 1_000_000
            
            average_cpc = None
            if hasattr(row, 'metrics') and hasattr(row.metrics, 'average_cpc'):
                if row.metrics.average_cpc is not None:
                    average_cpc = float(row.metrics.average_cpc) / 1_000_000
            
            campaign_data = {
                'id': row.campaign.id,
                'name': row.campaign.name,
                'status': row.campaign.status.name if row.campaign.status else None,
                'advertising_channel_type': row.campaign.advertising_channel_type.name if row.campaign.advertising_channel_type else None,
                'start_date': row.campaign.start_date if hasattr(row.campaign, 'start_date') and row.campaign.start_date else None,
                'end_date': row.campaign.end_date if hasattr(row.campaign, 'end_date') and row.campaign.end_date else None,
                'cpa': cost_per_conversion,
                'cpc': average_cpc,
            }
            print(f"[traceId: {trace_id}] Campanha encontrada: {campaign_data['name']} - CPA: {cost_per_conversion}, CPC: {average_cpc}")
            return campaign_data
    
    print(f"[traceId: {trace_id}] Campanha {campaign_id} não encontrada")
    return None


def get_ad_groups_metrics_from_google_ads(client: GoogleAdsClient, customer_id: str, campaign_id: int, trace_id: str) -> list:
    """
    Busca métricas de CPA e CPC de todos os grupos de anúncios de uma campanha
    
    Args:
        client: Instância do GoogleAdsClient
        customer_id: ID do cliente do Google Ads (sem hífens)
        campaign_id: ID da campanha
        trace_id: ID de rastreamento para logs
        
    Returns:
        Lista de dicionários com informações dos grupos de anúncios incluindo métricas de CPA e CPC
    """
    print(f"[traceId: {trace_id}] Buscando métricas de grupos de anúncios para campanha {campaign_id}")
    ga_service = client.get_service("GoogleAdsService")
    query = f"""
        SELECT
          ad_group.id,
          ad_group.name,
          ad_group.status,
          metrics.cost_per_conversion,
          metrics.average_cpc
        FROM ad_group
        WHERE campaign.id = {campaign_id}
          AND ad_group.status != 'REMOVED'
        ORDER BY ad_group.id"""
    
    stream = ga_service.search_stream(customer_id=customer_id, query=query)
    ad_groups = []
    for batch in stream:
        for row in batch.results:
            # Converter micros para valores decimais
            cost_per_conversion = None
            if hasattr(row, 'metrics') and hasattr(row.metrics, 'cost_per_conversion'):
                if row.metrics.cost_per_conversion is not None:
                    cost_per_conversion = float(row.metrics.cost_per_conversion) / 1_000_000
            
            average_cpc = None
            if hasattr(row, 'metrics') and hasattr(row.metrics, 'average_cpc'):
                if row.metrics.average_cpc is not None:
                    average_cpc = float(row.metrics.average_cpc) / 1_000_000
            
            ad_group_data = {
                'id': row.ad_group.id,
                'name': row.ad_group.name,
                'status': row.ad_group.status.name if row.ad_group.status else None,
                'cpa': cost_per_conversion,
                'cpc': average_cpc,
            }
            ad_groups.append(ad_group_data)
    
    print(f"[traceId: {trace_id}] Total de grupos de anúncios encontrados: {len(ad_groups)}")
    return ad_groups


def extract_client_id(event: Dict[str, Any], body: Optional[Dict[str, Any]] = None) -> Optional[str]:
    client_id = extract_path_param(event, "clientId")
    if client_id:
        return client_id
    
    client_id = extract_query_param(event, "clientId")
    if client_id:
        return client_id
    
    if body and isinstance(body, dict) and "clientId" in body:
        return body["clientId"]
    
    body_parsed = parse_body(event)
    if body_parsed and isinstance(body_parsed, dict) and "clientId" in body_parsed:
        return body_parsed["clientId"]
    
    return None