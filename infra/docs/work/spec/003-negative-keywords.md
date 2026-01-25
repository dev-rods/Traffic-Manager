# SPEC-003: Negative Keywords Detection and Management

**PRD:** [003-negative-keywords](../prd/003-negative-keywords.md)
**Status:** Ready for Implementation
**Created:** 2026-01-24

---

## Resumo das Mudancas

Esta spec implementa um sistema de deteccao e gerenciamento de palavras-chave negativas com:
1. Novos metodos no GoogleAdsClientService para search terms e negative keywords
2. Endpoint para listar termos de pesquisa com metricas (GET /keywords/search-terms)
3. Endpoint para analise via LLM de termos a negativar (POST /keywords/analyze-negatives)
4. Endpoint para aplicar negative keywords (POST /keywords/apply-negatives)
5. Endpoint para listar negative keywords existentes (GET /keywords/negatives)

---

## Ordem de Implementacao

1. Adicionar metodos no `google_ads_client_service.py` (get_search_terms, get_negative_keywords, add_negative_keywords)
2. Criar `src/functions/keywords/__init__.py`
3. Criar `src/functions/keywords/list_search_terms.py`
4. Criar `src/functions/keywords/list_negatives.py`
5. Criar `src/functions/keywords/analyze_negatives.py`
6. Criar `src/functions/keywords/apply_negatives.py`
7. Criar `sls/functions/keywords/interface.yml`
8. Atualizar `serverless.yml`

---

## Arquivos a Criar

### 1. `src/functions/keywords/__init__.py`

```python
# Keywords module - Negative keywords detection and management
```

### 2. `src/functions/keywords/list_search_terms.py`

```python
"""
Lambda handler para listar termos de pesquisa com metricas.

Endpoint: GET /keywords/search-terms
Query Params:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios
    - minImpressions (optional): Minimo de impressoes (default: 10)
    - days (optional): Periodo em dias (default: 30)
    - limit (optional): Limite de resultados (default: 500)
"""
import json
import logging
import os
import uuid
from datetime import datetime

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response, extract_query_param

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda handler para listar termos de pesquisa.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    logger.info(f"[traceId: {trace_id}] Iniciando ListSearchTerms")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    campaign_id = extract_query_param(event, "campaignId")
    ad_group_id = extract_query_param(event, "adGroupId")
    min_impressions_str = extract_query_param(event, "minImpressions")
    days_str = extract_query_param(event, "days")
    limit_str = extract_query_param(event, "limit")

    # Validar campos obrigatorios
    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio"
        })

    if not campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "campaignId e obrigatorio"
        })

    # Parse parametros opcionais
    try:
        min_impressions = int(min_impressions_str) if min_impressions_str else 10
        days = int(days_str) if days_str else 30
        limit = min(int(limit_str), 500) if limit_str else 500
    except ValueError:
        min_impressions, days, limit = 10, 30, 500

    try:
        # Buscar termos de pesquisa
        google_ads_service = GoogleAdsClientService()
        search_terms = google_ads_service.get_search_terms(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            days=days,
            min_impressions=min_impressions,
            limit=limit
        )

        logger.info(f"[traceId: {trace_id}] Encontrados {len(search_terms)} termos de pesquisa")

        return http_response(200, {
            "status": "SUCCESS",
            "searchTerms": search_terms,
            "count": len(search_terms),
            "filters": {
                "clientId": client_id,
                "campaignId": campaign_id,
                "adGroupId": ad_group_id,
                "minImpressions": min_impressions,
                "days": days
            }
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao listar search terms: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar termos de pesquisa: {str(e)}"
        })
```

### 3. `src/functions/keywords/list_negatives.py`

```python
"""
Lambda handler para listar negative keywords existentes.

Endpoint: GET /keywords/negatives
Query Params:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios
"""
import json
import logging
import os
import uuid

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response, extract_query_param

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    Lambda handler para listar negative keywords.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    logger.info(f"[traceId: {trace_id}] Iniciando ListNegativeKeywords")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    # Extrair parametros
    client_id = extract_query_param(event, "clientId")
    campaign_id = extract_query_param(event, "campaignId")
    ad_group_id = extract_query_param(event, "adGroupId")

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio"
        })

    if not campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "campaignId e obrigatorio"
        })

    try:
        google_ads_service = GoogleAdsClientService()
        negative_keywords = google_ads_service.get_negative_keywords(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id
        )

        logger.info(f"[traceId: {trace_id}] Encontradas {len(negative_keywords)} negative keywords")

        return http_response(200, {
            "status": "SUCCESS",
            "negativeKeywords": negative_keywords,
            "count": len(negative_keywords),
            "filters": {
                "clientId": client_id,
                "campaignId": campaign_id,
                "adGroupId": ad_group_id
            }
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao listar negative keywords: {str(e)}", exc_info=True)
        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao listar negative keywords: {str(e)}"
        })
```

