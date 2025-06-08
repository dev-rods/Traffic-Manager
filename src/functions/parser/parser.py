import json
import boto3
import os
import logging
from datetime import datetime
import re

# Configuração de logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Cliente do DynamoDB
dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

def handler(event, context):
    try:
        trace_id = event.get("traceId")
        client_id = event.get("clientId")
        stage = "PARSER"
        timestamp = datetime.utcnow().isoformat()
        run_type = event.get("runType", "FIRST_RUN")
        
        logger.info(f"[traceId: {trace_id}] Iniciando parsing da resposta da OpenAI para runType: {run_type}")
        
        if "openAIResponse" not in event:
            raise Exception("openAIResponse é obrigatório")
            
        openai_response = event.get("openAIResponse")
        
        # Extrair o JSON da resposta da OpenAI
        # A resposta pode ser um JSON direto ou um texto que contém um JSON
        try:
            # Tentar carregar como JSON direto
            openai_data = json.loads(openai_response)
        except json.JSONDecodeError:
            # Se falhar, tentar extrair JSON do texto usando regex
            json_match = re.search(r'```json\s*([\s\S]*?)\s*```|```([\s\S]*?)```|(\{[\s\S]*\})', openai_response)
            if json_match:
                json_str = json_match.group(1) or json_match.group(2) or json_match.group(3)
                try:
                    openai_data = json.loads(json_str.strip())
                except json.JSONDecodeError:
                    raise Exception("Não foi possível extrair um JSON válido da resposta")
            else:
                raise Exception("Resposta não contém um JSON válido")
                
        if run_type == "FIRST_RUN":
            google_ads_payload = build_campaign_creation_operations(
                openai_data, 
                event.get("templateData"),
                event.get("formData")
            )
        else:
            google_ads_payload = build_optimization_operations(
                openai_data,
                event.get("metricsData"),
                event.get("campaignId")
            )
            
        execution_record = {
            "traceId": trace_id,
            "stageTm": f"{stage}#{timestamp}",
            "stage": stage,
            "status": "COMPLETED",
            "timestamp": timestamp,
            "payload": json.dumps({
                "openai_processed": {
                    "valid": True,
                    "summary": summarize_payload(google_ads_payload, run_type)
                }
            })
        }
        
        if "runType" in event:
            execution_record["runType"] = event["runType"]
        if "storeId" in event:
            execution_record["storeId"] = event["storeId"]
        if "campaignId" in event:
            execution_record["campaignId"] = event["campaignId"]
        if "clientId" in event:
            execution_record["clientId"] = event["clientId"]
            
        execution_history_table.put_item(Item=execution_record)
        
        response = {
            "traceId": trace_id,
            "timestamp": timestamp,
            "runType": run_type,
            "clientId": client_id,
            "googleAdsPayload": {
                "operations": google_ads_payload,
                "clientId": client_id,
                "runType": run_type
            }
        }
        
        if "storeId" in event:
            response["storeId"] = event["storeId"]
        if "campaignId" in event:
            response["campaignId"] = event["campaignId"]
            
        logger.info(f"[traceId: {trace_id}] Parsing da resposta concluído com sucesso")
        return response
        
    except Exception as e:
        error_msg = str(e)
        logger.error(f"[traceId: {trace_id if 'trace_id' in locals() else 'unknown'}] Erro no parsing da resposta: {error_msg}")
        
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
                        'openai_response': event.get('openAIResponse', ''),
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
        raise Exception(f"Erro ao processar resposta da OpenAI: {error_msg}")

