# PRD-004: Keyword Expansion from Search Terms

**Status:** Implemented
**Created:** 2026-01-25
**Author:** Claude
**Branch:** feature/negative-keywords

---

## 1. Problema / Objetivo

Termos de pesquisa com bom desempenho (alto CTR, conversoes) devem ser adicionados como keywords para capturar variantes proximas (close variants) e aumentar o alcance da campanha.

A feature de Keyword Expansion vai:

1. Analisar termos de pesquisa com boas metricas (CTR alto, conversoes)
2. Usar LLM para identificar termos que devem virar keywords
3. Buscar metricas historicas via Google Ads KeywordPlanIdeaService
4. Retornar sugestoes com dados de volume, CPC estimado e competicao

### Fluxo Visual (conforme diagrama)

```
+------------------------+     +------------------------+
| palavras_chave_atuais  |     |   termos_de_pesquisa   |
|                        |     |                        |
|  Retorna lista de      |     |  Retorna termos dos    |
|  keywords do ad group  |     |  ultimos 30 dias com   |
|                        |     |  cliques, conversoes,  |
|                        |     |  CTR, CPC e CPA        |
+----------+-------------+     +----------+-------------+
           |                              |
           +-------------+----------------+
                         |
                         v
          +-----------------------------+
          |   palavras_chave_idea (LLM) |
          |                             |
          |  Recebe dados de termos de  |
          |  pesquisa e sugere NOVAS    |
          |  keywords diferentes das    |
          |  existentes.                |
          |                             |
          |  * Explicar ao LLM o que e  |
          |    correspondencia de frase |
          +-------------+---------------+
                        |
                        v
          +-----------------------------+
          |  KeywordPlanIdeaService     |
          |  .GenerateKeywordHistorical |
          |  Metrics (Google Ads API)   |
          |                             |
          |  Para cada keyword sugerida:|
          |  - Volume de buscas mensal  |
          |  - Indice de concorrencia   |
          |  - CPC estimado             |
          +-------------+---------------+
                        |
                        v
          +-----------------------------+
          |   palavras_chave_select     |
          |                             |
          |  Regras de negocio para     |
          |  selecionar as novas        |
          |  keywords com base nos      |
          |  dados de buscas            |
          +-------------+---------------+
                        |
                        v
          +-----------------------------+
          |     new_palavras_chave      |
          |                             |
          |  Lista final de keywords    |
          |  recomendadas para adicao   |
          +-----------------------------+
```

---

## 2. Solucao Proposta

### 2.1 Novo Metodo no Google Ads Service: `get_keyword_metrics()`

Busca metricas historicas para uma lista de keywords usando KeywordPlanIdeaService.

**Retorno:**
```python
{
    'keyword': str,
    'avg_monthly_searches': int,
    'competition': 'LOW|MEDIUM|HIGH',
    'competition_index': int,  # 0-100
    'low_top_of_page_bid_micros': int,
    'high_top_of_page_bid_micros': int
}
```

### 2.2 Novo Metodo no Google Ads Service: `add_keywords()`

Adiciona keywords a um ad group.

### 2.3 Novo Handler: `analyze_expansion.py`

**Endpoint:** `POST /keywords/analyze-expansion`

**Body:**
```json
{
  "clientId": "string (required)",
  "campaignId": "string (required)",
  "adGroupId": "string (optional)",
  "context": {
    "businessType": "string (optional)",
    "targetLocation": "string (optional)",
    "minCtr": "number (optional, default: 2.0)",
    "minConversions": "number (optional, default: 1)"
  }
}
```

**Fluxo:**
1. Buscar termos de pesquisa com boas metricas
2. Buscar keywords atuais (para evitar duplicatas)
3. Montar prompt para LLM identificar termos promissores
4. Para cada sugestao, buscar metricas historicas via KeywordPlanIdeaService
5. Retornar sugestoes ranqueadas por potencial

**Resposta:**
```json
{
  "status": "SUCCESS",
  "analysis": {
    "totalSearchTerms": 150,
    "highPerformingTerms": 25,
    "suggestedKeywords": 8
  },
  "suggestions": [
    {
      "term": "advogado trabalhista zona sul",
      "reason": "Alto CTR (4.5%) e 3 conversoes - variante geografica relevante",
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
      },
      "suggestedMatchType": "PHRASE",
      "priority": "HIGH"
    }
  ],
  "existingKeywords": ["advogado trabalhista", "advogado sp"],
  "recommendedActions": [
    "Adicionar 'advogado trabalhista zona sul' como PHRASE match",
    "Considerar 'advogado CLT' com alto volume de busca"
  ]
}
```

### 2.4 Novo Handler: `apply_keywords.py`

**Endpoint:** `POST /keywords/apply-expansion`

