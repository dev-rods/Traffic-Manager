import json
import boto3
import os
import logging
from datetime import datetime
from decimal import Decimal
from src.utils.auth import ClientAuth

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
prompts_table = dynamodb.Table(os.environ.get('PROMPTS_TABLE'))


def handler(event, context):
    """
    Handler para criar ou atualizar prompts via API
    
    Body esperado:
    {
        "promptId": "campaign-optimization-v1",
        "prompt": "Você é um especialista... {campaignId} ... {metrics}",
        "description": "Prompt para otimização de campanhas",
        "parameters": ["campaignId", "metrics", "campaignStructure"],
        "systemMessage": "Você é um especialista em Google Ads" (opcional),
        "model": "gpt-4" (opcional),
        "temperature": 0.7 (opcional),
        "maxTokens": 1500 (opcional)
    }
    """
    try:
        logger.info(f"Requisição recebida para criar/atualizar prompt: {json.dumps(event)}")
        
        if "body" not in event or not event["body"]:
            return response(400, {"message": "Corpo da requisição vazio ou inválido"})
        
        body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        
        # Validar API key
        api_key = get_api_key(event, body)
        if not api_key:
            logger.warning("API key não fornecida na requisição")
            return response(401, {"message": "API key não fornecida"})
        
        client_auth = ClientAuth()
        valid_api_key = client_auth.validate_api_key(api_key)
        if not valid_api_key:
            logger.warning(f"API key inválida: {api_key}")
            return response(401, {"message": "Cliente não autorizado"})
        
        # Validar campos obrigatórios
        if 'promptId' not in body:
            return response(400, {"message": "promptId é obrigatório"})
        
        if 'prompt' not in body:
            return response(400, {"message": "prompt é obrigatório"})
        
        prompt_id = body['promptId']
        timestamp = datetime.utcnow().isoformat()
        
        # Verificar se o prompt já existe
        existing_prompt = None
        try:
            existing_response = prompts_table.get_item(Key={'promptId': prompt_id})
            if 'Item' in existing_response:
                existing_prompt = existing_response['Item']
        except Exception as e:
            logger.warning(f"Erro ao verificar prompt existente: {str(e)}")
        
        # Preparar item para DynamoDB
        # Converter valores numéricos para Decimal (requisito do DynamoDB)
        temperature = body.get('temperature', 0.7)
        max_tokens = body.get('maxTokens', 1500)
        
        prompt_item = {
            'promptId': prompt_id,
            'prompt': body['prompt'],
            'description': body.get('description', ''),
            'parameters': body.get('parameters', []),
            'systemMessage': body.get('systemMessage', 'Você é um especialista em marketing digital e otimização de campanhas do Google Ads. Sua tarefa é analisar dados e fornecer recomendações para melhorar o desempenho das campanhas.'),
            'model': body.get('model', os.environ.get('OPENAI_MODEL', 'gpt-4.1')),
            'temperature': Decimal(str(temperature)),
            'maxTokens': Decimal(str(max_tokens)),
            'isActive': body.get('isActive', True),
            'updatedAt': timestamp
        }
        
        if not existing_prompt:
            prompt_item['createdAt'] = timestamp
        
        # Salvar no DynamoDB
        prompts_table.put_item(Item=prompt_item)
        
        logger.info(f"Prompt {prompt_id} {'criado' if not existing_prompt else 'atualizado'} com sucesso")
        
        response_data = {
            "message": f"Prompt {'criado' if not existing_prompt else 'atualizado'} com sucesso",
            "promptId": prompt_id,
            "description": prompt_item['description'],
            "parameters": prompt_item['parameters'],
            "isActive": prompt_item['isActive'],
            "updatedAt": timestamp
        }
        
        if not existing_prompt:
            response_data["createdAt"] = timestamp
        
        return response(200, response_data)
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro no processamento da criação/atualização de prompt: {error_msg}")
        return response(500, {"message": "Erro interno no servidor", "error": error_msg})


def get_api_key(event, body):
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
    
    if body and isinstance(body, dict):
        if "apiKey" in body:
            return body["apiKey"]
    
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