def process_first_run(openai_data, event):
    """
    Processa a resposta da OpenAI para uma primeira execução (criação de campanha)
    e prepara o payload para a API do Google Ads
    """
    # Validar a estrutura esperada
    required_fields = ['campaign_name', 'ad_groups', 'targeting', 'settings']
    for field in required_fields:
        if field not in openai_data:
            raise Exception(f"Campo obrigatório '{field}' não encontrado na resposta")
    
    # Transformar a resposta da OpenAI em um payload para o Google Ads
    # Para este esqueleto, estamos apenas simulando a estrutura
    google_ads_payload = {
        'operations': []
    }
    
    # Operação para criar a campanha
    campaign_operation = {
        'create': {
            'campaign': {
                'name': openai_data['campaign_name'],
                'status': 'ENABLED',
                'advertisingChannelType': 'SEARCH',
                'biddingStrategyConfiguration': {
                    'biddingStrategyType': openai_data['settings'].get('bidding_strategy', 'MAXIMIZE_CONVERSIONS')
                },
                'budget': {
                    'amount': {
                        'microAmount': int(openai_data['settings'].get('budget', 30.0) * 1000000)
                    }
                },
                'targetingSetting': {
                    'targetRestrictions': []
                }
            }
        }
    }
    
    google_ads_payload['operations'].append({
        'type': 'campaign',
        'operation': campaign_operation
    })
    
    # Operações para criar os grupos de anúncios, keywords e anúncios
    for ad_group in openai_data.get('ad_groups', []):
        # Operação para criar o grupo de anúncios
        ad_group_operation = {
            'create': {
                'adGroup': {
                    'name': ad_group['name'],
                    'status': 'ENABLED',
                    'type': 'SEARCH_STANDARD'
                }
            }
        }
        
        google_ads_payload['operations'].append({
            'type': 'adGroup',
            'operation': ad_group_operation,
            'campaignRef': openai_data['campaign_name']
        })
        
        # Operações para criar as keywords
        for keyword in ad_group.get('keywords', []):
            # Determinar o tipo de correspondência (match type)
            match_types = ad_group.get('match_types', ['EXACT'])
            
            for match_type in match_types:
                keyword_operation = {
                    'create': {
                        'keyword': {
                            'text': keyword,
                            'matchType': match_type
                        },
                        'status': 'ENABLED'
                    }
                }
                
                google_ads_payload['operations'].append({
                    'type': 'keyword',
                    'operation': keyword_operation,
                    'adGroupRef': ad_group['name'],
                    'campaignRef': openai_data['campaign_name']
                })
        
        # Operações para criar os anúncios
        for ad in ad_group.get('ads', []):
            ad_operation = {
                'create': {
                    'ad': {
                        'finalUrls': ['https://example.com'],  # Placeholder
                        'expandedTextAd': {
                            'headlinePart1': ad.get('headline1', ''),
                            'headlinePart2': ad.get('headline2', ''),
                            'headlinePart3': ad.get('headline3', ''),
                            'description1': ad.get('description1', ''),
                            'description2': ad.get('description2', '')
                        }
                    }
                }
            }
            
            google_ads_payload['operations'].append({
                'type': 'ad',
                'operation': ad_operation,
                'adGroupRef': ad_group['name'],
                'campaignRef': openai_data['campaign_name']
            })
    
    return google_ads_payload

def process_improve(openai_data, event):
    """
    Processa a resposta da OpenAI para uma execução de melhoria
    e prepara o payload para a API do Google Ads
    """
    # Validar a estrutura esperada
    required_fields = ['recommendations']
    for field in required_fields:
        if field not in openai_data:
            raise Exception(f"Campo obrigatório '{field}' não encontrado na resposta")
    
    # Extrair informações do contexto
    campaign_id = event.get('campaignId')
    campaign_structure = event.get('campaignStructure', {})
    campaign_name = campaign_structure.get('campaign_name', f"Campanha {campaign_id}")
    
    # Transformar a resposta da OpenAI em um payload para o Google Ads
    google_ads_payload = {
        'operations': []
    }
    
    # Processar cada recomendação
    for recommendation in openai_data.get('recommendations', []):
        rec_type = recommendation.get('type')
        action = recommendation.get('action')
        
        if not rec_type or not action:
            logger.warning(f"[traceId: {event.get('traceId')}] Recomendação ignorada por falta de tipo ou ação")
            continue
        
        if rec_type == 'keywords':
            process_keyword_recommendation(recommendation, google_ads_payload, campaign_id, campaign_name)
        elif rec_type == 'bidding':
            process_bidding_recommendation(recommendation, google_ads_payload, campaign_id, campaign_name)
        elif rec_type == 'ad':
            process_ad_recommendation(recommendation, google_ads_payload, campaign_id, campaign_name)
        else:
            logger.warning(f"[traceId: {event.get('traceId')}] Tipo de recomendação desconhecido: {rec_type}")
    
    return google_ads_payload

def process_keyword_recommendation(recommendation, payload, campaign_id, campaign_name):
    """
    Processa uma recomendação de keyword e adiciona ao payload
    """
    action = recommendation.get('action')
    items = recommendation.get('items', [])
    ad_group = recommendation.get('ad_group', 'Produtos Principais')  # Default
    match_type = recommendation.get('match_type', 'EXACT')
    
    for keyword in items:
        if action == 'add':
            operation = {
                'create': {
                    'keyword': {
                        'text': keyword,
                        'matchType': match_type
                    },
                    'status': 'ENABLED'
                }
            }
        elif action == 'remove':
            operation = {
                'remove': {
                    'resourceName': f"customers/{campaign_id}/keywords/{keyword}"
                }
            }
        elif action == 'modify':
            operation = {
                'update': {
                    'keyword': {
                        'text': keyword,
                        'matchType': match_type
                    },
                    'status': recommendation.get('status', 'ENABLED')
                }
            }
        else:
            continue
        
        payload['operations'].append({
            'type': 'keyword',
            'operation': operation,
            'adGroupRef': ad_group,
            'campaignRef': campaign_name
        })