### 4. `src/functions/keywords/analyze_negatives.py`

```python
"""
Lambda handler para analisar e sugerir negative keywords via LLM.

Endpoint: POST /keywords/analyze-negatives
Body:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios
    - context (optional): Contexto adicional para analise
        - businessType: Tipo do negocio
        - targetLocation: Regiao alvo dos anuncios
        - excludePatterns: Padroes a sempre excluir
"""
import json
import logging
import os
import uuid
from datetime import datetime

import boto3

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response
from src.utils.openai_utils import call_openai_api

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))

OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4.1')

# System message para analise de negative keywords
NEGATIVE_KEYWORDS_SYSTEM_MESSAGE = """Voce e um especialista em Google Ads focado em otimizacao de palavras-chave negativas.
Sua tarefa e analisar termos de pesquisa e identificar aqueles que devem ser negativados.

Criterios para negativar um termo:
1. Termos que indicam busca por servicos GRATUITOS: "gratis", "gratuito", "free", "de graca", "sem custo"
2. Termos com MUITAS impressoes mas ZERO ou poucas conversoes (indicam mismatch de intencao de busca)
3. Termos de OUTRAS REGIOES quando o anuncio e focado em uma regiao especifica
4. Termos que indicam PESQUISA/ESTUDO e nao intencao de compra: "como funciona", "o que e", "significado"
5. Termos de CONCORRENTES especificos (a menos que seja estrategia do cliente)
6. Termos com CTR muito baixo (< 1%) e muitas impressoes indicam irrelevancia

Para cada termo sugerido para negativacao:
- Explique o motivo da negativacao
- Sugira o match type apropriado (BROAD, PHRASE ou EXACT)
- Atribua uma prioridade (HIGH, MEDIUM, LOW) baseada no gasto desperdicado

Priorize termos com maior gasto sem retorno (custo alto sem conversoes).

Responda SEMPRE em formato JSON valido."""


def _build_analysis_prompt(search_terms, current_keywords, existing_negatives, context):
    """Constroi o prompt para analise de negative keywords."""

    # Resumo dos termos de pesquisa
    terms_summary = []
    total_cost = 0
    total_impressions = 0

    for term in search_terms[:100]:  # Limitar a 100 termos para o prompt
        terms_summary.append({
            "termo": term.get("search_term"),
            "impressoes": term.get("impressions", 0),
            "cliques": term.get("clicks", 0),
            "conversoes": term.get("conversions", 0),
            "custo": round(term.get("cost", 0), 2),
            "ctr": round(term.get("ctr", 0), 2),
            "cpc": round(term.get("cpc", 0), 2)
        })
        total_cost += term.get("cost", 0)
        total_impressions += term.get("impressions", 0)

    # Construir contexto do negocio
    business_context = ""
    if context:
        if context.get("businessType"):
            business_context += f"\nTipo de negocio: {context['businessType']}"
        if context.get("targetLocation"):
            business_context += f"\nRegiao alvo dos anuncios: {context['targetLocation']}"
        if context.get("excludePatterns"):
            business_context += f"\nPadroes que SEMPRE devem ser negativados: {', '.join(context['excludePatterns'])}"

    prompt = f"""Analise os termos de pesquisa abaixo e identifique quais devem ser adicionados como palavras-chave negativas.

## Contexto do Cliente{business_context}

## Palavras-chave atuais da campanha:
{json.dumps([kw.get('text') for kw in current_keywords[:50]], ensure_ascii=False)}

## Negative keywords ja existentes:
{json.dumps([nk.get('text') for nk in existing_negatives], ensure_ascii=False)}

## Termos de pesquisa dos ultimos 30 dias (ordenados por impressoes):
```json
{json.dumps(terms_summary, ensure_ascii=False, indent=2)}
```

## Metricas gerais:
- Total de termos analisados: {len(search_terms)}
- Custo total: R$ {round(total_cost, 2)}
- Impressoes totais: {total_impressions}

## Sua tarefa:
1. Identifique termos que devem ser negativados (que ainda NAO estao na lista de negatives existentes)
2. Para cada termo, explique o motivo e sugira o match type
3. Calcule o gasto desperdicado estimado

Responda no seguinte formato JSON:
{{
    "analysis": {{
        "totalSearchTerms": <numero>,
        "potentialNegatives": <numero de termos sugeridos>,
        "estimatedWastedSpend": <valor em reais>
    }},
    "suggestions": [
        {{
            "term": "<termo de pesquisa>",
            "reason": "<motivo para negativar>",
            "metrics": {{
                "impressions": <numero>,
                "clicks": <numero>,
                "conversions": <numero>,
                "cost": <valor>
            }},
            "priority": "HIGH|MEDIUM|LOW",
            "matchType": "BROAD|PHRASE|EXACT"
        }}
    ],
    "recommendedActions": [
        "<acao recomendada 1>",
        "<acao recomendada 2>"
    ]
}}"""

    return prompt


def handler(event, context):
    """
    Lambda handler para analisar negative keywords via LLM.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()
    stage = 'ANALYZE_NEGATIVE_KEYWORDS'

    logger.info(f"[traceId: {trace_id}] Iniciando AnalyzeNegativeKeywords")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    if not body:
        return http_response(400, {
            "status": "ERROR",
            "message": "Request body e obrigatorio"
        })

    # Extrair parametros do body
    client_id = body.get("clientId")
    campaign_id = body.get("campaignId")
    ad_group_id = body.get("adGroupId")
    analysis_context = body.get("context", {})

    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio"
        })

    if not campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "campaignId e obrigatorio"
        })

    try:
        google_ads_service = GoogleAdsClientService()

        # 1. Buscar termos de pesquisa dos ultimos 30 dias
        logger.info(f"[traceId: {trace_id}] Buscando search terms...")
        search_terms = google_ads_service.get_search_terms(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            days=30,
            min_impressions=5,
            limit=500
        )

        if not search_terms:
            return http_response(200, {
                "status": "SUCCESS",
                "message": "Nenhum termo de pesquisa encontrado para analise",
                "analysis": {
                    "totalSearchTerms": 0,
                    "potentialNegatives": 0,
                    "estimatedWastedSpend": 0
                },
                "suggestions": [],
                "existingNegatives": [],
                "recommendedActions": []
            })

        # 2. Buscar keywords atuais
        logger.info(f"[traceId: {trace_id}] Buscando keywords atuais...")
        current_keywords = google_ads_service.get_keywords(
            client_id=client_id,
            ad_group_id=ad_group_id,
            limit=100
        )

        # 3. Buscar negative keywords existentes
        logger.info(f"[traceId: {trace_id}] Buscando negative keywords existentes...")
        existing_negatives = google_ads_service.get_negative_keywords(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id
        )

        # 4. Montar prompt e chamar LLM
        logger.info(f"[traceId: {trace_id}] Chamando LLM para analise...")
        prompt = _build_analysis_prompt(
            search_terms=search_terms,
            current_keywords=current_keywords,
            existing_negatives=existing_negatives,
            context=analysis_context
        )

        openai_response = call_openai_api(
            prompt=prompt,
            system_message=NEGATIVE_KEYWORDS_SYSTEM_MESSAGE,
            model=OPENAI_MODEL,
            temperature=0.3,  # Baixa temperatura para respostas mais consistentes
            max_tokens=2000
        )

        if 'choices' not in openai_response or not openai_response['choices']:
            raise Exception("Resposta invalida da OpenAI")

        assistant_response = openai_response['choices'][0]['message']['content']

        # 5. Parse da resposta JSON
        try:
            # Remover possivel markdown code block
            json_str = assistant_response
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            llm_result = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"[traceId: {trace_id}] Erro ao fazer parse do JSON: {e}")
            llm_result = {
                "analysis": {"totalSearchTerms": len(search_terms), "potentialNegatives": 0, "estimatedWastedSpend": 0},
                "suggestions": [],
                "recommendedActions": ["Erro ao processar resposta do LLM - resposta raw disponivel"],
                "rawResponse": assistant_response
            }

        # 6. Registrar no ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'clientId': client_id,
            'campaignId': campaign_id,
            'payload': json.dumps({
                'searchTermsCount': len(search_terms),
                'suggestionsCount': len(llm_result.get('suggestions', [])),
                'model': OPENAI_MODEL
            })
        }
        execution_history_table.put_item(Item=execution_record)

        logger.info(f"[traceId: {trace_id}] Analise concluida - {len(llm_result.get('suggestions', []))} sugestoes")

        return http_response(200, {
            "status": "SUCCESS",
            "traceId": trace_id,
            "analysis": llm_result.get("analysis", {}),
            "suggestions": llm_result.get("suggestions", []),
            "existingNegatives": [nk.get("text") for nk in existing_negatives],
            "recommendedActions": llm_result.get("recommendedActions", [])
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro na analise de negative keywords: {str(e)}", exc_info=True)

        # Registrar erro
        try:
            error_record = {
                'traceId': trace_id,
                'stageTm': f"{stage}#{timestamp}",
                'stage': stage,
                'status': 'ERROR',
                'timestamp': timestamp,
                'clientId': client_id,
                'campaignId': campaign_id,
                'errorMsg': str(e)
            }
            execution_history_table.put_item(Item=error_record)
        except Exception:
            pass

        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro na analise: {str(e)}"
        })
```

