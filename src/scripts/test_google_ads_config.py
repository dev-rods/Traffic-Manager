#!/usr/bin/env python
"""
Script para testar configuração do Google Ads

Este script verifica se todas as configurações necessárias para o Google Ads
estão corretas e se é possível criar um cliente autenticado.
"""

import os
import sys
from pathlib import Path

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

def test_environment_variables():
    """Testa se as variáveis de ambiente estão configuradas"""
    
    print("🧪 Testando variáveis de ambiente...")
    
    required_vars = [
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'OAUTH2_CLIENT_ID', 
        'OAUTH2_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN'
    ]
    
    missing_vars = []
    
    for var in required_vars:
        value = os.environ.get(var)
        if not value:
            missing_vars.append(var)
        else:
            # Mascarar valor para log seguro
            masked_value = value[:8] + "***" if len(value) > 8 else "***"
            print(f"  ✅ {var}: {masked_value}")
    
    if missing_vars:
        print(f"  ❌ Variáveis ausentes: {missing_vars}")
        return False
    
    print("  ✅ Todas as variáveis de ambiente estão configuradas")
    return True

def test_google_ads_config():
    """Testa se a configuração do Google Ads está correta"""
    
    print("\n🧪 Testando GoogleAdsConfig...")
    
    try:
        from services.google_ads_config import GoogleAdsConfig
        
        config_service = GoogleAdsConfig()
        config = config_service.get_google_ads_config("1570932315")  # Customer ID de exemplo
        
        print("  ✅ Configuração carregada com sucesso")
        print(f"  📋 Campos configurados: {list(config.keys())}")
        
        # Verificar campos obrigatórios
        required_fields = ['developer_token', 'client_id', 'client_secret', 'refresh_token', 'use_proto_plus']
        missing_fields = [field for field in required_fields if field not in config]
        
        if missing_fields:
            print(f"  ❌ Campos ausentes na configuração: {missing_fields}")
            return False
        
        print("  ✅ Todos os campos obrigatórios estão presentes")
        return True
        
    except Exception as e:
        print(f"  ❌ Erro na configuração: {str(e)}")
        return False

def test_google_ads_client():
    """Testa se é possível criar um cliente Google Ads"""
    
    print("\n🧪 Testando criação do cliente Google Ads...")
    
    try:
        from google.ads.googleads.client import GoogleAdsClient
        from services.google_ads_config import GoogleAdsConfig
        
        # Obter configuração
        config_service = GoogleAdsConfig()
        config = config_service.get_google_ads_config("1570932315")
        
        # Tentar criar cliente fixando na versão suportada pelo ambiente
        client = GoogleAdsClient.load_from_dict(config, version="v14")
        print("  ✅ Cliente Google Ads criado com sucesso")
        
        # Testar obtenção de serviço
        customer_service = client.get_service("CustomerService")
        print("  ✅ Serviço CustomerService obtido com sucesso")
        
        print("  ✅ Cliente está funcional e pronto para uso")
        return True
        
    except Exception as e:
        print(f"  ❌ Erro ao criar cliente: {str(e)}")
        
        # Dar dicas baseadas no erro
        error_str = str(e)
        if "refresh_token" in error_str.lower():
            print("  💡 Dica: Verifique se a variável GOOGLE_ADS_REFRESH_TOKEN está configurada")
        elif "client_id" in error_str.lower():
            print("  💡 Dica: Verifique se a variável OAUTH2_CLIENT_ID está configurada")
        elif "client_secret" in error_str.lower():
            print("  💡 Dica: Verifique se a variável OAUTH2_CLIENT_SECRET está configurada")
        elif "developer_token" in error_str.lower():
            print("  💡 Dica: Verifique se a variável GOOGLE_ADS_DEVELOPER_TOKEN está configurada")
        
        return False

def test_google_ads_dependencies():
    """Testa se as dependências necessárias estão instaladas"""
    
    print("\n🧪 Testando dependências...")
    
    try:
        import google.ads.googleads.client
        print("  ✅ google-ads instalado")
    except ImportError:
        print("  ❌ google-ads não encontrado. Execute: pip install google-ads")
        return False
    
    try:
        import google_auth_oauthlib.flow
        print("  ✅ google-auth-oauthlib instalado")
    except ImportError:
        print("  ❌ google-auth-oauthlib não encontrado. Execute: pip install google-auth-oauthlib")
        return False
    
    print("  ✅ Todas as dependências estão instaladas")
    return True

def main():
    """Executa todos os testes"""
    
    print("🚀 Testando configuração completa do Google Ads...\n")
    
    tests = [
        ("Dependências", test_google_ads_dependencies),
        ("Variáveis de Ambiente", test_environment_variables),
        ("GoogleAdsConfig", test_google_ads_config),
        ("Cliente Google Ads", test_google_ads_client)
    ]
    
    results = {}
    
    for test_name, test_func in tests:
        try:
            results[test_name] = test_func()
        except Exception as e:
            print(f"  ❌ Erro inesperado no teste {test_name}: {str(e)}")
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
        print("🎉 Todos os testes passaram! Configuração está correta.")
        print("\n📋 Próximos passos:")
        print("1. Faça deploy da aplicação: serverless deploy")
        print("2. Teste a função Google Ads no AWS Lambda")
        return True
    else:
        print("❌ Alguns testes falharam. Verifique a configuração.")
        print("\n📋 Ações recomendadas:")
        print("1. Execute o script generate_refresh_token.py se necessário")
        print("2. Configure todas as variáveis de ambiente")
        print("3. Verifique se as credenciais estão corretas")
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