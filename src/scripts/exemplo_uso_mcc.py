#!/usr/bin/env python
"""
Exemplo prático de uso do sistema MCC

Este script demonstra como usar o sistema de associação MCC
em um cenário real de criação e gerenciamento de clientes.
"""

import os
import sys
import json
from pathlib import Path

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from scripts.create_client import execute as create_client
from scripts.monitor_mcc_status import execute as monitor_mcc_status
from services.google_ads_mcc_service import GoogleAdsMCCService

def exemplo_criacao_cliente_completo():
    """Exemplo completo de criação de cliente com associação MCC"""
    
    print("🚀 EXEMPLO: Criação Completa de Cliente com MCC")
    print("=" * 60)
    
    # Dados do cliente de exemplo
    cliente_data = {
        "name": "Empresa Exemplo Ltda",
        "email": "contato@empresaexemplo.com",
        "googleAdsCustomerId": "1234567890",  # Substitua por um ID real
        "sendMccInvitation": True
    }
    
    print(f"📝 Criando cliente: {cliente_data['name']}")
    print(f"📧 Email: {cliente_data['email']}")
    print(f"🆔 Customer ID: {cliente_data['googleAdsCustomerId']}")
    
    try:
        # Criar cliente
        resultado = create_client(cliente_data)
        
        print(f"\n✅ Cliente criado com sucesso!")
        print(f"   Client ID: {resultado['clientId']}")
        print(f"   Status MCC: {resultado['mccStatus']}")
        
        if resultado.get('mccInvitation'):
            convite = resultado['mccInvitation']
            if convite['success']:
                print(f"   ✅ Convite MCC enviado!")
                print(f"   Link ID: {convite['link_id']}")
                print(f"   Status: {convite['status']}")
            else:
                print(f"   ❌ Erro no convite MCC: {convite['error']}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro ao criar cliente: {str(e)}")
        return None

def exemplo_verificacao_status():
    """Exemplo de verificação de status de associação"""
    
    print("\n🔍 EXEMPLO: Verificação de Status MCC")
    print("=" * 60)
    
    customer_id = "1234567890"  # Substitua por um ID real
    
    try:
        mcc_service = GoogleAdsMCCService()
        status = mcc_service.get_link_status(customer_id)
        
        if status['found']:
            print(f"✅ Associação encontrada!")
            print(f"   Status: {status['status']}")
            print(f"   Link ID: {status['link_id']}")
            if status.get('created_date'):
                print(f"   Criado em: {status['created_date']}")
            
            # Explicar status
            explicacoes = {
                'PENDING': '⏳ Aguardando aceitação do cliente',
                'APPROVED': '✅ Associação aprovada e ativa',
                'REJECTED': '❌ Convite rejeitado pelo cliente',
                'CANCELLED': '🚫 Convite cancelado'
            }
            
            explicacao = explicacoes.get(status['status'], '❓ Status desconhecido')
            print(f"   {explicacao}")
            
        else:
            print("ℹ️  Nenhuma associação encontrada")
            if 'error' in status:
                print(f"   Erro: {status['error']}")
        
        return status
        
    except Exception as e:
        print(f"❌ Erro ao verificar status: {str(e)}")
        return None

def exemplo_listagem_associacoes():
    """Exemplo de listagem de todas as associações"""
    
    print("\n📋 EXEMPLO: Listagem de Todas as Associações")
    print("=" * 60)
    
    try:
        mcc_service = GoogleAdsMCCService()
        links = mcc_service.list_all_links()
        
        if not links:
            print("ℹ️  Nenhuma associação encontrada")
            return []
        
        print(f"📊 Encontradas {len(links)} associações:")
        print("-" * 60)
        
        for i, link in enumerate(links, 1):
            print(f"{i}. Cliente: {link['client_customer_id']}")
            print(f"   Status: {link['status']}")
            print(f"   Link ID: {link['link_id']}")
            if link.get('created_date'):
                print(f"   Criado em: {link['created_date']}")
            print()
        
        return links
        
    except Exception as e:
        print(f"❌ Erro ao listar associações: {str(e)}")
        return []

def exemplo_monitoramento():
    """Exemplo de monitoramento de status"""
    
    print("\n🔍 EXEMPLO: Monitoramento de Status")
    print("=" * 60)
    
    try:
        # Monitorar todos os clientes
        resultado = monitor_mcc_status({
            "check_all": True,
            "update_status": True
        })
        
        print(f"📊 Resultado do monitoramento:")
        print(f"   Clientes verificados: {resultado['checked_clients']}")
        print(f"   Status atualizados: {resultado['updated_clients']}")
        print(f"   Convites pendentes: {resultado['pending_invitations']}")
        print(f"   Associações aprovadas: {resultado['approved_links']}")
        print(f"   Convites rejeitados: {resultado['rejected_links']}")
        print(f"   Erros: {resultado['errors']}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro no monitoramento: {str(e)}")
        return None

