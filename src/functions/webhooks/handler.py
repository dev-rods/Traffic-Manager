import json
import boto3
import os
import uuid
from datetime import datetime
from src.utils.auth import ClientAuth


step_functions = boto3.client('stepfunctions')
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

def handler(event, context):
    try:
        print(f"Requisição recebida de webhook: {json.dumps(event)}")
        if "body" not in event or not event["body"]:
            return response(400, "Corpo da requisição vazio ou inválido")        
        body = json.loads(event["body"]) if isinstance(event["body"], str) else event["body"]        
        api_key = get_api_key(event, body)
        if not api_key:
            print("API key não fornecida na requisição")
            return response(401, "API key não fornecida")
        
        client_auth = ClientAuth()
        client = client_auth.validate_api_key(api_key)

        if not client:
            print(f"Cliente não encontrado para API key: {api_key}")
            return response(401, "Cliente não autorizado")
        
        if not client.get('active', False):
            print(f"Cliente inativo tentando acessar: {client['clientId']}")
            return response(403, "Cliente inativo")
        
        print(f"Cliente autenticado: {client['clientId']} ({client['name']})")
        
        print(f"Dados do body recebidos: {json.dumps(body)}")
        
        form_data = parse_form_data(body)
        if not form_data:
            print("Falha ao processar dados do formulário")
            return response(400, "Dados do formulário inválidos ou incompletos")
        
        # Log dos dados processados
        print(f"Dados do formulário processados com sucesso: {json.dumps(form_data)}")
        
        trace_id = str(uuid.uuid4())
        payload = {
            'traceId': trace_id,
            'storeId': client['clientId'],
            'storeName': client['name'],
            'formData': form_data,
            'timestamp': datetime.utcnow().isoformat()
        }
        record_execution_start(trace_id, client['clientId'], payload)

        region = os.environ.get('AWS_REGION', context.invoked_function_arn.split(':')[3])
        account_id = os.environ.get('ACCOUNT_ID', context.invoked_function_arn.split(':')[4])
        
        state_machine_name = os.environ.get('BASE_STATE_MACHINE_NAME') + "CampaignOptimization"
        state_machine_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{state_machine_name}"
        
        print(f"Iniciando Step Function: {state_machine_arn}")
        
        response_sf = step_functions.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"{client['clientId']}-{trace_id}",
            input=json.dumps(payload)
        )
        
        print(f"Step Function iniciada: {response_sf['executionArn']}")
        
        return response(200, {
            "message": "Processamento iniciado com sucesso",
            "traceId": trace_id,
            "executionArn": response_sf['executionArn']
        })
    
    except Exception as e:
        error_msg = str(e)
        print(f"Erro no processamento do webhook: {error_msg}")
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
    try:
        if 'formData' in body and body['formData']:
            form_data = body['formData']
        else:
            form_data = body
        if not form_data:
            return None
        processed_data = {
            'campaign_type': 'FIRST_RUN',
            'timestamp': form_data.get('Carimbo de data/hora', ''),
            'objectives': form_data.get('Selecione seu objetivo (Com o Google)', ''),
            'budget': form_data.get('Quanto estaria disposto (a) a investir mensalmentel?', ''),
            'industry': form_data.get('Qual é o seu produto ou serviço?', ''),
            'target_audience': form_data.get('Onde encontramos seu público? (Próximo ao seu local? Em sua cidade? Em seu Estado? Em todo o país? Em sua microregião?)', ''),
            'business_name': form_data.get('Qual é o seu produto ou serviço?', ''),
            'competitive_advantage': form_data.get('Qual é o maior diferencial competitivo do seu produto/serviço? (Ex: preço, tecnologia, atendimento, localização, experiência, etc.)  ', ''),
            'customer_benefit': form_data.get('O que o seu cliente ganha ao escolher você e não o concorrente? (Ex: menor preço, atendimento mais humano, melhores resultados, etc.)', ''),
            'customer_desires': form_data.get('Quais são os desejos das pessoas que se conectam com seu produto/serviço?  ', ''),
            'customer_pains': form_data.get('Quais são as dores ou frustrações que ela quer resolver com o seu produto?  ', ''),
            'cost_per_result': form_data.get('Quanto você espera pagar por resultado?', ''),
            'average_ticket': form_data.get('Qual é o seu Ticket Médio? (Divida seu faturamento em um período (dia ou semana) e divida pela quantidade de clientes nesse período. Vai ajudar a limitarmos os gastos por cliente.)', ''),
            'brand_perception': form_data.get('Como você quer ser percebido(a)? (Ex: Premium, acessível, inovador, confiável, rápido…)  ', ''),
            'customer_behavior': form_data.get('Seu cliente procura por você ou precisa ser convencido? ', ''),
            'company_name': form_data.get('Qual é o nome da sua empresa? (Se for autônomo, digite seu nome. Exemplos: Dra. Maria, Personal Rodrigo.)', ''),
            'business_niche': form_data.get('Qual é o nicho do seu negócio? (Exemplos: Odontologia, Estética, Advocacia.)', ''),
        }
        return processed_data
    except Exception as e:
        print(f"Erro ao processar dados do formulário: {str(e)}")
        return None

def record_execution_start(trace_id, client_id, payload):
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
        print(f"[traceId: {trace_id}] Registro criado na tabela ExecutionHistory")
    except Exception as e:
        print(f"Erro ao registrar início da execução: {str(e)}")

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