"""
Script para criar um novo cliente com integração MCC automática
"""
import os
import boto3
import logging
from datetime import datetime
import hashlib
import sys
from pathlib import Path

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from services.google_ads_mcc_service import GoogleAdsMCCService


def execute(params):
    """
    Args:
        params (dict): Parâmetros do comando
            - name (str): Nome do cliente
            - email (str): Email do cliente
            - googleAdsCustomerId (str): ID do cliente no Google Ads
            - sendMccInvitation (bool, opcional): Se deve enviar convite MCC automaticamente
    Returns:
        dict: Dados do cliente criado
    """
    print("params = ", params)
    name = params.get("name")
    email = params.get("email")
    googleAdsCustomerId = params.get("googleAdsCustomerId")
    send_mcc_invitation = params.get("sendMccInvitation", True)  # Padrão: True
    
    if not name or not email or not googleAdsCustomerId:
        raise ValueError("Nome, email e googleAdsCustomerId são obrigatórios")
    
    print(f"Criando cliente: {name} ({email})")
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))

    # Gerar ID e API key
    client_id = _generate_client_id(name)
    
    # Dados do cliente
    client_data = {
        "clientId": client_id,
        "name": name,
        "email": email,
        "active": True,
        "createdAt": datetime.utcnow().isoformat(),
        "googleAdsCustomerId": googleAdsCustomerId,
        "mccStatus": "NOT_LINKED"  # Status inicial da associação MCC
    }
    
    # Salvar no DynamoDB
    clients_table.put_item(Item=client_data)
    
    print(f"Cliente criado com sucesso: {client_id}")
    
    # Enviar convite MCC se solicitado
    mcc_result = None
    if send_mcc_invitation:
        print(f"Enviando convite MCC para cliente {googleAdsCustomerId}...")
        try:
            mcc_service = GoogleAdsMCCService()
            mcc_result = mcc_service.send_link_invitation(googleAdsCustomerId, name)
            
            if mcc_result['success']:
                print(f"✅ Convite MCC enviado com sucesso!")
                print(f"   Link ID: {mcc_result['link_id']}")
                print(f"   Status: {mcc_result['status']}")
                
                # Atualizar status MCC no cliente
                clients_table.update_item(
                    Key={"clientId": client_id},
                    UpdateExpression="SET mccStatus = :status, mccLinkId = :link_id, mccInvitationSentAt = :timestamp",
                    ExpressionAttributeValues={
                        ":status": mcc_result['status'],
                        ":link_id": mcc_result['link_id'],
                        ":timestamp": datetime.utcnow().isoformat()
                    }
                )
                
            else:
                print(f"⚠️  Erro ao enviar convite MCC: {mcc_result['error']}")
                # Atualizar status como erro
                clients_table.update_item(
                    Key={"clientId": client_id},
                    UpdateExpression="SET mccStatus = :status, mccError = :error",
                    ExpressionAttributeValues={
                        ":status": "ERROR",
                        ":error": mcc_result['error']
                    }
                )
                
        except Exception as e:
            print(f"⚠️  Erro inesperado ao enviar convite MCC: {str(e)}")
            mcc_result = {
                'success': False,
                'error': str(e)
            }
    
    response = {
        "clientId": client_id,
        "name": name,
        "email": email,
        "active": True,
        "createdAt": client_data["createdAt"],
        "googleAdsCustomerId": googleAdsCustomerId,
        "mccStatus": client_data["mccStatus"],
        "mccInvitation": mcc_result
    }

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