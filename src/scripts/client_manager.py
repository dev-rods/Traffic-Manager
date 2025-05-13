#!/usr/bin/env python3
"""
Script para gerenciamento de clientes
Uso: python client_manager.py [comando] [argumentos]

Comandos:
  - create: Cria um novo cliente
    Argumentos: --name "Nome do Cliente" --email "email@cliente.com"
  - list: Lista todos os clientes
  - regenerate-key: Regenera a API key de um cliente
    Argumentos: --id "client-id"
  - deactivate: Desativa um cliente
    Argumentos: --id "client-id"
  - activate: Ativa um cliente
    Argumentos: --id "client-id"
"""

import argparse
import boto3
import os
import sys
import json
from boto3.dynamodb.conditions import Key

# Adiciona o diretório src ao PYTHONPATH para permitir importação de módulos
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# Importa o utilitário de autenticação
from src.utils.auth import ClientAuth

def setup_args():
    """Configura o parser de argumentos"""
    parser = argparse.ArgumentParser(description='Gerenciamento de clientes')
    
    subparsers = parser.add_subparsers(dest='command', help='Comando a ser executado')
    
    # Comando create
    create_parser = subparsers.add_parser('create', help='Cria um novo cliente')
    create_parser.add_argument('--name', required=True, help='Nome do cliente')
    create_parser.add_argument('--email', required=True, help='Email do cliente')
    
    # Comando list
    subparsers.add_parser('list', help='Lista todos os clientes')
    
    # Comando regenerate-key
    regen_parser = subparsers.add_parser('regenerate-key', help='Regenera a API key de um cliente')
    regen_parser.add_argument('--id', required=True, help='ID do cliente')
    
    # Comando deactivate
    deactivate_parser = subparsers.add_parser('deactivate', help='Desativa um cliente')
    deactivate_parser.add_argument('--id', required=True, help='ID do cliente')
    
    # Comando activate
    activate_parser = subparsers.add_parser('activate', help='Ativa um cliente')
    activate_parser.add_argument('--id', required=True, help='ID do cliente')
    
    return parser.parse_args()

def create_client(args, client_auth):
    """Cria um novo cliente"""
    try:
        client_data = client_auth.create_client(args.name, args.email)
        print(f"Cliente criado com sucesso!")
        print(f"ID: {client_data['clientId']}")
        print(f"Nome: {client_data['name']}")
        print(f"Email: {client_data['email']}")
        print(f"API Key: {client_data['apiKey']}")
        print("\nIMPORTANTE: Guarde a API Key em local seguro, pois ela não será mostrada novamente!")
    except Exception as e:
        print(f"Erro ao criar cliente: {str(e)}")
        sys.exit(1)

def list_clients(client_auth):
    """Lista todos os clientes"""
    try:
        # Precisa usar o scan porque não estamos consultando por chave primária
        response = client_auth.clients_table.scan()
        
        if 'Items' not in response or not response['Items']:
            print("Nenhum cliente encontrado.")
            return
        
        clients = response['Items']
        print(f"Total de clientes: {len(clients)}")
        print("\n{:<15} {:<30} {:<30} {:<10}".format("ID", "Nome", "Email", "Status"))
        print("-" * 85)
        
        for client in clients:
            status = "Ativo" if client.get('active', False) else "Inativo"
            print("{:<15} {:<30} {:<30} {:<10}".format(
                client['clientId'][:15], 
                client['name'][:30], 
                client['email'][:30],
                status
            ))
    except Exception as e:
        print(f"Erro ao listar clientes: {str(e)}")
        sys.exit(1)

def regenerate_key(args, client_auth):
    """Regenera a API key de um cliente"""
    try:
        # Obter cliente atual
        response = client_auth.clients_table.get_item(Key={'clientId': args.id})
        
        if 'Item' not in response:
            print(f"Cliente com ID '{args.id}' não encontrado.")
            return
        
        client = response['Item']
        
        # Gerar nova API key
        new_api_key = client_auth.generate_api_key()
        
        # Atualizar no DynamoDB
        client_auth.clients_table.update_item(
            Key={'clientId': args.id},
            UpdateExpression="set apiKey = :k",
            ExpressionAttributeValues={':k': new_api_key}
        )
        
        print(f"API Key regenerada com sucesso para o cliente {client['name']}!")
        print(f"Nova API Key: {new_api_key}")
        print("\nIMPORTANTE: Guarde a API Key em local seguro, pois ela não será mostrada novamente!")
    except Exception as e:
        print(f"Erro ao regenerar API key: {str(e)}")
        sys.exit(1)

def update_client_status(args, client_auth, active):
    """Ativa ou desativa um cliente"""
    try:
        # Verificar se o cliente existe
        response = client_auth.clients_table.get_item(Key={'clientId': args.id})
        
        if 'Item' not in response:
            print(f"Cliente com ID '{args.id}' não encontrado.")
            return
        
        client = response['Item']
        status_text = "ativado" if active else "desativado"
        
        # Atualizar status
        client_auth.clients_table.update_item(
            Key={'clientId': args.id},
            UpdateExpression="set active = :a",
            ExpressionAttributeValues={':a': active}
        )
        
        print(f"Cliente '{client['name']}' {status_text} com sucesso!")
    except Exception as e:
        status_text = "ativar" if active else "desativar"
        print(f"Erro ao {status_text} cliente: {str(e)}")
        sys.exit(1)

def main():
    """Função principal"""
    args = setup_args()
    
    # Verificar se CLIENTS_TABLE está definido no ambiente
    if 'CLIENTS_TABLE' not in os.environ:
        # Use a convenção de nomeação para definir o nome da tabela
        stage = os.environ.get('STAGE', 'dev')
        os.environ['CLIENTS_TABLE'] = f"traffic-manager-infra-{stage}-clients"
        print(f"Variável CLIENTS_TABLE não encontrada. Usando: {os.environ['CLIENTS_TABLE']}")
    
    client_auth = ClientAuth()
    
    if args.command == 'create':
        create_client(args, client_auth)
    elif args.command == 'list':
        list_clients(client_auth)
    elif args.command == 'regenerate-key':
        regenerate_key(args, client_auth)
    elif args.command == 'deactivate':
        update_client_status(args, client_auth, False)
    elif args.command == 'activate':
        update_client_status(args, client_auth, True)
    else:
        print("Comando inválido. Use --help para ver os comandos disponíveis.")
        sys.exit(1)

if __name__ == "__main__":
    main() 