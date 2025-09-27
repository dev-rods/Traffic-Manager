import json
import boto3
import os
import logging
from datetime import datetime, timedelta
from src.services.google_ads_mcc_service import GoogleAdsMCCService

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Clientes AWS
dynamodb = boto3.resource('dynamodb')
step_functions = boto3.client('stepfunctions')
clients_table = dynamodb.Table(os.environ.get('CLIENTS_TABLE'))
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

def handler(event, context):
    """
    Função para verificar status MCC de clientes pendentes
    e iniciar Step Function quando aprovado
    
    Esta função pode ser acionada por:
    - EventBridge/CloudWatch Events (agendamento)
    - API Gateway (verificação manual)
    - Outras funções Lambda
    """
    try:
        logger.info(f"Verificando status MCC: {json.dumps(event)}")
        
        # Se recebeu clientId específico, verificar apenas esse
        if 'clientId' in event:
            client_id = event['clientId']
            return check_single_client_mcc_status(client_id)
        
        # Caso contrário, verificar todos os clientes com status PENDING
        return check_all_pending_mcc_clients()
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao verificar status MCC: {error_message}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Erro ao verificar status MCC',
                'error': error_message
            })
        }

def check_single_client_mcc_status(client_id):
    """Verifica status MCC de um cliente específico"""
    try:
        # Buscar dados do cliente
        response = clients_table.get_item(Key={'clientId': client_id})
        
        if 'Item' not in response:
            return {
                'statusCode': 404,
                'body': json.dumps({
                    'message': f'Cliente {client_id} não encontrado'
                })
            }
        
        client_data = response['Item']
        mcc_status = client_data.get('mccStatus', 'NOT_LINKED')
        google_ads_customer_id = client_data.get('googleAdsCustomerId')
        
        if not google_ads_customer_id:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'message': f'Cliente {client_id} não possui Google Ads Customer ID'
                })
            }
        
        if mcc_status != 'PENDING':
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Cliente {client_id} não está com status PENDING',
                    'currentStatus': mcc_status
                })
            }
        
        # Verificar status no Google Ads
        result = check_and_update_mcc_status(client_id, client_data, google_ads_customer_id)
        
        return {
            'statusCode': 200,
            'body': json.dumps(result)
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao verificar cliente {client_id}: {error_message}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': f'Erro ao verificar cliente {client_id}',
                'error': error_message
            })
        }

def check_all_pending_mcc_clients():
    """Verifica status MCC de todos os clientes com status PENDING"""
    try:
        # Buscar todos os clientes com status PENDING
        response = clients_table.scan(
            FilterExpression='mccStatus = :status',
            ExpressionAttributeValues={':status': 'PENDING'}
        )
        
        clients = response.get('Items', [])
        results = []
        
        logger.info(f"Encontrados {len(clients)} clientes com status MCC PENDING")
        
        for client in clients:
            client_id = client['clientId']
            google_ads_customer_id = client.get('googleAdsCustomerId')
            
            if not google_ads_customer_id:
                logger.warning(f"Cliente {client_id} não possui Google Ads Customer ID")
                continue
            
            try:
                result = check_and_update_mcc_status(client_id, client, google_ads_customer_id)
                results.append({
                    'clientId': client_id,
                    'result': result
                })
            except Exception as e:
                logger.error(f"Erro ao verificar cliente {client_id}: {str(e)}")
                results.append({
                    'clientId': client_id,
                    'error': str(e)
                })
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': f'Verificação concluída para {len(clients)} clientes',
                'results': results
            })
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao verificar clientes PENDING: {error_message}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Erro ao verificar clientes PENDING',
                'error': error_message
            })
        }

def check_and_update_mcc_status(client_id, client_data, google_ads_customer_id):
    """Verifica status MCC no Google Ads e atualiza no DynamoDB"""
    try:
        mcc_service = GoogleAdsMCCService()
        status_result = mcc_service.get_link_status(google_ads_customer_id)
        
        if not status_result.get('found'):
            logger.info(f"Cliente {client_id}: Link MCC não encontrado")
            return {
                'status': 'NOT_FOUND',
                'message': 'Link MCC não encontrado'
            }
        
        current_status = status_result.get('status')
        logger.info(f"Cliente {client_id}: Status MCC atual = {current_status}")
        
        # Atualizar status no DynamoDB
        clients_table.update_item(
            Key={'clientId': client_id},
            UpdateExpression="SET mccStatus = :status, mccLastCheckedAt = :timestamp",
            ExpressionAttributeValues={
                ':status': current_status,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        
        # Se foi aprovado, iniciar Step Function
        if current_status == 'APPROVED':
            logger.info(f"Cliente {client_id}: MCC aprovado! Iniciando Step Function...")
            return start_campaign_optimization_for_client(client_id, client_data)
        elif current_status == 'REJECTED':
            logger.warning(f"Cliente {client_id}: MCC rejeitado pelo cliente")
            return {
                'status': 'REJECTED',
                'message': 'Cliente rejeitou o convite MCC'
            }
        else:
            logger.info(f"Cliente {client_id}: Ainda aguardando confirmação (status: {current_status})")
            return {
                'status': current_status,
                'message': f'Aguardando confirmação do cliente (status: {current_status})'
            }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao verificar status MCC para {client_id}: {error_message}")
        
        # Atualizar com erro
        clients_table.update_item(
            Key={'clientId': client_id},
            UpdateExpression="SET mccStatus = :status, mccError = :error, mccLastCheckedAt = :timestamp",
            ExpressionAttributeValues={
                ':status': 'ERROR',
                ':error': error_message,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        
        return {
            'status': 'ERROR',
            'message': f'Erro ao verificar status: {error_message}'
        }

def start_campaign_optimization_for_client(client_id, client_data):
    """Inicia Step Function de otimização para o cliente"""
    try:
        # Buscar dados do formulário do cliente
        form_data = client_data.get('formData', {})
        
        # Preparar payload
        trace_id = f"mcc-approved-{client_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        payload = {
            'traceId': trace_id,
            'storeId': client_id,
            'storeName': client_data.get('name', ''),
            'formData': form_data,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'mcc_approval'
        }
        
        # Registrar início da execução
        execution_history_table.put_item(Item={
            'traceId': trace_id,
            'stageTm': 'mcc_approval_triggered',
            'status': 'RECEIVED',
            'timestamp': datetime.utcnow().isoformat(),
            'clientId': client_id,
            'payload': json.dumps(payload)
        })
        
        # Iniciar Step Function
        region = os.environ.get('AWS_REGION')
        account_id = os.environ.get('ACCOUNT_ID')
        state_machine_name = os.environ.get('BASE_STATE_MACHINE_NAME') + "CampaignOptimization"
        state_machine_arn = f"arn:aws:states:{region}:{account_id}:stateMachine:{state_machine_name}"
        
        response_sf = step_functions.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"{client_id}-{trace_id}",
            input=json.dumps(payload)
        )
        
        logger.info(f"Step Function iniciada para cliente {client_id}: {response_sf['executionArn']}")
        
        return {
            'status': 'APPROVED',
            'message': 'MCC aprovado e Step Function iniciada',
            'traceId': trace_id,
            'executionArn': response_sf['executionArn']
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao iniciar Step Function para {client_id}: {error_message}")
        
        return {
            'status': 'ERROR',
            'message': f'Erro ao iniciar Step Function: {error_message}'
        }
