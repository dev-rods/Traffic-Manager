# SPEC-004: Keyword Expansion from Search Terms

**PRD:** [004-keyword-expansion](../prd/004-keyword-expansion.md)
**Status:** Ready for Implementation
**Created:** 2026-01-25

---

## Resumo das Mudancas

Esta spec implementa um sistema de expansao de keywords baseado em termos de pesquisa com bom desempenho:
1. Novos metodos no GoogleAdsClientService para metricas historicas e adicao de keywords
2. Endpoint para analise via LLM de termos promissores (POST /keywords/analyze-expansion)
3. Endpoint para adicionar keywords ao ad group (POST /keywords/apply-expansion)
4. Regras de negocio para selecao baseada em metricas historicas

---

## Ordem de Implementacao

1. Adicionar metodo `get_keyword_historical_metrics()` em `google_ads_client_service.py`
2. Adicionar metodo `add_keywords()` em `google_ads_client_service.py`
3. Criar `src/functions/keywords/analyze_expansion.py`
4. Criar `src/functions/keywords/apply_expansion.py`
5. Atualizar `sls/functions/keywords/interface.yml`
6. Criar mocks e documentacao de testes

---

## Arquivos a Modificar

### 1. `src/services/google_ads_client_service.py`

**Adicionar** os seguintes metodos apos `add_negative_keywords()`:

```python
def get_keyword_historical_metrics(
    self,
    client_id: str,
    keywords: List[str],
    location_ids: Optional[List[str]] = None,
    language_id: str = "1014"  # Portuguese
) -> List[Dict[str, Any]]:
    """
    Obtem metricas historicas para uma lista de keywords usando KeywordPlanIdeaService.

    Args:
        client_id: ID do cliente no sistema
        keywords: Lista de keywords para buscar metricas
        location_ids: IDs de localizacao (default: Brasil = 2076)
        language_id: ID do idioma (default: 1014 = Portugues)

    Returns:
        list: Lista de metricas por keyword
            - keyword: texto da keyword
            - avg_monthly_searches: media de buscas mensais
            - competition: LOW|MEDIUM|HIGH
            - competition_index: 0-100
            - low_top_of_page_bid_micros: lance minimo para topo
            - high_top_of_page_bid_micros: lance maximo para topo
    """
    try:
        google_ads_client, customer_id = self.get_client_for_customer(client_id)

        if not google_ads_client:
            logger.error(f"Cliente {client_id} nao configurado para Google Ads")
            return []

        keyword_plan_idea_service = google_ads_client.get_service("KeywordPlanIdeaService")

        # Configurar request
        request = google_ads_client.get_type("GenerateKeywordHistoricalMetricsRequest")
        request.customer_id = customer_id

        # Adicionar keywords
        for kw in keywords:
            request.keywords.append(kw)

        # Configurar localizacao (default: Brasil)
        if not location_ids:
            location_ids = ["2076"]  # Brasil

        for loc_id in location_ids:
            geo_target = google_ads_client.get_type("GeoTargetConstantInfo")
            geo_target.geo_target_constant = f"geoTargetConstants/{loc_id}"
            request.geo_target_constants.append(geo_target.geo_target_constant)

        # Configurar idioma
        request.language = f"languageConstants/{language_id}"

        # Executar request
        response = keyword_plan_idea_service.generate_keyword_historical_metrics(request=request)

        results = []
        for result in response.results:
            metrics = result.keyword_metrics

            # Mapear competition enum
            competition_map = {
                0: "UNSPECIFIED",
                1: "UNKNOWN",
                2: "LOW",
                3: "MEDIUM",
                4: "HIGH"
            }
            competition = competition_map.get(metrics.competition, "UNKNOWN")

            results.append({
                'keyword': result.text,
                'avg_monthly_searches': metrics.avg_monthly_searches if metrics.avg_monthly_searches else 0,
                'competition': competition,
                'competition_index': metrics.competition_index if metrics.competition_index else 0,
                'low_top_of_page_bid_micros': metrics.low_top_of_page_bid_micros if metrics.low_top_of_page_bid_micros else 0,
                'high_top_of_page_bid_micros': metrics.high_top_of_page_bid_micros if metrics.high_top_of_page_bid_micros else 0,
                'low_top_of_page_bid': metrics.low_top_of_page_bid_micros / 1000000 if metrics.low_top_of_page_bid_micros else 0,
                'high_top_of_page_bid': metrics.high_top_of_page_bid_micros / 1000000 if metrics.high_top_of_page_bid_micros else 0
            })

        logger.info(f"Obtidas metricas historicas para {len(results)} keywords")
        return results

    except GoogleAdsException as ex:
        logger.error(f"Erro da API do Google Ads ao buscar metricas historicas: {ex.error.code().name}")
        return []
    except Exception as e:
        logger.error(f"Erro ao buscar metricas historicas para cliente {client_id}: {str(e)}")
        return []

def add_keywords(
    self,
    client_id: str,
    ad_group_id: str,
    keywords: List[Dict[str, str]]
) -> Dict[str, Any]:
    """
    Adiciona keywords a um ad group.

    Args:
        client_id: ID do cliente no sistema
        ad_group_id: ID do grupo de anuncios
        keywords: Lista de keywords [{text: str, matchType: EXACT|PHRASE|BROAD}]

    Returns:
        dict: Resultado da operacao
            - success (bool)
            - added (list): Keywords adicionadas com sucesso
            - errors (list): Erros por keyword
    """
    try:
        google_ads_client, customer_id = self.get_client_for_customer(client_id)

        if not google_ads_client:
            return {
                'success': False,
                'error': f'Cliente {client_id} nao configurado para Google Ads'
            }

        ad_group_criterion_service = google_ads_client.get_service("AdGroupCriterionService")

        # Mapear match types
        match_type_enum = google_ads_client.enums.KeywordMatchTypeEnum
        match_type_map = {
            'EXACT': match_type_enum.EXACT,
            'PHRASE': match_type_enum.PHRASE,
            'BROAD': match_type_enum.BROAD
        }

        operations = []
        added = []
        errors = []

        for kw in keywords:
            try:
                operation = google_ads_client.get_type("AdGroupCriterionOperation")
                criterion = operation.create

                criterion.ad_group = f"customers/{customer_id}/adGroups/{ad_group_id}"
                criterion.status = google_ads_client.enums.AdGroupCriterionStatusEnum.ENABLED
                criterion.keyword.text = kw.get("text")
                criterion.keyword.match_type = match_type_map.get(
                    kw.get("matchType", "PHRASE").upper(),
                    match_type_enum.PHRASE
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
                added.append(result.resource_name)

        logger.info(
            f"Keywords adicionadas para cliente {client_id}: "
            f"{len(added)} sucesso, {len(errors)} erros"
        )

        return {
            'success': len(errors) == 0,
            'added': added,
            'errors': errors if errors else None
        }

    except GoogleAdsException as ex:
        error_msg = f"Erro da API do Google Ads: {ex.error.code().name}"
        if ex.error.message:
            error_msg += f" - {ex.error.message}"

        logger.error(f"Erro ao adicionar keywords para cliente {client_id}: {error_msg}")

        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        logger.error(f"Erro ao adicionar keywords para cliente {client_id}: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
```

