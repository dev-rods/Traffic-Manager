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
campaign_metadata_table = dynamodb.Table(os.environ.get('CAMPAIGN_METADATA_TABLE'))

def handler(event, context):
    """
    Função para registrar o término do processo de otimização
    
    Esta função registra o término bem-sucedido do processo completo
    e atualiza o status na tabela de metadados da campanha.
    """
    try:
        trace_id = event.get('traceId')
        stage = 'FINISH'
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get('runType', 'FIRST_RUN')
        
        logger.info(f"[traceId: {trace_id}] Registrando conclusão do processo de otimização para runType: {run_type}")
        
        # Obter o ID da campanha, que pode vir diretamente do evento ou dos resultados do Google Ads
        campaign_id = event.get('campaignId')
        
        if not campaign_id and 'googleAdsResults' in event and 'created_campaign_id' in event['googleAdsResults']:
            campaign_id = event['googleAdsResults']['created_campaign_id']
            
        if not campaign_id:
            logger.warning(f"[traceId: {trace_id}] Nenhum ID de campanha encontrado para registro")
        
        # Registrar conclusão na tabela ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'payload': json.dumps({
                'summary': {
                    'runType': run_type,
                    'duration': calculate_duration(trace_id),
                    'status': 'SUCCESS'
                }
            })
        }
        
        # Adicionar campos adicionais, se existirem no evento original
        if 'runType' in event:
            execution_record['runType'] = event['runType']
        
        if 'storeId' in event:
            execution_record['storeId'] = event['storeId']
            
        if campaign_id:
            execution_record['campaignId'] = campaign_id
            
        # Salvar no DynamoDB
        execution_history_table.put_item(Item=execution_record)
        
        # Atualizar metadados da campanha, se tivermos um ID de campanha
        if campaign_id:
            update_campaign_status(campaign_id, 'ACTIVE', trace_id)
        
        # Preparar resposta
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'runType': run_type,
            'status': 'SUCCESS'
        }
        
        # Incluir outros campos relevantes do evento original
        if 'storeId' in event:
            response['storeId'] = event['storeId']
            
        if campaign_id:
            response['campaignId'] = campaign_id
            
        logger.info(f"[traceId: {trace_id}] Processo de otimização concluído e registrado com sucesso")
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro ao registrar conclusão: {error_msg}")
        
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
                    'payload': json.dumps({
                        'error': error_msg
                    })
                }
                
                # Adicionar campos adicionais se disponíveis
                if 'run_type' in locals():
                    error_record['runType'] = run_type
                    
                if 'campaign_id' in locals() and campaign_id:
                    error_record['campaignId'] = campaign_id
                    
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        # Propagar o erro para a Step Function
        raise Exception(f"Erro ao registrar conclusão do processo: {error_msg}")

def calculate_duration(trace_id):
    """
    Calcula a duração total do processo com base nos registros na tabela ExecutionHistory
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

def update_campaign_status(campaign_id, status, trace_id):
    """
    Atualiza o status da campanha na tabela de metadados
    """
    try:
        # Verificar se o registro existe
        response = campaign_metadata_table.get_item(
            Key={
                'googleCampaignId': campaign_id
            }
        )
        
        if 'Item' not in response:
            logger.warning(f"[traceId: {trace_id}] Registro de campanha {campaign_id} não encontrado na tabela de metadados")
            return
            
        # Atualizar o status
        campaign_metadata_table.update_item(
            Key={
                'googleCampaignId': campaign_id
            },
            UpdateExpression="set currentStatus = :status, lastUpdatedAt = :timestamp",
            ExpressionAttributeValues={
                ':status': status,
                ':timestamp': datetime.utcnow().isoformat()
            }
        )
        
        logger.info(f"[traceId: {trace_id}] Status da campanha {campaign_id} atualizado para {status}")
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao atualizar status da campanha {campaign_id}: {str(e)}")
        # Não propagar este erro para evitar falhar o processo principal 