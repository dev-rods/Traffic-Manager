import json
import boto3
import os
import logging
from datetime import datetime
from src.utils.auth import ClientAuth
from src.utils.openai_utils import call_openai_api, format_prompt, calculate_cost, get_prompt_from_table
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))


def handler(event, context):
    """
    Handler para executar um prompt específico com parâmetros
    
    Body esperado:
    {
        "promptId": "campaign-optimization-v1",
        "parameters": {
            "campaignId": "123456",
            "metrics": {...},
            "campaignStructure": {...}
        },
        "traceId": "optional-trace-id" (opcional)
    }
    """
    try:
        logger.info(f"Requisição recebida para executar prompt: {json.dumps(event)}")
        
        if "body" not in event or not event["body"]:
            return response(400, {"message": "Corpo da requisição vazio ou inválido"})
        
        body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]
        
        api_key = get_api_key(event, body)
        if not api_key:
            logger.warning("API key não fornecida na requisição")
            return response(401, {"message": "API key não fornecida"})
        
        client_auth = ClientAuth()
        valid_api_key = client_auth.validate_api_key(api_key)
        if not valid_api_key:
            logger.warning(f"API key inválida: {api_key}")
            return response(401, {"message": "Cliente não autorizado"})
        
        if 'promptId' not in body:
            return response(400, {"message": "promptId é obrigatório"})
        
        if 'parameters' not in body:
            return response(400, {"message": "parameters é obrigatório"})
        
        prompt_id = body['promptId']
        parameters = body['parameters']
        trace_id = body.get('traceId', f"prompt-{prompt_id}-{datetime.utcnow().timestamp()}")
        
        try:
            prompt_item = get_prompt_from_table(prompt_id)
            if not prompt_item:
                return response(404, {"message": f"Prompt '{prompt_id}' não encontrado"})
            
            if not prompt_item.get('isActive', True):
                return response(400, {"message": f"Prompt '{prompt_id}' está inativo"})
            
        except Exception as e:
            logger.error(f"Erro ao buscar prompt: {str(e)}")
            return response(500, {"message": "Erro ao buscar prompt", "error": str(e)})
        
        try:
            formatted_prompt = format_prompt(prompt_item['prompt'], parameters, strict=True)
        except KeyError as e:
            return response(400, {"message": f"Parâmetro obrigatório não fornecido: {str(e)}"})
        
        
        model = prompt_item.get('model', os.environ.get('OPENAI_MODEL', 'gpt-4.1'))
        system_message = prompt_item.get('systemMessage', 'Você é um especialista em marketing digital e otimização de campanhas do Google Ads. Sua tarefa é analisar dados e fornecer recomendações para melhorar o desempenho das campanhas.')
        
        temperature_value = prompt_item.get('temperature', Decimal('0.7'))
        max_tokens_value = prompt_item.get('maxTokens', Decimal('1500'))
        
        temperature = float(temperature_value) if isinstance(temperature_value, Decimal) else temperature_value
        max_tokens = int(max_tokens_value) if isinstance(max_tokens_value, Decimal) else max_tokens_value
        
        stage = 'OPENAI_CALL'
        timestamp = datetime.utcnow().isoformat()
        
        try:
            openai_response = call_openai_api(
                prompt=formatted_prompt,
                system_message=system_message,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
            
            if 'choices' not in openai_response or not openai_response['choices']:
                raise Exception("Resposta inválida da OpenAI")
            
            assistant_response = openai_response['choices'][0]['message']['content']
            
            execution_record = {
                'traceId': trace_id,
                'stageTm': f"{stage}#{timestamp}",
                'stage': stage,
                'status': 'COMPLETED',
                'timestamp': timestamp,
                'costUSD': calculate_cost(openai_response, default_model=model),
                'payload': json.dumps({
                    'promptId': prompt_id,
                    'context': {
                        'promptId': prompt_id,
                        'parameters': parameters
                    },
                    'prompt': formatted_prompt,
                    'response': assistant_response,
                    'model': openai_response.get('model', model),
                    'tokens': {
                        'prompt': openai_response.get('usage', {}).get('prompt_tokens', 0),
                        'completion': openai_response.get('usage', {}).get('completion_tokens', 0),
                        'total': openai_response.get('usage', {}).get('total_tokens', 0)
                    }
                })
            }
            
            execution_history_table.put_item(Item=execution_record)
            
            logger.info(f"[traceId: {trace_id}] Prompt '{prompt_id}' executado com sucesso")
            
            return response(200, {
                'traceId': trace_id,
                'timestamp': timestamp,
                'promptId': prompt_id,
                'openAIResponse': assistant_response,
                'model': model,
                'tokens': {
                    'prompt': openai_response.get('usage', {}).get('prompt_tokens', 0),
                    'completion': openai_response.get('usage', {}).get('completion_tokens', 0),
                    'total': openai_response.get('usage', {}).get('total_tokens', 0)
                },
                'costUSD': calculate_cost(openai_response, default_model=model)
            })
            
        except Exception as e:
            error_msg = str(e)
            logger.error(f"[traceId: {trace_id}] Erro ao chamar OpenAI: {error_msg}")
            
            try:
                error_record = {
                    'traceId': trace_id,
                    'stageTm': f"{stage}#{timestamp}",
                    'stage': stage,
                    'status': 'ERROR',
                    'timestamp': timestamp,
                    'errorMsg': error_msg,
                    'payload': json.dumps({
                        'promptId': prompt_id,
                        'parameters': parameters,
                        'error': error_msg
                    })
                }
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
            
            return response(500, {"message": "Erro ao chamar a OpenAI", "error": error_msg})
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro no processamento da execução de prompt: {error_msg}")
        return response(500, {"message": "Erro interno no servidor", "error": error_msg})




def get_api_key(event, body):
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
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Credentials': True
        },
        'body': json.dumps(body) if isinstance(body, dict) else json.dumps({"message": body})
    }

