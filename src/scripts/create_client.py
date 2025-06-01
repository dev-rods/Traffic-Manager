"""
Script para criar um novo cliente

Este script cria um novo cliente com API key gerada automaticamente.
"""
import os
import boto3
import logging
from datetime import datetime
from src.utils.auth import ClientAuth
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
            
    Returns:
        dict: Dados do cliente criado
    """
    name = params.get("name")
    email = params.get("email")
    
    if not name or not email:
        raise ValueError("Nome e email são obrigatórios")
    
    logger.info(f"Criando cliente: {name} ({email})")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    client_auth = ClientAuth()
    
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
    
    # Salvar no DynamoDB
    clients_table.put_item(Item=client_data)
    
    logger.info(f"Cliente criado com sucesso: {client_id}")
    
    return {
        "clientId": client_id,
        "name": name,
        "email": email,
        "apiKey": api_key,
        "active": True,
        "createdAt": client_data["createdAt"]
    }

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