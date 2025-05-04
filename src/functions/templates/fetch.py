import json
import boto3
import os
import logging
from datetime import datetime

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
templates_table = dynamodb.Table(os.environ.get('CAMPAIGN_TEMPLATES_TABLE'))
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

# Configurações padrão
DEFAULT_TEMPLATE_ID = "default_search_template"
DEFAULT_LOCALE = "pt_BR"

def handler(event, context):
    """
    Função para buscar o template de campanha para o processo de FIRST_RUN
    
    Esta função busca um template adequado na tabela CampaignTemplates
    e registra esta etapa na tabela ExecutionHistory.
    """
    try:
        trace_id = event.get('traceId')
        stage = 'FETCH_TEMPLATE'
        timestamp = datetime.utcnow().isoformat()
        
        logger.info(f"[traceId: {trace_id}] Buscando template de campanha")
        
        # Obter parâmetros para seleção do template
        template_id = event.get('templateId', DEFAULT_TEMPLATE_ID)
        locale = event.get('locale', DEFAULT_LOCALE)
        
        template = None
        template_found = False
        
        # Buscar o template no DynamoDB
        try:
            response = templates_table.get_item(
                Key={
                    'templateId': template_id
                }
            )
            if 'Item' in response:
                template = response['Item']
                template_found = True
                logger.info(f"[traceId: {trace_id}] Template {template_id} encontrado")
            else:
                logger.warning(f"[traceId: {trace_id}] Template {template_id} não encontrado, buscando template padrão")
                # Se o template especificado não foi encontrado, buscar o template padrão
                response = templates_table.get_item(
                    Key={
                        'templateId': DEFAULT_TEMPLATE_ID
                    }
                )
                
                if 'Item' in response:
                    template = response['Item']
                    template_found = True
                    logger.info(f"[traceId: {trace_id}] Template padrão {DEFAULT_TEMPLATE_ID} encontrado")
        except Exception as e:
            logger.warning(f"[traceId: {trace_id}] Erro ao buscar template: {str(e)}")
        
        # Se nenhum template foi encontrado, criar um template padrão em memória
        if not template_found:
            logger.warning(f"[traceId: {trace_id}] Nenhum template encontrado, criando template padrão em memória")
            template = {
                'templateId': DEFAULT_TEMPLATE_ID,
                'type': 'SEARCH',
                'version': '1.0',
                'jsonBody': {
                    'name': 'Campanha de Busca Padrão',
                    'description': 'Template padrão para campanhas de busca',
                    'adGroups': [
                        {
                            'name': 'Grupo de Anúncios Padrão',
                            'keywords': [
                                {'text': 'produto padrão', 'matchType': 'BROAD'},
                                {'text': 'comprar produto', 'matchType': 'PHRASE'}
                            ],
                            'ads': [
                                {
                                    'headline1': 'Produto Incrível',
                                    'headline2': 'Melhor Qualidade',
                                    'description': 'Compre agora com descontos especiais!'
                                }
                            ]
                        }
                    ],
                    'budget': {
                        'amount': 100.00,
                        'currency': 'BRL'
                    },
                    'targeting': {
                        'locations': ['BR'],
                        'languages': ['pt']
                    }
                }
            }
        
        # Filtrar template pelo locale se necessário
        if 'localeVersions' in template and locale in template['localeVersions']:
            template_content = template['localeVersions'][locale]
        elif 'jsonBody' in template:
            # Se não há versões por locale, use o jsonBody diretamente
            template_content = template['jsonBody']
        else:
            # Se o formato do template não for o esperado, criar um conteúdo padrão
            logger.warning(f"[traceId: {trace_id}] Formato de template inválido, usando conteúdo padrão")
            template_content = {
                'name': 'Campanha de Busca Padrão',
                'description': 'Template padrão para campanhas de busca',
                'adGroups': [
                    {
                        'name': 'Grupo de Anúncios Padrão',
                        'keywords': [
                            {'text': 'produto padrão', 'matchType': 'BROAD'},
                            {'text': 'comprar produto', 'matchType': 'PHRASE'}
                        ],
                        'ads': [
                            {
                                'headline1': 'Produto Incrível',
                                'headline2': 'Melhor Qualidade',
                                'description': 'Compre agora com descontos especiais!'
                            }
                        ]
                    }
                ],
                'budget': {
                    'amount': 100.00,
                    'currency': 'BRL'
                },
                'targeting': {
                    'locations': ['BR'],
                    'languages': ['pt']
                }
            }
        
        logger.info(f"[traceId: {trace_id}] Template utilizado: {template['templateId']}")
        
        # Registrar esta etapa na tabela ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'payload': json.dumps({
                'templateId': template['templateId'],
                'type': template.get('type', 'SEARCH'),
                'version': template.get('version', '1.0')
            })
        }
        
        # Adicionar campos adicionais, se existirem no evento original
        if 'runType' in event:
            execution_record['runType'] = event['runType']
        
        if 'storeId' in event:
            execution_record['storeId'] = event['storeId']
            
        # Salvar no DynamoDB
        execution_history_table.put_item(Item=execution_record)
        
        # Preparar resposta para o próximo passo
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'runType': event.get('runType', 'FIRST_RUN'),
            'templateData': template_content,
            'templateInfo': {
                'templateId': template['templateId'],
                'type': template.get('type', 'SEARCH'),
                'version': template.get('version', '1.0'),
                'locale': locale
            }
        }
        
        # Incluir outros campos relevantes do evento original
        if 'storeId' in event:
            response['storeId'] = event['storeId']
            
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro ao buscar template: {error_msg}")
        
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
        raise Exception(f"Erro ao buscar template de campanha: {error_msg}") 