### 5. `src/functions/keywords/apply_negatives.py`

```python
"""
Lambda handler para aplicar negative keywords no Google Ads.

Endpoint: POST /keywords/apply-negatives
Body:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios (se omitido, aplica a nivel de campanha)
    - negativeKeywords (required): Lista de keywords a negativar
        - text: Texto da keyword
        - matchType: BROAD, PHRASE ou EXACT (default: BROAD)
"""
import json
import logging
import os
import uuid
from datetime import datetime

import boto3

from src.services.google_ads_client_service import GoogleAdsClientService
from src.utils.http import require_api_key, parse_body, http_response

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')
execution_history_table = dynamodb.Table(os.environ.get('EXECUTION_HISTORY_TABLE'))


def _validate_negative_keywords(keywords):
    """Valida a lista de negative keywords."""
    if not keywords or not isinstance(keywords, list):
        return False, "negativeKeywords deve ser uma lista nao vazia"

    for i, kw in enumerate(keywords):
        if not isinstance(kw, dict):
            return False, f"Item {i} deve ser um objeto"
        if not kw.get("text"):
            return False, f"Item {i} deve ter o campo 'text'"

        match_type = kw.get("matchType", "BROAD").upper()
        if match_type not in ["BROAD", "PHRASE", "EXACT"]:
            return False, f"Item {i} tem matchType invalido: {match_type}"

    return True, ""


def handler(event, context):
    """
    Lambda handler para aplicar negative keywords.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()
    stage = 'APPLY_NEGATIVE_KEYWORDS'

    logger.info(f"[traceId: {trace_id}] Iniciando ApplyNegativeKeywords")

    # Validar API key
    body = parse_body(event)
    _, error_response = require_api_key(event, body)
    if error_response:
        return error_response

    if not body:
        return http_response(400, {
            "status": "ERROR",
            "message": "Request body e obrigatorio"
        })

    # Extrair parametros
    client_id = body.get("clientId")
    campaign_id = body.get("campaignId")
    ad_group_id = body.get("adGroupId")
    negative_keywords = body.get("negativeKeywords", [])

    # Validacoes
    if not client_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "clientId e obrigatorio"
        })

    if not campaign_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "campaignId e obrigatorio"
        })

    is_valid, error_msg = _validate_negative_keywords(negative_keywords)
    if not is_valid:
        return http_response(400, {
            "status": "ERROR",
            "message": error_msg
        })

    try:
        google_ads_service = GoogleAdsClientService()

        # Aplicar negative keywords
        logger.info(f"[traceId: {trace_id}] Aplicando {len(negative_keywords)} negative keywords...")

        result = google_ads_service.add_negative_keywords(
            client_id=client_id,
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            negative_keywords=negative_keywords
        )

        if not result.get("success"):
            return http_response(400, {
                "status": "ERROR",
                "message": result.get("error", "Erro ao aplicar negative keywords")
            })

        # Registrar no ExecutionHistory
        execution_record = {
            'traceId': trace_id,
            'stageTm': f"{stage}#{timestamp}",
            'stage': stage,
            'status': 'COMPLETED',
            'timestamp': timestamp,
            'clientId': client_id,
            'campaignId': campaign_id,
            'payload': json.dumps({
                'keywordsApplied': len(negative_keywords),
                'keywords': [kw.get("text") for kw in negative_keywords],
                'level': 'ad_group' if ad_group_id else 'campaign'
            })
        }
        execution_history_table.put_item(Item=execution_record)

        logger.info(f"[traceId: {trace_id}] {len(negative_keywords)} negative keywords aplicadas com sucesso")

        return http_response(200, {
            "status": "SUCCESS",
            "traceId": trace_id,
            "message": f"{len(negative_keywords)} negative keywords aplicadas com sucesso",
            "applied": result.get("applied", []),
            "level": "ad_group" if ad_group_id else "campaign"
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao aplicar negative keywords: {str(e)}", exc_info=True)

        # Registrar erro
        try:
            error_record = {
                'traceId': trace_id,
                'stageTm': f"{stage}#{timestamp}",
                'stage': stage,
                'status': 'ERROR',
                'timestamp': timestamp,
                'clientId': client_id,
                'campaignId': campaign_id,
                'errorMsg': str(e)
            }
            execution_history_table.put_item(Item=error_record)
        except Exception:
            pass

        return http_response(500, {
            "status": "ERROR",
            "message": f"Erro ao aplicar negative keywords: {str(e)}"
        })
```

