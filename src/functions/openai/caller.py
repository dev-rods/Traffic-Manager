import json
import boto3
import os
import logging
from datetime import datetime
import requests
import time

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do DynamoDB
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

# Configurações da OpenAI
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4')
OPENAI_API_URL = 'https://api.openai.com/v1/chat/completions'

def handler(event, context):
    """
    Função para chamar a API da OpenAI para otimização de campanhas
    
    Esta função monta o prompt adequado com base no tipo de execução,
    chama a API da OpenAI e registra a conversa na tabela ExecutionHistory.
    """
    try:
        trace_id = event.get('traceId')
        stage = 'OPENAI_CALL'
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get('runType', 'FIRST_RUN')
        
        logger.info(f"[traceId: {trace_id}] Iniciando chamada à OpenAI para runType: {run_type}")
        
        # Montar o prompt adequado baseado no tipo de execução
        if run_type == 'FIRST_RUN':
            # Para primeira execução, usar o template
            if 'templateData' not in event:
                raise Exception("templateData é obrigatório para execução FIRST_RUN")
                
            template_data = event.get('templateData')
            template_info = event.get('templateInfo', {})
            
            prompt = create_first_run_prompt(template_data, template_info)
            context_data = {
                'templateId': template_info.get('templateId', 'unknown'),
                'templateType': template_info.get('type', 'SEARCH'),
                'templateVersion': template_info.get('version', '1.0')
            }
        else:
            # Para melhorias, usar as métricas
            if 'metrics' not in event or 'campaignStructure' not in event:
                raise Exception("metrics e campaignStructure são obrigatórios para execução IMPROVE")
                
            metrics = event.get('metrics')
            campaign_structure = event.get('campaignStructure')
            campaign_id = event.get('campaignId')
            
            prompt = create_improve_prompt(metrics, campaign_structure, campaign_id)
            context_data = {
                'campaignId': campaign_id,
                'metrics_summary': {
                    'impressions': metrics.get('impressions'),
                    'clicks': metrics.get('clicks'),
                    'ctr': metrics.get('ctr'),
                    'conversions': metrics.get('conversions'),
                    'roas': metrics.get('roas')
                }
            }
        
        # Chamar a API da OpenAI
        openai_response = call_openai_api(prompt, model=OPENAI_MODEL)
        
        # Extrair o conteúdo da resposta
        if 'choices' not in openai_response or not openai_response['choices']:
            raise Exception("Resposta inválida da OpenAI")
            
        assistant_response = openai_response['choices'][0]['message']['content']
        
        # Registrar a conversa na tabela ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'costUSD': calculate_cost(openai_response),
            'payload': json.dumps({
                'context': context_data,
                'prompt': prompt,
                'response': assistant_response,
                'model': openai_response.get('model', OPENAI_MODEL),
                'tokens': {
                    'prompt': openai_response.get('usage', {}).get('prompt_tokens', 0),
                    'completion': openai_response.get('usage', {}).get('completion_tokens', 0),
                    'total': openai_response.get('usage', {}).get('total_tokens', 0)
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
        
        # Preparar resposta para o próximo passo
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'runType': run_type,
            'openAIResponse': assistant_response
        }
        
        # Incluir outros campos relevantes do evento original
        if 'storeId' in event:
            response['storeId'] = event['storeId']
            
        if 'campaignId' in event:
            response['campaignId'] = event['campaignId']
            
        # Manter dados de contexto para uso posterior
        if run_type == 'FIRST_RUN':
            response['templateInfo'] = event.get('templateInfo', {})
        else:
            response['metrics'] = event.get('metrics', {})
            response['campaignStructure'] = event.get('campaignStructure', {})
            
        logger.info(f"[traceId: {trace_id}] Chamada à OpenAI concluída com sucesso")
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro na chamada à OpenAI: {error_msg}")
        
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
                        'event': event,
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
        raise Exception(f"Erro ao chamar a OpenAI: {error_msg}")

def call_openai_api(prompt, model=OPENAI_MODEL):
    """
    Faz uma chamada para a API da OpenAI
    """
    # Em produção, implemente a chamada real à API
    # Simular uma chamada à API da OpenAI para este esqueleto
    
    # Para implementação real:
    headers = {
        'Authorization': f'Bearer {OPENAI_API_KEY}',
        'Content-Type': 'application/json'
    }
    
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': 'Você é um especialista em marketing digital e otimização de campanhas do Google Ads. Sua tarefa é analisar dados e fornecer recomendações para melhorar o desempenho das campanhas.'
            },
            {
                'role': 'user',
                'content': prompt
            }
        ],
        'temperature': 0.7,
        'max_tokens': 1500
    }
    
    # Comentado para não fazer chamadas reais durante o desenvolvimento do esqueleto
    response = requests.post(OPENAI_API_URL, headers=headers, json=payload)
    return response.json()
    
