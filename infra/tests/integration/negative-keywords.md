# Testes de Integracao - Negative Keywords

## Endpoints

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | /keywords/search-terms | Lista termos de pesquisa com metricas |
| GET | /keywords/negatives | Lista negative keywords existentes |
| POST | /keywords/analyze-negatives | Analisa e sugere negative keywords via LLM |
| POST | /keywords/apply-negatives | Aplica negative keywords no Google Ads |

---

## Pre-requisitos

1. Arquivo `.env` configurado com `API_KEY`
2. Cliente cadastrado no sistema com Google Ads configurado
3. Campanha ativa com termos de pesquisa

---

## 1. Listar Termos de Pesquisa

### Request

```bash
source .env

curl -X GET "https://YOUR_API_URL/keywords/search-terms?clientId=YOUR_CLIENT_ID&campaignId=YOUR_CAMPAIGN_ID&minImpressions=10&days=30" \
  -H "x-api-key: $API_KEY"
```

### Parametros

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| clientId | string | Sim | ID do cliente no sistema |
| campaignId | string | Sim | ID da campanha no Google Ads |
| adGroupId | string | Nao | ID do grupo de anuncios (opcional) |
| minImpressions | int | Nao | Minimo de impressoes (default: 10) |
| days | int | Nao | Periodo em dias (default: 30) |
| limit | int | Nao | Limite de resultados (default: 500) |

### Response (200)

```json
{
  "status": "SUCCESS",
  "searchTerms": [
    {
      "search_term": "advogado trabalhista sp",
      "status": "NONE",
      "campaign": {"id": 123456789, "name": "Campanha Principal"},
      "ad_group": {"id": 987654321, "name": "Grupo Trabalhista"},
      "impressions": 1500,
      "clicks": 45,
      "conversions": 3,
      "cost": 89.50,
      "ctr": 3.0,
      "cpc": 1.99,
      "cpa": 29.83
    }
  ],
  "count": 1,
  "filters": {
    "clientId": "meu-cliente",
    "campaignId": "123456789",
    "minImpressions": 10,
    "days": 30
  }
}
```

### Casos de Teste

- [ ] Retorna lista de termos com metricas
- [ ] Filtra por minImpressions corretamente
- [ ] Retorna erro 400 se clientId ausente
- [ ] Retorna erro 400 se campaignId ausente
- [ ] Retorna erro 401 se API key invalida

---

## 2. Listar Negative Keywords Existentes

### Request

```bash
source .env

curl -X GET "https://YOUR_API_URL/keywords/negatives?clientId=YOUR_CLIENT_ID&campaignId=YOUR_CAMPAIGN_ID" \
  -H "x-api-key: $API_KEY"
```

### Parametros

| Parametro | Tipo | Obrigatorio | Descricao |
|-----------|------|-------------|-----------|
| clientId | string | Sim | ID do cliente no sistema |
| campaignId | string | Sim | ID da campanha no Google Ads |
| adGroupId | string | Nao | ID do grupo de anuncios (opcional) |

### Response (200)

```json
{
  "status": "SUCCESS",
  "negativeKeywords": [
    {
      "id": 111222333,
      "text": "gratis",
      "match_type": "BROAD",
      "level": "campaign",
      "campaign": {"id": 123456789, "name": "Campanha Principal"}
    }
  ],
  "count": 1,
  "filters": {
    "clientId": "meu-cliente",
    "campaignId": "123456789",
    "adGroupId": null
  }
}
```

### Casos de Teste

- [ ] Retorna negative keywords a nivel de campanha
- [ ] Retorna negative keywords a nivel de ad group (se especificado)
- [ ] Retorna erro 400 se clientId ausente
- [ ] Retorna erro 400 se campaignId ausente

---

## 3. Analisar Negative Keywords (LLM)

### Request

```bash
source .env

curl -X POST "https://YOUR_API_URL/keywords/analyze-negatives" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "context": {
      "businessType": "Escritorio de advocacia trabalhista",
      "targetLocation": "Sao Paulo, SP",
      "excludePatterns": ["gratis", "gratuito", "free"]
    }
  }'
```

