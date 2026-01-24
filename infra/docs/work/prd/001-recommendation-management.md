# PRD-001: Recommendation Management System

**Status:** Implemented
**Created:** 2025-01-24
**Author:** Claude

---

## 1. Problema / Objetivo

Atualmente, as recomendações geradas pelo optimizer são armazenadas diretamente na tabela `campaign-metadata` sem um identificador único. Isso impede:
- Rastreamento individual de cada recomendação
- Verificação se uma recomendação já foi aplicada
- Histórico de recomendações por campanha
- Auditoria de aplicações

### Requisitos do Usuário
1. Salvar recomendações com um ID único ao gerá-las
2. Ao aplicar uma recomendação, receber: `clientId`, `campaignId`, `recommendationId`
3. Antes de aplicar, verificar se a recomendação já foi aplicada
4. Após aplicar, salvar informações sobre a aplicação
5. Endpoint para listar recomendações por `clientId` e `campaignId`

---

## 2. Solução Proposta

### 2.1 Nova Tabela DynamoDB: Recommendations

**Estrutura:**
| Campo | Tipo | Descrição |
|-------|------|-----------|
| `recommendationId` (PK) | String | UUID único da recomendação |
| `clientId` | String | ID do cliente |
| `campaignId` | String | ID da campanha Google Ads |
| `status` | String | `PENDING`, `APPLIED`, `SKIPPED`, `EXPIRED` |
| `action` | String | Ação recomendada (INCREASE_CPC_10, REDUCE_CPC_15, etc.) |
| `metrics` | Map | Métricas no momento da geração (currentCpa, healthyCpa, etc.) |
| `payload` | Map | Payload completo da recomendação |
| `createdAt` | String | ISO timestamp da criação |
| `appliedAt` | String | ISO timestamp da aplicação (se aplicada) |
| `appliedBy` | String | Identificador de quem aplicou |
| `applicationResult` | Map | Resultado da aplicação (sucesso, erros, operações) |

**Índices:**
- **GSI `clientId-campaignId-index`**: Para query por clientId + campaignId
  - Partition Key: `clientId`
  - Sort Key: `campaignId#createdAt`

### 2.2 Modificações em `generate_recommendations.py`

- Gerar `recommendationId` único (UUID) para cada recomendação
- Salvar na nova tabela `Recommendations` ao invés de `campaign-metadata`
- Incluir `recommendationId` no retorno da API

### 2.3 Novo Handler: `apply_recommendation.py`

**Endpoint:** `POST /recommendations/{recommendationId}/apply`

**Body:**
```json
{
  "clientId": "string",
  "campaignId": "string"
}
```

**Fluxo:**
1. Buscar recomendação por `recommendationId`
2. Validar que `clientId` e `campaignId` correspondem
3. Verificar status != `APPLIED`
4. Executar aplicação via Google Ads API
5. Atualizar recomendação com `status=APPLIED`, `appliedAt`, `applicationResult`
6. Retornar resultado

**Respostas:**
- `200 OK`: Aplicação bem-sucedida
- `400 Bad Request`: clientId/campaignId não correspondem
- `404 Not Found`: Recomendação não existe
- `409 Conflict`: Recomendação já foi aplicada

### 2.4 Novo Handler: `list_recommendations.py`

**Endpoint:** `GET /recommendations?clientId={clientId}&campaignId={campaignId}`

**Query Params:**
- `clientId` (required): ID do cliente
- `campaignId` (optional): Filtrar por campanha específica
- `status` (optional): Filtrar por status (PENDING, APPLIED, etc.)

**Resposta:**
```json
{
  "recommendations": [
    {
      "recommendationId": "uuid",
      "campaignId": "123456789",
      "action": "INCREASE_CPC_10",
      "status": "PENDING",
      "metrics": {...},
      "createdAt": "2025-01-24T10:00:00Z"
    }
  ],
  "count": 1
}
```

---

## 3. Arquivos Afetados

### Novos Arquivos
- `sls/resources/recommendations-table.yml` - Definição da tabela DynamoDB
- `src/functions/recommendations/list_recommendations.py` - Handler para listar
- `src/functions/recommendations/apply_recommendation.py` - Handler para aplicar

### Arquivos Modificados
- `serverless.yml` - Adicionar novas funções e endpoints
- `src/functions/optimizer/generate_recommendations.py` - Salvar com recommendationId

### Arquivos Potencialmente Removidos
- Lógica de salvamento em `campaign-metadata` (migrar para nova tabela)

---

## 4. Dependências

- UUID library (já disponível via `uuid` do Python stdlib)
- Boto3 para DynamoDB (já instalado)
- Reutilizar `src/utils/http.py` para handlers
- Reutilizar `src/utils/decimal_utils.py` para conversões

---

## 5. Considerações

### Migração
- Recomendações existentes em `campaign-metadata` podem ser ignoradas
- Nova tabela começa vazia; histórico anterior não será migrado

### Performance
- GSI permite queries eficientes por clientId + campaignId
- PAY_PER_REQUEST para billing on-demand

### Segurança
- Validar API key em todos os endpoints
- Garantir que clientId na request corresponde ao da recomendação

---

## 6. Decisões Tomadas

1. **Expiração**: Sem expiração automática - recomendações permanecem PENDING indefinidamente
2. **Bulk Apply**: Não suportado - aplicar uma recomendação por vez
3. **Legacy Handler**: Remover `apply_recommendations.py` existente e usar apenas a nova abordagem baseada em recommendationId

---

## Histórico

| Data | Status | Notas |
|------|--------|-------|
| 2025-01-24 | Draft | PRD criado |
| 2025-01-24 | Spec Generated | Spec criada |
| 2025-01-24 | Implemented | Codigo implementado |
