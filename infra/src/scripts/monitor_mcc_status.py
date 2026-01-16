#!/usr/bin/env python
"""
Script para monitorar e atualizar status das associações MCC

Este script verifica periodicamente o status das associações MCC
e atualiza os registros dos clientes no DynamoDB.
"""

import os
import sys
import json
import boto3
from datetime import datetime, timedelta
from pathlib import Path

# Adicionar src ao path para imports
sys.path.append(str(Path(__file__).parent.parent))

from services.google_ads_mcc_service import GoogleAdsMCCService

def execute(params):
    """
    Executa monitoramento de associações MCC
    
    Args:
        params (dict): Parâmetros do comando
            - check_all (bool, opcional): Se deve verificar todos os clientes
            - client_id (str, opcional): ID específico do cliente para verificar
            - update_status (bool, opcional): Se deve atualizar status no DynamoDB
    Returns:
        dict: Resultado do monitoramento
    """
    print("Iniciando monitoramento de associações MCC...")
    
    check_all = params.get("check_all", True)
    specific_client_id = params.get("client_id")
    update_status = params.get("update_status", True)
    
    # Inicializar recursos
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    mcc_service = GoogleAdsMCCService()
    results = {
        "checked_clients": 0,
        "updated_clients": 0,
        "pending_invitations": 0,
        "approved_links": 0,
        "rejected_links": 0,
        "errors": 0,
        "details": []
    }
    
    try:
        if specific_client_id:
            # Verificar cliente específico
            print(f"Verificando cliente específico: {specific_client_id}")
            clients_to_check = [{"clientId": specific_client_id}]
        else:
            # Buscar todos os clientes com Google Ads Customer ID
            print("Buscando todos os clientes com Google Ads...")
            response = clients_table.scan(
                FilterExpression="attribute_exists(googleAdsCustomerId)"
            )
            clients_to_check = response.get("Items", [])
        
        print(f"Encontrados {len(clients_to_check)} clientes para verificar")
        
        for client in clients_to_check:
            client_id = client["clientId"]
            customer_id = client.get("googleAdsCustomerId")
            
            if not customer_id:
                print(f"⚠️  Cliente {client_id} não tem googleAdsCustomerId")
                continue
            
            print(f"\n🔍 Verificando cliente: {client_id} (Customer ID: {customer_id})")
            
            try:
                # Verificar status da associação MCC
                status_result = mcc_service.get_link_status(customer_id)
                results["checked_clients"] += 1
                
                current_status = client.get("mccStatus", "NOT_LINKED")
                new_status = status_result.get("status", "NOT_LINKED") if status_result.get("found") else "NOT_LINKED"
                
                print(f"   Status atual: {current_status}")
                print(f"   Status no Google Ads: {new_status}")
                
                # Atualizar status se necessário
                if update_status and new_status != current_status:
                    print(f"   🔄 Atualizando status de {current_status} para {new_status}")
                    
                    update_data = {
                        "mccStatus": new_status,
                        "mccLastCheckedAt": datetime.utcnow().isoformat()
                    }
                    
                    if status_result.get("found"):
                        update_data["mccLinkId"] = status_result.get("link_id")
                        if status_result.get("created_date"):
                            update_data["mccLinkCreatedAt"] = status_result.get("created_date")
                    
                    clients_table.update_item(
                        Key={"clientId": client_id},
                        UpdateExpression="SET " + ", ".join([f"{k} = :{k}" for k in update_data.keys()]),
                        ExpressionAttributeValues={f":{k}": v for k, v in update_data.items()}
                    )
                    
                    results["updated_clients"] += 1
                    print(f"   ✅ Status atualizado com sucesso")
                
                # Contar por tipo de status
                if new_status == "PENDING":
                    results["pending_invitations"] += 1
                elif new_status == "APPROVED":
                    results["approved_links"] += 1
                elif new_status == "REJECTED":
                    results["rejected_links"] += 1
                
                # Adicionar detalhes
                results["details"].append({
                    "client_id": client_id,
                    "customer_id": customer_id,
                    "old_status": current_status,
                    "new_status": new_status,
                    "updated": new_status != current_status,
                    "link_id": status_result.get("link_id"),
                    "created_date": status_result.get("created_date")
                })
                
            except Exception as e:
                print(f"   ❌ Erro ao verificar cliente {client_id}: {str(e)}")
                results["errors"] += 1
                results["details"].append({
                    "client_id": client_id,
                    "customer_id": customer_id,
                    "error": str(e)
                })
        
        # Resumo final
        print(f"\n📊 RESUMO DO MONITORAMENTO:")
        print(f"   Clientes verificados: {results['checked_clients']}")
        print(f"   Status atualizados: {results['updated_clients']}")
        print(f"   Convites pendentes: {results['pending_invitations']}")
        print(f"   Associações aprovadas: {results['approved_links']}")
        print(f"   Convites rejeitados: {results['rejected_links']}")
        print(f"   Erros: {results['errors']}")
        
        return results
        
    except Exception as e:
        print(f"❌ Erro geral no monitoramento: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "results": results
        }

