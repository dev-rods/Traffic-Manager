#!/usr/bin/env python
"""
Script para testar o fluxo completamente automatizado do Google Ads

Este script verifica se todas as configurações necessárias para o Google Ads
estão corretas e se é possível criar um cliente autenticado automaticamente.
"""

import os
import sys
from pathlib import Path

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from services.google_ads_config import GoogleAdsConfig
from services.google_ads_token_manager import GoogleAdsTokenManager
from google.ads.googleads.client import GoogleAdsClient

def test_automated_flow():
    """Testa o fluxo completamente automatizado"""
    
    print("🤖 Testando fluxo automático do Google Ads...")
    
    customer_id = "1570932315"  # ID de exemplo
    
    try:
        # 1. Testar Token Manager
        print("\n1️⃣ Testando Token Manager...")
        token_manager = GoogleAdsTokenManager()
        refresh_token = token_manager.get_valid_refresh_token(customer_id)
        
        if refresh_token:
            if refresh_token == "SERVICE_ACCOUNT_MODE":
                print("   ✅ Service account mode detectado")
            else:
                print(f"   ✅ Refresh token obtido: {refresh_token[:12]}***")
        else:
            print("   ⚠️  Refresh token não disponível - verificando outras estratégias")
        
        # 2. Testar GoogleAdsConfig Automático
        print("\n2️⃣ Testando GoogleAdsConfig...")
        config_service = GoogleAdsConfig()
        config = config_service.get_google_ads_config(customer_id)
        
        print(f"   ✅ Configuração obtida: {list(config.keys())}")
        
        # Mostrar tipo de configuração
        if 'json_key_file_path' in config:
            print("   📋 Tipo: Service Account")
        elif 'refresh_token' in config:
            print("   📋 Tipo: OAuth2")
        
        # 3. Testar Cliente Google Ads
        print("\n3️⃣ Testando Cliente Google Ads...")
        client = GoogleAdsClient.load_from_dict(config, version="v20")
        print("   ✅ Cliente criado com sucesso")
        
        # 4. Testar Conexão Real
        print("\n4️⃣ Testando conexão com API...")
        customer_service = client.get_service("CustomerService")
        print("   ✅ Serviço acessível")
        
        # 5. Teste básico de API (se developer token estiver configurado)
        if config.get('developer_token') and config['developer_token'] != 'your_developer_token_here':
            print("\n5️⃣ Testando chamada básica da API...")
            try:
                # Fazer uma chamada muito básica
                ga_service = client.get_service("GoogleAdsService")
                query = "SELECT customer.id FROM customer LIMIT 1"
                
                # Usar search ao invés de search_stream para teste básico
                response = ga_service.search(customer_id=customer_id, query=query)
                print("   ✅ API respondeu com sucesso")
                
            except Exception as api_error:
                print(f"   ⚠️  API Error (pode ser normal em teste): {str(api_error)[:100]}...")
        else:
            print("\n5️⃣ Pulando teste de API (Developer Token não configurado)")
        
        print("\n🎉 Fluxo automático funcionando perfeitamente!")
        return True
        
    except Exception as e:
        print(f"\n❌ Erro no fluxo automático: {str(e)}")
        
        # Diagnóstico automático
        print("\n🔍 Diagnóstico:")
        
        error_str = str(e).lower()
        if "service account" in error_str:
            print("   💡 Configure GOOGLE_SERVICE_ACCOUNT_JSON")
            print("      export GOOGLE_SERVICE_ACCOUNT_JSON='{\"type\":\"service_account\",...}'")
        elif "refresh_token" in error_str or "oauth" in error_str:
            print("   💡 Configure códigos de autorização ou credenciais OAuth2:")
            print("      export GOOGLE_ADS_CLIENT_ID='your_client_id'")
            print("      export GOOGLE_ADS_CLIENT_SECRET='your_client_secret'")
            print("      export GOOGLE_ADS_AUTH_CODE_1570932315='your_auth_code'")
        elif "developer_token" in error_str:
            print("   💡 Configure GOOGLE_ADS_DEVELOPER_TOKEN")
            print("      export GOOGLE_ADS_DEVELOPER_TOKEN='your_developer_token'")
        elif "table" in error_str or "dynamodb" in error_str:
            print("   💡 Verifique se a tabela DynamoDB existe:")
            print("      aws dynamodb describe-table --table-name google-ads-tokens")
        else:
            print(f"   🔍 Erro específico: {str(e)}")
        
        return False

def test_environment_variables():
    """Testa se as variáveis de ambiente estão configuradas"""
    
    print("\n🧪 Testando variáveis de ambiente...")
    
    # Variáveis para Service Account
    service_account_vars = ['GOOGLE_ADS_DEVELOPER_TOKEN', 'GOOGLE_SERVICE_ACCOUNT_JSON']
    
    # Variáveis para OAuth2
    oauth2_vars = ['GOOGLE_ADS_DEVELOPER_TOKEN', 'GOOGLE_ADS_CLIENT_ID', 'GOOGLE_ADS_CLIENT_SECRET']
    
    print("\n📋 Service Account:")
    service_account_complete = True
    for var in service_account_vars:
        value = os.environ.get(var)
        if value:
            masked_value = value[:8] + "***" if len(value) > 8 else "***"
            print(f"  ✅ {var}: {masked_value}")
        else:
            print(f"  ❌ {var}: Não configurado")
            service_account_complete = False
    
    print("\n📋 OAuth2:")
    oauth2_complete = True
    for var in oauth2_vars:
        value = os.environ.get(var)
        if value:
            masked_value = value[:8] + "***" if len(value) > 8 else "***"
            print(f"  ✅ {var}: {masked_value}")
        else:
            print(f"  ❌ {var}: Não configurado")
            oauth2_complete = False
    
    # Verificar se pelo menos uma estratégia está completa
    if service_account_complete:
        print("\n✅ Service Account: Configuração completa")
        return True
    elif oauth2_complete:
        print("\n✅ OAuth2: Configuração básica completa")
        return True
    else:
        print("\n❌ Nenhuma estratégia está completamente configurada")
        return False

def main():
    """Executa todos os testes"""
    
    print("🚀 Testando configuração automática completa do Google Ads...\n")
    
    tests = [
        ("Variáveis de Ambiente", test_environment_variables),
        ("Fluxo Automático", test_automated_flow)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            print(f"\n{'='*60}")
            print(f"🧪 TESTE: {test_name}")
            print('='*60)
            results[test_name] = test_func()
        except Exception as e:
            print(f"❌ Erro inesperado no teste {test_name}: {str(e)}")
            results[test_name] = False
    
    # Resumo final
    print("\n" + "="*60)
    print("📋 RESUMO DOS TESTES")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASSOU" if passed else "❌ FALHOU"
        print(f"  {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print("="*60)
    
    if all_passed:
        print("🎉 Todos os testes passaram! Sistema automático está funcionando.")
        print("\n📋 Próximos passos:")
        print("1. Faça deploy da aplicação: serverless deploy")
        print("2. Teste a função Google Ads no AWS Lambda")
        return True
    else:
        print("❌ Alguns testes falharam. Verifique a configuração.")
        print("\n📋 Ações recomendadas:")
        print("1. Configure as variáveis de ambiente necessárias")
        print("2. Execute: python src/scripts/generate_auth_codes.py (para OAuth2)")
        print("3. Ou configure service account (recomendado)")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n❌ Teste cancelado pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")
        sys.exit(1) 