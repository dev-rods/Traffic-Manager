#!/usr/bin/env python
"""
Script para gerar códigos de autorização do Google Ads

Este script ajuda a gerar códigos de autorização que podem ser configurados
como variáveis de ambiente para permitir o fluxo automático.
"""

import os
import sys
from pathlib import Path
from google_auth_oauthlib.flow import Flow

def generate_authorization_url():
    """Gera URL de autorização do Google"""
    
    client_id = os.environ.get('GOOGLE_ADS_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_ADS_CLIENT_SECRET')
    
    if not client_id or not client_secret:
        print("❌ Erro: Configure primeiro as variáveis de ambiente:")
        print("   export GOOGLE_ADS_CLIENT_ID='your_client_id'")
        print("   export GOOGLE_ADS_CLIENT_SECRET='your_client_secret'")
        return None
    
    # Configuração do fluxo OAuth2
    flow_config = {
        'web': {
            'client_id': client_id,
            'client_secret': client_secret,
            'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
            'token_uri': 'https://oauth2.googleapis.com/token'
        }
    }
    
    flow = Flow.from_client_config(
        flow_config,
        scopes=['https://www.googleapis.com/auth/adwords']
    )
    
    # URI de redirecionamento
    flow.redirect_uri = 'urn:ietf:wg:oauth:2.0:oob'
    
    # Gerar URL de autorização
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Força o prompt para garantir refresh_token
    )
    
    return authorization_url, flow, state

def exchange_code_for_token(authorization_code, flow):
    """Troca código de autorização por tokens"""
    
    try:
        # Trocar código por tokens
        flow.fetch_token(code=authorization_code)
        
        credentials = flow.credentials
        
        return {
            'access_token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret
        }
        
    except Exception as e:
        print(f"❌ Erro ao trocar código por tokens: {str(e)}")
        return None

def main():
    """Executa o processo de geração de códigos de autorização"""
    
    print("🔐 Gerador de Códigos de Autorização Google Ads")
    print("=" * 60)
    
    print("\n📋 Este script irá:")
    print("1. Gerar uma URL de autorização")
    print("2. Aguardar você inserir o código de autorização")
    print("3. Trocar o código por um refresh token")
    print("4. Fornecer as variáveis de ambiente necessárias")
    
    # Passo 1: Gerar URL de autorização
    print("\n1️⃣ Gerando URL de autorização...")
    result = generate_authorization_url()
    
    if not result:
        return False
    
    authorization_url, flow, state = result
    
    print(f"\n✅ URL de autorização gerada!")
    print("\n📋 PASSO 1: Abra a seguinte URL no seu navegador:")
    print("=" * 60)
    print(authorization_url)
    print("=" * 60)
    
    print("\n📋 PASSO 2: Faça login com a conta Google Ads e autorize a aplicação.")
    print("📋 PASSO 3: Copie o código de autorização que aparecerá na tela.")
    
    # Passo 2: Aguardar código de autorização
    print("\n2️⃣ Aguardando código de autorização...")
    
    try:
        authorization_code = input("\n📝 Cole aqui o código de autorização: ").strip()
        
        if not authorization_code:
            print("❌ Código de autorização não fornecido")
            return False
        
        print(f"✅ Código recebido: {authorization_code[:12]}***")
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return False
    
    # Passo 3: Trocar código por tokens
    print("\n3️⃣ Trocando código por tokens...")
    
    tokens = exchange_code_for_token(authorization_code, flow)
    
    if not tokens:
        return False
    
    print("✅ Tokens obtidos com sucesso!")
    
    # Passo 4: Gerar variáveis de ambiente
    print("\n4️⃣ Gerando variáveis de ambiente...")
    
    customer_id = input("\n📝 Digite o Customer ID do Google Ads (formato: 123-456-7890): ").strip()
    
    if customer_id:
        # Remover hífens do customer ID
        clean_customer_id = customer_id.replace('-', '')
        
        print("\n" + "=" * 60)
        print("🎉 CONFIGURAÇÃO COMPLETA!")
        print("=" * 60)
        
        print("\n📋 Adicione estas variáveis de ambiente:")
        print("=" * 60)
        
        print(f'export GOOGLE_ADS_CLIENT_ID="{tokens["client_id"]}"')
        print(f'export GOOGLE_ADS_CLIENT_SECRET="{tokens["client_secret"]}"')
        print(f'export GOOGLE_ADS_AUTH_CODE_{clean_customer_id}="{authorization_code}"')
        print(f'export GOOGLE_ADS_DEVELOPER_TOKEN="your_developer_token_here"')
        
        print("\n📋 Ou adicione ao serverless.yml:")
        print("=" * 60)
        print("environment:")
        print(f'  GOOGLE_ADS_CLIENT_ID: "{tokens["client_id"]}"')
        print(f'  GOOGLE_ADS_CLIENT_SECRET: "{tokens["client_secret"]}"')
        print(f'  GOOGLE_ADS_AUTH_CODE_{clean_customer_id}: "{authorization_code}"')
        print('  GOOGLE_ADS_DEVELOPER_TOKEN: "your_developer_token_here"')
        
        print("\n📋 Ou armazenar diretamente o refresh token:")
        print("=" * 60)
        print(f'export GOOGLE_ADS_REFRESH_TOKEN="{tokens["refresh_token"]}"')
        
        print("\n✅ Agora você pode usar o fluxo completamente automático!")
        
    else:
        print("\n⚠️  Customer ID não fornecido, mas tokens foram gerados:")
        print(f"   Refresh Token: {tokens['refresh_token']}")
    
    print("\n📋 Próximos passos:")
    print("1. Configure as variáveis de ambiente acima")
    print("2. Execute: python src/scripts/test_automated_google_ads.py")
    print("3. Faça deploy: serverless deploy")
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")
        sys.exit(1) 