#!/usr/bin/env python
"""
Script para gerenciar associações MCC do Google Ads

Este script permite enviar convites de associação, verificar status
e gerenciar as associações entre contas de clientes e a conta MCC.
"""

import os
import sys
import json
import argparse
from pathlib import Path
from datetime import datetime

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from services.google_ads_mcc_service import GoogleAdsMCCService

def print_header():
    """Imprime o cabeçalho do script"""
    print("🔗 Gerenciador de Associações MCC - Google Ads")
    print("=" * 60)
    print("Sistema para gerenciar associações entre contas de clientes e MCC")
    print("=" * 60)

def check_mcc_configuration():
    """Verifica se a configuração MCC está correta"""
    print("\n🔍 VERIFICANDO CONFIGURAÇÃO MCC:")
    print("=" * 60)
    
    required_vars = [
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'GOOGLE_ADS_CLIENT_ID', 
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN',
        'MCC_CUSTOMER_ID'
    ]
    
    missing_vars = []
    for var in required_vars:
        value = os.environ.get(var)
        if value:
            # Mascarar valores sensíveis
            if 'TOKEN' in var or 'SECRET' in var:
                masked_value = value[:8] + "..." if len(value) > 8 else "***"
            else:
                masked_value = value
            print(f"   ✅ {var}: {masked_value}")
        else:
            print(f"   ❌ {var}: Ausente")
            missing_vars.append(var)
    
    if missing_vars:
        print(f"\n⚠️  Variáveis ausentes: {', '.join(missing_vars)}")
        print("Configure essas variáveis antes de continuar.")
        return False
    
    print("\n✅ Configuração MCC completa!")
    return True

def send_invitation_interactive():
    """Interface interativa para enviar convite"""
    print("\n📤 ENVIAR CONVITE DE ASSOCIAÇÃO:")
    print("=" * 60)
    
    try:
        client_customer_id = input("📝 Digite o Customer ID do cliente (formato: 1234567890): ").strip()
        if not client_customer_id:
            print("❌ Customer ID é obrigatório")
            return False
        
        # Remover hífens se existirem
        client_customer_id = client_customer_id.replace('-', '')
        
        client_name = input("📝 Digite o nome do cliente (opcional): ").strip()
        
        print(f"\n🚀 Enviando convite para cliente {client_customer_id}...")
        
        mcc_service = GoogleAdsMCCService()
        result = mcc_service.send_link_invitation(client_customer_id, client_name)
        
        if result['success']:
            print("✅ Convite enviado com sucesso!")
            print(f"   Link ID: {result['link_id']}")
            print(f"   Status: {result['status']}")
            print(f"\n💡 O cliente precisa aceitar o convite no Google Ads para completar a associação.")
        else:
            print(f"❌ Erro ao enviar convite: {result['error']}")
        
        return result['success']
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        return False

def check_status_interactive():
    """Interface interativa para verificar status"""
    print("\n🔍 VERIFICAR STATUS DE ASSOCIAÇÃO:")
    print("=" * 60)
    
    try:
        client_customer_id = input("📝 Digite o Customer ID do cliente: ").strip()
        if not client_customer_id:
            print("❌ Customer ID é obrigatório")
            return False
        
        # Remover hífens se existirem
        client_customer_id = client_customer_id.replace('-', '')
        
        print(f"\n🔍 Verificando status para cliente {client_customer_id}...")
        
        mcc_service = GoogleAdsMCCService()
        result = mcc_service.get_link_status(client_customer_id)
        
        if result['found']:
            print("✅ Associação encontrada!")
            print(f"   Status: {result['status']}")
            print(f"   Link ID: {result['link_id']}")
            if result.get('created_date'):
                print(f"   Data de criação: {result['created_date']}")
            
            # Explicar status
            status_explanations = {
                'PENDING': '⏳ Aguardando aceitação do cliente',
                'APPROVED': '✅ Associação aprovada e ativa',
                'REJECTED': '❌ Convite rejeitado pelo cliente',
                'CANCELLED': '🚫 Convite cancelado'
            }
            
            explanation = status_explanations.get(result['status'], '❓ Status desconhecido')
            print(f"   {explanation}")
            
        else:
            print("ℹ️  Nenhuma associação encontrada")
            if 'error' in result:
                print(f"   Erro: {result['error']}")
        
        return True
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        return False

