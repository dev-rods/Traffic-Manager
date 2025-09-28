import boto3
import os
import logging
import secrets
import hashlib
logger = logging.getLogger()
logger.setLevel(logging.INFO)

class ClientAuth:
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.clients_table = self.dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    def validate_api_key(self, api_key):
        try:
            expected_api_key = os.environ.get("FORM_SUBMISSION_X_API_KEY")
            if not expected_api_key:
                logger.error("FORM_SUBMISSION_X_API_KEY não configurada no ambiente")
                return None
            return expected_api_key == api_key

        except Exception as e:
            logger.error(f"Erro ao validar API key: {str(e)}")
            return None
    
    def generate_api_key(self):
        return secrets.token_hex(32)
    
    def create_client(self, client_name, client_email):
        client_id = self._generate_client_id(client_name)
        api_key = self.generate_api_key()
        client_data = {
            "clientId": client_id,
            "name": client_name,
            "email": client_email,
            "apiKey": api_key,
            "active": True
        }
        
        try:
            self.clients_table.put_item(Item=client_data)
            return client_data
        except Exception as e:
            logger.error(f"Erro ao criar cliente: {str(e)}")
            raise
    
    def _generate_client_id(self, client_name):
        base = "".join(e for e in client_name if e.isalnum()).lower()
        hash_suffix = hashlib.md5(client_name.encode()).hexdigest()[:6]
        return f"{base}-{hash_suffix}" 