"""
Script para regenerar API key de um cliente

Este script regenera a API key de um cliente existente.
"""
import os
import boto3
import logging
from datetime import datetime
from src.utils.auth import ClientAuth

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute(params):
    """
    Executa a regeneração de API key de um cliente
    
    Args:
        params (dict): Parâmetros do comando
            - clientId (str): ID do cliente
            
    Returns:
        dict: Dados do cliente com nova API key
    """
    client_id = params.get("clientId")
    
    if not client_id:
        raise ValueError("ID do cliente é obrigatório")
    
    logger.info(f"Regenerando API key para cliente: {client_id}")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    client_auth = ClientAuth()
    
    # Verificar se o cliente existe
    response = clients_table.get_item(Key={"clientId": client_id})
    
    if "Item" not in response:
        raise ValueError(f"Cliente com ID '{client_id}' não encontrado")
    
    client = response["Item"]
    
    # Gerar nova API key
    new_api_key = client_auth.generate_api_key()
    
    # Atualizar no DynamoDB
    clients_table.update_item(
        Key={"clientId": client_id},
        UpdateExpression="set apiKey = :apiKey, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":apiKey": new_api_key,
            ":updatedAt": datetime.utcnow().isoformat()
        }
    )
    
    logger.info(f"API key regenerada com sucesso para cliente: {client_id}")
    
    return {
        "clientId": client_id,
        "name": client.get("name"),
        "email": client.get("email"),
        "apiKey": new_api_key,
        "updatedAt": datetime.utcnow().isoformat()
    } 