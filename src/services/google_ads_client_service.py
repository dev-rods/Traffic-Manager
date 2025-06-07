"""
Serviço para gerenciar clientes do Google Ads

Este serviço cria e gerencia clientes autenticados do Google Ads
baseado nos tokens específicos de cada cliente.
"""
import os
import boto3
import logging
from google.ads.googleads.client import GoogleAdsClient
from google.ads.googleads.errors import GoogleAdsException
from src.utils.encryption import TokenEncryption

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class GoogleAdsClientService:
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
        self.encryption = TokenEncryption()
        self._client_cache = {}
    
    def get_client_for_customer(self, client_id):
        """
        Obtém um cliente autenticado do Google Ads para um cliente específico
        
        Args:
            client_id (str): ID do cliente no sistema
            
        Returns:
            tuple: (GoogleAdsClient, customer_id) ou (None, None) se não configurado
        """
        try:
            # Verificar cache primeiro
            if client_id in self._client_cache:
                return self._client_cache[client_id]
            
            # Buscar dados do cliente
            response = self.clients_table.get_item(Key={"clientId": client_id})
            
            if "Item" not in response:
                logger.error(f"Cliente não encontrado: {client_id}")
                return None, None
            
            client_data = response["Item"]
            
            # Verificar se tem configuração do Google Ads
            if "googleAdsConfig" not in client_data:
                logger.warning(f"Cliente {client_id} não tem configuração do Google Ads")
                return None, None
            
            # Descriptografar configuração
            encrypted_config = client_data["googleAdsConfig"]
            config = self.encryption.decrypt_google_ads_config(encrypted_config)
            
            # Criar cliente do Google Ads
            google_ads_config = {
                'developer_token': config['developerToken'],
                'client_id': config['clientId'],
                'client_secret': config['clientSecret'],
                'refresh_token': config['refreshToken'],
                'use_proto_plus': True
            }
            
            google_ads_client = GoogleAdsClient.load_from_dict(google_ads_config)
            customer_id = config['developerId']
            
            # Armazenar no cache
            self._client_cache[client_id] = (google_ads_client, customer_id)
            
            logger.info(f"Cliente Google Ads criado com sucesso para {client_id}")
            return google_ads_client, customer_id
            
        except Exception as e:
            logger.error(f"Erro ao criar cliente Google Ads para {client_id}: {str(e)}")
            return None, None
    
    def validate_client_access(self, client_id):
        """
        Valida se o cliente tem acesso válido ao Google Ads
        
        Args:
            client_id (str): ID do cliente no sistema
            
        Returns:
            dict: Resultado da validação
                - valid (bool): Se o acesso é válido
                - error (str): Mensagem de erro se inválido
                - customer_info (dict): Informações do cliente se válido
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)
            
            if not google_ads_client:
                return {
                    'valid': False,
                    'error': 'Cliente não configurado para Google Ads'
                }
            
            # Fazer uma chamada simples para validar o acesso
            customer_service = google_ads_client.get_service("CustomerService")
            customer = customer_service.get_customer(customer_id=customer_id)
            
            customer_info = {
                'customer_id': customer_id,
                'currency_code': customer.currency_code,
                'time_zone': customer.time_zone,
                'descriptive_name': customer.descriptive_name if customer.descriptive_name else 'N/A'
            }
            
            return {
                'valid': True,
                'customer_info': customer_info
            }
            
        except GoogleAdsException as ex:
            error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
            if ex.error.message:
                error_msg += f" - {ex.error.message}"
            
            return {
                'valid': False,
                'error': error_msg
            }
            
        except Exception as e:
            return {
                'valid': False,
                'error': f"Erro na validação: {str(e)}"
            }
    
    def clear_cache(self, client_id=None):
        """
        Limpa o cache de clientes
        
        Args:
            client_id (str, opcional): ID específico para limpar, ou None para limpar tudo
        """
        if client_id:
            self._client_cache.pop(client_id, None)
            logger.info(f"Cache limpo para cliente: {client_id}")
        else:
            self._client_cache.clear()
            logger.info("Cache de clientes Google Ads limpo completamente")
    
    def get_customer_campaigns(self, client_id, limit=50):
        """
        Obtém campanhas do cliente no Google Ads
        
        Args:
            client_id (str): ID do cliente no sistema
            limit (int): Limite de campanhas a retornar
            
        Returns:
            list: Lista de campanhas ou lista vazia se erro
        """
        try:
            google_ads_client, customer_id = self.get_client_for_customer(client_id)
            
            if not google_ads_client:
                logger.error(f"Cliente {client_id} não configurado para Google Ads")
                return []
            
            # Buscar campanhas
            ga_service = google_ads_client.get_service("GoogleAdsService")
            
            query = f"""
                SELECT 
                    campaign.id,
                    campaign.name,
                    campaign.status,
                    campaign.advertising_channel_type,
                    metrics.impressions,
                    metrics.clicks,
                    metrics.cost_micros
                FROM campaign 
                WHERE campaign.status != 'REMOVED'
                LIMIT {limit}
            """
            
            search_request = google_ads_client.get_type("SearchGoogleAdsRequest")
            search_request.customer_id = customer_id
            search_request.query = query
            
            response = ga_service.search(request=search_request)
            
            campaigns = []
            for row in response:
                campaign = {
                    'id': row.campaign.id,
                    'name': row.campaign.name,
                    'status': row.campaign.status.name,
                    'type': row.campaign.advertising_channel_type.name,
                    'metrics': {
                        'impressions': row.metrics.impressions,
                        'clicks': row.metrics.clicks,
                        'cost': row.metrics.cost_micros / 1000000  # Converter de micros para unidade
                    }
                }
                campaigns.append(campaign)
            
            logger.info(f"Encontradas {len(campaigns)} campanhas para cliente {client_id}")
            return campaigns
            
        except Exception as e:
            logger.error(f"Erro ao buscar campanhas para cliente {client_id}: {str(e)}")
            return [] 