### 6. `sls/functions/keywords/interface.yml`

```yaml
ListSearchTerms:
  image:
    name: lambdaimage
    command: ["src.functions.keywords.list_search_terms.handler"]
  memorySize: 1024
  timeout: 60
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ListSearchTerms-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
      Resource: !GetAtt ClientsTable.Arn
    - Effect: Allow
      Action:
        - ssm:GetParameter
      Resource: "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: keywords/search-terms
        method: get
        cors: true

ListNegativeKeywords:
  image:
    name: lambdaimage
    command: ["src.functions.keywords.list_negatives.handler"]
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ListNegativeKeywords-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
      Resource: !GetAtt ClientsTable.Arn
    - Effect: Allow
      Action:
        - ssm:GetParameter
      Resource: "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: keywords/negatives
        method: get
        cors: true

AnalyzeNegativeKeywords:
  image:
    name: lambdaimage
    command: ["src.functions.keywords.analyze_negatives.handler"]
  memorySize: 1024
  timeout: 120
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-AnalyzeNegativeKeywords-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
      Resource: !GetAtt ClientsTable.Arn
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource: !GetAtt ExecutionHistoryTable.Arn
    - Effect: Allow
      Action:
        - ssm:GetParameter
      Resource: "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: keywords/analyze-negatives
        method: post
        cors: true

ApplyNegativeKeywords:
  image:
    name: lambdaimage
    command: ["src.functions.keywords.apply_negatives.handler"]
  memorySize: 1024
  timeout: 60
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ApplyNegativeKeywords-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
      Resource: !GetAtt ClientsTable.Arn
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource: !GetAtt ExecutionHistoryTable.Arn
    - Effect: Allow
      Action:
        - ssm:GetParameter
      Resource: "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: keywords/apply-negatives
        method: post
        cors: true
```