def create_first_run_prompt(template_data, template_info):
    """
    Cria o prompt para primeira execução (criação de campanha)
    """
    template_id = template_info.get('templateId', 'default')
    template_type = template_info.get('type', 'SEARCH')
    
    prompt = f"""
    Você é um especialista em Google Ads encarregado de criar uma nova campanha.
    
    Você está usando o template {template_id} do tipo {template_type}.
    
    Por favor, analise os dados abaixo e crie uma estrutura otimizada para uma nova campanha:
    
    {json.dumps(template_data, indent=2)}
    
    Seu resultado deve ser um JSON válido com a seguinte estrutura:
    {{
      "campaign_name": "Nome da Campanha",
      "ad_groups": [
        {{
          "name": "Nome do Grupo de Anúncios",
          "keywords": ["palavra-chave 1", "palavra-chave 2"],
          "match_types": ["EXACT", "PHRASE"],
          "ads": [
            {{
              "headline1": "Título 1",
              "headline2": "Título 2",
              "headline3": "Título 3",
              "description1": "Descrição 1",
              "description2": "Descrição 2"
            }}
          ]
        }}
      ],
      "targeting": {{
        "locations": ["Brasil"],
        "languages": ["pt"],
        "devices": ["mobile", "desktop"]
      }},
      "settings": {{
        "budget": 30.00,
        "bidding_strategy": "MAXIMIZE_CONVERSIONS"
      }}
    }}
    """
    
    return prompt
    
def create_improve_prompt(metrics, campaign_structure, campaign_id):
    """
    Cria o prompt para melhorias em campanhas existentes
    """
    prompt = f"""
    Você é um especialista em Google Ads encarregado de otimizar a campanha {campaign_id}.
    
    Aqui estão as métricas de performance dos últimos 30 dias:
    {json.dumps(metrics, indent=2)}
    
    E aqui está a estrutura atual da campanha:
    {json.dumps(campaign_structure, indent=2)}
    
    Com base nessas informações, por favor forneça recomendações para melhorar o desempenho da campanha.
    
    Seu resultado deve ser um JSON válido com a seguinte estrutura:
    {{
      "analysis": "Sua análise dos dados atuais",
      "recommendations": [
        {{
          "type": "keywords",
          "action": "add|remove|modify",
          "items": ["keyword1", "keyword2"]
        }},
        {{
          "type": "bidding",
          "action": "increase|decrease",
          "target": "nome do grupo de anúncios ou keyword",
          "value": 0.10 // 10% de alteração
        }},
        {{
          "type": "ad",
          "action": "add|modify|pause",
          "ad_group": "nome do grupo de anúncios",
          "headlines": ["headline1", "headline2", "headline3"],
          "descriptions": ["description1", "description2"]
        }}
      ],
      "reasoning": "Explicação detalhada da lógica por trás das recomendações"
    }}
    """
    
    return prompt
    
def calculate_cost(openai_response):
    """
    Calcula o custo aproximado da chamada à API da OpenAI
    Baseado nos preços de abril/2023, ajustar conforme necessário
    """
    model = openai_response.get('model', OPENAI_MODEL)
    usage = openai_response.get('usage', {})
    
    prompt_tokens = usage.get('prompt_tokens', 0)
    completion_tokens = usage.get('completion_tokens', 0)
    
    # Preços aproximados por 1000 tokens (em USD)
    # Atualizar conforme necessário
    prices = {
        'gpt-4': {'prompt': 0.03, 'completion': 0.06},
        'gpt-4-32k': {'prompt': 0.06, 'completion': 0.12},
        'gpt-3.5-turbo': {'prompt': 0.0015, 'completion': 0.002}
    }
    
    # Usar os preços do gpt-3.5-turbo como fallback
    model_prices = prices.get(model, prices['gpt-3.5-turbo'])
    
    # Calcular o custo
    prompt_cost = (prompt_tokens / 1000) * model_prices['prompt']
    completion_cost = (completion_tokens / 1000) * model_prices['completion']
    
    return round(prompt_cost + completion_cost, 6) 