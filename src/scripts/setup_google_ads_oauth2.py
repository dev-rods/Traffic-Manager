#!/usr/bin/env python
"""
Script Master para Configuração Automática do Google Ads OAuth2

Este script orienta o usuário através de todo o processo de configuração
do sistema automático de tokens para Google Ads API.
"""

import os
import sys
import json
from pathlib import Path

def print_header():
    """Imprime o cabeçalho do script"""
    print("🚀 Configurador Automático Google Ads OAuth2")
    print("=" * 60)
    print("Sistema de geração automática de tokens sem intervenção manual")
    print("=" * 60)

def print_strategies():
    """Explica as estratégias disponíveis"""
    
    print("\n📋 ESTRATÉGIAS DISPONÍVEIS:")
    print("=" * 60)
    
    print("\n🥇 ESTRATÉGIA 1: Service Account (RECOMENDADA)")
    print("   ✅ 100% Automático - zero intervenção manual")
    print("   ✅ Mais seguro - não expira")
    print("   ✅ Escalável para múltiplos clientes")
    print("   📋 Requer: Service Account + Developer Token")
    
    print("\n🥈 ESTRATÉGIA 2: OAuth2 com Códigos Pré-autorizados")
    print("   ⚡ Semi-automático - configuração única por cliente")
    print("   🔄 Tokens renovam automaticamente")
    print("   📋 Requer: Client ID + Client Secret + Códigos de autorização")
    
    print("\n🥉 ESTRATÉGIA 3: Webhook Authorization (AVANÇADO)")
    print("   🌐 Interface web para autorização")
    print("   🔄 Totalmente automático após setup inicial")
    print("   📋 Requer: Infraestrutura web adicional")

def check_current_configuration():
    """Verifica a configuração atual"""
    
    print("\n🔍 VERIFICANDO CONFIGURAÇÃO ATUAL:")
    print("=" * 60)
    
    # Verificar variáveis básicas
    developer_token = os.environ.get('GOOGLE_ADS_DEVELOPER_TOKEN')
    service_account = os.environ.get('GOOGLE_SERVICE_ACCOUNT_JSON')
    client_id = os.environ.get('GOOGLE_ADS_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_ADS_CLIENT_SECRET')
    
    print(f"\n📊 Status das Variáveis:")
    print(f"   GOOGLE_ADS_DEVELOPER_TOKEN: {'✅ Configurado' if developer_token else '❌ Ausente'}")
    print(f"   GOOGLE_SERVICE_ACCOUNT_JSON: {'✅ Configurado' if service_account else '❌ Ausente'}")
    print(f"   GOOGLE_ADS_CLIENT_ID: {'✅ Configurado' if client_id else '❌ Ausente'}")
    print(f"   GOOGLE_ADS_CLIENT_SECRET: {'✅ Configurado' if client_secret else '❌ Ausente'}")
    
    # Determinar estratégia recomendada
    if service_account and developer_token:
        print("\n🎯 Estratégia detectada: SERVICE ACCOUNT (Estratégia 1)")
        print("   ✅ Configuração ideal - sistema 100% automático")
        return 1
    elif client_id and client_secret and developer_token:
        print("\n🎯 Estratégia detectada: OAUTH2 (Estratégia 2)")
        print("   ⚡ Configuração semi-automática - precisa gerar códigos")
        return 2
    else:
        print("\n🎯 Estratégia recomendada: SERVICE ACCOUNT (Estratégia 1)")
        print("   💡 Configure service account para máxima automação")
        return 0

def show_strategy_1_setup():
    """Mostra como configurar Strategy 1 - Service Account"""
    
    print("\n🔧 SETUP ESTRATÉGIA 1 - SERVICE ACCOUNT:")
    print("=" * 60)
    
    print("\n📋 Passos:")
    print("1. Criar Service Account no Google Cloud Console")
    print("2. Baixar JSON do service account") 
    print("3. Configurar variáveis de ambiente")
    print("4. Testar configuração")
    
    print("\n🎯 Comandos:")
    print("   python src/scripts/setup_service_account.py")
    print("   python src/scripts/test_automated_google_ads.py")
    
    print("\n💡 Vantagens:")
    print("   ✅ Zero manutenção após configuração")
    print("   ✅ Funciona para múltiplos clientes")
    print("   ✅ Mais seguro que OAuth2")