def process_bidding_recommendation(recommendation, payload, campaign_id, campaign_name):
    """
    Processa uma recomendação de bidding e adiciona ao payload
    """
    action = recommendation.get('action')
    target = recommendation.get('target')
    value = recommendation.get('value', 0.1)  # Default 10%
    
    if not target:
        return
    
    # Simulação - em produção, construir o payload real para ajuste de lances
    operation = {
        'update': {
            'biddingStrategy': {
                'targetRoas': {
                    'targetRoas': value if action == 'increase' else -value
                }
            }
        }
    }
    
    payload['operations'].append({
        'type': 'bidding',
        'operation': operation,
        'target': target,
        'campaignRef': campaign_name,
        'action': action
    })

def process_ad_recommendation(recommendation, payload, campaign_id, campaign_name):
    """
    Processa uma recomendação de anúncio e adiciona ao payload
    """
    action = recommendation.get('action')
    ad_group = recommendation.get('ad_group')
    
    if not ad_group:
        return
    
    headlines = recommendation.get('headlines', [])
    descriptions = recommendation.get('descriptions', [])
    
    if action == 'add':
        operation = {
            'create': {
                'ad': {
                    'finalUrls': ['https://example.com'],  # Placeholder
                    'expandedTextAd': {
                        'headlinePart1': headlines[0] if len(headlines) > 0 else '',
                        'headlinePart2': headlines[1] if len(headlines) > 1 else '',
                        'headlinePart3': headlines[2] if len(headlines) > 2 else '',
                        'description1': descriptions[0] if len(descriptions) > 0 else '',
                        'description2': descriptions[1] if len(descriptions) > 1 else ''
                    }
                }
            }
        }
    elif action == 'modify':
        operation = {
            'update': {
                'ad': {
                    'finalUrls': ['https://example.com'],  # Placeholder
                    'expandedTextAd': {
                        'headlinePart1': headlines[0] if len(headlines) > 0 else '',
                        'headlinePart2': headlines[1] if len(headlines) > 1 else '',
                        'headlinePart3': headlines[2] if len(headlines) > 2 else '',
                        'description1': descriptions[0] if len(descriptions) > 0 else '',
                        'description2': descriptions[1] if len(descriptions) > 1 else ''
                    }
                }
            }
        }
    elif action == 'pause':
        operation = {
            'update': {
                'status': 'PAUSED'
            }
        }
    else:
        return
    
    payload['operations'].append({
        'type': 'ad',
        'operation': operation,
        'adGroupRef': ad_group,
        'campaignRef': campaign_name
    })

def summarize_payload(payload, run_type):
    """
    Cria um resumo do payload para log
    """
    operations = payload.get('operations', [])
    summary = {
        'total_operations': len(operations),
        'by_type': {}
    }
    
    for op in operations:
        op_type = op.get('type', 'unknown')
        if op_type not in summary['by_type']:
            summary['by_type'][op_type] = 0
        summary['by_type'][op_type] += 1
    
    return summary


def build_campaign_creation_operations(ai_response, template_data, form_data):
    operations = []
    
    business_name = form_data.get("clientInfo", {}).get("businessName", "Sua Empresa")
    monthly_budget = form_data.get("marketingGoals", {}).get("monthlyBudget", 3000)
    daily_budget_micros = int((monthly_budget / 30) * 1000000)
    
    campaign_op = {
        "type": "CREATE_CAMPAIGN",
        "data": {
            "name": f"{business_name} - {ai_response.get('campaignStrategy', 'Pesquisa')}",
            "advertisingChannelType": "SEARCH",
            "status": "ACTIVE",
            "budget": {
                "dailyBudgetMicros": daily_budget_micros
            },
            "biddingStrategy": {
                "type": ai_response.get("biddingStrategy", "MAXIMIZE_CLICKS")
            },
            "geoTargeting": {
                "includedLocations": form_data.get("marketingGoals", {}).get("geoTargeting", ["2076"])
            }
        }
    }
    operations.append(campaign_op)
    
    for i, ad_group in enumerate(ai_response.get("adGroups", [])):
        ad_group_op = {
            "type": "CREATE_AD_GROUP",
            "data": {
                "name": ad_group.get("name", f"Grupo {i+1}"),
                "campaignId": "{CAMPAIGN_ID}",
                "status": "ACTIVE",
                "cpcBidMicros": int(ad_group.get("defaultBid", 2.0) * 1000000)
            }
        }
        operations.append(ad_group_op)
        
        keywords = ad_group.get("keywords", [])
        if keywords:
            keyword_op = {
                "type": "CREATE_KEYWORDS",
                "data": {
                    "adGroupId": f"{{AD_GROUP_ID_{i}}}",
                    "keywords": [
                        {
                            "text": kw.get("text", kw) if isinstance(kw, dict) else kw,
                            "matchType": kw.get("matchType", "PHRASE") if isinstance(kw, dict) else "PHRASE",
                            "cpcBidMicros": int(kw.get("bid", 2.5) * 1000000) if isinstance(kw, dict) else 2500000
                        }
                        for kw in keywords[:10]
                    ]
                }
            }
            operations.append(keyword_op)
        
        ads = ad_group.get("ads", [])
        if ads:
            ad_op = {
                "type": "CREATE_ADS",
                "data": {
                    "adGroupId": f"{{AD_GROUP_ID_{i}}}",
                    "ads": [
                        {
                            "type": "RESPONSIVE_SEARCH_AD",
                            "headlines": [
                                ad.get("headline1", "Produto Incrível"),
                                ad.get("headline2", "Melhor Qualidade"),
                                ad.get("headline3", "Entrega Rápida")
                            ],
                            "descriptions": [
                                ad.get("description1", "Compre agora com desconto"),
                                ad.get("description2", "Garantia de satisfação")
                            ]
                        }
                        for ad in ads[:3]
                    ]
                }
            }
            operations.append(ad_op)
    
    return operations


