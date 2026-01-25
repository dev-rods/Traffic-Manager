"""
Lambda handler para analisar e sugerir keywords para expansao via LLM.

Endpoint: POST /keywords/analyze-expansion
Body:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (optional): ID do grupo de anuncios
    - context (optional): Contexto adicional para analise
        - businessType: Tipo do negocio
        - targetLocation: Regiao alvo dos anuncios
        - minCtr: CTR minimo para considerar (default: 2.0)
        - minConversions: Conversoes minimas (default: 1)
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

# Regras de selecao de keywords
SELECTION_RULES = {
    'min_monthly_searches': 100,
    'max_competition_index': 80,
}

# System message para analise de expansao de keywords
KEYWORD_EXPANSION_SYSTEM_MESSAGE = """Voce e um especialista em Google Ads focado em expansao de palavras-chave.
Sua tarefa e analisar termos de pesquisa com bom desempenho e sugerir NOVAS keywords diferentes das existentes.

## Tipos de Correspondencia (Match Types) - IMPORTANTE

1. **EXACT**: O anuncio aparece apenas para buscas exatas ou variantes muito proximas.
   - Use quando: o termo ja converte bem e queremos controle total
   - Exemplo: [advogado trabalhista] aparece para "advogado trabalhista" e "advogados trabalhistas"

2. **PHRASE**: O anuncio aparece quando a busca CONTEM a frase na ordem correta.
   - Use quando: queremos capturar variantes com palavras adicionais antes/depois
   - Exemplo: "advogado trabalhista" aparece para "melhor advogado trabalhista sp"

3. **BROAD**: O anuncio aparece para buscas relacionadas, mesmo sem as palavras exatas.
   - Use quando: queremos descobrir novos termos (mais arriscado, mais alcance)
   - Exemplo: advogado trabalhista pode aparecer para "direitos do trabalhador"

## Criterios para Sugerir Keywords

1. Termos com CTR acima de 2% - indica relevancia
2. Termos com pelo menos 1 conversao - prova que funciona
3. NAO sugerir termos que ja sao keywords existentes
4. Preferir termos com potencial de variantes (2-4 palavras ideal)
5. Termos relevantes para o negocio do cliente

## Output

Para cada termo sugerido:
- Explique o MOTIVO da sugestao
- Sugira o MATCH TYPE apropriado com justificativa
- Atribua PRIORIDADE (HIGH, MEDIUM, LOW) baseada no potencial

Priorize termos com maior volume de conversoes e CTR.

Responda SEMPRE em formato JSON valido."""


def _filter_high_performing_terms(search_terms, min_ctr=2.0, min_conversions=1):
    """Filtra termos de pesquisa com bom desempenho."""
    high_performing = []
    for term in search_terms:
        ctr = term.get('ctr', 0)
        conversions = term.get('conversions', 0)

        # Filtrar por CTR alto OU conversoes
        if ctr >= min_ctr or conversions >= min_conversions:
            high_performing.append(term)

    # Ordenar por conversoes (desc), depois CTR (desc)
    high_performing.sort(key=lambda x: (x.get('conversions', 0), x.get('ctr', 0)), reverse=True)

    return high_performing


def _build_expansion_prompt(search_terms, current_keywords, context):
    """Constroi o prompt para analise de expansao de keywords."""

    # Resumo dos termos de pesquisa com bom desempenho
    terms_summary = []
    for term in search_terms[:50]:  # Limitar a 50 termos
        terms_summary.append({
            "termo": term.get("search_term"),
            "impressoes": term.get("impressions", 0),
            "cliques": term.get("clicks", 0),
            "conversoes": term.get("conversions", 0),
            "ctr": round(term.get("ctr", 0), 2),
            "custo": round(term.get("cost", 0), 2)
        })

    # Contexto do negocio
    business_context = ""
    if context:
        if context.get("businessType"):
            business_context += f"\nTipo de negocio: {context['businessType']}"
        if context.get("targetLocation"):
            business_context += f"\nRegiao alvo: {context['targetLocation']}"

    # Keywords existentes (apenas texto)
    existing_kw_texts = [kw.get('text', '').lower() for kw in current_keywords]

    prompt = f"""Analise os termos de pesquisa abaixo e identifique quais devem ser adicionados como NOVAS keywords.