def exemplo_envio_convite_manual():
    """Exemplo de envio manual de convite"""
    
    print("\n📤 EXEMPLO: Envio Manual de Convite")
    print("=" * 60)
    
    customer_id = "1234567890"  # Substitua por um ID real
    client_name = "Cliente Manual"
    
    try:
        mcc_service = GoogleAdsMCCService()
        resultado = mcc_service.send_link_invitation(customer_id, client_name)
        
        if resultado['success']:
            print(f"✅ Convite enviado com sucesso!")
            print(f"   Link ID: {resultado['link_id']}")
            print(f"   Status: {resultado['status']}")
            print(f"   Mensagem: {resultado['message']}")
        else:
            print(f"❌ Erro ao enviar convite: {resultado['error']}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        return None

def exemplo_cancelamento_convite():
    """Exemplo de cancelamento de convite"""
    
    print("\n🚫 EXEMPLO: Cancelamento de Convite")
    print("=" * 60)
    
    customer_id = "1234567890"  # Substitua por um ID real
    
    try:
        mcc_service = GoogleAdsMCCService()
        resultado = mcc_service.cancel_link_invitation(customer_id)
        
        if resultado['success']:
            print(f"✅ Convite cancelado com sucesso!")
            print(f"   Mensagem: {resultado['message']}")
        else:
            print(f"❌ Erro ao cancelar convite: {resultado['error']}")
        
        return resultado
        
    except Exception as e:
        print(f"❌ Erro inesperado: {str(e)}")
        return None

def verificar_configuracao():
    """Verifica se a configuração está correta"""
    
    print("🔧 VERIFICANDO CONFIGURAÇÃO")
    print("=" * 60)
    
    variaveis_necessarias = [
        'GOOGLE_ADS_DEVELOPER_TOKEN',
        'GOOGLE_ADS_CLIENT_ID',
        'GOOGLE_ADS_CLIENT_SECRET',
        'GOOGLE_ADS_REFRESH_TOKEN',
        'MCC_CUSTOMER_ID',
        'CLIENTS_TABLE',
        'EXECUTION_HISTORY_TABLE'
    ]
    
    configuracao_ok = True
    
    for var in variaveis_necessarias:
        valor = os.environ.get(var)
        if valor:
            # Mascarar valores sensíveis
            if 'TOKEN' in var or 'SECRET' in var:
                valor_mascarado = valor[:8] + "..." if len(valor) > 8 else "***"
            else:
                valor_mascarado = valor
            print(f"   ✅ {var}: {valor_mascarado}")
        else:
            print(f"   ❌ {var}: Ausente")
            configuracao_ok = False
    
    if configuracao_ok:
        print("\n✅ Configuração completa!")
    else:
        print("\n❌ Configure as variáveis ausentes antes de continuar")
    
    return configuracao_ok

def main():
    """Função principal com menu de exemplos"""
    
    print("🎯 EXEMPLOS PRÁTICOS - SISTEMA MCC")
    print("=" * 60)
    print("Este script demonstra como usar o sistema de associação MCC")
    print("em cenários reais de gestão de clientes.")
    print("=" * 60)
    
    # Verificar configuração
    if not verificar_configuracao():
        print("\n⚠️  Configure as variáveis de ambiente antes de executar os exemplos")
        return False
    
    while True:
        print("\n🎯 ESCOLHA UM EXEMPLO:")
        print("1. 🚀 Criação completa de cliente com MCC")
        print("2. 🔍 Verificação de status de associação")
        print("3. 📋 Listagem de todas as associações")
        print("4. 🔍 Monitoramento de status")
        print("5. 📤 Envio manual de convite")
        print("6. 🚫 Cancelamento de convite")
        print("7. 🔧 Verificar configuração novamente")
        print("0. 🚪 Sair")
        
        try:
            escolha = input("\n📝 Digite sua escolha (0-7): ").strip()
            
            if escolha == "0":
                print("\n👋 Obrigado por usar os exemplos!")
                break
            elif escolha == "1":
                exemplo_criacao_cliente_completo()
            elif escolha == "2":
                exemplo_verificacao_status()
            elif escolha == "3":
                exemplo_listagem_associacoes()
            elif escolha == "4":
                exemplo_monitoramento()
            elif escolha == "5":
                exemplo_envio_convite_manual()
            elif escolha == "6":
                exemplo_cancelamento_convite()
            elif escolha == "7":
                verificar_configuracao()
            else:
                print("❌ Opção inválida. Tente novamente.")
            
            # Pausa antes de mostrar menu novamente
            if escolha != "0":
                input("\n⏸️  Pressione Enter para continuar...")
                
        except KeyboardInterrupt:
            print("\n❌ Operação cancelada pelo usuário")
            break
        except Exception as e:
            print(f"❌ Erro inesperado: {str(e)}")
    
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