---

## Arquivos a Modificar

### 1. `src/services/google_ads_client_service.py`

**Adicionar** os seguintes metodos apos o metodo `get_keywords()`:

```python
def get_search_terms(
    self,
    client_id: str,
    campaign_id: str,
    ad_group_id: Optional[str] = None,
    days: int = 30,
    min_impressions: int = 10,
    limit: int = 500
) -> List[Dict[str, Any]]:
    """
    Obtem termos de pesquisa com metricas dos ultimos N dias.

    Args:
        client_id: ID do cliente no sistema
        campaign_id: ID da campanha
        ad_group_id: ID do grupo de anuncios (opcional)
        days: Periodo em dias (default: 30)
        min_impressions: Minimo de impressoes para filtrar (default: 10)
        limit: Limite de resultados (default: 500)

    Returns:
        list: Lista de termos de pesquisa com metricas
    """
    try:
        google_ads_client, customer_id = self.get_client_for_customer(client_id)

        if not google_ads_client:
            logger.error(f"Cliente {client_id} nao configurado para Google Ads")
            return []

        ga_service = google_ads_client.get_service("GoogleAdsService")

        # Construir filtro de ad_group se especificado
        ad_group_filter = ""
        if ad_group_id:
            ad_group_filter = f"AND ad_group.id = {ad_group_id}"

        # Query para search terms - usando LAST_30_DAYS ou periodo customizado
        date_range = f"LAST_{days}_DAYS" if days in [7, 14, 30, 90] else "LAST_30_DAYS"

        query = f"""
            SELECT
                search_term_view.search_term,
                search_term_view.status,
                campaign.id,
                campaign.name,
                ad_group.id,
                ad_group.name,
                metrics.impressions,
                metrics.clicks,
                metrics.conversions,
                metrics.cost_micros,
                metrics.ctr,
                metrics.average_cpc
            FROM search_term_view
            WHERE campaign.id = {campaign_id}
                AND segments.date DURING {date_range}
                AND metrics.impressions >= {min_impressions}
                {ad_group_filter}
            ORDER BY metrics.impressions DESC
            LIMIT {limit}
        """

        stream = ga_service.search_stream(customer_id=customer_id, query=query)

        search_terms = []
        for batch in stream:
            for row in batch.results:
                cost = row.metrics.cost_micros / 1000000 if row.metrics.cost_micros else 0
                conversions = row.metrics.conversions if row.metrics.conversions else 0

                term_data = {
                    'search_term': row.search_term_view.search_term,
                    'status': row.search_term_view.status.name,
                    'campaign': {
                        'id': row.campaign.id,
                        'name': row.campaign.name
                    },
                    'ad_group': {
                        'id': row.ad_group.id,
                        'name': row.ad_group.name
                    },
                    'impressions': row.metrics.impressions,
                    'clicks': row.metrics.clicks,
                    'conversions': conversions,
                    'cost': cost,
                    'ctr': round(row.metrics.ctr * 100, 2) if row.metrics.ctr else 0,
                    'cpc': row.metrics.average_cpc / 1000000 if row.metrics.average_cpc else 0,
                    'cpa': round(cost / conversions, 2) if conversions > 0 else None
                }
                search_terms.append(term_data)

        logger.info(f"Encontrados {len(search_terms)} termos de pesquisa para cliente {client_id}")
        return search_terms

    except GoogleAdsException as ex:
        logger.error(f"Erro da API do Google Ads ao buscar search terms: {ex.error.code().name}")
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar search terms para cliente {client_id}: {str(e)}")
        return []

def get_negative_keywords(
    self,
    client_id: str,
    campaign_id: str,
    ad_group_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Obtem negative keywords existentes de uma campanha ou ad group.

    Args:
        client_id: ID do cliente no sistema
        campaign_id: ID da campanha
        ad_group_id: ID do grupo de anuncios (opcional)

    Returns:
        list: Lista de negative keywords
    """
    try:
        google_ads_client, customer_id = self.get_client_for_customer(client_id)

        if not google_ads_client:
            logger.error(f"Cliente {client_id} nao configurado para Google Ads")
            return []

        ga_service = google_ads_client.get_service("GoogleAdsService")

        negative_keywords = []

        # 1. Buscar negative keywords a nivel de campanha
        campaign_query = f"""
            SELECT
                campaign_criterion.criterion_id,
                campaign_criterion.keyword.text,
                campaign_criterion.keyword.match_type,
                campaign_criterion.negative,
                campaign.id,
                campaign.name
            FROM campaign_criterion
            WHERE campaign.id = {campaign_id}
                AND campaign_criterion.type = 'KEYWORD'
                AND campaign_criterion.negative = TRUE
        """

        stream = ga_service.search_stream(customer_id=customer_id, query=campaign_query)

        for batch in stream:
            for row in batch.results:
                negative_keywords.append({
                    'id': row.campaign_criterion.criterion_id,
                    'text': row.campaign_criterion.keyword.text,
                    'match_type': row.campaign_criterion.keyword.match_type.name,
                    'level': 'campaign',
                    'campaign': {
                        'id': row.campaign.id,
                        'name': row.campaign.name
                    }
                })

        # 2. Buscar negative keywords a nivel de ad group (se especificado)
        if ad_group_id:
            ad_group_query = f"""
                SELECT
                    ad_group_criterion.criterion_id,
                    ad_group_criterion.keyword.text,
                    ad_group_criterion.keyword.match_type,
                    ad_group_criterion.negative,
                    ad_group.id,
                    ad_group.name,
                    campaign.id,
                    campaign.name
                FROM ad_group_criterion
                WHERE ad_group.id = {ad_group_id}
                    AND ad_group_criterion.type = 'KEYWORD'
                    AND ad_group_criterion.negative = TRUE
            """

            stream = ga_service.search_stream(customer_id=customer_id, query=ad_group_query)

            for batch in stream:
                for row in batch.results:
                    negative_keywords.append({
                        'id': row.ad_group_criterion.criterion_id,
                        'text': row.ad_group_criterion.keyword.text,
                        'match_type': row.ad_group_criterion.keyword.match_type.name,
                        'level': 'ad_group',
                        'ad_group': {
                            'id': row.ad_group.id,
                            'name': row.ad_group.name
                        },
                        'campaign': {
                            'id': row.campaign.id,
                            'name': row.campaign.name
                        }
                    })

        logger.info(f"Encontradas {len(negative_keywords)} negative keywords para cliente {client_id}")
        return negative_keywords

    except GoogleAdsException as ex:
        logger.error(f"Erro da API do Google Ads ao buscar negative keywords: {ex.error.code().name}")
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar negative keywords para cliente {client_id}: {str(e)}")
        return []

def add_negative_keywords(
    self,
    client_id: str,
    campaign_id: str,
    negative_keywords: List[Dict[str, str]],
    ad_group_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Adiciona negative keywords a uma campanha ou ad group.

    Args:
        client_id: ID do cliente no sistema
        campaign_id: ID da campanha
        negative_keywords: Lista de keywords [{text: str, matchType: BROAD|PHRASE|EXACT}]
        ad_group_id: ID do grupo de anuncios (opcional, se omitido aplica a nivel de campanha)

    Returns:
        dict: Resultado da operacao
            - success (bool)
            - applied (list): Keywords aplicadas com sucesso
            - errors (list): Erros por keyword
    """
    try:
        google_ads_client, customer_id = self.get_client_for_customer(client_id)

        if not google_ads_client:
            return {
                'success': False,
                'error': f'Cliente {client_id} nao configurado para Google Ads'
            }

        applied = []
        errors = []

        # Mapear match types
        match_type_enum = google_ads_client.enums.KeywordMatchTypeEnum
        match_type_map = {
            'BROAD': match_type_enum.BROAD,
            'PHRASE': match_type_enum.PHRASE,
            'EXACT': match_type_enum.EXACT
        }

        if ad_group_id:
            # Aplicar a nivel de ad group
            ad_group_criterion_service = google_ads_client.get_service("AdGroupCriterionService")
            operations = []

            for kw in negative_keywords:
                try:
                    operation = google_ads_client.get_type("AdGroupCriterionOperation")
                    criterion = operation.create

                    criterion.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
                    criterion.negative = True
                    criterion.keyword.text = kw.get("text")
                    criterion.keyword.match_type = match_type_map.get(
                        kw.get("matchType", "BROAD").upper(),
                        match_type_enum.BROAD
                    )

                    operations.append(operation)
                except Exception as e:
                    errors.append({
                        'keyword': kw.get("text"),
                        'error': str(e)
                    })

            if operations:
                response = ad_group_criterion_service.mutate_ad_group_criteria(
                    customer_id=customer_id,
                    operations=operations
                )

                for result in response.results:
                    applied.append(result.resource_name)
        else:
            # Aplicar a nivel de campanha
            campaign_criterion_service = google_ads_client.get_service("CampaignCriterionService")
            operations = []

            for kw in negative_keywords:
                try:
                    operation = google_ads_client.get_type("CampaignCriterionOperation")
                    criterion = operation.create

                    criterion.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
                    criterion.negative = True
                    criterion.keyword.text = kw.get("text")
                    criterion.keyword.match_type = match_type_map.get(
                        kw.get("matchType", "BROAD").upper(),
                        match_type_enum.BROAD
                    )

                    operations.append(operation)
                except Exception as e:
                    errors.append({
                        'keyword': kw.get("text"),
                        'error': str(e)
                    })

            if operations:
                response = campaign_criterion_service.mutate_campaign_criteria(
                    customer_id=customer_id,
                    operations=operations
                )

                for result in response.results:
                    applied.append(result.resource_name)

        logger.info(
            f"Negative keywords aplicadas para cliente {client_id}: "
            f"{len(applied)} sucesso, {len(errors)} erros"
        )

        return {
            'success': len(errors) == 0,
            'applied': applied,
            'errors': errors if errors else None
        }

    except GoogleAdsException as ex:
        error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
        if ex.error.message:
            error_msg += f" - {ex.error.message}"

        logger.error(f"Erro ao adicionar negative keywords para cliente {client_id}: {error_msg}")

        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        logger.error(f"Erro ao adicionar negative keywords para cliente {client_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
```

