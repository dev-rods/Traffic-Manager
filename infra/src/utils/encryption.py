"""
Serviço de criptografia para tokens sensíveis

Este módulo fornece funcionalidades para criptografar e descriptografar
tokens do Google Ads de forma segura.
"""
import os
import base64
import boto3
import logging
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class TokenEncryption:
    
    def __init__(self):
        self.ssm = boto3.client('ssm')
        self._encryption_key = None
    
    def _get_encryption_key(self):
        """
        Obtém a chave de criptografia do AWS Systems Manager
        Se não existir, cria uma nova
        """
        if self._encryption_key:
            return self._encryption_key
            
        try:
            # Tentar buscar a chave existente
            parameter_name = f"/traffic-manager/{os.environ.get('STAGE', 'dev')}/encryption-key"
            response = self.ssm.get_parameter(
                Name=parameter_name,
                WithDecryption=True
            )
            self._encryption_key = response['Parameter']['Value'].encode()
            logger.info("Chave de criptografia recuperada do SSM")
            
        except self.ssm.exceptions.ParameterNotFound:
            # Criar nova chave se não existir
            logger.info("Criando nova chave de criptografia")
            self._encryption_key = Fernet.generate_key()
            
            # Salvar no SSM
            self.ssm.put_parameter(
                Name=parameter_name,
                Value=self._encryption_key.decode(),
                Type='SecureString',
                Description='Chave de criptografia para tokens do Google Ads'
            )
            logger.info("Nova chave de criptografia salva no SSM")
            
        except Exception as e:
            logger.error(f"Erro ao obter chave de criptografia: {str(e)}")
            raise
            
        return self._encryption_key
    
    def encrypt_token(self, token):
        """
        Criptografa um token
        
        Args:
            token (str): Token a ser criptografado
            
        Returns:
            str: Token criptografado em base64
        """
        try:
            if not token:
                return None
                
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_token = fernet.encrypt(token.encode())
            return base64.b64encode(encrypted_token).decode()
            
        except Exception as e:
            logger.error(f"Erro ao criptografar token: {str(e)}")
            raise
    
    def decrypt_token(self, encrypted_token):
        """
        Descriptografa um token
        
        Args:
            encrypted_token (str): Token criptografado em base64
            
        Returns:
            str: Token descriptografado
        """
        try:
            if not encrypted_token:
                return None
                
            key = self._get_encryption_key()
            fernet = Fernet(key)
            encrypted_bytes = base64.b64decode(encrypted_token.encode())
            decrypted_token = fernet.decrypt(encrypted_bytes)
            return decrypted_token.decode()
            
        except Exception as e:
            logger.error(f"Erro ao descriptografar token: {str(e)}")
            raise
    
    def encrypt_google_ads_config(self, config):
        """
        Criptografa toda a configuração do Google Ads
        
        Args:
            config (dict): Configuração com tokens do Google Ads
            
        Returns:
            dict: Configuração com tokens criptografados
        """
        if not config:
            return None
            
        encrypted_config = {}
        
        # Campos que devem ser criptografados
        sensitive_fields = ['clientSecret', 'refreshToken', 'developerToken']
        
        for key, value in config.items():
            if key in sensitive_fields and value:
                encrypted_config[key] = self.encrypt_token(value)
            else:
                encrypted_config[key] = value
                
        return encrypted_config
    
    def decrypt_google_ads_config(self, encrypted_config):
        """
        Descriptografa toda a configuração do Google Ads
        
        Args:
            encrypted_config (dict): Configuração com tokens criptografados
            
        Returns:
            dict: Configuração com tokens descriptografados
        """
        if not encrypted_config:
            return None
            
        decrypted_config = {}
        
        # Campos que devem ser descriptografados
        sensitive_fields = ['clientSecret', 'refreshToken', 'developerToken']
        
        for key, value in encrypted_config.items():
            if key in sensitive_fields and value:
                decrypted_config[key] = self.decrypt_token(value)
            else:
                decrypted_config[key] = value
                
        return decrypted_config 