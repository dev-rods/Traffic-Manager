# Integration Tests — 005 Areas CRUD e Associacao Service-Areas

> Guia de testes para os endpoints de Areas (CRUD independente) e associacao Service-Areas.

## Setup

```bash
source scheduler/.env 2>/dev/null
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
API_KEY="YOUR_SCHEDULER_API_KEY"
CLINIC_ID="YOUR_CLINIC_ID"
SERVICE_ID="YOUR_SERVICE_ID"
```

---

## Endpoints

### Areas (CRUD independente)

| Metodo | Rota | Descricao |
|--------|------|-----------|
| POST | `/clinics/{clinicId}/areas` | Criar area(s) |
| GET | `/clinics/{clinicId}/areas` | Listar areas da clinica |
| GET | `/areas/{areaId}` | Buscar area por ID |
| PUT | `/areas/{areaId}` | Atualizar area |
| DELETE | `/areas/{areaId}` | Soft delete da area |

### Service-Areas (associacao)

| Metodo | Rota | Descricao |
|--------|------|-----------|
| POST | `/services/{serviceId}/areas` | Associar areas a um servico |
| GET | `/services/{serviceId}/areas` | Listar areas do servico |
| DELETE | `/services/{serviceId}/areas/{areaId}` | Remover associacao |

---

## Pre-requisitos

- Clinica criada (`CLINIC_ID` disponivel)
- Servico criado (`SERVICE_ID` disponivel)
- `API_KEY` configurada no `.env`

---

## Casos de Teste — Areas CRUD

### Test 1 — Criar area individual

```bash
source scheduler/.env 2>/dev/null

curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/areas" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pernas",
    "display_order": 1
  }'
```

**Esperado:** HTTP 201. Resposta contem o objeto da area criada:

```json
{
  "area": {
    "id": "uuid",
    "clinic_id": "CLINIC_ID",
    "name": "Pernas",
    "display_order": 1,
    "active": true,
    "created_at": "2026-02-14T..."
  }
}
```

---

### Test 2 — Criar areas em lote

```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/areas" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '[
    {"name": "Axilas", "display_order": 2},
    {"name": "Braco", "display_order": 3},
    {"name": "Virilha", "display_order": 4},
    {"name": "Rosto", "display_order": 5}
  ]'
```

**Esperado:** HTTP 201. Resposta contem array com todas as areas criadas:

```json
{
  "areas": [
    {"id": "uuid-1", "name": "Axilas", "display_order": 2, "active": true},
    {"id": "uuid-2", "name": "Braco", "display_order": 3, "active": true},
    {"id": "uuid-3", "name": "Virilha", "display_order": 4, "active": true},
    {"id": "uuid-4", "name": "Rosto", "display_order": 5, "active": true}
  ]
}
```

---

### Test 3 — Criar area sem campos obrigatorios (erro)

```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/areas" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Esperado:** HTTP 400. Mensagem indicando campo `name` obrigatorio.

```json
{
  "error": "Field 'name' is required"
}
```

---

### Test 4 — Listar areas da clinica

```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/areas" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 200. Array de areas ordenadas por `display_order`:

```json
{
  "areas": [
    {"id": "uuid", "name": "Pernas", "display_order": 1, "active": true},
    {"id": "uuid", "name": "Axilas", "display_order": 2, "active": true},
    {"id": "uuid", "name": "Braco", "display_order": 3, "active": true}
  ]
}
```

---

### Test 5 — Buscar area por ID

```bash
AREA_ID="YOUR_AREA_ID"

curl -s -X GET "$BASE_URL/$STAGE/areas/$AREA_ID" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 200. Objeto da area:

```json
{
  "area": {
    "id": "AREA_ID",
    "clinic_id": "CLINIC_ID",
    "name": "Pernas",
    "display_order": 1,
    "active": true,
    "created_at": "2026-02-14T...",
    "updated_at": "2026-02-14T..."
  }
}
```

---

### Test 6 — Area nao encontrada

```bash
curl -s -X GET "$BASE_URL/$STAGE/areas/00000000-0000-0000-0000-000000000000" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 404.

```json
{
  "error": "Area not found"
}
```

---

### Test 7 — Atualizar area

```bash
AREA_ID="YOUR_AREA_ID"

curl -s -X PUT "$BASE_URL/$STAGE/areas/$AREA_ID" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Pernas Completas",
    "display_order": 10
  }'
```

**Esperado:** HTTP 200. Resposta com dados atualizados:

```json
{
  "area": {
    "id": "AREA_ID",
    "name": "Pernas Completas",
    "display_order": 10,
    "active": true,
    "updated_at": "2026-02-14T..."
  }
}
```

---

### Test 8 — Soft delete de area

```bash
AREA_ID="YOUR_AREA_ID"

curl -s -X DELETE "$BASE_URL/$STAGE/areas/$AREA_ID" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 200. Area marcada como inativa (soft delete):

```json
{
  "message": "Area deleted successfully"
}
```

Apos o delete, a area nao deve aparecer na listagem (GET `/clinics/{clinicId}/areas`).

---

### Test 9 — Deletar area inexistente

```bash
curl -s -X DELETE "$BASE_URL/$STAGE/areas/00000000-0000-0000-0000-000000000000" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 404.

