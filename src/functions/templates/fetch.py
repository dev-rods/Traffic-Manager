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
    try:
        trace_id = event.get("traceId")
        client_id = event.get("clientId")
        stage = "FETCH_TEMPLATE"
        timestamp = datetime.utcnow().isoformat()
        form_data = event.get("formData", {})
        
        logger.info(f"[traceId: {trace_id}] Buscando template de campanha")
        
        template_id = DEFAULT_TEMPLATE_ID
        if form_data:
            template_id = select_template_by_criteria(form_data)
            logger.info(f"[traceId: {trace_id}] Template selecionado baseado no formulário: {template_id}")
        else:
            template_id = event.get("templateId", DEFAULT_TEMPLATE_ID)
            
        locale = event.get("locale", DEFAULT_LOCALE)
        
        template = None
        template_found = False
        
        # Buscar o template no DynamoDB
        try:
            response = templates_table.get_item(
                Key={
                    "templateId": template_id
                }
            )
            if "Item" in response:
                template = response["Item"]
                template_found = True
                logger.info(f"[traceId: {trace_id}] Template {template_id} encontrado")
            else:
                logger.warning(f"[traceId: {trace_id}] Template {template_id} não encontrado, buscando template padrão")
                response = templates_table.get_item(
                    Key={
                        "templateId": DEFAULT_TEMPLATE_ID
                    }
                )
                
                if "Item" in response:
                    template = response["Item"]
                    template_found = True
                    logger.info(f"[traceId: {trace_id}] Template padrão {DEFAULT_TEMPLATE_ID} encontrado")
        except Exception as e:
            logger.warning(f"[traceId: {trace_id}] Erro ao buscar template: {str(e)}")
        
        if not template_found:
            logger.warning(f"[traceId: {trace_id}] Nenhum template encontrado, criando template padrão em memória")
            template = create_default_template()
            
        template_content = extract_template_content(template, locale)
        
        if form_data:
            template_content = customize_template_with_form_data(template_content, form_data)
        
        logger.info(f"[traceId: {trace_id}] Template utilizado: {template['templateId']}")
        
        execution_record = {
            "traceId": trace_id,
            "stageTm": f"{stage}#{timestamp}",
            "stage": stage,
            "status": "COMPLETED",
            "timestamp": timestamp,
            "payload": json.dumps({
                "templateId": template["templateId"],
                "type": template.get("type", "SEARCH"),
                "version": template.get("version", "1.0")
            })
        }
        
        if "runType" in event:
            execution_record["runType"] = event["runType"]
        if "storeId" in event:
            execution_record["storeId"] = event["storeId"]
        if "clientId" in event:
            execution_record["clientId"] = event["clientId"]
            
        execution_history_table.put_item(Item=execution_record)
        
        response = {
            "traceId": trace_id,
            "timestamp": timestamp,
            "runType": event.get("runType", "FIRST_RUN"),
            "templateData": template_content,
            "templateInfo": {
                "templateId": template["templateId"],
                "type": template.get("type", "SEARCH"),
                "version": template.get("version", "1.0"),
                "locale": locale
            }
        }
        
        if "storeId" in event:
            response["storeId"] = event["storeId"]
        if "clientId" in event:
            response["clientId"] = event["clientId"]
        if "formData" in event:
            response["formData"] = event["formData"]
            
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


def select_template_by_criteria(form_data):
    business_details = form_data.get("businessDetails", {})
    marketing_goals = form_data.get("marketingGoals", {})
    
    category = business_details.get("category", "").upper()
    monthly_budget = marketing_goals.get("monthlyBudget", 0)
    
    template_map = {
        "ECOMMERCE": {
            "low_budget": "ecommerce-search-basic",
            "medium_budget": "ecommerce-search-display", 
            "high_budget": "ecommerce-search-display-shopping"
        },
        "LOCAL_BUSINESS": {
            "low_budget": "local-search-basic",
            "medium_budget": "local-search-display",
            "high_budget": "local-search-display-video"
        },
        "SERVICES": {
            "low_budget": "services-search-basic",
            "medium_budget": "services-search-display",
            "high_budget": "services-search-display-video"
        }
    }
    
    if monthly_budget < 2000:
        budget_tier = "low_budget"
    elif monthly_budget < 5000:
        budget_tier = "medium_budget"
    else:
        budget_tier = "high_budget"
    
    return template_map.get(category, {}).get(budget_tier, DEFAULT_TEMPLATE_ID)


def create_default_template():
    return {
        "templateId": DEFAULT_TEMPLATE_ID,
        "type": "SEARCH",
        "version": "1.0",
        "jsonBody": {
            "name": "Campanha de Busca Padrão",
            "description": "Template padrão para campanhas de busca",
            "adGroups": [
                {
                    "name": "Grupo de Anúncios Padrão",
                    "keywords": [
                        {"text": "produto padrão", "matchType": "BROAD"},
                        {"text": "comprar produto", "matchType": "PHRASE"}
                    ],
                    "ads": [
                        {
                            "headline1": "Produto Incrível",
                            "headline2": "Melhor Qualidade",
                            "description": "Compre agora com descontos especiais!"
                        }
                    ]
                }
            ],
            "budget": {
                "amount": 100.00,
                "currency": "BRL"
            },
            "targeting": {
                "locations": ["BR"],
                "languages": ["pt"]
            }
        }
    }


def extract_template_content(template, locale):
    if "localeVersions" in template and locale in template["localeVersions"]:
        return template["localeVersions"][locale]
    elif "jsonBody" in template:
        return template["jsonBody"]
    else:
        return create_default_template()["jsonBody"]


def customize_template_with_form_data(template_content, form_data):
    client_info = form_data.get("clientInfo", {})
    business_details = form_data.get("businessDetails", {})
    marketing_goals = form_data.get("marketingGoals", {})
    
    customized = template_content.copy()
    
    business_name = client_info.get("businessName", "Sua Empresa")
    customized["name"] = f"{business_name} - Campanha de Busca"
    
    if marketing_goals.get("monthlyBudget"):
        daily_budget = marketing_goals["monthlyBudget"] / 30
        customized["budget"]["amount"] = daily_budget
    
    if business_details.get("productCategories"):
        products = business_details["productCategories"][:3]
        if customized.get("adGroups") and len(customized["adGroups"]) > 0:
            for i, product in enumerate(products):
                if i < len(customized["adGroups"]):
                    customized["adGroups"][i]["name"] = f"Grupo {product.title()}"
                    
                    keywords = [
                        {"text": product, "matchType": "PHRASE"},
                        {"text": f"comprar {product}", "matchType": "PHRASE"},
                        {"text": f"{product} online", "matchType": "BROAD"}
                    ]
                    customized["adGroups"][i]["keywords"] = keywords
    
    if marketing_goals.get("geoTargeting"):
        locations = marketing_goals["geoTargeting"]
        customized["targeting"]["locations"] = locations
    
    return customized 