def show_strategy_2_setup():
    """Mostra como configurar Strategy 2 - OAuth2"""
    
    print("\n🔧 SETUP ESTRATÉGIA 2 - OAUTH2:")
    print("=" * 60)
    
    print("\n📋 Passos:")
    print("1. Configurar OAuth2 credentials no Google Cloud Console")
    print("2. Gerar códigos de autorização por cliente")
    print("3. Configurar variáveis de ambiente")
    print("4. Testar configuração")
    
    print("\n🎯 Comandos:")
    print("   python src/scripts/generate_auth_codes.py")
    print("   python src/scripts/test_automated_google_ads.py")
    
    print("\n💡 Vantagens:")
    print("   ⚡ Setup mais rápido")
    print("   🔄 Tokens renovam automaticamente")

def show_testing_commands():
    """Mostra comandos de teste"""
    
    print("\n🧪 COMANDOS DE TESTE:")
    print("=" * 60)
    
    print("\n📊 Testes Disponíveis:")
    print("   python src/scripts/test_automated_google_ads.py  # Teste completo")
    print("   python src/scripts/generate_auth_codes.py        # Gerar códigos OAuth2")
    print("   python src/scripts/setup_service_account.py      # Configurar service account")
    
    print("\n🚀 Deploy:")
    print("   serverless deploy  # Deploy da infraestrutura")

def show_troubleshooting():
    """Mostra dicas de troubleshooting"""
    
    print("\n🔧 TROUBLESHOOTING:")
    print("=" * 60)
    
    print("\n❌ Problemas Comuns:")
    print("   'refresh_token missing' → Execute generate_auth_codes.py")
    print("   'developer_token invalid' → Verifique token no Google Ads")
    print("   'service account error' → Verifique JSON e permissões")
    print("   'table not found' → Execute serverless deploy")
    
    print("\n🔍 Debug:")
    print("   export GOOGLE_ADS_DEBUG=1  # Ativar debug")
    print("   python src/scripts/test_automated_google_ads.py -v  # Verbose")

def get_user_choice():
    """Obtém escolha do usuário"""
    
    print("\n🎯 ESCOLHA UMA OPÇÃO:")
    print("=" * 60)
    print("1. 🔧 Configurar Service Account (Estratégia 1)")
    print("2. 🔧 Configurar OAuth2 (Estratégia 2)")
    print("3. 🧪 Testar configuração atual")
    print("4. 🚀 Fazer deploy")
    print("5. 🔍 Troubleshooting")
    print("6. ❓ Mostrar estratégias novamente")
    print("0. 🚪 Sair")
    
    try:
        choice = input("\n📝 Digite sua escolha (0-6): ").strip()
        return choice
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return "0"

def run_script(script_name):
    """Executa um script específico"""
    
    script_path = Path(__file__).parent / script_name
    
    if script_path.exists():
        print(f"\n🚀 Executando: {script_name}")
        print("=" * 60)
        os.system(f"python {script_path}")
    else:
        print(f"❌ Script não encontrado: {script_name}")

def main():
    """Função principal"""
    
    print_header()
    print_strategies()
    
    current_strategy = check_current_configuration()
    
    while True:
        choice = get_user_choice()
        
        if choice == "0":
            print("\n👋 Obrigado por usar o configurador!")
            break
        elif choice == "1":
            show_strategy_1_setup()
            run_choice = input("\n🚀 Executar setup_service_account.py? (y/n): ").strip().lower()
            if run_choice in ['y', 'yes', 's', 'sim']:
                run_script("setup_service_account.py")
        elif choice == "2":
            show_strategy_2_setup()
            run_choice = input("\n🚀 Executar generate_auth_codes.py? (y/n): ").strip().lower()
            if run_choice in ['y', 'yes', 's', 'sim']:
                run_script("generate_auth_codes.py")
        elif choice == "3":
            run_script("test_automated_google_ads.py")
        elif choice == "4":
            print("\n🚀 Fazendo deploy...")
            print("=" * 60)
            os.system("serverless deploy")
        elif choice == "5":
            show_troubleshooting()
        elif choice == "6":
            print_strategies()
        else:
            print("❌ Opção inválida. Tente novamente.")
    
    return True

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")
        sys.exit(1) 