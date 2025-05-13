import json
import boto3
import os
import uuid
import logging
from datetime import datetime

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do DynamoDB
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

def handler(event, context):
    """
    Função orquestradora do processo de otimização de campanhas
    
    Esta função determina se é um FIRST_RUN ou um IMPROVE, gera um traceId 
    e registra o início do processo na tabela ExecutionHistory.
    """
    try:
        trace_id = event.get('traceId', str(uuid.uuid4()))
        timestamp = datetime.utcnow().isoformat()
        logger.info(f"[traceId: {trace_id}] Iniciando orquestração do processo de otimização")
        
        # Verificar se temos o ID do cliente (storeId)
        if 'storeId' not in event:
            logger.warning(f"[traceId: {trace_id}] storeId não fornecido no evento")
            raise Exception("storeId é obrigatório para identificação do cliente")
        
        if 'campaignId' in event and event['campaignId']:
            run_type = 'IMPROVE'
            logger.info(f"[traceId: {trace_id}] Tipo de execução: {run_type} para campanha {event['campaignId']}")
        else:
            run_type = 'FIRST_RUN'
            logger.info(f"[traceId: {trace_id}] Tipo de execução: {run_type} (nova campanha)")
        execution_record = {
            'traceId': trace_id,
            'runType': run_type,
            'status': 'STARTED',
            'timestamp': timestamp,
            'payload': json.dumps(event),
            'stageTm': 'orchestrator',
            'storeId': event['storeId']
        }
        if 'storeName' in event:
            execution_record['storeName'] = event['storeName']
        if 'campaignId' in event:
            execution_record['campaignId'] = event['campaignId']
        if 'formData' in event:
            execution_record['formData'] = json.dumps(event['formData'])
        execution_history_table.put_item(Item=execution_record)
        logger.info(f"[traceId: {trace_id}] Registro criado na tabela ExecutionHistory")
        response = {
            'traceId': trace_id,
            'runType': run_type,
            'timestamp': timestamp,
            'storeId': event['storeId']
        }
        if 'storeName' in event:
            response['storeName'] = event['storeName']
        if 'campaignId' in event:
            response['campaignId'] = event['campaignId']
        if 'formData' in event:
            response['formData'] = event['formData']
        response['originalEvent'] = event
        return response
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro na orquestração: {error_msg}")
        if 'trace_id' in locals():
            try:
                error_record = {
                    'traceId': trace_id,
                    'status': 'ERROR',
                    'timestamp': timestamp,
                    'errorMsg': error_msg,
                    'payload': json.dumps(event),
                    'stageTm': 'orchestrator'
                }
                if 'storeId' in event:
                    error_record['storeId'] = event['storeId']
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")        
        raise Exception(f"Erro na orquestração do processo: {error_msg}") 