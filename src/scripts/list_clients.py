"""
Script para listar todos os clientes

Este script retorna uma lista de todos os clientes cadastrados.
"""
import os
import boto3
import logging

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute(params):
    """
    Executa a listagem de clientes
    
    Args:
        params (dict): Parâmetros do comando (opcionais)
            - active_only (bool): Se True, lista apenas clientes ativos
            
    Returns:
        dict: Lista de clientes e estatísticas
    """
    active_only = params.get("active_only", False)
    
    logger.info(f"Listando clientes (ativos apenas: {active_only})")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    # Buscar clientes
    response = clients_table.scan()
    clients = response.get("Items", [])
    
    # Filtrar por status se necessário
    if active_only:
        clients = [client for client in clients if client.get("active", False)]
    
    # Calcular estatísticas
    total_clients = len(clients)
    active_clients = len([c for c in clients if c.get("active", False)])
    inactive_clients = total_clients - active_clients
    
    # Remover API keys dos resultados por segurança
    clients_safe = []
    for client in clients:
        client_safe = {k: v for k, v in client.items() if k != "apiKey"}
        clients_safe.append(client_safe)
    
    logger.info(f"Clientes encontrados: {total_clients} (ativos: {active_clients}, inativos: {inactive_clients})")
    
    return {
        "clients": clients_safe,
        "statistics": {
            "total": total_clients,
            "active": active_clients,
            "inactive": inactive_clients
        }
    } 