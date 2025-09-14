import json
import boto3
import os
import uuid
from datetime import datetime
from src.services.google_ads_client_service import GoogleAdsClientService


dynamodb = boto3.resource("dynamodb")
execution_history_table = dynamodb.Table(os.environ.get("EXECUTION_HISTORY_TABLE"))
clients_table = dynamodb.Table(os.environ.get("CLIENTS_TABLE"))

def handler(event, context):
    try:
        trace_id = event.get("traceId", str(uuid.uuid4()))
        timestamp = datetime.utcnow().isoformat()
        print(f"[traceId: {trace_id}] Iniciando orquestração do processo de otimização")
        
        client_id = None
        run_type = None
        
        if "formData" in event:
            run_type = "FIRST_RUN"
            client_id = determine_client_from_email(event["formData"].get("email"))
            print(f"[traceId: {trace_id}] Dados do Forms detectados - runType: {run_type}")
        elif "campaignId" in event and event["campaignId"]:
            run_type = "IMPROVE"
            client_id = get_client_from_campaign(event["campaignId"])
            print(f"[traceId: {trace_id}] Campanha existente detectada - runType: {run_type}")
        elif "storeId" in event:
            client_id = event["storeId"]
            run_type = "IMPROVE" if event.get("campaignId") else "FIRST_RUN"
            print(f"[traceId: {trace_id}] StoreId fornecido - runType: {run_type}")
        else:
            raise Exception("Dados insuficientes: formData, campaignId ou storeId são obrigatórios")
        
        if not client_id:
            raise Exception("Não foi possível determinar o clientId")
        
        ads_service = GoogleAdsClientService()
        validation = ads_service.validate_client_access(client_id)
        if not validation["valid"]:
            raise Exception(f"Cliente sem acesso Google Ads: {validation['error']}")
        execution_record = {
            "traceId": trace_id,
            "runType": run_type,
            "status": "STARTED",
            "timestamp": timestamp,
            "payload": json.dumps(event),
            "stageTm": "orchestrator",
            "clientId": client_id
        }
        
        if "storeName" in event:
            execution_record["storeName"] = event["storeName"]
        if "campaignId" in event:
            execution_record["campaignId"] = event["campaignId"]
        if "formData" in event:
            execution_record["formData"] = json.dumps(event["formData"])
        if "storeId" in event:
            execution_record["storeId"] = event["storeId"]
            
        execution_history_table.put_item(Item=execution_record)
        print(f"[traceId: {trace_id}] Registro criado na tabela ExecutionHistory")
        
        response = {
            "traceId": trace_id,
            "runType": run_type,
            "timestamp": timestamp,
            "clientId": client_id
        }
        
        if "storeName" in event:
            response["storeName"] = event["storeName"]
        if "campaignId" in event:
            response["campaignId"] = event["campaignId"]
        if "formData" in event:
            response["formData"] = event["formData"]
        if "storeId" in event:
            response["storeId"] = event["storeId"]
            
        response["originalEvent"] = event
        return response
    except Exception as e:
        error_msg = str(e)
        print(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro na orquestração: {error_msg}")
        if "trace_id" in locals():
            try:
                error_record = {
                    "traceId": trace_id,
                    "status": "ERROR",
                    "timestamp": timestamp,
                    "errorMsg": error_msg,
                    "payload": json.dumps(event),
                    "stageTm": "orchestrator"
                }
                if "storeId" in event:
                    error_record["storeId"] = event["storeId"]
                if "client_id" in locals():
                    error_record["clientId"] = client_id
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                print(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")        
        raise Exception(f"Erro na orquestração do processo: {error_msg}")


def determine_client_from_email(email):
    if not email:
        raise Exception("Email é obrigatório para determinar o cliente")
    try:
        response = clients_table.scan(FilterExpression="email = :email", ExpressionAttributeValues={":email": email})
        if response["Items"]:
            client = response["Items"][0]
            return client["clientId"]
        else:
            raise Exception(f"Cliente não encontrado para o email: {email}")
    except Exception as e:
        print(f"Erro ao buscar cliente por email {email}: {str(e)}")
        raise


def get_client_from_campaign(campaign_id):
    if not campaign_id:
        raise Exception("Campaign ID é obrigatório")
    
    try:
        response = execution_history_table.query(
            IndexName="campaignId-index",
            KeyConditionExpression="campaignId = :campaignId",
            ExpressionAttributeValues={":campaignId": campaign_id},
            ScanIndexForward=False,
            Limit=1
        )
        
        if response["Items"]:
            execution = response["Items"][0]
            return execution.get("clientId") or execution.get("storeId")
        else:
            raise Exception(f"Cliente não encontrado para a campanha: {campaign_id}")
            
    except Exception as e:
        print(f"Erro ao buscar cliente por campanha {campaign_id}: {str(e)}")
        raise 