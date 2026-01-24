import json
import boto3
from boto3.dynamodb.conditions import Attr
import os
import logging
from src.utils.auth import ClientAuth
from src.utils.openai_utils import get_prompt_from_table

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
prompts_table = dynamodb.Table(os.environ.get('PROMPTS_TABLE'))


def handler(event, context):
    """
    Handler para recuperar prompts via API
    
    Endpoints:
    - GET /prompts - Lista todos os prompts (opcional: ?isActive=true/false)
    - GET /prompts/{promptId} - Busca um prompt específico
    """
    try:
        logger.info(f"Requisição recebida para recuperar prompts: {json.dumps(event)}")
        
        api_key = get_api_key(event)
        if not api_key:
            logger.warning("API key não fornecida na requisição")
            return response(401, {"message": "API key não fornecida"})
        
        client_auth = ClientAuth()
        valid_api_key = client_auth.validate_api_key(api_key)
        if not valid_api_key:
            logger.warning(f"API key inválida: {api_key}")
            return response(401, {"message": "Cliente não autorizado"})
        
        prompt_id = extract_path_param(event, 'promptId')
        
        if prompt_id:
            return get_single_prompt(prompt_id)
        else:
            is_active_filter = extract_query_param(event, 'isActive')
            return list_prompts(is_active_filter)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro no processamento da recuperação de prompts: {error_msg}")
        return response(500, {"message": "Erro interno no servidor", "error": error_msg})


def get_single_prompt(prompt_id):
    """
    Busca um prompt específico por ID
    """
    try:
        prompt_item = get_prompt_from_table(prompt_id)
        
        if not prompt_item:
            return response(404, {"message": f"Prompt '{prompt_id}' não encontrado"})
        
        # Remover campos internos se necessário e formatar resposta
        # Converter Decimal de volta para float/int para JSON serialization
        temperature = prompt_item.get('temperature')
        max_tokens = prompt_item.get('maxTokens')
        
        response_data = {
            "promptId": prompt_item.get('promptId'),
            "prompt": prompt_item.get('prompt'),
            "description": prompt_item.get('description', ''),
            "parameters": prompt_item.get('parameters', []),
            "systemMessage": prompt_item.get('systemMessage'),
            "model": prompt_item.get('model'),
            "temperature": float(temperature) if temperature is not None else None,
            "maxTokens": int(max_tokens) if max_tokens is not None else None,
            "isActive": prompt_item.get('isActive', True),
            "createdAt": prompt_item.get('createdAt'),
            "updatedAt": prompt_item.get('updatedAt')
        }
        
        return response(200, response_data)
        
    except Exception as e:
        logger.error(f"Erro ao buscar prompt '{prompt_id}': {str(e)}")
        return response(500, {"message": "Erro ao buscar prompt", "error": str(e)})


def list_prompts(is_active_filter=None):
    """
    Lista todos os prompts, opcionalmente filtrados por isActive
    """
    try:
        # Scan na tabela (para tabelas pequenas/médias é aceitável)
        # Para produção com muitos prompts, considerar paginação
        scan_kwargs = {}
        
        # Filtrar por isActive se fornecido
        if is_active_filter is not None:
            # Garantir que is_active_filter seja uma string antes de chamar .lower()
            is_active_str = str(is_active_filter).lower() if is_active_filter else ''
            is_active = is_active_str == 'true'
            scan_kwargs['FilterExpression'] = Attr('isActive').eq(is_active)
        
        response = prompts_table.scan(**scan_kwargs)
        items = response.get('Items', [])
        
        # Formatar resposta
        # Converter Decimal de volta para float/int para JSON serialization
        prompts = []
        for item in items:
            temperature = item.get('temperature')
            max_tokens = item.get('maxTokens')
            
            prompts.append({
                "promptId": item.get('promptId'),
                "description": item.get('description', ''),
                "parameters": item.get('parameters', []),
                "model": item.get('model'),
                "temperature": float(temperature) if temperature is not None else None,
                "maxTokens": int(max_tokens) if max_tokens is not None else None,
                "isActive": item.get('isActive', True),
                "createdAt": item.get('createdAt'),
                "updatedAt": item.get('updatedAt')
            })
        
        # Ordenar por updatedAt (mais recentes primeiro)
        prompts.sort(key=lambda x: x.get('updatedAt', ''), reverse=True)
        
        return response(200, {
            "prompts": prompts,
            "count": len(prompts)
        })
        
    except Exception as e:
        logger.error(f"Erro ao listar prompts: {str(e)}")
        return response(500, {"message": "Erro ao listar prompts", "error": str(e)})


def extract_path_param(event, param_name):
    """
    Extrai parâmetro do path do evento
    Exemplo: /prompts/{promptId} -> extrai promptId
    """
    if 'pathParameters' in event and event['pathParameters']:
        return event['pathParameters'].get(param_name)
    return None


def extract_query_param(event, param_name):
    """
    Extrai parâmetro da query string
    Exemplo: ?isActive=true -> retorna 'true'
    """
    if 'queryStringParameters' in event and event['queryStringParameters']:
        return event['queryStringParameters'].get(param_name)
    return None


def get_api_key(event):
    """
    Extrai a API key da requisição
    Verifica headers (Authorization Bearer ou x-api-key) e query parameters
    """
    if "headers" in event and event["headers"]:
        headers = event["headers"]
        if "Authorization" in headers:
            auth_header = headers["Authorization"]
            if auth_header.startswith("Bearer "):
                return auth_header[7:]
        if "x-api-key" in headers:
            return headers["x-api-key"]
    
    if "queryStringParameters" in event and event["queryStringParameters"]:
        query_params = event["queryStringParameters"]
        if "apiKey" in query_params:
            return query_params["apiKey"]
    
    return None


def response(status_code, body):
    """
    Cria resposta HTTP padronizada
    """
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True
        },
        'body': json.dumps(body) if isinstance(body, dict) else json.dumps({"message": body})
    }

