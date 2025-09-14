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
    try:
        trace_id = event.get("traceId")
        client_id = event.get("clientId")
        stage = "FINISH"
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get("runType", "FIRST_RUN")
        
        logger.info(f"[traceId: {trace_id}] Registrando conclusão do processo de otimização para runType: {run_type}")
        
        campaign_id = event.get("campaignId")
        google_ads_results = event.get("googleAdsResults", {})
        
        if not campaign_id and "created_campaign_id" in google_ads_results:
            campaign_id = google_ads_results["created_campaign_id"]
            
        if not campaign_id:
            logger.warning(f"[traceId: {trace_id}] Nenhum ID de campanha encontrado para registro")
        
        process_summary = generate_process_summary(trace_id, run_type, google_ads_results)
        
        execution_record = {
            "traceId": trace_id,
            "stageTm": f"{stage}#{timestamp}",
            "stage": stage,
            "status": "COMPLETED",
            "timestamp": timestamp,
            "payload": json.dumps(process_summary)
        }
        
        if "runType" in event:
            execution_record["runType"] = event["runType"]
        if "storeId" in event:
            execution_record["storeId"] = event["storeId"]
        if "clientId" in event:
            execution_record["clientId"] = event["clientId"]
        if campaign_id:
            execution_record["campaignId"] = campaign_id
            
        execution_history_table.put_item(Item=execution_record)
        
        if campaign_id:
            if run_type == "FIRST_RUN":
                create_campaign_metadata_record(campaign_id, client_id, trace_id, event)
            else:
                update_campaign_metadata_record(campaign_id, trace_id, google_ads_results)
        
        response = {
            "traceId": trace_id,
            "timestamp": timestamp,
            "runType": run_type,
            "status": "SUCCESS",
            "summary": process_summary
        }
        
        if "storeId" in event:
            response["storeId"] = event["storeId"]
        if "clientId" in event:
            response["clientId"] = event["clientId"]
        if campaign_id:
            response["campaignId"] = campaign_id
            
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


def generate_process_summary(trace_id, run_type, google_ads_results):
    duration = calculate_duration(trace_id)
    
    summary = {
        "runType": run_type,
        "duration": duration,
        "status": "SUCCESS",
        "googleAdsResults": {
            "successCount": google_ads_results.get("success_count", 0),
            "failureCount": google_ads_results.get("failure_count", 0)
        }
    }
    
    if run_type == "FIRST_RUN":
        summary["campaignCreated"] = google_ads_results.get("created_campaign_id") is not None
        if google_ads_results.get("created_campaign_id"):
            summary["newCampaignId"] = google_ads_results["created_campaign_id"]
    else:
        summary["optimizationsApplied"] = google_ads_results.get("success_count", 0)
    
    return summary


def create_campaign_metadata_record(campaign_id, client_id, trace_id, event):
    try:
        metadata_record = {
            "googleCampaignId": campaign_id,
            "clientId": client_id,
            "createdAt": datetime.utcnow().isoformat(),
            "currentStatus": "ACTIVE",
            "lastUpdatedAt": datetime.utcnow().isoformat(),
            "creationTraceId": trace_id,
            "campaignType": "SEARCH"
        }
        
        if "storeId" in event:
            metadata_record["storeId"] = event["storeId"]
        if "formData" in event:
            form_data = event["formData"]
            if isinstance(form_data, str):
                form_data = json.loads(form_data)
            
            client_info = form_data.get("clientInfo", {})
            metadata_record["business_name"] = client_info.get("business_name", "")
            metadata_record["businessEmail"] = client_info.get("email", "")
        
        campaign_metadata_table.put_item(Item=metadata_record)
        logger.info(f"[traceId: {trace_id}] Metadados da campanha {campaign_id} criados")
        
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao criar metadados da campanha {campaign_id}: {str(e)}")


def update_campaign_metadata_record(campaign_id, trace_id, google_ads_results):
    try:
        update_expression = "SET lastUpdatedAt = :timestamp, lastOptimizationTraceId = :traceId"
        expression_values = {
            ":timestamp": datetime.utcnow().isoformat(),
            ":traceId": trace_id
        }
        
        if google_ads_results.get("success_count", 0) > 0:
            update_expression += ", optimizationCount = if_not_exists(optimizationCount, :zero) + :increment"
            expression_values[":zero"] = 0
            expression_values[":increment"] = 1
        
        campaign_metadata_table.update_item(
            Key={"googleCampaignId": campaign_id},
            UpdateExpression=update_expression,
            ExpressionAttributeValues=expression_values
        )
        
        logger.info(f"[traceId: {trace_id}] Metadados da campanha {campaign_id} atualizados")
        
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao atualizar metadados da campanha {campaign_id}: {str(e)}") 