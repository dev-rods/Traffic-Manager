"""
Script para desativar um cliente

Este script desativa um cliente, impedindo o uso da API.
"""
import os
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute(params):
    """
    Executa a desativação de um cliente
    
    Args:
        params (dict): Parâmetros do comando
            - clientId (str): ID do cliente
            
    Returns:
        dict: Dados do cliente atualizado
    """
    client_id = params.get("clientId")
    
    if not client_id:
        raise ValueError("ID do cliente é obrigatório")
    
    logger.info(f"Desativando cliente: {client_id}")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    # Verificar se o cliente existe
    response = clients_table.get_item(Key={"clientId": client_id})
    
    if "Item" not in response:
        raise ValueError(f"Cliente com ID '{client_id}' não encontrado")
    
    client = response["Item"]
    
    # Atualizar status para inativo
    result = clients_table.update_item(
        Key={"clientId": client_id},
        UpdateExpression="set active = :active, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":active": False,
            ":updatedAt": datetime.utcnow().isoformat()
        },
        ReturnValues="ALL_NEW"
    )
    
    updated_client = result.get("Attributes", {})
    
    logger.info(f"Cliente desativado com sucesso: {client_id}")
    
    # Remover API key do retorno por segurança
    client_safe = {k: v for k, v in updated_client.items() if k != "apiKey"}
    
    return {
        "message": f"Cliente '{client.get('name')}' desativado com sucesso",
        "client": client_safe
    } 