def list_all_associations():
    """Lista todas as associações MCC"""
    print("\n📋 LISTAR TODAS AS ASSOCIAÇÕES:")
    print("=" * 60)
    
    try:
        print("🔍 Buscando associações...")
        
        mcc_service = GoogleAdsMCCService()
        links = mcc_service.list_all_links()
        
        if not links:
            print("ℹ️  Nenhuma associação encontrada")
            return True
        
        print(f"\n📊 Encontradas {len(links)} associações:")
        print("-" * 60)
        
        for i, link in enumerate(links, 1):
            print(f"{i}. Cliente: {link['client_customer_id']}")
            print(f"   Status: {link['status']}")
            print(f"   Link ID: {link['link_id']}")
            if link.get('created_date'):
                print(f"   Criado em: {link['created_date']}")
            print()
        
        return True
        
    except Exception as e:
        print(f"❌ Erro ao listar associações: {str(e)}")
        return False

def cancel_invitation_interactive():
    """Interface interativa para cancelar convite"""
    print("\n🚫 CANCELAR CONVITE DE ASSOCIAÇÃO:")
    print("=" * 60)
    
    try:
        client_customer_id = input("📝 Digite o Customer ID do cliente: ").strip()
        if not client_customer_id:
            print("❌ Customer ID é obrigatório")
            return False
        
        # Remover hífens se existirem
        client_customer_id = client_customer_id.replace('-', '')
        
        # Confirmar ação
        confirm = input(f"\n⚠️  Tem certeza que deseja cancelar o convite para {client_customer_id}? (y/n): ").strip().lower()
        if confirm not in ['y', 'yes', 's', 'sim']:
            print("❌ Operação cancelada")
            return False
        
        print(f"\n🚫 Cancelando convite para cliente {client_customer_id}...")
        
        mcc_service = GoogleAdsMCCService()
        result = mcc_service.cancel_link_invitation(client_customer_id)
        
        if result['success']:
            print("✅ Convite cancelado com sucesso!")
        else:
            print(f"❌ Erro ao cancelar convite: {result['error']}")
        
        return result['success']
        
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        return False

def show_menu():
    """Mostra o menu principal"""
    print("\n🎯 ESCOLHA UMA OPÇÃO:")
    print("=" * 60)
    print("1. 📤 Enviar convite de associação")
    print("2. 🔍 Verificar status de associação")
    print("3. 📋 Listar todas as associações")
    print("4. 🚫 Cancelar convite de associação")
    print("5. 🔧 Verificar configuração MCC")
    print("6. ❓ Mostrar ajuda")
    print("0. 🚪 Sair")
    
    try:
        choice = input("\n📝 Digite sua escolha (0-6): ").strip()
        return choice
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        return "0"

def show_help():
    """Mostra informações de ajuda"""
    print("\n❓ AJUDA - GERENCIADOR MCC:")
    print("=" * 60)
    
    print("\n📋 O que é MCC?")
    print("   MCC (My Client Center) é uma conta de gerenciamento que permite")
    print("   gerenciar múltiplas contas de anunciantes do Google Ads.")
    
    print("\n🔗 Como funciona a associação?")
    print("   1. Você envia um convite para a conta do cliente")
    print("   2. O cliente recebe uma notificação no Google Ads")
    print("   3. O cliente aceita ou rejeita o convite")
    print("   4. Após aceito, você pode gerenciar a conta do cliente")
    
    print("\n📤 Enviar convite:")
    print("   - Use quando quiser associar uma nova conta de cliente")
    print("   - Você precisa do Customer ID da conta do cliente")
    print("   - O cliente receberá uma notificação para aceitar")
    
    print("\n🔍 Verificar status:")
    print("   - Use para ver se um convite foi aceito")
    print("   - Status possíveis: PENDING, APPROVED, REJECTED, CANCELLED")
    
    print("\n📋 Listar associações:")
    print("   - Mostra todas as contas associadas ao seu MCC")
    print("   - Inclui status e datas de criação")
    
    print("\n🚫 Cancelar convite:")
    print("   - Use para cancelar um convite pendente")
    print("   - Só funciona para convites com status PENDING")
    
    print("\n🔧 Configuração necessária:")
    print("   - GOOGLE_ADS_DEVELOPER_TOKEN: Token de desenvolvedor")
    print("   - GOOGLE_ADS_CLIENT_ID: Client ID do OAuth2")
    print("   - GOOGLE_ADS_CLIENT_SECRET: Client Secret do OAuth2")
    print("   - GOOGLE_ADS_REFRESH_TOKEN: Refresh Token do OAuth2")
    print("   - MCC_CUSTOMER_ID: ID da sua conta MCC")

