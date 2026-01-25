# PRD-003: Negative Keywords Detection and Management

**Status:** Draft
**Created:** 2026-01-24
**Author:** Claude
**Branch:** feature/negative-keywords

---

## 1. Problema / Objetivo

O sistema precisa identificar automaticamente termos de pesquisa que estao gerando impressoes mas nao convertem, desperdicando orcamento de anuncios. A feature de Negative Keywords vai:

1. Coletar termos de pesquisa dos ultimos 30 dias com metricas (impressoes, cliques, conversoes, CTR, CPC, CPA)
2. Usar LLM para analisar e sugerir palavras-chave negativas baseado em:
   - Termos com muitas impressoes mas poucos cliques/conversoes
   - Termos que indicam busca por servicos gratuitos ("gratuita", "gratis", "free")
   - Termos que nao fazem sentido para a regiao do anuncio
3. Permitir aplicar as sugestoes de palavras-chave negativas

### Fluxo Visual (conforme diagrama)

```
+------------------------+     +------------------------+
|  palavras_chave_atuais |     |   termos_de_pesquisa   |
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
          |  palavras_chave_negative    |
          |          (LLM)              |
          |                             |
          |  Analisa e sugere keywords  |
          |  que devem ser negativadas: |
          |  - "gratuita", "gratis"     |
          |  - Termos com impressoes    |
          |    mas sem conversoes       |
          |  - Termos fora da regiao    |
          +-----------------------------+
```

---

## 2. Solucao Proposta

### 2.1 Novo Metodo no Google Ads Service: `get_search_terms()`

Recupera termos de pesquisa dos ultimos 30 dias usando a Google Ads API.

**Query GAQL:**
```sql
SELECT
    search_term_view.search_term,
    search_term_view.status,
    segments.date,
    metrics.impressions,
    metrics.clicks,
    metrics.conversions,
    metrics.cost_micros,
    metrics.ctr,
    metrics.average_cpc
FROM search_term_view
WHERE segments.date DURING LAST_30_DAYS
  AND campaign.id = {campaign_id}
  AND metrics.impressions > 0
ORDER BY metrics.impressions DESC
LIMIT 500
```

**Retorno:**
```python
{
    'search_term': str,
    'status': 'ADDED|EXCLUDED|NONE',
    'impressions': int,
    'clicks': int,
    'conversions': float,
    'cost': float,  # em reais
    'ctr': float,   # porcentagem
    'cpc': float,   # custo por clique em reais
    'cpa': float    # custo por conversao (se conversions > 0)
}
```

### 2.2 Novo Metodo no Google Ads Service: `get_negative_keywords()`

Lista palavras-chave negativas existentes no ad group ou campanha.

### 2.3 Novo Metodo no Google Ads Service: `add_negative_keywords()`

Adiciona palavras-chave negativas a um ad group ou campanha.

### 2.4 Novo Handler: `analyze_negative_keywords.py`

**Endpoint:** `POST /keywords/analyze-negatives`

**Body:**
```json
{
  "clientId": "string (required)",
  "campaignId": "string (required)",
  "adGroupId": "string (optional)",
  "context": {
    "businessType": "string (optional) - tipo do negocio",
    "targetLocation": "string (optional) - regiao alvo dos anuncios",
    "excludePatterns": ["array (optional) - padroes a sempre excluir"]
  }
}
```

**Fluxo:**
1. Buscar keywords atuais do ad group/campanha
2. Buscar termos de pesquisa dos ultimos 30 dias
3. Buscar negative keywords existentes
4. Montar prompt para LLM com:
   - Contexto do negocio
   - Keywords atuais
   - Termos de pesquisa com metricas
   - Exemplos de padroes a negativar ("gratuita", "gratis", etc.)
5. Chamar OpenAI para analise
6. Retornar sugestoes de negative keywords com justificativa

**Resposta:**
```json
{
  "status": "SUCCESS",
  "analysis": {
    "totalSearchTerms": 150,
    "potentialNegatives": 12,
    "estimatedWastedSpend": 45.50
  },
  "suggestions": [
    {
      "term": "advogado gratuito",
      "reason": "Indica busca por servico gratuito - cliente paga por servicos",
      "metrics": {
        "impressions": 1250,
        "clicks": 45,
        "conversions": 0,
        "cost": 89.50
      },
      "priority": "HIGH",
      "matchType": "PHRASE"
    }
  ],
  "existingNegatives": ["gratis", "free"],
  "recommendedActions": [
    "Adicionar 'gratuito' como BROAD match negative",
    "Adicionar termos de outras cidades como negative"
  ]
}
```

### 2.5 Novo Handler: `apply_negative_keywords.py`

**Endpoint:** `POST /keywords/apply-negatives`

**Body:**
```json
{
  "clientId": "string (required)",
  "campaignId": "string (required)",
  "adGroupId": "string (optional)",
  "negativeKeywords": [
    {
      "text": "gratuito",
      "matchType": "BROAD"
    }
  ]
}
```

