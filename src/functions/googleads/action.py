import json
import boto3
import os
import logging
from datetime import datetime
import time

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do DynamoDB
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))
campaign_metadata_table = dynamodb.Table(os.environ.get('CAMPAIGN_METADATA_TABLE'))

# Importação para simular a API do Google Ads para este esqueleto
# Em produção, use a biblioteca real do Google Ads: 
# from google.ads.googleads.client import GoogleAdsClient

def handler(event, context):
    """
    Função para executar operações na API do Google Ads
    
    Esta função recebe o payload preparado pelo parser e executa
    as operações necessárias na API do Google Ads.
    """
    try:
        trace_id = event.get('traceId')
        stage = 'GOOGLE_ADS_ACTION'
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get('runType', 'FIRST_RUN')
        
        logger.info(f"[traceId: {trace_id}] Iniciando execução de ações no Google Ads para runType: {run_type}")
        
        # Verificar se temos o payload do Google Ads
        if 'googleAdsPayload' not in event:
            raise Exception("googleAdsPayload é obrigatório")
            
        google_ads_payload = event.get('googleAdsPayload')
        operations = google_ads_payload.get('operations', [])
        
        if not operations:
            logger.warning(f"[traceId: {trace_id}] Nenhuma operação para executar no Google Ads")
        else:
            logger.info(f"[traceId: {trace_id}] Executando {len(operations)} operações no Google Ads")
        
        # TODO: Em um ambiente real, inicializar o cliente do Google Ads
        # google_ads_client = GoogleAdsClient.load_from_env()
        
        # Resultados das operações
        results = {
            'success': [],
            'failure': []
        }
        
        # Agrupar operações por tipo para execução
        operation_groups = {}
        for op in operations:
            op_type = op.get('type')
            if op_type not in operation_groups:
                operation_groups[op_type] = []
            operation_groups[op_type].append(op)
        
        # Processar operações na ordem correta
        # 1. Campanha
        # 2. Grupos de anúncios
        # 3. Keywords
        # 4. Anúncios
        # 5. Ajustes de lances (bidding)
        
        # Simular o processamento das operações
        created_campaign_id = None
        
        # Criar/atualizar campanha
        if 'campaign' in operation_groups:
            created_campaign_id = process_campaign_operations(operation_groups['campaign'], results, trace_id)
        
        # Criar/atualizar grupos de anúncios
        if 'adGroup' in operation_groups:
            process_ad_group_operations(operation_groups['adGroup'], results, trace_id, created_campaign_id)
        
        # Criar/atualizar keywords
        if 'keyword' in operation_groups:
            process_keyword_operations(operation_groups['keyword'], results, trace_id)
        
        # Criar/atualizar anúncios
        if 'ad' in operation_groups:
            process_ad_operations(operation_groups['ad'], results, trace_id)
            
        # Ajustar lances
        if 'bidding' in operation_groups:
            process_bidding_operations(operation_groups['bidding'], results, trace_id)
        
        # Atualizar metadados da campanha se for FIRST_RUN e uma campanha foi criada
        if run_type == 'FIRST_RUN' and created_campaign_id:
            update_campaign_metadata(created_campaign_id, trace_id, event.get('storeId', 'unknown'))
        
        # Registrar os resultados na tabela ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'payload': json.dumps({
                'summary': {
                    'total_operations': len(operations),
                    'success_count': len(results['success']),
                    'failure_count': len(results['failure'])
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
        elif created_campaign_id:
            execution_record['campaignId'] = created_campaign_id
            
        # Salvar no DynamoDB
        execution_history_table.put_item(Item=execution_record)
        
        # Preparar resposta para o próximo passo
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'runType': run_type,
            'googleAdsResults': {
                'success_count': len(results['success']),
                'failure_count': len(results['failure']),
                'created_campaign_id': created_campaign_id
            }
        }
        
        # Incluir outros campos relevantes do evento original
        if 'storeId' in event:
            response['storeId'] = event['storeId']
            
        if 'campaignId' in event:
            response['campaignId'] = event['campaignId']
        elif created_campaign_id:
            response['campaignId'] = created_campaign_id
            
        logger.info(f"[traceId: {trace_id}] Execução de ações no Google Ads concluída com sucesso. Operações: {len(results['success'])} sucesso, {len(results['failure'])} falha")
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro na execução de ações no Google Ads: {error_msg}")
        
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
                    
                if 'campaignId' in event:
                    error_record['campaignId'] = event['campaignId']
                    
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        
        # Propagar o erro para a Step Function
        raise Exception(f"Erro ao executar ações no Google Ads: {error_msg}")