### 2. `serverless.yml`

**Adicionar** na secao `functions`:
```yaml
- ${file(sls/functions/keywords/interface.yml)}
```

---

## Endpoints Resultantes

| Metodo | Path | Descricao |
|--------|------|-----------|
| GET | /keywords/search-terms | Lista termos de pesquisa com metricas |
| GET | /keywords/negatives | Lista negative keywords existentes |
| POST | /keywords/analyze-negatives | Analisa e sugere negative keywords via LLM |
| POST | /keywords/apply-negatives | Aplica negative keywords no Google Ads |

---

## Exemplos de Uso

### Listar Search Terms (GET /keywords/search-terms)

```bash
source .env

curl -X GET "https://api.example.com/keywords/search-terms?clientId=meu-cliente&campaignId=123456789&minImpressions=50&days=30" \
  -H "x-api-key: $API_KEY"
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "searchTerms": [
    {
      "search_term": "advogado trabalhista",
      "status": "NONE",
      "impressions": 1500,
      "clicks": 45,
      "conversions": 3,
      "cost": 89.50,
      "ctr": 3.0,
      "cpc": 1.99,
      "cpa": 29.83
    },
    {
      "search_term": "advogado gratuito",
      "status": "NONE",
      "impressions": 800,
      "clicks": 12,
      "conversions": 0,
      "cost": 24.00,
      "ctr": 1.5,
      "cpc": 2.00,
      "cpa": null
    }
  ],
  "count": 2,
  "filters": {
    "clientId": "meu-cliente",
    "campaignId": "123456789",
    "minImpressions": 50,
    "days": 30
  }
}
```