def main():
    """Função principal"""
    print_header()
    
    # Verificar configuração inicial
    if not check_mcc_configuration():
        print("\n❌ Configure as variáveis de ambiente antes de continuar.")
        return False
    
    while True:
        choice = show_menu()
        
        if choice == "0":
            print("\n👋 Obrigado por usar o gerenciador MCC!")
            break
        elif choice == "1":
            send_invitation_interactive()
        elif choice == "2":
            check_status_interactive()
        elif choice == "3":
            list_all_associations()
        elif choice == "4":
            cancel_invitation_interactive()
        elif choice == "5":
            check_mcc_configuration()
        elif choice == "6":
            show_help()
        else:
            print("❌ Opção inválida. Tente novamente.")
        
        # Pausa antes de mostrar menu novamente
        if choice != "0":
            input("\n⏸️  Pressione Enter para continuar...")
    
    return True

def execute_from_params(params):
    """
    Executa operação baseada em parâmetros (para uso via CLI)
    
    Args:
        params (dict): Parâmetros da operação
            - operation (str): Tipo de operação (send_invitation, check_status, etc.)
            - client_customer_id (str): ID da conta do cliente
            - client_name (str, opcional): Nome do cliente
    """
    operation = params.get('operation')
    client_customer_id = params.get('client_customer_id')
    client_name = params.get('client_name')
    
    if not operation:
        raise ValueError("Parâmetro 'operation' é obrigatório")
    
    mcc_service = GoogleAdsMCCService()
    
    if operation == 'send_invitation':
        if not client_customer_id:
            raise ValueError("Parâmetro 'client_customer_id' é obrigatório para send_invitation")
        
        client_customer_id = client_customer_id.replace('-', '')
        return mcc_service.send_link_invitation(client_customer_id, client_name)
    
    elif operation == 'check_status':
        if not client_customer_id:
            raise ValueError("Parâmetro 'client_customer_id' é obrigatório para check_status")
        
        client_customer_id = client_customer_id.replace('-', '')
        return mcc_service.get_link_status(client_customer_id)
    
    elif operation == 'list_all':
        return mcc_service.list_all_links()
    
    elif operation == 'cancel_invitation':
        if not client_customer_id:
            raise ValueError("Parâmetro 'client_customer_id' é obrigatório para cancel_invitation")
        
        client_customer_id = client_customer_id.replace('-', '')
        return mcc_service.cancel_link_invitation(client_customer_id)
    
    else:
        raise ValueError(f"Operação '{operation}' não reconhecida")

if __name__ == "__main__":
    try:
        # Verificar se foi chamado com parâmetros (modo CLI)
        if len(sys.argv) > 1:
            # Modo CLI com parâmetros
            parser = argparse.ArgumentParser(description='Gerenciador de Associações MCC')
            parser.add_argument('--operation', required=True, 
                              choices=['send_invitation', 'check_status', 'list_all', 'cancel_invitation'],
                              help='Tipo de operação a executar')
            parser.add_argument('--client-customer-id', help='Customer ID do cliente')
            parser.add_argument('--client-name', help='Nome do cliente')
            
            args = parser.parse_args()
            
            params = {
                'operation': args.operation,
                'client_customer_id': args.client_customer_id,
                'client_name': args.client_name
            }
            
            result = execute_from_params(params)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            # Modo interativo
            main()
            
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")
        sys.exit(1)
