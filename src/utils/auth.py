import boto3
import os
import logging
import secrets
import hmac
import hashlib
import base64
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class ClientAuth:
    """Classe para gerenciar autenticação e operações de clientes"""
    
    def __init__(self):
        self.dynamodb = boto3.resource('dynamodb')
        self.clients_table = self.dynamodb.Table(os.environ.get('CLIENTS_TABLE'))
    
    def validate_api_key(self, api_key):
        """
        Valida a API key e retorna os dados do cliente caso seja válida
        
        Args:
            api_key (str): A chave de API a ser validada
            
        Returns:
            dict: Dados do cliente se a chave for válida, None caso contrário
        """
        try:
            # Consulta pelo índice secundário de API key
            response = self.clients_table.query(
                IndexName='apiKey-index',
                KeyConditionExpression=Key('apiKey').eq(api_key)
            )
            
            if response.get('Items') and len(response['Items']) > 0:
                return response['Items'][0]
            
            logger.warning(f"API key inválida: {api_key}")
            return None
        
        except Exception as e:
            logger.error(f"Erro ao validar API key: {str(e)}")
            return None
    
    def generate_api_key(self):
        """Gera uma nova API key segura"""
        return secrets.token_hex(32)  # 64 caracteres hexadecimais
    
    def create_client(self, client_name, client_email):
        """
        Cria um novo cliente com uma API key gerada
        
        Args:
            client_name (str): Nome do cliente
            client_email (str): Email do cliente
            
        Returns:
            dict: Dados do cliente criado incluindo a API key
        """
        client_id = self._generate_client_id(client_name)
        api_key = self.generate_api_key()
        
        client_data = {
            'clientId': client_id,
            'name': client_name,
            'email': client_email,
            'apiKey': api_key,
            'active': True
        }
        
        try:
            self.clients_table.put_item(Item=client_data)
            return client_data
        except Exception as e:
            logger.error(f"Erro ao criar cliente: {str(e)}")
            raise
    
    def _generate_client_id(self, client_name):
        """Gera um ID do cliente baseado no nome"""
        # Remove espaços e caracteres especiais e converte para lowercase
        base = ''.join(e for e in client_name if e.isalnum()).lower()
        # Adiciona um hash curto para evitar colisões
        hash_suffix = hashlib.md5(client_name.encode()).hexdigest()[:6]
        return f"{base}-{hash_suffix}" 