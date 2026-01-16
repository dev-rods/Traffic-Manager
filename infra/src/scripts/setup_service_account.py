#!/usr/bin/env python
"""
Script para auxiliar na configuração de Service Account para Google Ads

Este script ajuda a configurar e validar service accounts para acesso
completamente automático ao Google Ads API.
"""

import os
import sys
import json
from pathlib import Path

def validate_service_account_json(service_account_json: str) -> bool:
    """Valida se o JSON do service account está correto"""
    
    try:
        data = json.loads(service_account_json)
        
        required_fields = [
            'type', 'project_id', 'private_key_id', 'private_key',
            'client_email', 'client_id', 'auth_uri', 'token_uri'
        ]
        
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            print(f"❌ Campos obrigatórios ausentes: {missing_fields}")
            return False
        
        if data.get('type') != 'service_account':
            print("❌ Tipo deve ser 'service_account'")
            return False
        
        print("✅ JSON do service account válido")
        print(f"   📧 Client Email: {data['client_email']}")
        print(f"   🏗️  Project ID: {data['project_id']}")
        print(f"   🔑 Client ID: {data['client_id']}")
        
        return True
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON inválido: {str(e)}")
        return False
    except Exception as e:
        print(f"❌ Erro ao validar service account: {str(e)}")
        return False

def generate_serverless_config(service_account_json: str, developer_token: str) -> str:
    """Gera configuração para o serverless.yml"""
    
    try:
        data = json.loads(service_account_json)
        
        config = f"""# Service Account Configuration
# Adicione estas variáveis ao seu serverless.yml:

environment:
  # Google Ads Service Account (Estratégia 1 - Recomendada)
  GOOGLE_ADS_DEVELOPER_TOKEN: "{developer_token}"
  GOOGLE_SERVICE_ACCOUNT_JSON: '{service_account_json}'
  GOOGLE_ADS_IMPERSONATED_EMAIL: "user@yourdomain.com"  # Email do usuário a ser impersonado

# Ou configure via SSM Parameters (mais seguro):
environment:
  GOOGLE_ADS_DEVELOPER_TOKEN: ${{ssm:/MCC_DEVELOPER_TOKEN}}
  GOOGLE_SERVICE_ACCOUNT_JSON: ${{ssm:/GOOGLE_SERVICE_ACCOUNT_JSON~true}}
  GOOGLE_ADS_IMPERSONATED_EMAIL: ${{ssm:/GOOGLE_ADS_IMPERSONATED_EMAIL}}

# Commands to store in SSM:
# aws ssm put-parameter --name "/MCC_DEVELOPER_TOKEN" --value "{developer_token}" --type "String"
# aws ssm put-parameter --name "/GOOGLE_SERVICE_ACCOUNT_JSON" --value '{service_account_json}' --type "SecureString"
# aws ssm put-parameter --name "/GOOGLE_ADS_IMPERSONATED_EMAIL" --value "user@yourdomain.com" --type "String"
"""
        
        return config
        
    except Exception as e:
        print(f"❌ Erro ao gerar configuração: {str(e)}")
        return ""

def main():
    """Executa o setup de service account"""
    
    print("🔐 Configurador de Service Account para Google Ads")
    print("=" * 60)
    
    print("\n📋 Este script irá:")
    print("1. Validar o JSON do service account")
    print("2. Gerar a configuração para serverless.yml")
    print("3. Fornecer comandos para armazenar no SSM")
    
    print("\n⚠️  Pré-requisitos:")
    print("1. Service account criado no Google Cloud Console")
    print("2. Service account com acesso ao Google Ads API")
    print("3. Developer token do Google Ads")
    
    # Passo 1: Obter JSON do service account
    print("\n1️⃣ Configurando Service Account...")
    
    print("\n📝 Como obter o JSON do service account:")
    print("1. Acesse Google Cloud Console")
    print("2. Vá para IAM & Admin > Service Accounts")
    print("3. Clique no service account")
    print("4. Vá para Keys > Add Key > Create new key")
    print("5. Escolha JSON e baixe o arquivo")
    
    try:
        service_account_file = input("\n📂 Caminho para o arquivo JSON do service account: ").strip()
        
        if not service_account_file:
            print("❌ Caminho não fornecido")
            return False
        
        if not os.path.exists(service_account_file):
            print(f"❌ Arquivo não encontrado: {service_account_file}")
            return False
        
        with open(service_account_file, 'r') as f:
            service_account_json = f.read()
        
        print("✅ Arquivo JSON carregado")
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return False
    except Exception as e:
        print(f"❌ Erro ao ler arquivo: {str(e)}")
        return False
    
    # Passo 2: Validar JSON
    print("\n2️⃣ Validando JSON do service account...")
    
    if not validate_service_account_json(service_account_json):
        return False
    
    # Passo 3: Obter developer token
    print("\n3️⃣ Configurando Developer Token...")
    
    try:
        developer_token = input("\n📝 Digite o Developer Token do Google Ads: ").strip()
        
        if not developer_token:
            print("❌ Developer token não fornecido")
            return False
        
        print(f"✅ Developer token configurado: {developer_token[:8]}***")
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return False
    
    # Passo 4: Gerar configuração
    print("\n4️⃣ Gerando configuração...")
    
    config = generate_serverless_config(service_account_json, developer_token)
    
    if not config:
        return False
    
    print("\n" + "=" * 60)
    print("🎉 CONFIGURAÇÃO COMPLETA!")
    print("=" * 60)
    
    print(config)
    
    # Passo 5: Salvar configuração em arquivo
    try:
        save_config = input("\n💾 Salvar configuração em arquivo? (y/n): ").strip().lower()
        
        if save_config in ['y', 'yes', 's', 'sim']:
            config_file = f"google_ads_service_account_config_{data['project_id']}.txt"
            
            with open(config_file, 'w') as f:
                f.write(config)
            
            print(f"✅ Configuração salva em: {config_file}")
        
    except Exception as e:
        print(f"⚠️  Erro ao salvar configuração: {str(e)}")
    
    print("\n📋 Próximos passos:")
    print("1. Adicione as configurações ao seu serverless.yml")
    print("2. Configure as variáveis no SSM (mais seguro)")
    print("3. Execute: python src/scripts/test_automated_google_ads.py")
    print("4. Faça deploy: serverless deploy")
    
    print("\n💡 Dicas de segurança:")
    print("- Use SSM Parameters para dados sensíveis")
    print("- Não commite o JSON do service account no Git")
    print("- Configure IAM roles com permissões mínimas necessárias")
    
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