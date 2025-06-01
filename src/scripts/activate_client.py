"""
Script para ativar um cliente

Este script ativa um cliente previamente desativado.
"""
import os
import boto3
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute(params):
    """
    Executa a ativação de um cliente
    
    Args:
        params (dict): Parâmetros do comando
            - clientId (str): ID do cliente
            
    Returns:
        dict: Dados do cliente atualizado
    """
    client_id = params.get("clientId")
    
    if not client_id:
        raise ValueError("ID do cliente é obrigatório")
    
    logger.info(f"Ativando cliente: {client_id}")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    # Verificar se o cliente existe
    response = clients_table.get_item(Key={"clientId": client_id})
    
    if "Item" not in response:
        raise ValueError(f"Cliente com ID '{client_id}' não encontrado")
    
    client = response["Item"]
    
    # Atualizar status para ativo
    result = clients_table.update_item(
        Key={"clientId": client_id},
        UpdateExpression="set active = :active, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":active": True,
            ":updatedAt": datetime.utcnow().isoformat()
        },
        ReturnValues="ALL_NEW"
    )
    
    updated_client = result.get("Attributes", {})
    
    logger.info(f"Cliente ativado com sucesso: {client_id}")
    
    # Remover API key do retorno por segurança
    client_safe = {k: v for k, v in updated_client.items() if k != "apiKey"}
    
    return {
        "message": f"Cliente '{client.get('name')}' ativado com sucesso",
        "client": client_safe
    } 