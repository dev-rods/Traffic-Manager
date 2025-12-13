import json
import boto3
import os
import logging
from datetime import datetime
from src.utils.openai_utils import call_openai_api, format_prompt,calculate_cost, get_prompt_from_table
from decimal import Decimal

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1')

def handler(event, context):
    try:
        trace_id = event.get('traceId')
        stage = 'OPENAI_CALL'
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get('runType', 'FIRST_RUN')
        logger.info(f"[traceId: {trace_id}] Iniciando chamada à OpenAI para runType: {run_type}")
        
        prompt_id = event.get('promptId')
        if prompt_id:
            prompt_item = get_prompt_from_table(prompt_id)
            if not prompt_item:
                raise Exception(f"Prompt '{prompt_id}' não encontrado na tabela")
            
            if not prompt_item.get('isActive', True):
                raise Exception(f"Prompt '{prompt_id}' está inativo")
            
            parameters = event.get('parameters', {})
            prompt = format_prompt(prompt_item['prompt'], parameters, strict=False)
            system_message = prompt_item.get('systemMessage', 'Você é um especialista em marketing digital e otimização de campanhas do Google Ads. Sua tarefa é analisar dados e fornecer recomendações para melhorar o desempenho das campanhas.')
            model = prompt_item.get('model', OPENAI_MODEL)
            
            temperature_value = prompt_item.get('temperature', Decimal('0.7'))
            max_tokens_value = prompt_item.get('maxTokens', Decimal('1500'))
            
            temperature = float(temperature_value) if isinstance(temperature_value, Decimal) else temperature_value
            max_tokens = int(max_tokens_value) if isinstance(max_tokens_value, Decimal) else max_tokens_value
            
            context_data = {
                'promptId': prompt_id,
                'parameters': parameters
            }
            
            openai_response = call_openai_api(
                prompt=prompt,
                system_message=system_message,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            )
        else:
            if run_type == 'FIRST_RUN':
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
            openai_response = call_openai_api(prompt, model=OPENAI_MODEL)
        if 'choices' not in openai_response or not openai_response['choices']:
            raise Exception("Resposta inválida da OpenAI")
        assistant_response = openai_response['choices'][0]['message']['content']
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'costUSD': calculate_cost(openai_response, default_model=OPENAI_MODEL),
            'payload': json.dumps({
                'context': context_data,
                'prompt': prompt,
                'response': assistant_response,
                'model': openai_response.get('model', OPENAI_MODEL),
                'tokens': {
                    'prompt': openai_response.get('usage', {}).get('prompt_tokens', 0),
                    'completion': openai_response.get('usage', {}).get('completion_tokens', 0),
                    'total': openai_response.get('usage', {}).get('total_tokens', 0)
                },
                'promptId': prompt_id if prompt_id else None
            })
        }
        if 'runType' in event:
            execution_record['runType'] = event['runType']
        if 'storeId' in event:
            execution_record['storeId'] = event['storeId']
        if 'campaignId' in event:
            execution_record['campaignId'] = event['campaignId']
        execution_history_table.put_item(Item=execution_record)
        response = {
            'traceId': trace_id,
            'timestamp': timestamp,
            'runType': run_type,
            'openAIResponse': assistant_response
        }
        if 'storeId' in event:
            response['storeId'] = event['storeId']
        if 'campaignId' in event:
            response['campaignId'] = event['campaignId']
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
                if 'run_type' in locals():
                    error_record['runType'] = run_type
                if 'campaignId' in event:
                    error_record['campaignId'] = event['campaignId']
                execution_history_table.put_item(Item=error_record)
            except Exception as inner_e:
                logger.error(f"[traceId: {trace_id}] Erro ao registrar falha: {str(inner_e)}")
        raise Exception(f"Erro ao chamar a OpenAI: {error_msg}")

    
def create_first_run_prompt(template_data, template_info):
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
    