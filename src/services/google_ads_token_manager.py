#!/usr/bin/env python
"""
Google Ads Token Manager Automático
Gerencia automaticamente refresh tokens sem intervenção manual
"""

import os
import json
import boto3
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
import hashlib
import socket
from urllib.parse import unquote
import socket
import re
import sys

# Ensure console uses UTF-8 when possible and provide safe print fallback for Windows
try:
    # Reconfigure stdout/stderr to UTF-8 (best effort; harmless if not supported)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

def safe_print(*args, **kwargs):
    """Print wrapper that falls back to ASCII-only output if console encoding
    does not support certain Unicode characters (e.g., emojis on Windows)."""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        sanitized_args = []
        for arg in args:
            try:
                text = str(arg)
            except Exception:
                text = repr(arg)
            # Strip non-ASCII characters as a fallback
            sanitized_args.append(text.encode("ascii", "ignore").decode("ascii"))
        print(*sanitized_args, **kwargs)


class GoogleAdsTokenManager:
    """
    Gerenciador automático de tokens do Google Ads
    
    - Detecta tokens ausentes ou expirados
    - Gera automaticamente novos tokens
    - Armazena de forma segura no DynamoDB
    - Renova tokens automaticamente
    """
    
    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")
        self.ssm = boto3.client("ssm")
        self.tokens_table = self.dynamodb.Table(os.environ.get("TOKENS_TABLE", "google-ads-tokens"))
    
    def get_valid_refresh_token(self, customer_id: str) -> Optional[str]:
        """
        Obtém um refresh token válido, gerando automaticamente se necessário
        
        Args:
            customer_id (str): ID do customer do Google Ads
            
        Returns:
            str: Refresh token válido ou None se falhar
        """
        
        print(f"Obtendo refresh token para customer: {customer_id}")
        
        # 1. Tentar obter token existente
        existing_token = self._get_stored_refresh_token(customer_id)
        
        if existing_token and self._is_token_valid(existing_token):
            print("Usando refresh token existente válido")
            return existing_token
        
        # 2. Tentar renovar token expirado
        if existing_token:
            print("Tentando renovar refresh token expirado")
            renewed_token = self._renew_refresh_token(existing_token, customer_id)
            if renewed_token:
                return renewed_token
        
        # 3. Gerar novo token automaticamente
        print("Gerando novo refresh token automaticamente")
        new_token = self._generate_refresh_token_automatically(customer_id)
        
        if new_token:
            self._store_refresh_token(customer_id, new_token)
            return new_token
        
        print(f"Falha ao obter refresh token para customer: {customer_id}")
        return None
    
    def _get_stored_refresh_token(self, customer_id: str) -> Optional[str]:
        """Obtém token armazenado no DynamoDB"""
        
        try:
            response = self.tokens_table.get_item(
                Key={"customer_id": customer_id, "token_type": "refresh_token"}
            )
            
            if "Item" in response:
                return response["Item"]["token_value"]
            
        except Exception as e:
            print(f"Erro ao buscar token armazenado: {str(e)}")
        
        return None
    
    def _is_token_valid(self, refresh_token: str) -> bool:
        """Verifica se o refresh token ainda é válido"""
        
        try:
            # Criar credenciais temporárias para testar
            credentials = Credentials(
                token=None,  # Access token será gerado automaticamente
                refresh_token=refresh_token,
                token_uri="https://oauth2.googleapis.com/token",
                client_id=os.environ.get('GOOGLE_ADS_CLIENT_ID'),
                client_secret=os.environ.get('GOOGLE_ADS_CLIENT_SECRET')
            )
            
            # Tentar renovar access token
            request = Request()
            credentials.refresh(request)
            
            return credentials.valid
            
        except Exception as e:
            print(f"Token inválido: {str(e)}")
            return False
    
    def _renew_refresh_token(self, old_refresh_token: str, customer_id: str) -> Optional[str]:
        """Tenta renovar um refresh token expirado"""
        
        # Na maioria dos casos, refresh tokens não expiram
        # Mas podemos implementar lógica de renovação se necessário
        print("Refresh tokens geralmente não expiram, retornando o mesmo")
        return old_refresh_token if self._is_token_valid(old_refresh_token) else None
    
    def _generate_refresh_token_automatically(self, customer_id: str) -> Optional[str]:
        """
        Gera refresh token automaticamente usando diferentes estratégias
        """
        
        # Estratégia 1: Tentar usar token pré-autorizado
        preauth_token = self._try_preauthorized_flow(customer_id)
        if preauth_token:
            return preauth_token
        
        # Estratégia 2: Usar service account se configurado
        service_account_token = self._try_service_account_flow(customer_id)
        if service_account_token:
            return service_account_token
        
        # Estratégia 3: Endpoint webhook para autorização
        webhook_token = self._try_webhook_authorization(customer_id)
        if webhook_token:
            return webhook_token
        
        print("Todas as estratégias de geração automática falharam")
        return None
    
    def _try_preauthorized_flow(self, customer_id: str) -> Optional[str]:
        """Implementa fluxo OAuth2 interativo para obter refresh token"""
        
        try:
            
            
            # Configurações do servidor local
            _SERVER = "127.0.0.1"
            _PORT = 8080
            _REDIRECT_URI = f"http://{_SERVER}:{_PORT}"
            
            # Criar configuração do fluxo OAuth
            flow_config = {
                'web': {
                    'client_id': os.environ.get('GOOGLE_ADS_CLIENT_ID'),
                    'client_secret': os.environ.get('GOOGLE_ADS_CLIENT_SECRET'),
                    'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                    'token_uri': 'https://oauth2.googleapis.com/token'
                }
            }
            
            flow = Flow.from_client_config(
                flow_config,
                scopes=['https://www.googleapis.com/auth/adwords']
            )
            
            flow.redirect_uri = _REDIRECT_URI
            
            # Criar token de segurança anti-forgery
            passthrough_val = hashlib.sha256(os.urandom(1024)).hexdigest()
            
            # Gerar URL de autorização
            authorization_url, state = flow.authorization_url(
                access_type="offline",
                state=passthrough_val,
                prompt="consent",
                include_granted_scopes="true",
            )
            
            print(f"\n=== AUTORIZAÇÃO OAUTH2 NECESSÁRIA ===")
            print(f"Customer ID: {customer_id}")
            print(f"Acesse esta URL no seu navegador:")
            print(f"{authorization_url}")
            print(f"\nAguardando callback em: {_REDIRECT_URI}")
            print("Após autorizar, você será redirecionado automaticamente...\n")
            
            # Obter código de autorização via socket
            code = unquote(self._get_authorization_code(_SERVER, _PORT, passthrough_val))
            
            if not code:
                print("Não foi possível obter código de autorização")
                return None
            
            # Trocar código por tokens
            flow.fetch_token(code=code)
            refresh_token = flow.credentials.refresh_token
            
            if refresh_token:
                safe_print(f"✅ Refresh token obtido com sucesso para customer: {customer_id}")
                return refresh_token
            else:
                safe_print("❌ Não foi possível obter refresh token")
                return None
                
        except Exception as e:
            print(f"Erro no fluxo OAuth2: {str(e)}")
            return None
    
    def _get_authorization_code(self, server: str, port: int, passthrough_val: str) -> Optional[str]:
        """
        Abre socket para receber callback OAuth2 com código de autorização
        
        Args:
            server: Endereço do servidor local
            port: Porta do servidor local  
            passthrough_val: Token anti-forgery para validação
            
        Returns:
            Código de autorização ou None se falhar
        """
   
        
        try:
            # Abrir socket local
            sock = socket.socket()
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((server, port))
            sock.listen(1)
            sock.settimeout(300)  # Timeout de 5 minutos
            
            print(f"Servidor local iniciado em {server}:{port}")
            print("Aguardando autorização...")
            
            connection, address = sock.accept()
            data = connection.recv(1024)
            
            # Parse dos parâmetros da requisição
            params = self._parse_raw_query_params(data)
            
            message = "Autorização recebida com sucesso!"
            success = True
            
            if not params.get("code"):
                error = params.get("error", "Código não encontrado")
                message = f"Falha na autorização. Erro: {error}"
                success = False
            elif params.get("state") != passthrough_val:
                message = "Token de estado inválido - possível ataque CSRF"
                success = False
            
            # Enviar resposta HTTP
            status = "200 OK" if success else "400 Bad Request"
            response = (
                f"HTTP/1.1 {status}\n"
                "Content-Type: text/html; charset=utf-8\n\n"
                f"<html><body>"
                f"<h2>{'✅' if success else '❌'} {message}</h2>"
                f"<p>{'Você pode fechar esta janela.' if success else 'Verifique o console para mais detalhes.'}</p>"
                f"</body></html>\n"
            )
            
            connection.sendall(response.encode('utf-8'))
            connection.close()
            sock.close()
            
            if success:
                safe_print("✅ Autorização concluída com sucesso!")
                return params.get("code")
            else:
                safe_print(f"❌ {message}")
                return None
                
        except socket.timeout:
            safe_print("❌ Timeout: Autorização não recebida em 5 minutos")
            return None
        except Exception as e:
            safe_print(f"❌ Erro no servidor de autorização: {str(e)}")
            return None
        finally:
            try:
                sock.close()
            except:
                pass
    
    @staticmethod
    def _parse_raw_query_params(data):
        """Parses a raw HTTP request to extract its query params as a dict.

        Note that this logic is likely irrelevant if you're building OAuth logic
        into a complete web application, where response parsing is handled by a
        framework.

        Args:
            data: raw request data as bytes.

        Returns:
            a dict of query parameter key value pairs.
        """
        try:
            # Decode the request into a utf-8 encoded string
            decoded = data.decode("utf-8")
            # Use a regular expression to extract the URL query parameters string
            match = re.search(r"GET\s\/\?(.*) ", decoded)
            params = match.group(1)
            # Split the parameters to isolate the key/value pairs
            pairs = [pair.split("=") for pair in params.split("&")]
            # Convert pairs to a dict to make it easy to access the values
            return {key: val for key, val in pairs}
            
        except Exception as e:
            print(f"Erro ao fazer parse dos parâmetros: {str(e)}")
            return {}
    
    def _try_service_account_flow(self, customer_id: str) -> Optional[str]:
        """Tenta usar service account se configurado"""
        
        service_account_info = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
        
        if not service_account_info:
            return None
        
        try:
            # Para service accounts, não precisamos de refresh token
            # O próprio service account JSON serve como credencial
            print("Service account detectado - não precisa de refresh token")
            return "SERVICE_ACCOUNT_MODE"  # Indicador especial
            
        except Exception as e:
            print(f"Erro com service account: {str(e)}")
            return None
    
    def _try_webhook_authorization(self, customer_id: str) -> Optional[str]:
        """Implementa autorização via webhook/callback"""
        
        # Esta estratégia requer um endpoint web configurado
        # que pode receber callbacks do Google OAuth
        
        webhook_url = os.environ.get('GOOGLE_ADS_WEBHOOK_URL')
        
        if not webhook_url:
            print("Webhook não configurado")
            return None
        
        # Implementação do fluxo webhook seria mais complexa
        # Requer infraestrutura web adicional
        print("Fluxo webhook não implementado ainda")
        return None
    
    def _store_refresh_token(self, customer_id: str, refresh_token: str):
        """Armazena refresh token no DynamoDB"""
        
        try:
            self.tokens_table.put_item(
                Item={
                    'customer_id': customer_id,
                    'token_type': 'refresh_token',
                    'token_value': refresh_token,
                    'created_at': datetime.utcnow().isoformat(),
                    'expires_at': (datetime.utcnow() + timedelta(days=365)).isoformat(),  # Refresh tokens duram ~1 ano
                    'ttl': int((datetime.utcnow() + timedelta(days=365)).timestamp())  # TTL para DynamoDB
                }
            )
            
            print(f"Refresh token armazenado para customer: {customer_id}")
            
        except Exception as e:
            print(f"Erro ao armazenar token: {str(e)}") 