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
        # Se o evento já tem um traceId, utilize-o, caso contrário gere um novo
        trace_id = event.get('traceId', str(uuid.uuid4()))
        timestamp = datetime.utcnow().isoformat()
        stage = 'ORCHESTRATOR'
        
        logger.info(f"[traceId: {trace_id}] Iniciando orquestração do processo de otimização")
        
        # Determinar o tipo de execução (FIRST_RUN ou IMPROVE)
        if 'campaignId' in event and event['campaignId']:
            run_type = 'IMPROVE'
            logger.info(f"[traceId: {trace_id}] Tipo de execução: {run_type} para campanha {event['campaignId']}")
        else:
            run_type = 'FIRST_RUN'
            logger.info(f"[traceId: {trace_id}] Tipo de execução: {run_type} (nova campanha)")
        
        # Registrar o início do processo na tabela ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'runType': run_type,
            'status': 'STARTED',
            'timestamp': timestamp,
            'payload': json.dumps(event)
        }
        
        # Adicionar storeId e campaignId se disponíveis
        if 'storeId' in event:
            execution_record['storeId'] = event['storeId']
        
        if 'campaignId' in event:
            execution_record['campaignId'] = event['campaignId']
        
        # Salvar no DynamoDB
        execution_history_table.put_item(Item=execution_record)
        
        logger.info(f"[traceId: {trace_id}] Registro criado na tabela ExecutionHistory para estágio {stage}")
        
        # Preparar resposta para o próximo passo
        response = {
            'traceId': trace_id,
            'runType': run_type,
            'timestamp': timestamp
        }
        
        # Passar campaignId e storeId se existirem no evento original
        if 'campaignId' in event:
            response['campaignId'] = event['campaignId']
        
        if 'storeId' in event:
            response['storeId'] = event['storeId']
            
        # Adicionar qualquer outro dado relevante do evento original
        response['originalEvent'] = event
        
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro na orquestração: {error_msg}")
        
        # Tentar registrar o erro se possível
        if 'trace_id' in locals():
            try:
                error_record = {
                    'traceId': trace_id,
                    'stageTm': f"{stage}#{timestamp}",
                    'stage': stage,
                    'status': 'ERROR',
                    'timestamp': timestamp,
                    'errorMsg': error_msg,
                    'payload': json.dumps(event)
                }
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        # Propagar o erro para a Step Function
        raise Exception(f"Erro na orquestração do processo: {error_msg}") 