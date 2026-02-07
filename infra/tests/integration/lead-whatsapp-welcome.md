# Lead WhatsApp Welcome Integration Tests

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | /leads | Cria lead e opcionalmente envia WhatsApp welcome |

## Test Cases

| # | Test Case | clinicId | Expected Status | WhatsApp Status |
|---|-----------|----------|-----------------|-----------------|
| 1 | Criar lead sem clinicId (sem WhatsApp) | - | 201 | N/A |
| 2 | Criar lead com clinicId valido | laser-beauty-sp-abc123 | 201 | SENT |
| 3 | Criar lead com clinicId invalido | clinica-inexistente | 201 | FAILED |
| 4 | Criar lead com clinicId sem phone | laser-beauty-sp-abc123 | 400 | N/A (phone required) |

## Setup

Prerequisitos:
- Scheduler project deployado com funcao SendMessage ativa
- SSM parameter `/${stage}/SCHEDULER_API_KEY` configurado
- Clinica `laser-beauty-sp-abc123` cadastrada no scheduler
- API key do infra configurada no `.env`

## Test Commands

### Test 1: Criar lead sem clinicId (sem WhatsApp)

```bash
source .env

curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/leads" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "empresarodsteste-bd5f23",
    "name": "Joao Teste",
    "phone": "5511999999999",
    "email": "joao@example.com"
  }'
```

**Resposta esperada (201):**
```json
{
  "status": "SUCCESS",
  "message": "Lead registrado com sucesso",
  "leadId": "uuid",
  "lead": {
    "leadId": "uuid",
    "clientId": "empresarodsteste-bd5f23",
    "name": "Joao Teste",
    "phone": "5511999999999",
    "email": "joao@example.com",
    "location": "",
    "source": "web-form",
    "createdAt": "2026-02-07T...",
    "metadata": {}
  }
}
```

### Test 2: Criar lead com clinicId valido (WhatsApp enviado)

```bash
source .env

curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/leads" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "empresarodsteste-bd5f23",
    "name": "Maria Silva",
    "phone": "5511999999999",
    "email": "maria@example.com",
    "clinicId": "laser-beauty-sp-abc123"
  }'
```

**Resposta esperada (201):**
```json
{
  "status": "SUCCESS",
  "message": "Lead registrado com sucesso",
  "leadId": "uuid",
  "lead": {
    "leadId": "uuid",
    "clientId": "empresarodsteste-bd5f23",
    "name": "Maria Silva",
    "phone": "5511999999999",
    "email": "maria@example.com",
    "location": "",
    "source": "web-form",
    "createdAt": "2026-02-07T...",
    "metadata": {},
    "clinicId": "laser-beauty-sp-abc123",
    "whatsappStatus": "SENT",
    "whatsappMessageId": "uuid",
    "whatsappSentAt": "2026-02-07T..."
  }
}
```

### Test 3: Criar lead com clinicId invalido (WhatsApp falha)

```bash
source .env

curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/leads" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clientId": "empresarodsteste-bd5f23",
    "name": "Carlos Erro",
    "phone": "5511999999999",
    "email": "carlos@example.com",
    "clinicId": "clinica-inexistente"
  }'
```

**Resposta esperada (201):** Lead criado com sucesso, mas `whatsappStatus: "FAILED"` e `whatsappError` preenchido.

## Cleanup

Leads de teste podem ser consultados via `GET /leads?clientId=empresarodsteste-bd5f23` para verificacao.
