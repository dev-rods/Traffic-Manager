import json
import boto3
import os
import uuid
import logging
from datetime import datetime
from src.utils.auth import ClientAuth

logger = logging.getLogger()
logger.setLevel(logging.INFO)

step_functions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

def handler(event, context):
    """
    Função para receber webhooks do Google Sheets e iniciar o fluxo de otimização de campanha
    
    Esta função:
    1. Valida a API key do cliente
    2. Processa os dados do formulário do Google Sheets
    3. Inicia a Step Function de otimização da campanha
    """
    try:
        logger.info(f"Requisição recebida de webhook: {json.dumps(event)}")
        if "body" not in event or not event["body"]:
            return response(400, "Corpo da requisição vazio ou inválido")        
        body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]        
        api_key = get_api_key(event, body)
        if not api_key:
            logger.warning("API key não fornecida na requisição")
            return response(401, "API key não fornecida")
        
        # Validar a API key e obter os dados do cliente
        client_auth = ClientAuth()
        client = client_auth.validate_api_key(api_key)
        
        if not client:
            logger.warning(f"Cliente não encontrado para API key: {api_key}")
            return response(401, "Cliente não autorizado")
        
        if not client.get('active', False):
            logger.warning(f"Cliente inativo tentando acessar: {client['clientId']}")
            return response(403, "Cliente inativo")
        
        # Log de cliente autenticado
        logger.info(f"Cliente autenticado: {client['clientId']} ({client['name']})")
        
        # Processar dados do formulário
        form_data = parse_form_data(body)
        if not form_data:
            return response(400, "Dados do formulário inválidos ou incompletos")
        
        # Gerar trace ID para rastreamento
        trace_id = str(uuid.uuid4())
        
        # Preparar payload para a Step Function
        payload = {
            'traceId': trace_id,
            'storeId': client['clientId'],
            'storeName': client['name'],
            'formData': form_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Registrar início do processamento no histórico
        record_execution_start(trace_id, client['clientId'], payload)
        
        # Obter a região atual da função Lambda
        region = os.environ.get('AWS_REGION', context.invoked_function_arn.split(':')[3])
        account_id = os.environ.get('ACCOUNT_ID', context.invoked_function_arn.split(':')[4])
        
        # Iniciar Step Function
        state_machine_name = os.environ.get('BASE_STATE_MACHINE_NAME') + "CampaignOptimization"
        state_machine_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{state_machine_name}"
        
        logger.info(f"Iniciando Step Function: {state_machine_arn}")
        
        response_sf = step_functions.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"{client['clientId']}-{trace_id}",
            input=json.dumps(payload)
        )
        
        logger.info(f"Step Function iniciada: {response_sf['executionArn']}")
        
        # Retornar sucesso
        return response(200, {
            "message": "Processamento iniciado com sucesso",
            "traceId": trace_id,
            "executionArn": response_sf['executionArn']
        })
    
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro no processamento do webhook: {error_msg}")
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

def parse_form_data(body):
    """
    Processa os dados do formulário do Google Sheets
    
    Args:
        body (dict): Os dados recebidos do webhook
        
    Returns:
        dict: Dados formatados do formulário ou None se inválidos
    """
    try:
        # Verificar se os dados do formulário existem
        if 'formData' not in body or not body['formData']:
            return None
        
        form_data = body['formData']
        
        # Exemplo de processamento - adaptar conforme a estrutura real do seu formulário
        processed_data = {
            'businessName': form_data.get('businessName', ''),
            'industry': form_data.get('industry', ''),
            'budget': form_data.get('budget', ''),
            'objectives': form_data.get('objectives', ''),
            'targetAudience': form_data.get('targetAudience', ''),
            'campaign_type': form_data.get('campaignType', 'FIRST_RUN')
        }
        
        return processed_data
    
    except Exception as e:
        logger.error(f"Erro ao processar dados do formulário: {str(e)}")
        return None

def record_execution_start(trace_id, client_id, payload):
    """
    Registra o início da execução na tabela de histórico
    """
    try:
        timestamp = datetime.utcnow().isoformat()
        
        execution_record = {
            'traceId': trace_id,
            'stageTm': 'webhook',
            'status': 'RECEIVED',
            'timestamp': timestamp,
            'clientId': client_id,
            'payload': json.dumps(payload)
        }
        
        execution_history_table.put_item(Item=execution_record)
        logger.info(f"[traceId: {trace_id}] Registro criado na tabela ExecutionHistory")
    
    except Exception as e:
        logger.error(f"Erro ao registrar início da execução: {str(e)}")

def response(status_code, body):
    """
    Formata a resposta HTTP
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