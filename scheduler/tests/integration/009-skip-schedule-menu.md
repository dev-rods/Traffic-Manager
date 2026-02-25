# Integration Tests — 009 Skip Schedule Menu

> Testes para o skip do SCHEDULE_MENU: ao clicar "Agendar sessão", vai direto para seleção de áreas.

## Setup

```bash
source scheduler/.env 2>/dev/null
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
PHONE="5511999990000"
```

---

## Funcionalidades testadas

| Feature | Descricao |
|---------|-----------|
| Skip SCHEDULE_MENU | Botão "Agendar sessão" vai direto para SELECT_SERVICES (auto-skip) → SELECT_AREAS |
| Back navigation | "Voltar" em SELECT_AREAS retorna para MAIN_MENU (não SCHEDULE_MENU) |
| Preços nas áreas | Preços são exibidos na listagem de áreas |

---

## Cenarios de teste

### Test 1 — Agendar sessão vai direto para áreas

```bash
# Primeiro, iniciar conversa
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-SKIP-001",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706750000000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "text": {"message": "Oi"}
  }'

# Clicar em "Agendar sessão"
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-SKIP-002",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706750100000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "buttonResponseMessage": {"selectedButtonId": "schedule", "title": "Agendar sessão"}
  }'
```

**Esperado:** Resposta 200 OK. Sessão pula SCHEDULE_MENU, auto-seleciona serviço único e vai para SELECT_AREAS mostrando áreas com preços.

---

### Test 2 — Voltar de SELECT_AREAS vai para MAIN_MENU

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-SKIP-003",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706750200000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "text": {"message": "voltar"}
  }'
```

**Esperado:** Sessão volta para MAIN_MENU (não SCHEDULE_MENU).

---

## Verificação nos logs

```bash
cd scheduler && serverless logs -f WhatsAppWebhook --stage dev --aws-profile dev-andre --startTime 5m | grep -E "(Transition|skipped|auto-selecting)"
```

**Esperado:**
```
Transition: MAIN_MENU -> SELECT_SERVICES (input='schedule')
_on_enter_select_services: single service 'Depilação a Laser' -> auto-selecting
on_enter redirected: SELECT_SERVICES -> SELECT_AREAS
Back navigation: skipped services, redirecting to MAIN_MENU
Transition: SELECT_AREAS -> MAIN_MENU (input='back')
```
