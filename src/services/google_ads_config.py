"""
Serviço de configuração do Google Ads

Este módulo gerencia as configurações do Google Ads seguindo exatamente
o padrão da documentação oficial, criando dinamicamente o arquivo de configuração
que seria equivalente ao google-ads.yaml
"""

import os
import boto3
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class GoogleAdsConfig:
    """
    Classe para gerenciar configurações do Google Ads seguindo a documentação oficial
    
    Esta classe replica a funcionalidade do arquivo google-ads.yaml mencionado
    na documentação, mas usando variáveis de ambiente e DynamoDB.
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    def get_google_ads_config(self, customer_id: Optional[str] = None) -> Dict[str, str]:
        """
        Retorna configuração do Google Ads seguindo o formato da documentação
        
        Equivalente ao arquivo google-ads.yaml mencionado na documentação:
        https://github.com/googleads/google-ads-python/tree/1d2434e452e1c8f4e356ae2c8b0e261aaa5da640
        
        Args:
            customer_id (str, opcional): ID do customer específico
            
        Returns:
            dict: Configuração no formato esperado pelo GoogleAdsClient.load_from_dict()
        """
        
        # Configuração base do SSM (credenciais globais)
        config = {
            # Developer token - obrigatório para todas as requisições
            'developer_token': os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN'),
            
            # OAuth2 configuration - método recomendado na documentação
            'client_id': os.environ.get('GOOGLE_ADS_CLIENT_ID'),
            'client_secret': os.environ.get('GOOGLE_ADS_CLIENT_SECRET'),
            'refresh_token': os.environ.get('GOOGLE_ADS_REFRESH_TOKEN'),
            
            # Use proto plus - conforme documentação
            'use_proto_plus': True,
            
            # Login customer ID - obrigatório para contas de gerente
            'login_customer_id': os.environ.get('GOOGLE_ADS_LOGIN_CUSTOMER_ID')
        }
        
        # Validar configurações obrigatórias
        required_fields = ['developer_token', 'client_id', 'client_secret', 'refresh_token']
        missing_fields = [field for field in required_fields if not config.get(field)]
        
        if missing_fields:
            raise ValueError(f"Configurações obrigatórias ausentes no SSM: {missing_fields}")
        
        # Remover campos None para evitar problemas no cliente
        config = {k: v for k, v in config.items() if v is not None}
        
        logger.info("Configuração do Google Ads carregada com sucesso")
        return config
    
    def get_customer_specific_config(self, client_id: str, customer_id: str) -> Dict[str, str]:
        """
        Obtém configuração específica de um cliente/customer
        
        Busca configurações específicas no DynamoDB que podem sobrescrever
        as configurações globais do SSM.
        
        Args:
            client_id (str): ID do cliente no sistema
            customer_id (str): Customer ID do Google Ads
            
        Returns:
            dict: Configuração mesclada (global + específica do cliente)
        """
        
        # Começar com configuração base
        config = self.get_google_ads_config()
        
        try:
            # Buscar configurações específicas do cliente
            response = self.clients_table.get_item(Key={"clientId": client_id})
            
            if "Item" in response:
                client_data = response["Item"]
                
                # Se existe configuração específica do Google Ads para este cliente
                if "googleAdsConfig" in client_data:
                    client_google_config = client_data["googleAdsConfig"]
                    
                    # Sobrescrever configurações específicas do cliente
                    # (mantendo as globais como fallback)
                    if "customerSpecific" in client_google_config:
                        customer_config = client_google_config["customerSpecific"]
                        config.update(customer_config)
                    
                    logger.info(f"Configuração específica carregada para cliente: {client_id}")
                
        except Exception as e:
            logger.warning(f"Erro ao carregar configuração específica do cliente {client_id}: {str(e)}")
            # Continuar com configuração global em caso de erro
        
        return config
    
    def validate_config(self, config: Dict[str, str]) -> bool:
        """
        Valida se a configuração está correta segundo a documentação
        
        Args:
            config (dict): Configuração a ser validada
            
        Returns:
            bool: True se válida, False caso contrário
        """
        
        required_oauth_fields = [
            'developer_token',
            'client_id', 
            'client_secret',
            'refresh_token'
        ]
        
        for field in required_oauth_fields:
            if not config.get(field):
                logger.error(f"Campo obrigatório ausente: {field}")
                return False
        
        # Validar formato do developer_token (deve começar com letras/números)
        dev_token = config.get('developer_token', '')
        if not dev_token or len(dev_token) < 10:
            logger.error("Developer token inválido")
            return False
        
        # Validar se use_proto_plus é boolean
        if 'use_proto_plus' in config and not isinstance(config['use_proto_plus'], bool):
            logger.error("use_proto_plus deve ser boolean")
            return False
        
        logger.info("Configuração Google Ads validada com sucesso")
        return True
    
    def get_config_summary(self, config: Dict[str, str]) -> Dict[str, str]:
        """
        Retorna um resumo da configuração (sem dados sensíveis) para logs
        
        Args:
            config (dict): Configuração original
            
        Returns:
            dict: Resumo seguro da configuração
        """
        
        summary = {}
        
        # Campos que podem ser mostrados (mascarados)
        if config.get('developer_token'):
            summary['developer_token'] = config['developer_token'][:8] + "***"
        
        if config.get('client_id'):
            summary['client_id'] = config['client_id'][:10] + "***"
        
        summary['use_proto_plus'] = config.get('use_proto_plus', True)
        summary['has_refresh_token'] = bool(config.get('refresh_token'))
        summary['has_client_secret'] = bool(config.get('client_secret'))
        
        if config.get('login_customer_id'):
            summary['login_customer_id'] = config['login_customer_id']
        
        return summary 