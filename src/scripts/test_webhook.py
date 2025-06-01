#!/usr/bin/env python3
"""
Script para testar webhook

Este script simula o envio de dados para o webhook, útil para testes.
"""
import logging
import requests
import json
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def execute(params):
    """
    Executa o teste de webhook
    
    Args:
        params (dict): Parâmetros do comando
            - url (str): URL do webhook
            - apiKey (str): API Key do cliente
            - businessName (str, opcional): Nome da empresa
            - industry (str, opcional): Indústria/Setor
            - budget (str, opcional): Orçamento mensal
            - objectives (str, opcional): Objetivos
            - targetAudience (str, opcional): Público-alvo
            
    Returns:
        dict: Resultado do teste
    """
    url = params.get("url")
    api_key = params.get("apiKey")
    
    if not url or not api_key:
        raise ValueError("URL e API Key são obrigatórios")
    
    logger.info(f"Testando webhook: {url}")
    
    # Montar dados do formulário
    form_data = {
        'businessName': params.get('businessName', 'Empresa Teste'),
        'industry': params.get('industry', 'Tecnologia'),
        'budget': params.get('budget', '1000'),
        'objectives': params.get('objectives', 'Aumentar vendas online'),
        'targetAudience': params.get('targetAudience', 'Homens e mulheres, 25-45 anos'),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Montar payload
    payload = {
        'apiKey': api_key,
        'formData': form_data
    }
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key
    }
    
    logger.info(f"Enviando payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=30)
        
        result = {
            "url": url,
            "statusCode": response.status_code,
            "success": 200 <= response.status_code < 300,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Tentar parsear resposta como JSON
        try:
            result["response"] = response.json()
        except:
            result["response"] = response.text
        
        if result["success"]:
            logger.info(f"Webhook testado com sucesso. Status: {response.status_code}")
        else:
            logger.warning(f"Webhook retornou erro. Status: {response.status_code}")
        
        return result
        
    except requests.exceptions.Timeout:
        raise ValueError("Timeout ao conectar com o webhook")
    except requests.exceptions.ConnectionError:
        raise ValueError("Erro de conexão com o webhook")
    except Exception as e:
        raise ValueError(f"Erro ao testar webhook: {str(e)}")

if __name__ == "__main__":
    # Exemplo de uso
    params = {
        "url": "https://example.com/webhook",
        "apiKey": "your_api_key"
    }
    result = execute(params)
    print(result) 