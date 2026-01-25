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
