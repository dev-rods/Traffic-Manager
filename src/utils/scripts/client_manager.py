"""
Script para gerenciamento de clientes
Permite criar, listar, ativar, desativar clientes e regenerar API keys
"""
import json
import boto3
import os
import logging
import secrets
import hashlib
from boto3.dynamodb.conditions import Key
from datetime import datetime
from src.utils.auth import ClientAuth


logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")


def create_client(params):
    """
    Cria um novo cliente com uma API key gerada

    Args:
        params (dict): Parâmetros do cliente
            - name (str): Nome do cliente
            - email (str): Email do cliente

    Returns:
        dict: Dados do cliente criado
    """
    name = params.get("name")
    email = params.get("email")
    if not name or not email:
        raise ValueError("Nome e email são obrigatórios")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    client_id = _generate_client_id(name)
    api_key = ClientAuth().generate_api_key()
    client_data = {
        "clientId": client_id,
        "name": name,
        "email": email,
        "apiKey": api_key,
        "active": True,
        "createdAt": datetime.utcnow().isoformat()
    }
    clients_table.put_item(Item=client_data)
    return client_data


def list_clients(params=None):
    """
    Lista todos os clientes

    Args:
        params (dict, optional): Parâmetros opcionais de filtro

    Returns:
        list: Lista de clientes
    """
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    result = clients_table.scan()
    return result.get("Items", [])


def regenerate_key(params):
    """
    Regenera a API key de um cliente

    Args:
        params (dict): Parâmetros
            - clientId (str): ID do cliente

    Returns:
        dict: Cliente com nova API key
    """
    client_id = params.get("clientId")
    if not client_id:
        raise ValueError("ID do cliente é obrigatório")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    client = get_client({"clientId": client_id})
    new_api_key = ClientAuth().generate_api_key()
    result = clients_table.update_item(
        Key={"clientId": client_id},
        UpdateExpression="set apiKey = :apiKey, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":apiKey": new_api_key,
            ":updatedAt": datetime.utcnow().isoformat()
        },
        ReturnValues="ALL_NEW"
    )
    return {
        "clientId": client_id,
        "name": client.get("name"),
        "apiKey": new_api_key
    }


def update_client_status(params):
    """
    Ativa ou desativa um cliente

    Args:
        params (dict): Parâmetros
            - clientId (str): ID do cliente
            - active (bool): Status de ativação

    Returns:
        dict: Cliente atualizado
    """
    client_id = params.get("clientId")
    active = params.get("active")
    
    if client_id is None or active is None:
        raise ValueError("ID do cliente e status são obrigatórios")
    
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    # Verificar se o cliente existe
    get_client({"clientId": client_id})
    
    # Atualizar status
    result = clients_table.update_item(
        Key={"clientId": client_id},
        UpdateExpression="set active = :active, updatedAt = :updatedAt",
        ExpressionAttributeValues={
            ":active": active,
            ":updatedAt": datetime.utcnow().isoformat()
        },
        ReturnValues="ALL_NEW"
    )
    
    return result.get("Attributes", {})


def get_client(params):
    """
    Obtém um cliente pelo ID

    Args:
        params (dict): Parâmetros
            - clientId (str): ID do cliente

    Returns:
        dict: Dados do cliente
    """
    client_id = params.get("clientId")
    if not client_id:
        raise ValueError("ID do cliente é obrigatório")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    result = clients_table.get_item(Key={"clientId": client_id})
    if "Item" not in result:
        raise ValueError(f"Cliente com ID "{client_id}" não encontrado")
    return result["Item"]


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