def build_optimization_operations(ai_response, metrics_data, campaign_id):
    operations = []
    
    for recommendation in ai_response.get("recommendations", []):
        rec_type = recommendation.get("type")
        
        if rec_type == "KEYWORD_BID_ADJUSTMENT":
            operations.extend(build_keyword_bid_operations(recommendation, campaign_id))
        elif rec_type == "ADD_KEYWORDS":
            operations.extend(build_add_keywords_operations(recommendation, campaign_id))
        elif rec_type == "PAUSE_KEYWORDS":
            operations.extend(build_pause_keywords_operations(recommendation, campaign_id))
        elif rec_type == "AD_COPY_UPDATE":
            operations.extend(build_ad_copy_operations(recommendation, campaign_id))
        elif rec_type == "BUDGET_ADJUSTMENT":
            operations.extend(build_budget_operations(recommendation, campaign_id))
    
    return operations


def build_keyword_bid_operations(recommendation, campaign_id):
    operations = []
    
    for keyword_adjustment in recommendation.get("keywords", []):
        operation = {
            "type": "UPDATE_KEYWORD_BID",
            "data": {
                "campaignId": campaign_id,
                "keywordId": keyword_adjustment.get("keywordId"),
                "newBidMicros": int(keyword_adjustment.get("newBid", 2.0) * 1000000),
                "reason": keyword_adjustment.get("reason", "IA recommendation")
            }
        }
        operations.append(operation)
    
    return operations


def build_add_keywords_operations(recommendation, campaign_id):
    operations = []
    
    for ad_group_keywords in recommendation.get("adGroups", []):
        operation = {
            "type": "ADD_KEYWORDS",
            "data": {
                "campaignId": campaign_id,
                "adGroupId": ad_group_keywords.get("adGroupId"),
                "keywords": [
                    {
                        "text": kw.get("text"),
                        "matchType": kw.get("matchType", "PHRASE"),
                        "cpcBidMicros": int(kw.get("bid", 2.0) * 1000000)
                    }
                    for kw in ad_group_keywords.get("keywords", [])
                ]
            }
        }
        operations.append(operation)
    
    return operations


def build_pause_keywords_operations(recommendation, campaign_id):
    operations = []
    
    for keyword_id in recommendation.get("keywordIds", []):
        operation = {
            "type": "PAUSE_KEYWORD",
            "data": {
                "campaignId": campaign_id,
                "keywordId": keyword_id,
                "reason": recommendation.get("reason", "Low performance")
            }
        }
        operations.append(operation)
    
    return operations


def build_ad_copy_operations(recommendation, campaign_id):
    operations = []
    
    for ad_update in recommendation.get("ads", []):
        operation = {
            "type": "UPDATE_AD",
            "data": {
                "campaignId": campaign_id,
                "adGroupId": ad_update.get("adGroupId"),
                "adId": ad_update.get("adId"),
                "headlines": ad_update.get("headlines", []),
                "descriptions": ad_update.get("descriptions", [])
            }
        }
        operations.append(operation)
    
    return operations


def build_budget_operations(recommendation, campaign_id):
    operations = []
    
    new_budget = recommendation.get("newDailyBudget")
    if new_budget:
        operation = {
            "type": "UPDATE_BUDGET",
            "data": {
                "campaignId": campaign_id,
                "dailyBudgetMicros": int(new_budget * 1000000),
                "reason": recommendation.get("reason", "Performance optimization")
            }
        }
        operations.append(operation)
    
    return operations