def process_campaign_operations(operations, results, trace_id):
    """
    Processa operações relacionadas a campanhas
    
    Para este esqueleto, estamos apenas simulando a chamada à API.
    Em um ambiente real, implementar a chamada real à API do Google Ads.
    """
    # Simular processamento com uma pequena latência
    time.sleep(0.5)
    
    # Para fins de simulação, gerar um ID de campanha
    campaign_id = f"campaign-{int(time.time())}"
    
    # Processar cada operação
    for op in operations:
        operation = op.get('operation', {})
        
        # Simular sucesso da operação
        results['success'].append({
            'type': 'campaign',
            'operation': 'create' if 'create' in operation else 'update',
            'resourceName': f"customers/123456789/campaigns/{campaign_id}"
        })
        
        logger.info(f"[traceId: {trace_id}] Campanha criada/atualizada com sucesso: {campaign_id}")
    
    return campaign_id

def process_ad_group_operations(operations, results, trace_id, campaign_id=None):
    """
    Processa operações relacionadas a grupos de anúncios
    """
    # Simular processamento com uma pequena latência
    time.sleep(0.5)
    
    # Processar cada operação
    for op in operations:
        operation = op.get('operation', {})
        ad_group_name = operation.get('create', {}).get('adGroup', {}).get('name', 'Unnamed')
        
        # Simular sucesso da operação
        ad_group_id = f"adgroup-{ad_group_name.replace(' ', '')}-{int(time.time())}"
        
        results['success'].append({
            'type': 'adGroup',
            'operation': 'create' if 'create' in operation else 'update',
            'resourceName': f"customers/123456789/adGroups/{ad_group_id}",
            'adGroupName': ad_group_name,
            'campaignId': campaign_id
        })
        
        logger.info(f"[traceId: {trace_id}] Grupo de anúncios criado/atualizado com sucesso: {ad_group_id} ({ad_group_name})")

def process_keyword_operations(operations, results, trace_id):
    """
    Processa operações relacionadas a keywords
    """
    # Simular processamento com uma pequena latência
    time.sleep(0.3)
    
    # Processar cada operação
    for op in operations:
        operation = op.get('operation', {})
        keyword = operation.get('create', {}).get('keyword', {}).get('text', 'unknown')
        
        # Simular sucesso da operação
        keyword_id = f"keyword-{int(time.time())}"
        
        results['success'].append({
            'type': 'keyword',
            'operation': 'create' if 'create' in operation else ('remove' if 'remove' in operation else 'update'),
            'resourceName': f"customers/123456789/keywords/{keyword_id}",
            'keyword': keyword
        })
        
        logger.info(f"[traceId: {trace_id}] Keyword processada com sucesso: {keyword}")

def process_ad_operations(operations, results, trace_id):
    """
    Processa operações relacionadas a anúncios
    """
    # Simular processamento com uma pequena latência
    time.sleep(0.4)
    
    # Processar cada operação
    for op in operations:
        operation = op.get('operation', {})
        ad_data = operation.get('create', {}).get('ad', {}).get('expandedTextAd', {})
        headline1 = ad_data.get('headlinePart1', '')
        
        # Simular sucesso da operação
        ad_id = f"ad-{int(time.time())}"
        
        results['success'].append({
            'type': 'ad',
            'operation': 'create' if 'create' in operation else 'update',
            'resourceName': f"customers/123456789/ads/{ad_id}",
            'headline': headline1
        })
        
        logger.info(f"[traceId: {trace_id}] Anúncio processado com sucesso: {headline1}")

def process_bidding_operations(operations, results, trace_id):
    """
    Processa operações relacionadas a ajustes de lances
    """
    # Simular processamento com uma pequena latência
    time.sleep(0.2)
    
    # Processar cada operação
    for op in operations:
        operation = op.get('operation', {})
        target = op.get('target', 'unknown')
        action = op.get('action', 'unknown')
        
        # Simular sucesso da operação
        results['success'].append({
            'type': 'bidding',
            'operation': 'update',
            'target': target,
            'action': action
        })
        
        logger.info(f"[traceId: {trace_id}] Lance ajustado com sucesso para {target} ({action})")

def update_campaign_metadata(campaign_id, trace_id, store_id):
    """
    Atualiza ou cria um registro de metadados para a campanha no DynamoDB
    """
    try:
        # Preparar o item para o DynamoDB
        item = {
            'googleCampaignId': campaign_id,
            'traceId': trace_id,
            'storeId': store_id,
            'createdAt': datetime.utcnow().isoformat(),
            'currentStatus': 'ACTIVE'
        }
        
        # Salvar no DynamoDB
        campaign_metadata_table.put_item(Item=item)
        
        logger.info(f"[traceId: {trace_id}] Metadados da campanha {campaign_id} atualizados com sucesso")
    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao atualizar metadados da campanha: {str(e)}")
        # Não propagar este erro para evitar falhar o processo principal 