### Analisar Negative Keywords (POST /keywords/analyze-negatives)

```bash
source .env

curl -X POST "https://api.example.com/keywords/analyze-negatives" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "meu-cliente",
    "campaignId": "123456789",
    "context": {
      "businessType": "Escritorio de advocacia trabalhista",
      "targetLocation": "Sao Paulo, SP",
      "excludePatterns": ["gratis", "gratuito", "free"]
    }
  }'
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "traceId": "abc123",
  "analysis": {
    "totalSearchTerms": 150,
    "potentialNegatives": 8,
    "estimatedWastedSpend": 156.50
  },
  "suggestions": [
    {
      "term": "advogado gratuito",
      "reason": "Indica busca por servico gratuito - escritorio cobra honorarios",
      "metrics": {
        "impressions": 800,
        "clicks": 12,
        "conversions": 0,
        "cost": 24.00
      },
      "priority": "HIGH",
      "matchType": "BROAD"
    },
    {
      "term": "advogado rio de janeiro",
      "reason": "Termo de outra regiao - escritorio atende apenas em SP",
      "metrics": {
        "impressions": 450,
        "clicks": 8,
        "conversions": 0,
        "cost": 16.00
      },
      "priority": "HIGH",
      "matchType": "PHRASE"
    }
  ],
  "existingNegatives": ["gratis", "de graca"],
  "recommendedActions": [
    "Adicionar 'gratuito' como BROAD match negative",
    "Adicionar termos de outras cidades como PHRASE match negative",
    "Revisar termos com CTR < 1% para possivel negativacao"
  ]
}
```