## Contexto do Cliente{business_context}

## Keywords EXISTENTES (NAO sugerir estas):
{json.dumps(existing_kw_texts, ensure_ascii=False)}

## Termos de pesquisa com BOM DESEMPENHO (ordenados por conversoes/CTR):
```json
{json.dumps(terms_summary, ensure_ascii=False, indent=2)}
```

## Sua tarefa:
1. Identifique termos que devem virar keywords (que NAO estao na lista de existentes)
2. Para cada termo, explique o motivo e sugira o match type (EXACT, PHRASE ou BROAD)
3. Atribua prioridade baseada no potencial de conversao

Responda no seguinte formato JSON:
{{
    "analysis": {{
        "totalTermsAnalyzed": <numero>,
        "highPerformingTerms": <numero de termos com bom desempenho>,
        "suggestedKeywords": <numero de keywords sugeridas>
    }},
    "suggestions": [
        {{
            "term": "<termo de pesquisa>",
            "reason": "<motivo para adicionar como keyword>",
            "suggestedMatchType": "EXACT|PHRASE|BROAD",
            "matchTypeReason": "<por que este match type>",
            "priority": "HIGH|MEDIUM|LOW"
        }}
    ],
    "recommendedActions": [
        "<acao recomendada 1>",
        "<acao recomendada 2>"
    ]
}}"""

    return prompt


def _apply_selection_rules(suggestions, historical_metrics):
    """Aplica regras de negocio para filtrar sugestoes baseado em metricas historicas."""

    # Criar mapa de metricas por keyword
    metrics_map = {m['keyword'].lower(): m for m in historical_metrics}

    filtered_suggestions = []
    for suggestion in suggestions:
        term = suggestion.get('term', '').lower()
        metrics = metrics_map.get(term, {})

        # Aplicar filtros
        avg_searches = metrics.get('avg_monthly_searches', 0)
        competition_index = metrics.get('competition_index', 100)

        # Verificar regras minimas
        if avg_searches < SELECTION_RULES['min_monthly_searches']:
            suggestion['filtered'] = True
            suggestion['filterReason'] = f"Volume de buscas muito baixo ({avg_searches}/mes)"
            continue

        if competition_index > SELECTION_RULES['max_competition_index']:
            suggestion['filtered'] = True
            suggestion['filterReason'] = f"Concorrencia muito alta ({competition_index}/100)"
            continue

        # Adicionar metricas historicas a sugestao
        suggestion['historicalMetrics'] = {
            'avgMonthlySearches': avg_searches,
            'competition': metrics.get('competition', 'UNKNOWN'),
            'competitionIndex': competition_index,
            'lowTopOfPageBid': metrics.get('low_top_of_page_bid', 0),
            'highTopOfPageBid': metrics.get('high_top_of_page_bid', 0)
        }
        suggestion['filtered'] = False
        filtered_suggestions.append(suggestion)

    # Ordenar por prioridade e volume de buscas
    priority_order = {'HIGH': 0, 'MEDIUM': 1, 'LOW': 2}
    filtered_suggestions.sort(key=lambda x: (
        priority_order.get(x.get('priority', 'LOW'), 2),
        -x.get('historicalMetrics', {}).get('avgMonthlySearches', 0)
    ))

    return filtered_suggestions


def handler(event, context):
    """
    Lambda handler para analisar keywords para expansao via LLM.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()
    stage = 'ANALYZE_KEYWORD_EXPANSION'

    logger.info(f"[traceId: {trace_id}] Iniciando AnalyzeKeywordExpansion")

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

    # Parametros de filtro
    min_ctr = analysis_context.get("minCtr", 2.0)
    min_conversions = analysis_context.get("minConversions", 1)

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
            min_impressions=10,
            limit=500
        )

        if not search_terms:
            return http_response(200, {
                "status": "SUCCESS",
                "message": "Nenhum termo de pesquisa encontrado para analise",
                "analysis": {
                    "totalSearchTerms": 0,
                    "highPerformingTerms": 0,
                    "suggestedKeywords": 0
                },
                "suggestions": [],
                "existingKeywords": [],
                "recommendedActions": []
            })

        # 2. Filtrar termos com bom desempenho
        high_performing = _filter_high_performing_terms(search_terms, min_ctr, min_conversions)
        logger.info(f"[traceId: {trace_id}] {len(high_performing)} termos com bom desempenho")

        if not high_performing:
            return http_response(200, {
                "status": "SUCCESS",
                "message": "Nenhum termo com desempenho suficiente para expansao",
                "analysis": {
                    "totalSearchTerms": len(search_terms),
                    "highPerformingTerms": 0,
                    "suggestedKeywords": 0
                },
                "suggestions": [],
                "existingKeywords": [],
                "recommendedActions": [
                    f"Nenhum termo com CTR >= {min_ctr}% ou conversoes >= {min_conversions}",
                    "Considere reduzir os criterios de filtro"
                ]
            })

        # 3. Buscar keywords atuais
        logger.info(f"[traceId: {trace_id}] Buscando keywords atuais...")
        current_keywords = google_ads_service.get_keywords(
            client_id=client_id,
            ad_group_id=ad_group_id,
            limit=200
        )

        # 4. Chamar LLM para analise
        logger.info(f"[traceId: {trace_id}] Chamando LLM para analise...")
        prompt = _build_expansion_prompt(
            search_terms=high_performing,
            current_keywords=current_keywords,
            context=analysis_context
        )

        openai_response = call_openai_api(
            prompt=prompt,
            system_message=KEYWORD_EXPANSION_SYSTEM_MESSAGE,
            model=OPENAI_MODEL,
            temperature=0.3,
            max_tokens=2000
        )

        if 'choices' not in openai_response or not openai_response['choices']:
            raise Exception("Resposta invalida da OpenAI")

        assistant_response = openai_response['choices'][0]['message']['content']

        # 5. Parse da resposta JSON
        try:
            json_str = assistant_response
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0]
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0]

            llm_result = json.loads(json_str.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"[traceId: {trace_id}] Erro ao fazer parse do JSON: {e}")
            llm_result = {
                "analysis": {"totalTermsAnalyzed": len(high_performing), "suggestedKeywords": 0},
                "suggestions": [],
                "recommendedActions": ["Erro ao processar resposta do LLM"],
                "rawResponse": assistant_response
            }

        suggestions = llm_result.get('suggestions', [])

        # 6. Buscar metricas historicas para as sugestoes
        if suggestions:
            suggested_terms = [s.get('term') for s in suggestions if s.get('term')]
            logger.info(f"[traceId: {trace_id}] Buscando metricas historicas para {len(suggested_terms)} termos...")

            historical_metrics = google_ads_service.get_keyword_historical_metrics(
                client_id=client_id,
                keywords=suggested_terms
            )

            # 7. Aplicar regras de selecao
            if historical_metrics:
                suggestions = _apply_selection_rules(suggestions, historical_metrics)

        # 8. Adicionar metricas atuais dos search terms as sugestoes
        search_terms_map = {t['search_term'].lower(): t for t in search_terms}
        for suggestion in suggestions:
            term = suggestion.get('term', '').lower()
            if term in search_terms_map:
                st = search_terms_map[term]
                suggestion['currentMetrics'] = {
                    'impressions': st.get('impressions', 0),
                    'clicks': st.get('clicks', 0),
                    'conversions': st.get('conversions', 0),
                    'ctr': st.get('ctr', 0),
                    'cost': st.get('cost', 0)
                }

        # 9. Registrar no ExecutionHistory
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
                'highPerformingCount': len(high_performing),
                'suggestionsCount': len(suggestions),
                'model': OPENAI_MODEL
            })
        }
        execution_history_table.put_item(Item=execution_record)

        logger.info(f"[traceId: {trace_id}] Analise concluida - {len(suggestions)} sugestoes")

        return http_response(200, {
            "status": "SUCCESS",
            "traceId": trace_id,
            "analysis": {
                "totalSearchTerms": len(search_terms),
                "highPerformingTerms": len(high_performing),
                "suggestedKeywords": len(suggestions)
            },
            "suggestions": suggestions,
            "existingKeywords": [kw.get("text") for kw in current_keywords],
            "recommendedActions": llm_result.get("recommendedActions", []),
            "selectionRules": SELECTION_RULES
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro na analise de expansao: {str(e)}", exc_info=True)

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
