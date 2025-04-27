import json
import boto3
import os
import uuid
import logging
from datetime import datetime

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do Step Functions
sfn_client = boto3.client('stepfunctions')

def handler(event, context):
    """
    Função Lambda que inicia a execução do Step Function para otimização de campanhas
    
    Esta função é acionada pelo EventBridge Scheduler e inicia o fluxo de trabalho
    que otimiza campanhas do Google Ads usando a OpenAI.
    """
    try:
        # Gera um ID de trace único para esta execução
        trace_id = str(uuid.uuid4())
        logger.info(f"[traceId: {trace_id}] Iniciando processo de otimização de campanha")
        
        # Obter o ARN da Step Function do ambiente
        state_machine_arn = os.environ.get('STATE_MACHINE_ARN')
        
        # Parâmetros de entrada para o fluxo
        input_data = {
            'traceId': trace_id,
            'timestamp': datetime.utcnow().isoformat(),
            'source': 'scheduled-trigger'
        }
        
        # Se o evento contiver um campaignId, incluí-lo na entrada para o Step Function
        # para que o fluxo saiba que é uma execução de melhoria e não uma primeira execução
        if event.get('campaignId'):
            input_data['campaignId'] = event.get('campaignId')
            input_data['storeId'] = event.get('storeId', 'unknown')
            logger.info(f"[traceId: {trace_id}] Executando otimização para campanha existente: {input_data['campaignId']}")
        else:
            logger.info(f"[traceId: {trace_id}] Executando criação de nova campanha (FIRST_RUN)")
            
        # Iniciar execução do Step Function
        execution = sfn_client.start_execution(
            stateMachineArn=state_machine_arn,
            name=f"campaign-optimization-{trace_id}",
            input=json.dumps(input_data)
        )
        
        # Registrar o ARN da execução
        execution_arn = execution['executionArn']
        logger.info(f"[traceId: {trace_id}] Step Function iniciado com sucesso: {execution_arn}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Campaign optimization process initiated successfully',
                'traceId': trace_id,
                'executionArn': execution_arn
            })
        }
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro ao iniciar o processo: {error_msg}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Error initiating campaign optimization process',
                'error': error_msg
            })
        } 