def check_pending_invitations():
    """
    Verifica especificamente convites pendentes e envia alertas se necessário
    """
    print("🔍 Verificando convites pendentes...")
    
    dynamodb = boto3.resource("dynamodb")
    clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
    
    # Buscar clientes com convites pendentes há mais de 24 horas
    cutoff_time = (datetime.utcnow() - timedelta(hours=24)).isoformat()
    
    response = clients_table.scan(
        FilterExpression="mccStatus = :status AND mccInvitationSentAt < :cutoff",
        ExpressionAttributeValues={
            ":status": "PENDING",
            ":cutoff": cutoff_time
        }
    )
    
    pending_clients = response.get("Items", [])
    
    if pending_clients:
        print(f"⚠️  {len(pending_clients)} convites pendentes há mais de 24 horas:")
        for client in pending_clients:
            print(f"   - {client['name']} ({client['clientId']}) - Enviado em: {client.get('mccInvitationSentAt')}")
        
        # Aqui você pode implementar notificações (email, Slack, etc.)
        return {
            "pending_count": len(pending_clients),
            "clients": pending_clients,
            "alert_needed": True
        }
    else:
        print("✅ Nenhum convite pendente há mais de 24 horas")
        return {
            "pending_count": 0,
            "alert_needed": False
        }

def main():
    """Função principal para execução interativa"""
    print("🔍 Monitor de Associações MCC - Google Ads")
    print("=" * 60)
    
    # Verificar configuração MCC
    required_vars = ['GOOGLE_ADS_DEVELOPER_TOKEN', 'OAUTH2_CLIENT_ID', 
                     'OAUTH2_CLIENT_SECRET', 'GOOGLE_ADS_REFRESH_TOKEN', 'MCC_CUSTOMER_ID']
    
    missing_vars = [var for var in required_vars if not os.environ.get(var)]
    if missing_vars:
        print(f"❌ Variáveis de ambiente ausentes: {', '.join(missing_vars)}")
        return False
    
    print("✅ Configuração MCC verificada")
    
    while True:
        print("\n🎯 ESCOLHA UMA OPÇÃO:")
        print("1. 🔍 Verificar todos os clientes")
        print("2. 🔍 Verificar cliente específico")
        print("3. ⏰ Verificar convites pendentes")
        print("4. 📊 Mostrar estatísticas")
        print("0. 🚪 Sair")
        
        try:
            choice = input("\n📝 Digite sua escolha (0-4): ").strip()
            
            if choice == "0":
                print("👋 Saindo do monitor...")
                break
            elif choice == "1":
                print("\n🔍 Verificando todos os clientes...")
                result = execute({"check_all": True, "update_status": True})
                print(f"\n✅ Verificação concluída: {result['checked_clients']} clientes verificados")
            elif choice == "2":
                client_id = input("📝 Digite o Client ID: ").strip()
                if client_id:
                    print(f"\n🔍 Verificando cliente {client_id}...")
                    result = execute({"client_id": client_id, "update_status": True})
                    print(f"\n✅ Verificação concluída")
                else:
                    print("❌ Client ID é obrigatório")
            elif choice == "3":
                result = check_pending_invitations()
                if result["alert_needed"]:
                    print(f"\n⚠️  Atenção: {result['pending_count']} convites precisam de acompanhamento")
                else:
                    print("\n✅ Todos os convites estão dentro do prazo")
            elif choice == "4":
                show_statistics()
            else:
                print("❌ Opção inválida")
                
        except KeyboardInterrupt:
            print("\n❌ Operação cancelada")
            break
        except Exception as e:
            print(f"❌ Erro: {str(e)}")
    
    return True

def show_statistics():
    """Mostra estatísticas das associações MCC"""
    print("\n📊 ESTATÍSTICAS DAS ASSOCIAÇÕES MCC:")
    print("=" * 60)
    
    try:
        dynamodb = boto3.resource("dynamodb")
        clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))
        
        # Buscar todos os clientes
        response = clients_table.scan()
        clients = response.get("Items", [])
        
        # Contar por status
        status_counts = {}
        total_with_google_ads = 0
        
        for client in clients:
            if client.get("googleAdsCustomerId"):
                total_with_google_ads += 1
                status = client.get("mccStatus", "NOT_LINKED")
                status_counts[status] = status_counts.get(status, 0) + 1
        
        print(f"📈 Total de clientes: {len(clients)}")
        print(f"📈 Clientes com Google Ads: {total_with_google_ads}")
        print(f"\n📊 Status das associações MCC:")
        
        for status, count in status_counts.items():
            percentage = (count / total_with_google_ads * 100) if total_with_google_ads > 0 else 0
            print(f"   {status}: {count} ({percentage:.1f}%)")
        
        # Mostrar clientes por status
        for status in ["PENDING", "APPROVED", "REJECTED", "ERROR"]:
            if status_counts.get(status, 0) > 0:
                print(f"\n📋 Clientes com status {status}:")
                for client in clients:
                    if client.get("mccStatus") == status and client.get("googleAdsCustomerId"):
                        print(f"   - {client['name']} ({client['clientId']})")
        
    except Exception as e:
        print(f"❌ Erro ao mostrar estatísticas: {str(e)}")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n❌ Operação cancelada pelo usuário")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Erro inesperado: {str(e)}")
        sys.exit(1)
