import json
import os
import logging
import requests
import time
import re
import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1')
OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'

# Inicializar tabela de prompts se necessário
dynamodb = None
prompts_table = None


def get_prompts_table():
    """
    Lazy initialization da tabela de prompts
    """
    global dynamodb, prompts_table
    if prompts_table is None:
        dynamodb = boto3.resource('dynamodb')
        prompts_table = dynamodb.Table(os.environ.get('PROMPTS_TABLE'))
    return prompts_table


def call_openai_api(prompt, system_message=None, model=None, temperature=0.7, max_tokens=1500):
    """
    Chama a API da OpenAI com retry logic
    
    Args:
        prompt: O prompt do usuário
        system_message: Mensagem do sistema (opcional, usa padrão se não fornecido)
        model: Modelo a ser usado (opcional, usa OPENAI_MODEL se não fornecido)
        temperature: Temperatura para a chamada (padrão: 0.7)
        max_tokens: Máximo de tokens (padrão: 1500)
    
    Returns:
        dict: Resposta da API da OpenAI
    """
    if system_message is None:
        system_message = 'Você é um especialista em marketing digital e otimização de campanhas do Google Ads. Sua tarefa é analisar dados e fornecer recomendações para melhorar o desempenho das campanhas.'
    
    if model is None:
        model = OPENAI_MODEL
    
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': system_message
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': temperature,
        'max_tokens': max_tokens
    }
    
    retry_count = 0
    max_retries = 3
    
    while retry_count < max_retries:
        response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 429 or response.status_code >= 500:
            retry_count += 1
            wait_time = 2 ** retry_count  # Exponential backoff
            logger.warning(f"Erro na API da OpenAI (status {response.status_code}). Tentando novamente em {wait_time}s...")
            time.sleep(wait_time)
        else:
            response.raise_for_status()
    
    raise Exception(f"Falha ao chamar a API da OpenAI após {max_retries} tentativas. Último status: {response.status_code}")


def format_prompt(prompt_template, parameters, strict=True):
    """
    Substitui placeholders no template do prompt pelos valores dos parâmetros
    Suporta placeholders no formato {paramName}
    
    Args:
        prompt_template: Template do prompt com placeholders
        parameters: Dicionário com os valores dos parâmetros
        strict: Se True, lança exceção se houver placeholders não substituídos (padrão: True)
    
    Returns:
        str: Prompt formatado
    
    Raises:
        KeyError: Se strict=True e houver placeholders não substituídos
    """
    formatted = prompt_template
    
    # Substituir parâmetros simples
    for key, value in parameters.items():
        if isinstance(value, (dict, list)):
            # Para objetos e listas, converter para JSON
            formatted = formatted.replace(f"{{{key}}}", json.dumps(value, indent=2, ensure_ascii=False))
        else:
            formatted = formatted.replace(f"{{{key}}}", str(value))
    
    # Verificar se ainda há placeholders não substituídos
    remaining_placeholders = re.findall(r'\{([^}]+)\}', formatted)
    if remaining_placeholders:
        if strict:
            raise KeyError(f"Placeholders não substituídos: {', '.join(remaining_placeholders)}")
        else:
            logger.warning(f"Placeholders não substituídos: {', '.join(remaining_placeholders)}")
    
    return formatted


def calculate_cost(openai_response, default_model=None):
    """
    Calcula o custo da chamada à OpenAI baseado no modelo e tokens usados
    
    Args:
        openai_response: Resposta da API da OpenAI
        default_model: Modelo padrão caso não esteja na resposta (opcional)
    
    Returns:
        float: Custo em USD
    """
    model = openai_response.get('model', default_model or OPENAI_MODEL)
    usage = openai_response.get('usage', {})
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)
    
    prices = {
        'gpt-4': {'prompt': 0.03, 'completion': 0.06},
        'gpt-4-32k': {'prompt': 0.06, 'completion': 0.12},
        'gpt-3.5-turbo': {'prompt': 0.0015, 'completion': 0.002},
        'gpt-4.1': {'prompt': 0.03, 'completion': 0.06}  # Assumindo mesmo preço do gpt-4
    }
    
    model_prices = prices.get(model, prices['gpt-3.5-turbo'])
    prompt_cost = (prompt_tokens / 1000) * model_prices['prompt']
    completion_cost = (completion_tokens / 1000) * model_prices['completion']
    
    return round(prompt_cost + completion_cost, 6)


def get_prompt_from_table(prompt_id):
    """
    Busca um prompt da tabela DynamoDB
    
    Args:
        prompt_id: ID do prompt a ser buscado
    
    Returns:
        dict: Item do prompt ou None se não encontrado
    """
    try:
        table = get_prompts_table()
        response = table.get_item(Key={'promptId': prompt_id})
        if 'Item' in response:
            return response['Item']
        return None
    except Exception as e:
        logger.error(f"Erro ao buscar prompt '{prompt_id}' da tabela: {str(e)}")
        return None