**Fluxo:**
1. Validar API key
2. Validar que cliente existe
3. Chamar `add_negative_keywords()` no Google Ads Service
4. Registrar no ExecutionHistory
5. Retornar resultado

### 2.6 Novo Handler: `list_search_terms.py`

**Endpoint:** `GET /keywords/search-terms`

**Query Params:**
- `clientId` (required)
- `campaignId` (required)
- `adGroupId` (optional)
- `minImpressions` (optional, default: 10)
- `days` (optional, default: 30)

Retorna lista de termos de pesquisa com metricas para visualizacao.

### 2.7 Novo Prompt Template: `negative_keywords_analysis`

Armazenado na tabela `Prompts` do DynamoDB.

**System Message:**
```
Voce e um especialista em Google Ads focado em otimizacao de palavras-chave negativas.
Sua tarefa e analisar termos de pesquisa e identificar aqueles que devem ser negativados.

Criterios para negativar um termo:
1. Termos que indicam busca por servicos GRATUITOS: "gratis", "gratuito", "free", "de graca"
2. Termos com MUITAS impressoes mas ZERO conversoes (indicam mismatch de intencao)
3. Termos de OUTRAS REGIOES quando o anuncio e focado em uma regiao especifica
4. Termos que indicam PESQUISA/ESTUDO e nao intencao de compra: "como funciona", "o que e"
5. Termos de CONCORRENTES especificos (a menos que seja estrategia do cliente)

Para cada termo sugerido, explique o motivo da negativacao.
Priorize termos com maior gasto sem retorno (impressions * CPC sem conversoes).
```

---

## 3. Arquivos Afetados

### Novos Arquivos
| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `src/functions/keywords/__init__.py` | criar | Modulo Python |
| `src/functions/keywords/analyze_negatives.py` | criar | Handler para analise de negativas |
| `src/functions/keywords/apply_negatives.py` | criar | Handler para aplicar negativas |
| `src/functions/keywords/list_search_terms.py` | criar | Handler para listar termos de pesquisa |
| `sls/functions/keywords/interface.yml` | criar | Configuracao das funcoes Lambda |

### Arquivos Modificados
| Caminho | Tipo | Descricao |
|---------|------|-----------|
| `src/services/google_ads_client_service.py` | modificar | Adicionar metodos get_search_terms, get_negative_keywords, add_negative_keywords |
| `serverless.yml` | modificar | Importar novas funcoes |

---

## 4. Dependencias

- Google Ads API v17+ (search_term_view, CampaignCriterion para negatives)
- OpenAI API (analise de termos)
- Tabela `Prompts` existente (novo prompt template)
- Tabela `ExecutionHistory` existente (logs)
- Utils existentes: `http.py`, `auth.py`, `encryption.py`

---

## 5. Riscos e Consideracoes

### Riscos
1. **Rate Limits Google Ads**: Queries de search terms podem ser pesadas
   - Mitigacao: Limitar a 500 termos por request, cache de resultados

2. **Custo OpenAI**: Prompts com muitos termos podem ser caros
   - Mitigacao: Filtrar termos com poucos impressoes antes de enviar ao LLM

3. **Falsos Positivos**: LLM pode sugerir negativar termos validos
   - Mitigacao: Sempre retornar sugestoes para aprovacao humana, nunca aplicar automaticamente

### Consideracoes
- Negative keywords podem ser aplicadas a nivel de ad group ou campanha
- Match types para negatives: EXACT, PHRASE, BROAD
- Manter historico de negatives aplicadas para auditoria

---

## 6. Criterios de Aceite

- [ ] Endpoint GET /keywords/search-terms retorna termos dos ultimos 30 dias com metricas
- [ ] Endpoint POST /keywords/analyze-negatives retorna sugestoes de negativas via LLM
- [ ] Endpoint POST /keywords/apply-negatives adiciona negativas no Google Ads
- [ ] LLM identifica termos com "gratuito/gratis" como candidatos a negativas
- [ ] LLM identifica termos com muitas impressoes e zero conversoes
- [ ] Todas as acoes sao logadas no ExecutionHistory
- [ ] Documentacao de integracao criada
- [ ] Postman requests criados

---

## 7. Referencias

- `CLAUDE.md` - Padroes do projeto
- `src/services/google_ads_client_service.py` - Servico existente de Google Ads
- `src/functions/openai/caller.py` - Integracao com OpenAI
- Google Ads API: [Search Term View](https://developers.google.com/google-ads/api/fields/v17/search_term_view)
- Google Ads API: [Campaign Criterion](https://developers.google.com/google-ads/api/fields/v17/campaign_criterion)

---

## Historico

| Data | Status | Notas |
|------|--------|-------|
| 2026-01-24 | Draft | PRD criado |
| 2026-01-24 | Spec Generated | Spec criada em docs/work/spec/003-negative-keywords.md |
| 2026-01-24 | Implemented | Codigo implementado |
