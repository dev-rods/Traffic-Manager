"""
Script para testar webhooks enviando dados de teste
"""
import requests
import json
import logging
from datetime import datetime

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

def test_webhook(params):
    """
    Envia uma requisição de teste para um webhook

    Args:
        params (dict): Parâmetros do teste
            - url (str): URL do webhook
            - apiKey (str): API Key do cliente
            - formData (dict, optional): Dados do formulário

    Returns:
        dict: Resultado da requisição
    """
    url = params.get('url')
    api_key = params.get('apiKey')
    form_data = params.get('formData', {})
    
    if not url:
        raise ValueError('URL do webhook é obrigatória')
    
    if not api_key:
        raise ValueError('API Key é obrigatória')
    
    # Preparando os dados do formulário com valores padrão se não fornecidos
    default_form_data = {
        'businessName': form_data.get('businessName', 'Empresa Teste'),
        'industry': form_data.get('industry', 'Tecnologia'),
        'budget': form_data.get('budget', '1000'),
        'objectives': form_data.get('objectives', 'Aumentar vendas online'),
        'targetAudience': form_data.get('targetAudience', 'Homens e mulheres, 25-45 anos'),
        'timestamp': datetime.utcnow().isoformat()
    }
    
    # Montando o payload
    payload = {
        'apiKey': api_key,
        'formData': default_form_data
    }
    
    # Headers
    headers = {
        'Content-Type': 'application/json',
        'x-api-key': api_key
    }
    
    logger.info(f"Enviando payload para {url}: {json.dumps(payload)}")
    
    try:
        # Enviando a requisição
        response = requests.post(url, json=payload, headers=headers)
        
        result = {
            'status': response.status_code,
            'statusText': response.reason,
            'data': response.json() if response.headers.get('content-type') == 'application/json' else response.text,
            'success': response.status_code >= 200 and response.status_code < 300
        }
        
        return result
    
    except requests.exceptions.RequestException as e:
        # Erro na requisição
        raise Exception(f"Erro ao enviar requisição: {str(e)}") 