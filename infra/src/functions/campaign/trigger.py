import json
import boto3
import os
import logging
from datetime import datetime

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente Step Functions
sfn_client = boto3.client('stepfunctions')
STATE_MACHINE_ARN = os.environ.get('STATE_MACHINE_ARN')

def handler(event, context):
    """
    Função para iniciar o processo de otimização de campanhas
    
    Esta função é o ponto de entrada do processo, podendo ser acionada
    manualmente ou por uma regra do EventBridge/CloudWatch Events.
    """
    try:
        # Registrar a chamada
        logger.info(f"Iniciando processo de otimização de campanhas: {json.dumps(event)}")
        
        # Preparar payload para a Step Function
        payload = {}
        
        # Se recebemos parâmetros, incluí-los no payload
        if 'campaignId' in event:
            payload['campaignId'] = event['campaignId']
            
        if 'storeId' in event:
            payload['storeId'] = event['storeId']
            
        if 'templateId' in event:
            payload['templateId'] = event['templateId']
            
        if 'locale' in event:
            payload['locale'] = event['locale']
        
        # Iniciar a execução da Step Function
        execution_name = f"campaign-optimization-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        response = sfn_client.start_execution(
            stateMachineArn=STATE_MACHINE_ARN,
            name=execution_name,
            input=json.dumps(payload)
        )
        
        # Retornar o ARN da execução iniciada
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Processo de otimização de campanhas iniciado com sucesso',
                'executionArn': response['executionArn']
            })
        }
        
    except Exception as e:
        error_message = str(e)
        logger.error(f"Erro ao iniciar processo de otimização: {error_message}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'message': 'Erro ao iniciar processo de otimização',
                'error': error_message
            })
        } 