**Body:**
```json
{
  "clientId": "string (required)",
  "campaignId": "string (required)",
  "adGroupId": "string (required)",
  "keywords": [
    {
      "text": "advogado trabalhista zona sul",
      "matchType": "PHRASE"
    }
  ]
}
```

### 2.5 Novo Prompt Template: `keyword_expansion_analysis`

**System Message:**
```
Voce e um especialista em Google Ads focado em expansao de palavras-chave.
Sua tarefa e analisar termos de pesquisa com bom desempenho e sugerir
NOVAS keywords diferentes das existentes.

## Tipos de Correspondencia (Match Types) - IMPORTANTE

Explique ao sugerir cada keyword:

1. **EXACT [palavra]**: O anuncio aparece apenas para buscas exatas ou variantes muito proximas.
   - Use quando: o termo ja converte bem e queremos controle total
   - Exemplo: [advogado trabalhista] aparece para "advogado trabalhista" e "advogados trabalhistas"

2. **PHRASE "palavra"**: O anuncio aparece quando a busca CONTEM a frase na ordem correta.
   - Use quando: queremos capturar variantes com palavras adicionais antes/depois
   - Exemplo: "advogado trabalhista" aparece para "melhor advogado trabalhista sp"

3. **BROAD palavra**: O anuncio aparece para buscas relacionadas, mesmo sem as palavras exatas.
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
```

### 2.6 Regras de Negocio para Selecao (palavras_chave_select)

Apos receber as metricas historicas do Google Ads, aplicar filtros:

```python
# Regras de selecao de keywords
SELECTION_RULES = {
    'min_monthly_searches': 100,      # Volume minimo mensal
    'max_competition_index': 80,      # Indice maximo de concorrencia (0-100)
    'max_high_cpc': None,             # Opcional: CPC maximo aceitavel
    'prefer_low_competition': True,   # Priorizar baixa concorrencia
}
```

**Criterios de Selecao:**
1. Volume de buscas >= 100/mes (termo tem demanda)
2. Indice de concorrencia <= 80 (nao e impossivel competir)
3. Se CPC maximo definido, filtrar por ele
4. Ordenar por: conversoes atuais > CTR > volume de buscas

---

## 3. Arquivos Afetados

### Novos Arquivos
| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `src/functions/keywords/analyze_expansion.py` | criar | Handler para analise de expansao |
| `src/functions/keywords/apply_expansion.py` | criar | Handler para aplicar keywords |

### Arquivos Modificados
| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `src/services/google_ads_client_service.py` | modificar | Adicionar get_keyword_metrics, add_keywords |
| `sls/functions/keywords/interface.yml` | modificar | Adicionar novos endpoints |

---

## 4. Dependencias

- Google Ads API KeywordPlanIdeaService
- OpenAI API (analise de termos)
- Metodos existentes: get_search_terms(), get_keywords()

---

## 5. Riscos e Consideracoes

### Riscos
1. **KeywordPlanIdeaService requer KeywordPlan**: Pode ser necessario criar um KeywordPlan temporario
   - Mitigacao: Usar GenerateKeywordIdeas com seed keywords

2. **Custo de adicionar keywords**: Mais keywords = mais gastos potenciais
   - Mitigacao: Sempre retornar sugestoes para aprovacao humana

### Consideracoes
- Keywords podem ser adicionadas como EXACT, PHRASE ou BROAD
- Close variants sao automaticamente capturados pelo Google Ads
- Evitar duplicatas de keywords existentes

---

## 6. Criterios de Aceite

- [ ] Endpoint POST /keywords/analyze-expansion retorna sugestoes de keywords via LLM
- [ ] Sugestoes incluem metricas historicas do Google Ads
- [ ] Endpoint POST /keywords/apply-expansion adiciona keywords ao ad group
- [ ] LLM identifica termos com alto CTR e conversoes
- [ ] Evita sugerir duplicatas de keywords existentes
- [ ] Todas as acoes sao logadas no ExecutionHistory
- [ ] Documentacao de integracao criada
- [ ] Postman requests criados

---

## 7. Referencias

- `CLAUDE.md` - Padroes do projeto
- `src/services/google_ads_client_service.py` - Servico existente
- Google Ads API: [KeywordPlanIdeaService](https://developers.google.com/google-ads/api/reference/rpc/v17/KeywordPlanIdeaService)
- Google Ads API: [GenerateKeywordIdeas](https://developers.google.com/google-ads/api/reference/rpc/v17/KeywordPlanIdeaService#generatekeywordideas)

---

## Historico

| Data | Status | Notas |
|------|--------|-------|
| 2026-01-25 | Draft | PRD criado |
| 2026-01-25 | Spec Generated | Spec criada em docs/work/spec/004-keyword-expansion.md |
| 2026-01-25 | Implemented | Handlers, service methods, mocks, Postman e docs criados |
