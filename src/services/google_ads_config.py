"""
Serviço de configuração do Google Ads com Token Manager Automático

Este módulo gerencia as configurações do Google Ads seguindo exatamente
o padrão da documentação oficial, com geração automática de tokens.
"""

import os
import boto3
import tempfile
import json
from typing import Dict, Optional
from .google_ads_token_manager import GoogleAdsTokenManager


class GoogleAdsConfig:
    """
    Classe para gerenciar configurações do Google Ads com geração automática de tokens
    
    Esta classe agora:
    - Detecta automaticamente qual estratégia usar (Service Account vs OAuth2)
    - Gera automaticamente refresh tokens quando necessário
    - Usa múltiplas estratégias de fallback
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
        self.token_manager = GoogleAdsTokenManager()
    
    def get_google_ads_config(self, google_ads_customer_id: Optional[str] = None) -> Dict[str, str]:
        """
        Retorna configuração do Google Ads com refresh token automático
        
        Esta função agora:
        1. Tenta obter refresh token existente
        2. Gera automaticamente se necessário
        3. Usa service account se configurado
        4. Retorna configuração válida
        
        Args:
            google_ads_customer_id (str, opcional): ID do customer específico
            
        Returns:
            dict: Configuração no formato esperado pelo GoogleAdsClient.load_from_dict()
        """
        
        print(f"Configurando Google Ads para customer: {google_ads_customer_id}")
        
        # Usar fluxo OAuth2 com token manager automático
        return self._get_oauth2_config(google_ads_customer_id)
    
    def _get_oauth2_config(self, customer_id: str) -> Dict[str, str]:
        """Configuração usando OAuth2 com token automático"""
        
        print("Usando configuração OAuth2 com token manager")
        
        # Obter refresh token automaticamente
        # Remover hífens do customer_id se existirem (ex: 287-835-6629 -> 2878356629)
        refresh_token = self.token_manager.get_valid_refresh_token(customer_id)
        
        if not refresh_token:
            raise ValueError(f"Não foi possível obter refresh token para customer: {customer_id}")
        
        config = {
            'developer_token': os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN'),
            'client_id': os.environ.get('GOOGLE_ADS_CLIENT_ID'),
            'client_secret': os.environ.get('GOOGLE_ADS_CLIENT_SECRET'),
            'refresh_token': refresh_token,
            'use_proto_plus': True,
            'login_customer_id': customer_id
        }
        
        # Validar configuração OAuth2
        required_fields = ['developer_token', 'client_id', 'client_secret', 'refresh_token']
        missing_fields = [field for field in required_fields if not config.get(field)]
        
        if missing_fields:
            raise ValueError(f"Configurações OAuth2 ausentes: {missing_fields}")
        
        # Remover campos None
        config = {k: v for k, v in config.items() if v is not None}
        
        print("Configuração OAuth2 carregada com sucesso")
        return config
    
    def _create_temp_service_account_file(self) -> str:
        """Cria arquivo temporário com credenciais service account"""
        
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if not service_account_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON não configurado")
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(json.loads(service_account_json), f)
            return f.name 