```json
{
  "error": "Area not found"
}
```

---

## Casos de Teste — Service-Areas (associacao)

### Test 10 — Associar areas a um servico

```bash
AREA_ID_1="YOUR_AREA_ID_1"
AREA_ID_2="YOUR_AREA_ID_2"

curl -s -X POST "$BASE_URL/$STAGE/services/$SERVICE_ID/areas" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"area_ids\": [\"$AREA_ID_1\", \"$AREA_ID_2\"]
  }"
```

**Esperado:** HTTP 201. Associacoes criadas:

```json
{
  "message": "Areas associated successfully",
  "service_id": "SERVICE_ID",
  "area_ids": ["AREA_ID_1", "AREA_ID_2"]
}
```

---

### Test 11 — Associar area inexistente a servico (erro)

```bash
curl -s -X POST "$BASE_URL/$STAGE/services/$SERVICE_ID/areas" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "area_ids": ["00000000-0000-0000-0000-000000000000"]
  }'
```

**Esperado:** HTTP 404.

```json
{
  "error": "Area not found: 00000000-0000-0000-0000-000000000000"
}
```

---

### Test 12 — Associar sem area_ids (erro)

```bash
curl -s -X POST "$BASE_URL/$STAGE/services/$SERVICE_ID/areas" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**Esperado:** HTTP 400.

```json
{
  "error": "Field 'area_ids' is required"
}
```

---

### Test 13 — Listar areas do servico

```bash
curl -s -X GET "$BASE_URL/$STAGE/services/$SERVICE_ID/areas" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 200. Array de areas associadas ao servico (dados vindos do JOIN com tabela `areas`):

```json
{
  "service_id": "SERVICE_ID",
  "areas": [
    {"id": "AREA_ID_1", "name": "Pernas", "display_order": 1},
    {"id": "AREA_ID_2", "name": "Axilas", "display_order": 2}
  ]
}
```

---

### Test 14 — Listar areas de servico sem associacoes

```bash
curl -s -X GET "$BASE_URL/$STAGE/services/$SERVICE_ID/areas" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 200. Array vazio:

```json
{
  "service_id": "SERVICE_ID",
  "areas": []
}
```

---

### Test 15 — Remover associacao area-servico

```bash
AREA_ID="YOUR_AREA_ID"

curl -s -X DELETE "$BASE_URL/$STAGE/services/$SERVICE_ID/areas/$AREA_ID" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 200.

```json
{
  "message": "Area association removed successfully"
}
```

Apos remocao, a area nao deve aparecer no GET `/services/{serviceId}/areas`.

---

### Test 16 — Remover associacao inexistente

```bash
curl -s -X DELETE "$BASE_URL/$STAGE/services/$SERVICE_ID/areas/00000000-0000-0000-0000-000000000000" \
  -H "x-api-key: $API_KEY"
```

**Esperado:** HTTP 404.

```json
{
  "error": "Association not found"
}
```

---

## Verificacao do Fluxo WhatsApp

O fluxo completo de agendamento via WhatsApp deve considerar as areas:

```
Paciente envia "Ola"
  -> Bot exibe MENU_PRINCIPAL
  -> Paciente seleciona "Agendar sessao"
  -> Bot exibe lista de SERVICOS
  -> Paciente seleciona servico (ex: "Depilacao a laser")
  -> Bot consulta service_areas JOIN areas para o servico selecionado
  -> Bot exibe lista de AREAS do servico (ex: "Pernas", "Axilas", "Virilha")
  -> Paciente seleciona area(s)
  -> Bot segue para selecao de DATA e HORARIO
  -> Confirmacao do agendamento
```

### Simulacao via webhook

```bash
PHONE="5511999990000"
INSTANCE_ID="YOUR_INSTANCE_ID"

# 1. Inicio da conversa
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-AREA-001\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"text\": {\"message\": \"Ola\"}
  }"

# 2. Selecionar "Agendar sessao"
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-AREA-002\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonResponseMessage\": {\"selectedButtonId\": \"schedule\"}
  }"

# 3. Selecionar servico (ex: service_UUID)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-AREA-003\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"listResponseMessage\": {\"selectedRowId\": \"service_$SERVICE_ID\"}
  }"

# 4. Selecionar area (ex: area_UUID)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-AREA-004\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"listResponseMessage\": {\"selectedRowId\": \"area_$AREA_ID\"}
  }"
```

**Esperado:** Apos selecionar a area, o bot deve avancar para a etapa de selecao de data, mostrando os dias disponiveis para agendamento.

---

## Resumo dos Campos

### Area

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `name` | string | Sim | Nome da area exibido ao paciente |
| `display_order` | integer | Nao | Ordem de exibicao na lista (menor = primeiro) |
| `active` | boolean | Nao | Se a area esta ativa (default: true) |

### Service-Area (associacao)

| Campo | Tipo | Obrigatorio | Descricao |
|-------|------|-------------|-----------|
| `area_ids` | array[string] | Sim | Lista de IDs de areas para associar ao servico |
