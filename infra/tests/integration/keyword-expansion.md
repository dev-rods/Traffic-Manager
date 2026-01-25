# Keyword Expansion Integration Tests

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /keywords/analyze-expansion | Analisa termos de pesquisa e sugere novas keywords via LLM |
| POST | /keywords/apply-expansion | Adiciona keywords sugeridas ao ad group |

## Test Cases

### POST /keywords/analyze-expansion

| # | Test Case | Expected Status | Expected Response |
|---|-----------|-----------------|-------------------|
| 1 | Sucesso com todos os parametros | 200 | Retorna sugestoes de keywords com metricas |
| 2 | Sucesso sem ad group (analisa campanha inteira) | 200 | Retorna sugestoes para toda a campanha |
| 3 | Sem clientId | 400 | `{"status": "ERROR", "message": "clientId e obrigatorio"}` |
| 4 | Sem campaignId | 400 | `{"status": "ERROR", "message": "campaignId e obrigatorio"}` |
| 5 | Sem API key | 401 | `{"status": "ERROR", "message": "API key is required"}` |
| 6 | Nenhum termo de pesquisa encontrado | 200 | `{"status": "SUCCESS", "suggestions": [], "analysis": {"totalSearchTerms": 0}}` |

### POST /keywords/apply-expansion

| # | Test Case | Expected Status | Expected Response |
|---|-----------|-----------------|-------------------|
| 1 | Sucesso - adicionar keywords | 200 | Retorna lista de keywords adicionadas |
| 2 | Sem clientId | 400 | `{"status": "ERROR", "message": "clientId e obrigatorio"}` |
| 3 | Sem campaignId | 400 | `{"status": "ERROR", "message": "campaignId e obrigatorio"}` |
| 4 | Sem adGroupId | 400 | `{"status": "ERROR", "message": "adGroupId e obrigatorio para adicionar keywords"}` |
| 5 | Lista de keywords vazia | 400 | `{"status": "ERROR", "message": "keywords deve ser uma lista nao vazia"}` |
| 6 | matchType invalido | 400 | `{"status": "ERROR", "message": "Item X tem matchType invalido"}` |
| 7 | Keyword sem texto | 400 | `{"status": "ERROR", "message": "Item X deve ter o campo 'text'"}` |
| 8 | Sem API key | 401 | `{"status": "ERROR", "message": "API key is required"}` |

## Setup

Antes de executar os testes, certifique-se de:

1. Ter um cliente cadastrado com credenciais Google Ads validas
2. Ter uma campanha ativa com termos de pesquisa
3. Ter um ad group para adicionar keywords
4. Exportar a API key: `source .env`

## Test Commands

### Analyze Keyword Expansion

```bash
# TC-1: Sucesso com todos os parametros
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/analyze-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "adGroupId": "YOUR_AD_GROUP_ID",
    "context": {
      "businessType": "Escritorio de advocacia",
      "targetLocation": "Sao Paulo, SP",
      "minCtr": 2.0,
      "minConversions": 1
    }
  }'

# TC-2: Sem ad group (campanha inteira)
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/analyze-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID"
  }'

# TC-3: Sem clientId
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/analyze-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "campaignId": "YOUR_CAMPAIGN_ID"
  }'

# TC-4: Sem campaignId
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/analyze-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID"
  }'

# TC-5: Sem API key
curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/analyze-expansion" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID"
  }'
```

### Apply Keyword Expansion

```bash
# TC-1: Sucesso - adicionar keywords
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/apply-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "adGroupId": "YOUR_AD_GROUP_ID",
    "keywords": [
      {"text": "advogado trabalhista zona sul", "matchType": "PHRASE"},
      {"text": "advogado CLT", "matchType": "EXACT"}
    ]
  }'

# TC-4: Sem adGroupId
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/apply-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "keywords": [{"text": "teste", "matchType": "EXACT"}]
  }'

# TC-5: Lista de keywords vazia
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/apply-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "adGroupId": "YOUR_AD_GROUP_ID",
    "keywords": []
  }'

# TC-6: matchType invalido
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/apply-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "adGroupId": "YOUR_AD_GROUP_ID",
    "keywords": [{"text": "teste", "matchType": "INVALID"}]
  }'

# TC-7: Keyword sem texto
source .env && curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/keywords/apply-expansion" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "adGroupId": "YOUR_AD_GROUP_ID",
    "keywords": [{"matchType": "EXACT"}]
  }'
```

## Expected Responses

### Analyze Keyword Expansion - Success

```json
{
  "status": "SUCCESS",
  "traceId": "abc-123-def",
  "analysis": {
    "totalSearchTerms": 150,
    "highPerformingTerms": 25,
    "suggestedKeywords": 5
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
      "matchTypeReason": "Termo especifico, PHRASE captura variantes",
      "priority": "HIGH"
    }
  ],
  "existingKeywords": ["advogado trabalhista", "advogado sp"],
  "recommendedActions": [
    "Adicionar 'advogado trabalhista zona sul' como PHRASE match"
  ],
  "selectionRules": {
    "min_monthly_searches": 100,
    "max_competition_index": 80
  }
}
```

### Apply Keyword Expansion - Success

```json
{
  "status": "SUCCESS",
  "traceId": "def-456-ghi",
  "message": "2 keywords adicionadas com sucesso",
  "added": [
    "customers/1234567890/adGroupCriteria/123~456",
    "customers/1234567890/adGroupCriteria/123~457"
  ],
  "adGroupId": "22222222222"
}
```

## Cleanup

Apos os testes de apply-expansion, as keywords adicionadas permanecem no Google Ads.
Para remover, use o Google Ads UI ou crie um endpoint de remocao.

## Notes

- O endpoint analyze-expansion usa LLM (OpenAI) para analisar os termos
- O tempo de resposta pode variar dependendo da quantidade de termos (30-60s)
- Suggestions sao filtradas por regras de selecao:
  - `min_monthly_searches`: 100 (minimo de buscas mensais)
  - `max_competition_index`: 80 (indice maximo de concorrencia 0-100)
- Match types suportados: EXACT, PHRASE, BROAD
