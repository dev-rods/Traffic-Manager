#!/usr/bin/env python
"""
Google Ads OAuth2 Refresh Token Generator
Adaptado da documentação oficial do Google Ads para o projeto Traffic Manager Infra

Baseado em:
https://github.com/googleads/google-ads-python/blob/main/examples/authentication/generate_user_credentials.py

Este script gera um refresh token que será usado pela aplicação para autenticação
automática com a API do Google Ads.

IMPORTANTE: Execute este script LOCALMENTE, não no Lambda.
"""

import argparse
import hashlib
import os
import re
import socket
import sys
from urllib.parse import unquote
from google_auth_oauthlib.flow import Flow

_SCOPE = "https://www.googleapis.com/auth/adwords"
_SERVER = "127.0.0.1"
_PORT = 8080
_REDIRECT_URI = f"http://{_SERVER}:{_PORT}"

def main(client_secrets_path, scopes):
    """
    Gera refresh token usando o fluxo OAuth2
    
    Args:
        client_secrets_path (str): Caminho para o arquivo client_secrets.json
        scopes (list): Lista de scopes a serem solicitados
    """
    
    if not os.path.exists(client_secrets_path):
        print(f"❌ Arquivo não encontrado: {client_secrets_path}")
        return False
    
    print("🚀 Iniciando geração de refresh token para Google Ads...")
    print(f"📁 Usando arquivo de credenciais: {client_secrets_path}")
    print(f"📋 Scopes solicitados: {scopes}")
    
    try:
        # Criar fluxo OAuth2
        flow = Flow.from_client_secrets_file(client_secrets_path, scopes=scopes)
        flow.redirect_uri = _REDIRECT_URI

        # Criar token anti-forgery
        passthrough_val = hashlib.sha256(os.urandom(1024)).hexdigest()

        # Obter URL de autorização
        authorization_url, state = flow.authorization_url(
            access_type="offline",
            state=passthrough_val,
            prompt="consent",
            include_granted_scopes="true",
        )

        print("\n" + "="*60)
        print("📋 INSTRUÇÕES:")
        print("1. Copie e cole esta URL no seu navegador:")
        print(f"   {authorization_url}")
        print("\n2. Faça login com a conta Google que tem acesso ao Google Ads")
        print("3. Autorize o acesso à aplicação")
        print("4. O navegador será redirecionado automaticamente")
        print("="*60)
        print(f"\n⏳ Aguardando autorização em: {_REDIRECT_URI}")

        # Aguardar código de autorização
        code = unquote(get_authorization_code(passthrough_val))
        
        # Trocar código por refresh token
        flow.fetch_token(code=code)
        refresh_token = flow.credentials.refresh_token

        if not refresh_token:
            print("❌ Refresh token não foi retornado.")
            print("   Certifique-se de que está usando 'access_type=offline' e 'prompt=consent'")
            return False

        print(f"\n✅ Refresh token gerado com sucesso!")
        print(f"🔑 Refresh Token: {refresh_token}")
        
        # Salvar em arquivo
        save_token_to_file(refresh_token)
        
        print("\n" + "="*60)
        print("🎉 CONCLUÍDO!")
        print("📋 Próximos passos:")
        print("1. Copie o refresh token acima")
        print("2. Configure as variáveis de ambiente:")
        print(f"   export GOOGLE_ADS_REFRESH_TOKEN='{refresh_token}'")
        print("3. Atualize o serverless.yml")
        print("4. Faça deploy da aplicação")
        print("="*60)
        
        return True
        
    except Exception as e:
        print(f"❌ Erro durante geração do token: {str(e)}")
        return False

