"""
Script para criar um novo cliente

Este script cria um novo cliente com API key gerada automaticamente
e configuração do Google Ads.
"""
import os
import boto3
import logging
from datetime import datetime
from src.utils.auth import ClientAuth
from src.utils.encryption import TokenEncryption
from src.utils.google_ads_validator import GoogleAdsTokenValidator
import hashlib

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute(params):
    """
    Executa a criação de um novo cliente
    
    Args:
        params (dict): Parâmetros do comando
            - name (str): Nome do cliente
            - email (str): Email do cliente
            - google_ads_config (dict, opcional): Configuração do Google Ads
                - developerId (str): ID do desenvolvedor (Customer ID)
                - clientId (str): Client ID do OAuth2
                - clientSecret (str): Client Secret do OAuth2
                - refreshToken (str): Refresh Token
                - developerToken (str): Developer Token
            - validate_google_ads (bool, opcional): Se deve validar tokens (padrão: True)
            
    Returns:
        dict: Dados do cliente criado
    """
    name = params.get("name")
    email = params.get("email")
    google_ads_config = params.get("google_ads_config")
    validate_google_ads = params.get("validate_google_ads", True)
    
    if not name or not email:
        raise ValueError("Nome e email são obrigatórios")
    
    logger.info(f"Criando cliente: {name} ({email})")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    client_auth = ClientAuth()
    
    # Validar e criptografar configuração do Google Ads se fornecida
    encrypted_google_ads_config = None
    google_ads_info = None
    
    if google_ads_config:
        logger.info("Validando configuração do Google Ads")
        
        # Validação básica de formato
        validator = GoogleAdsTokenValidator()
        format_validation = validator.validate_basic_format(google_ads_config)
        
        if not format_validation['valid']:
            raise ValueError(f"Configuração do Google Ads inválida: {'; '.join(format_validation['errors'])}")
        
        # Validação completa com chamada à API (se solicitado)
        if validate_google_ads:
            logger.info("Validando tokens com a API do Google Ads")
            api_validation = validator.validate_tokens(google_ads_config)
            
            if not api_validation['valid']:
                raise ValueError(f"Tokens do Google Ads inválidos: {api_validation['error']}")
            
            google_ads_info = api_validation.get('customer_info')
            logger.info(f"Tokens validados para conta: {google_ads_info.get('descriptive_name', 'N/A')}")
        
        # Criptografar tokens sensíveis
        encryption = TokenEncryption()
        encrypted_google_ads_config = encryption.encrypt_google_ads_config(google_ads_config)
        logger.info("Tokens do Google Ads criptografados com sucesso")
    
    # Gerar ID e API key
    client_id = _generate_client_id(name)
    api_key = client_auth.generate_api_key()
    
    # Dados do cliente
    client_data = {
        "clientId": client_id,
        "name": name,
        "email": email,
        "apiKey": api_key,
        "active": True,
        "createdAt": datetime.utcnow().isoformat()
    }
    
    # Adicionar configuração do Google Ads se fornecida
    if encrypted_google_ads_config:
        client_data["googleAdsConfig"] = encrypted_google_ads_config
        
        # Adicionar informações da conta se validada
        if google_ads_info:
            client_data["googleAdsInfo"] = {
                "customerId": google_ads_info["customer_id"],
                "currencyCode": google_ads_info["currency_code"],
                "timeZone": google_ads_info["time_zone"],
                "descriptiveName": google_ads_info["descriptive_name"],
                "validatedAt": datetime.utcnow().isoformat()
            }
    
    # Salvar no DynamoDB
    clients_table.put_item(Item=client_data)
    
    logger.info(f"Cliente criado com sucesso: {client_id}")
    
    # Preparar resposta (sem tokens sensíveis)
    response = {
        "clientId": client_id,
        "name": name,
        "email": email,
        "apiKey": api_key,
        "active": True,
        "createdAt": client_data["createdAt"]
    }
    
    # Incluir informações do Google Ads se disponíveis (sem tokens)
    if google_ads_info:
        response["googleAdsInfo"] = client_data["googleAdsInfo"]
        response["googleAdsConfigured"] = True
    else:
        response["googleAdsConfigured"] = False
    
    return response

def _generate_client_id(client_name):
    """
    Gera um ID do cliente baseado no nome
    
    Args:
        client_name (str): Nome do cliente
        
    Returns:
        str: ID gerado
    """
    base = "".join(e for e in client_name if e.isalnum()).lower()
    hash_suffix = hashlib.md5(client_name.encode()).hexdigest()[:6]
    return f"{base}-{hash_suffix}" 