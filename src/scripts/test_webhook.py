#!/usr/bin/env python3
"""
Script para testar o webhook localmente

Este script simula o envio de dados do Google Sheets para o webhook.
Útil para testes durante o desenvolvimento.

Uso:
  python test_webhook.py --api-key YOUR_API_KEY --url YOUR_WEBHOOK_URL
"""

import argparse
import json
import requests
import sys
from datetime import datetime

def setup_args():
    """Configuração dos argumentos de linha de comando"""
    parser = argparse.ArgumentParser(description='Testador de Webhook para Google Sheets')
    parser.add_argument('--api-key', required=True, help='API Key do cliente')
    parser.add_argument('--url', required=True, help='URL do webhook')
    parser.add_argument('--business-name', default="Empresa Teste", help='Nome da empresa')
    parser.add_argument('--industry', default="Tecnologia", help='Indústria/Setor')
    parser.add_argument('--budget', default="1000", help='Orçamento mensal')
    parser.add_argument('--objectives', default="Aumentar vendas online", help='Objetivos')
    parser.add_argument('--target-audience', default="Homens e mulheres, 25-45 anos", help='Público-alvo')
    return parser.parse_args()

def main():
    """Função principal"""
    args = setup_args()
    
    # Montar payload
    form_data = {
        'businessName': args.business_name,
        'industry': args.industry,
        'budget': args.budget,
        'objectives': args.objectives,
        'targetAudience': args.target_audience,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    payload = {
        'apiKey': args.api_key,
        'formData': form_data
    }
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': args.api_key  # Alternativa: incluir a API key nos headers também
    }
    
    print(f"Enviando payload para {args.url}:")
    print(json.dumps(payload, indent=2))
    
    try:
        response = requests.post(args.url, json=payload, headers=headers)
        print(f"\nCódigo de resposta: {response.status_code}")
        
        if response.status_code >= 200 and response.status_code < 300:
            print("Sucesso! Detalhes:")
        else:
            print("Erro! Detalhes:")
        
        try:
            print(json.dumps(response.json(), indent=2))
        except:
            print(response.text)
    
    except Exception as e:
        print(f"Erro ao enviar requisição: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 