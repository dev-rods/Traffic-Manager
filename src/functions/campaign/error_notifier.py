import json
import boto3
import os
import logging
from datetime import datetime

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do DynamoDB
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

# Cliente do SNS para notificações (opcional)
sns_client = boto3.client('sns')
ERROR_TOPIC_ARN = os.environ.get('ERROR_NOTIFICATION_TOPIC_ARN')

def handler(event, context):
    """
    Função para notificar erros no processo de otimização
    
    Esta função é chamada quando ocorre um erro em alguma etapa do processo
    e registra o erro de forma consolidada.
    """
    try:
        trace_id = event.get('traceId')
        stage = 'ERROR_NOTIFICATION'
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get('runType', 'UNKNOWN')
        
        # Verificar se há informações de erro no evento
        error_info = event.get('error', {})
        error_message = error_info.get('Cause', 'Erro desconhecido')
        
        if isinstance(error_message, str) and error_message.startswith('{'):
            try:
                error_json = json.loads(error_message)
                if 'errorMessage' in error_json:
                    error_message = error_json['errorMessage']
            except json.JSONDecodeError:
                pass
                
        # Identificar a etapa que falhou
        failed_stage = 'UNKNOWN'
        for stage_name in ['ORCHESTRATOR', 'FETCH_TEMPLATE', 'FETCH_METRICS', 'OPENAI_CALL', 'PARSER', 'GOOGLE_ADS_ACTION']:
            if stage_name.lower() in error_message.lower():
                failed_stage = stage_name
                break
        
        logger.error(f"[traceId: {trace_id}] Erro no processo de otimização: {error_message}")
        
        # Registrar o erro na tabela ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'ERROR',
            'timestamp': timestamp,
            'errorMsg': error_message[:1000] if error_message else 'Erro desconhecido',  # Limitar tamanho
            'payload': json.dumps({
                'failed_stage': failed_stage,
                'error_details': str(error_info)[:2000] if error_info else None,  # Limitar tamanho
                'process_info': {
                    'runType': run_type,
                    'duration': calculate_duration(trace_id)
                }
            })
        }
        
        # Adicionar campos adicionais, se existirem no evento original
        if 'runType' in event:
            execution_record['runType'] = event['runType']
        
        if 'storeId' in event:
            execution_record['storeId'] = event['storeId']
            
        if 'campaignId' in event:
            execution_record['campaignId'] = event['campaignId']
            
        # Salvar no DynamoDB
        execution_history_table.put_item(Item=execution_record)
        
        # Enviar notificação via SNS, se configurado
        if ERROR_TOPIC_ARN:
            send_error_notification(trace_id, failed_stage, error_message, run_type, event)
        
        # Preparar resposta
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'status': 'ERROR',
            'errorMessage': error_message
        }
        
        return response
        
    except Exception as e:
        logger.error(f"Erro ao processar notificação de erro: {str(e)}")
        return {
            'status': 'ERROR',
            'message': f"Erro ao processar notificação: {str(e)}"
        }

def calculate_duration(trace_id):
    """
    Calcula a duração desde o início do processo até agora
    """
    try:
        # Consultar o primeiro registro (ORCHESTRATOR)
        response = execution_history_table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('traceId').eq(trace_id),
            ScanIndexForward=True,  # Ordem ascendente por sk (timestamp)
            Limit=1
        )
        
        if not response['Items']:
            return None
            
        start_time = datetime.fromisoformat(response['Items'][0]['timestamp'])
        current_time = datetime.utcnow()
        
        # Calcular duração em segundos
        duration_seconds = (current_time - start_time).total_seconds()
        
        return round(duration_seconds, 2)
    except Exception as e:
        logger.error(f"Erro ao calcular duração para traceId {trace_id}: {str(e)}")
        return None

def send_error_notification(trace_id, failed_stage, error_message, run_type, event):
    """
    Envia uma notificação de erro via SNS
    """
    try:
        # Preparar o conteúdo da notificação
        store_id = event.get('storeId', 'unknown')
        campaign_id = event.get('campaignId', 'N/A')
        
        notification_subject = f"Erro na otimização de campanha - {failed_stage}"
        
        notification_message = {
            'traceId': trace_id,
            'runType': run_type,
            'failedStage': failed_stage,
            'errorMessage': error_message[:500] if error_message else 'Erro desconhecido',  # Limitar tamanho
            'storeId': store_id,
            'campaignId': campaign_id,
            'timestamp': datetime.utcnow().isoformat()
        }
        
        # Enviar para o tópico SNS
        sns_client.publish(
            TopicArn=ERROR_TOPIC_ARN,
            Subject=notification_subject,
            Message=json.dumps(notification_message)
        )
        
        logger.info(f"[traceId: {trace_id}] Notificação de erro enviada para o tópico SNS")
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao enviar notificação SNS: {str(e)}")
        # Não propagar este erro para evitar falhar o processo de notificação 