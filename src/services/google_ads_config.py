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
        config = {
            'developer_token': os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN'),
            'client_id': os.environ.get('OAUTH2_CLIENT_ID'),
            'client_secret': os.environ.get('OAUTH2_CLIENT_SECRET'),
            'refresh_token': os.environ.get('GOOGLE_ADS_REFRESH_TOKEN'),
            'use_proto_plus': True,
            'login_customer_id': google_ads_customer_id
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

        """Cria arquivo temporário com credenciais service account"""
        
        service_account_json = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if not service_account_json:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON não configurado")
        
        # Criar arquivo temporário
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(json.loads(service_account_json), f)
            return f.name 