### Aplicar Negative Keywords (POST /keywords/apply-negatives)

```bash
source .env

curl -X POST "https://api.example.com/keywords/apply-negatives" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "meu-cliente",
    "campaignId": "123456789",
    "negativeKeywords": [
      {"text": "gratuito", "matchType": "BROAD"},
      {"text": "advogado rio de janeiro", "matchType": "PHRASE"}
    ]
  }'
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "traceId": "def456",
  "message": "2 negative keywords aplicadas com sucesso",
  "applied": [
    "customers/1234567890/campaignCriteria/123~456",
    "customers/1234567890/campaignCriteria/123~457"
  ],
  "level": "campaign"
}
```

---

## Checklist de Implementacao

- [ ] Adicionar metodo `get_search_terms()` em `google_ads_client_service.py`
- [ ] Adicionar metodo `get_negative_keywords()` em `google_ads_client_service.py`
- [ ] Adicionar metodo `add_negative_keywords()` em `google_ads_client_service.py`
- [ ] Criar diretorio `src/functions/keywords/`
- [ ] Criar `src/functions/keywords/__init__.py`
- [ ] Criar `src/functions/keywords/list_search_terms.py`
- [ ] Criar `src/functions/keywords/list_negatives.py`
- [ ] Criar `src/functions/keywords/analyze_negatives.py`
- [ ] Criar `src/functions/keywords/apply_negatives.py`
- [ ] Criar diretorio `sls/functions/keywords/`
- [ ] Criar `sls/functions/keywords/interface.yml`
- [ ] Atualizar `serverless.yml` (functions)
- [ ] Deploy e teste dos endpoints
- [ ] Criar documentacao em `tests/integration/`
- [ ] Criar Postman requests em `tests/postman/`

---

## Convencoes Respeitadas

- **Logging:** `[traceId: {trace_id}]` em todas as mensagens de log
- **Naming:** Lambda functions em PascalCase, handlers como module paths
- **Secrets:** API keys via SSM, credenciais Google Ads encriptadas no DynamoDB
- **Response:** Formato padrao com `status`, `message`, dados relevantes
- **Error handling:** Try/catch com logging detalhado e registro no ExecutionHistory