---

## Arquivos a Criar

### 2. `src/functions/keywords/analyze_expansion.py`

```python
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
```

### 3. `src/functions/keywords/apply_expansion.py`

```python
"""
Lambda handler para aplicar keywords de expansao no Google Ads.

Endpoint: POST /keywords/apply-expansion
Body:
    - clientId (required): ID do cliente
    - campaignId (required): ID da campanha
    - adGroupId (required): ID do grupo de anuncios
    - keywords (required): Lista de keywords a adicionar
        - text: Texto da keyword
        - matchType: EXACT, PHRASE ou BROAD (default: PHRASE)
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


def _validate_keywords(keywords):
    """Valida a lista de keywords."""
    if not keywords or not isinstance(keywords, list):
        return False, "keywords deve ser uma lista nao vazia"

    for i, kw in enumerate(keywords):
        if not isinstance(kw, dict):
            return False, f"Item {i} deve ser um objeto"
        if not kw.get("text"):
            return False, f"Item {i} deve ter o campo 'text'"

        match_type = kw.get("matchType", "PHRASE").upper()
        if match_type not in ["EXACT", "PHRASE", "BROAD"]:
            return False, f"Item {i} tem matchType invalido: {match_type}"

    return True, ""


def handler(event, context):
    """
    Lambda handler para aplicar keywords de expansao.
    """
    trace_id = event.get('requestContext', {}).get('requestId', str(uuid.uuid4()))
    timestamp = datetime.utcnow().isoformat()
    stage = 'APPLY_KEYWORD_EXPANSION'

    logger.info(f"[traceId: {trace_id}] Iniciando ApplyKeywordExpansion")

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
    keywords = body.get("keywords", [])

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

    if not ad_group_id:
        return http_response(400, {
            "status": "ERROR",
            "message": "adGroupId e obrigatorio para adicionar keywords"
        })

    is_valid, error_msg = _validate_keywords(keywords)
    if not is_valid:
        return http_response(400, {
            "status": "ERROR",
            "message": error_msg
        })

    try:
        google_ads_service = GoogleAdsClientService()

        # Adicionar keywords
        logger.info(f"[traceId: {trace_id}] Adicionando {len(keywords)} keywords...")

        result = google_ads_service.add_keywords(
            client_id=client_id,
            ad_group_id=ad_group_id,
            keywords=keywords
        )

        if not result.get("success"):
            return http_response(400, {
                "status": "ERROR",
                "message": result.get("error", "Erro ao adicionar keywords"),
                "errors": result.get("errors")
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
            'adGroupId': ad_group_id,
            'payload': json.dumps({
                'keywordsAdded': len(keywords),
                'keywords': [kw.get("text") for kw in keywords]
            })
        }
        execution_history_table.put_item(Item=execution_record)

        logger.info(f"[traceId: {trace_id}] {len(keywords)} keywords adicionadas com sucesso")

        return http_response(200, {
            "status": "SUCCESS",
            "traceId": trace_id,
            "message": f"{len(keywords)} keywords adicionadas com sucesso",
            "added": result.get("added", []),
            "adGroupId": ad_group_id
        })

    except Exception as e:
        logger.error(f"[traceId: {trace_id}] Erro ao adicionar keywords: {str(e)}", exc_info=True)

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
            "message": f"Erro ao adicionar keywords: {str(e)}"
        })
```