### Body

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| clientId | string | Sim | ID do cliente no sistema |
| campaignId | string | Sim | ID da campanha no Google Ads |
| adGroupId | string | Nao | ID do grupo de anuncios (opcional) |
| context | object | Nao | Contexto para analise |
| context.businessType | string | Nao | Tipo do negocio |
| context.targetLocation | string | Nao | Regiao alvo dos anuncios |
| context.excludePatterns | array | Nao | Padroes que sempre devem ser negativados |

### Response (200)

```json
{
  "status": "SUCCESS",
  "traceId": "abc-123",
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
    }
  ],
  "existingNegatives": ["gratis", "de graca"],
  "recommendedActions": [
    "Adicionar 'gratuito' como BROAD match negative",
    "Adicionar termos de outras cidades como PHRASE match negative"
  ]
}
```

### Casos de Teste

- [ ] Retorna sugestoes de negative keywords
- [ ] LLM identifica termos com "gratuito/gratis"
- [ ] LLM identifica termos com muitas impressoes e zero conversoes
- [ ] Retorna lista vazia se nao houver search terms
- [ ] Registra no ExecutionHistory
- [ ] Retorna erro 400 se clientId ausente
- [ ] Retorna erro 400 se campaignId ausente

---

## 4. Aplicar Negative Keywords

### Request

```bash
source .env

curl -X POST "https://YOUR_API_URL/keywords/apply-negatives" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "YOUR_CLIENT_ID",
    "campaignId": "YOUR_CAMPAIGN_ID",
    "negativeKeywords": [
      {"text": "gratuito", "matchType": "BROAD"},
      {"text": "advogado rio de janeiro", "matchType": "PHRASE"}
    ]
  }'
```

### Body

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| clientId | string | Sim | ID do cliente no sistema |
| campaignId | string | Sim | ID da campanha no Google Ads |
| adGroupId | string | Nao | ID do grupo de anuncios (se omitido, aplica a nivel de campanha) |
| negativeKeywords | array | Sim | Lista de keywords a negativar |
| negativeKeywords[].text | string | Sim | Texto da keyword |
| negativeKeywords[].matchType | string | Nao | BROAD, PHRASE ou EXACT (default: BROAD) |

### Response (200)

```json
{
  "status": "SUCCESS",
  "traceId": "def-456",
  "message": "2 negative keywords aplicadas com sucesso",
  "applied": [
    "customers/1234567890/campaignCriteria/123~456",
    "customers/1234567890/campaignCriteria/123~457"
  ],
  "level": "campaign"
}
```

### Casos de Teste

- [ ] Aplica negative keywords a nivel de campanha
- [ ] Aplica negative keywords a nivel de ad group (se adGroupId especificado)
- [ ] Valida matchType (BROAD, PHRASE, EXACT)
- [ ] Registra no ExecutionHistory
- [ ] Retorna erro 400 se clientId ausente
- [ ] Retorna erro 400 se campaignId ausente
- [ ] Retorna erro 400 se negativeKeywords vazio
- [ ] Retorna erro 400 se keyword sem campo text

---

## Fluxo de Teste Completo

1. **Listar search terms** - Verificar termos de pesquisa existentes
2. **Listar negatives** - Ver negative keywords ja aplicadas
3. **Analisar** - Usar LLM para sugerir novas negativas
4. **Aplicar** - Adicionar as sugestoes aprovadas
5. **Verificar** - Listar negatives novamente para confirmar

---

## Erros Comuns

| Codigo | Mensagem | Causa |
|--------|----------|-------|
| 400 | clientId e obrigatorio | Parametro clientId nao enviado |
| 400 | campaignId e obrigatorio | Parametro campaignId nao enviado |
| 400 | negativeKeywords deve ser uma lista nao vazia | Lista de keywords vazia ou invalida |
| 401 | API key invalida | x-api-key incorreta ou ausente |
| 500 | Erro da API do Google Ads | Problema na comunicacao com Google Ads |