def get_authorization_code(passthrough_val):
    """
    Obtém código de autorização via socket HTTP local
    
    Args:
        passthrough_val (str): Token anti-forgery para validação
        
    Returns:
        str: Código de autorização
    """
    
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        sock.bind((_SERVER, _PORT))
        sock.listen(1)
        
        print(f"🌐 Servidor local iniciado em {_REDIRECT_URI}")
        
        connection, address = sock.accept()
        data = connection.recv(1024)
        
        # Parse da requisição HTTP
        params = parse_raw_query_params(data)
        
        message = ""
        
        if not params.get("code"):
            error = params.get("error")
            message = f"❌ Falha ao obter código de autorização. Erro: {error}"
            raise ValueError(message)
        elif params.get("state") != passthrough_val:
            message = "❌ Token de estado não confere. Possível ataque CSRF."
            raise ValueError(message)
        else:
            message = "✅ Código de autorização obtido com sucesso!"
        
        # Resposta HTTP
        response = (
            "HTTP/1.1 200 OK\n"
            "Content-Type: text/html; charset=utf-8\n\n"
            "<!DOCTYPE html>"
            "<html><head><title>Google Ads OAuth2</title></head>"
            "<body style='font-family: Arial; padding: 40px; text-align: center;'>"
            f"<h2>{message}</h2>"
            "<p>Você pode fechar esta aba e voltar ao terminal.</p>"
            "</body></html>"
        )
        
        connection.sendall(response.encode('utf-8'))
        print(f"✅ {message}")
        
    finally:
        if 'connection' in locals():
            connection.close()
        sock.close()

    return params.get("code")

def parse_raw_query_params(data):
    """
    Parse dos parâmetros da requisição HTTP
    
    Args:
        data (bytes): Dados brutos da requisição HTTP
        
    Returns:
        dict: Dicionário com parâmetros da query string
    """
    
    decoded = data.decode("utf-8")
    match = re.search(r"GET\s\/\?(.*) ", decoded)
    
    if not match:
        return {}
    
    params = match.group(1)
    pairs = [pair.split("=") for pair in params.split("&")]
    
    return {key: val for key, val in pairs}

def save_token_to_file(refresh_token):
    """
    Salva o refresh token em arquivo para backup
    
    Args:
        refresh_token (str): Token a ser salvo
    """
    
    # Criar diretório se não existir
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tokens_dir = os.path.join(script_dir, "tokens")
    os.makedirs(tokens_dir, exist_ok=True)
    
    # Salvar token
    token_file = os.path.join(tokens_dir, "google_ads_refresh_token.txt")
    
    with open(token_file, 'w') as f:
        f.write(refresh_token)
    
    print(f"💾 Token salvo em: {token_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Gera refresh token para Google Ads OAuth2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:

    # Gerar token usando arquivo client_secrets.json
    python generate_refresh_token.py -c client_secrets.json
    
    # Com scopes adicionais
    python generate_refresh_token.py -c client_secrets.json --additional_scopes https://www.googleapis.com/auth/analytics

IMPORTANTE:
- Execute este script LOCALMENTE, não no servidor
- Certifique-se que http://127.0.0.1:8080 está nas "Authorized redirect URIs" do Google Cloud Console
- Use a conta Google que tem acesso ao Google Ads Manager Center

REQUISITOS:
- pip install google-auth-oauthlib
- Arquivo client_secrets.json baixado do Google Cloud Console
"""
    )
    
    parser.add_argument(
        "-c", "--client_secrets_path",
        required=True,
        help="Caminho para o arquivo client_secrets.json do Google Cloud Console"
    )
    
    parser.add_argument(
        "--additional_scopes",
        default=None,
        nargs="+",
        help="Scopes adicionais para incluir na autorização"
    )
    
    args = parser.parse_args()
    
    try:
        # Configurar scopes
        configured_scopes = [_SCOPE]
        
        if args.additional_scopes:
            configured_scopes.extend(args.additional_scopes)
            print(f"📋 Scopes configurados: {configured_scopes}")
        
        # Gerar token
        success = main(args.client_secrets_path, configured_scopes)
        
        if success:
            print("\n🎉 Processo concluído com sucesso!")
        else:
            print("\n❌ Processo falhou!")
            sys.exit(1)
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")
        sys.exit(1) 