### 4. Atualizar `sls/functions/keywords/interface.yml`

**Adicionar** ao final do arquivo:

```yaml

AnalyzeKeywordExpansion:
  image:
    name: lambdaimage
    command: ["src.functions.keywords.analyze_expansion.handler"]
  memorySize: 1024
  timeout: 120
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-AnalyzeKeywordExpansion-lambdaRole
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
        path: keywords/analyze-expansion
        method: post
        cors: true

ApplyKeywordExpansion:
  image:
    name: lambdaimage
    command: ["src.functions.keywords.apply_expansion.handler"]
  memorySize: 1024
  timeout: 60
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ApplyKeywordExpansion-lambdaRole
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
        path: keywords/apply-expansion
        method: post
        cors: true
```

---

## Endpoints Resultantes

| Metodo | Path | Descricao |
|--------|------|-----------|
| POST | `/keywords/analyze-expansion` | Analisa termos e sugere keywords para adicionar |
| POST | `/keywords/apply-expansion` | Adiciona keywords ao ad group |

---

## Exemplos de Uso

### Analisar Keywords para Expansao (POST /keywords/analyze-expansion)

```bash
source .env

curl -X POST "https://YOUR_API_URL/keywords/analyze-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "context": {
      "businessType": "Escritorio de advocacia trabalhista",
      "targetLocation": "Sao Paulo, SP",
      "minCtr": 2.0,
      "minConversions": 1
    }
  }'
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "traceId": "abc-123",
  "analysis": {
    "totalSearchTerms": 150,
    "highPerformingTerms": 25,
    "suggestedKeywords": 5
  },
  "suggestions": [
    {
      "term": "advogado trabalhista zona sul",
      "reason": "Alto CTR (4.5%) e 3 conversoes - variante geografica relevante",
      "suggestedMatchType": "PHRASE",
      "matchTypeReason": "Permite capturar variantes como 'melhor advogado trabalhista zona sul sp'",
      "priority": "HIGH",
      "currentMetrics": {
        "impressions": 500,
        "clicks": 23,
        "conversions": 3,
        "ctr": 4.5,
        "cost": 45.00
      },
      "historicalMetrics": {
        "avgMonthlySearches": 720,
        "competition": "MEDIUM",
        "competitionIndex": 45,
        "lowTopOfPageBid": 1.50,
        "highTopOfPageBid": 4.20
      }
    }
  ],
  "existingKeywords": ["advogado trabalhista", "advogado sp"],
  "recommendedActions": [
    "Adicionar 'advogado trabalhista zona sul' como PHRASE match",
    "Monitorar performance por 2 semanas antes de adicionar mais"
  ],
  "selectionRules": {
    "min_monthly_searches": 100,
    "max_competition_index": 80
  }
}
```

### Aplicar Keywords (POST /keywords/apply-expansion)

```bash
source .env

curl -X POST "https://YOUR_API_URL/keywords/apply-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "adGroupId": "YOUR_AD_GROUP_ID",
    "keywords": [
      {"text": "advogado trabalhista zona sul", "matchType": "PHRASE"},
      {"text": "advogado CLT sp", "matchType": "EXACT"}
    ]
  }'
```

**Response (200):**
```json
{
  "status": "SUCCESS",
  "traceId": "def-456",
  "message": "2 keywords adicionadas com sucesso",
  "added": [
    "customers/1234567890/adGroupCriteria/123~456",
    "customers/1234567890/adGroupCriteria/123~457"
  ],
  "adGroupId": "987654321"
}
```

---

## Checklist de Implementacao

- [ ] Adicionar metodo `get_keyword_historical_metrics()` em `google_ads_client_service.py`
- [ ] Adicionar metodo `add_keywords()` em `google_ads_client_service.py`
- [ ] Criar `src/functions/keywords/analyze_expansion.py`
- [ ] Criar `src/functions/keywords/apply_expansion.py`
- [ ] Atualizar `sls/functions/keywords/interface.yml`
- [ ] Criar mocks em `tests/mocks/keywords/`
- [ ] Atualizar `tests/integration/negative-keywords.md` ou criar novo arquivo
- [ ] Atualizar Postman collection
- [ ] Deploy e teste dos endpoints

---

## Convencoes Respeitadas

- **Logging:** `[traceId: {trace_id}]` em todas as mensagens
- **Naming:** Lambda functions em PascalCase
- **Response:** Formato padrao com `status`, `message`, dados
- **Error handling:** Try/catch com registro no ExecutionHistory
