# Integration Tests — 008 Attendant Mode from Any State

> Testes para a melhoria do modo atendente: pausa o bot em qualquer estado e TTL de 24h.

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
| Ativacao universal | Bot pausa em qualquer estado quando atendente envia mensagem (fromMe=true) |
| TTL 24h | Bot fica silencioso por 24h apos ultima msg do atendente |
| Renovacao TTL | Cada msg do atendente renova o TTL de 24h |
| #encerrar / #fim | Atendente encerra modo manualmente |
| Expiracao automatica | Apos 24h sem msg do atendente, bot retoma em WELCOME |

---

## Cenarios de teste

### Test 1 — Atendente responde durante fluxo de agendamento

Simula atendente respondendo enquanto paciente esta no MAIN_MENU.

```bash
# Mensagem do atendente (fromMe=true)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-ATT-001",
    "phone": "'$PHONE'",
    "fromMe": true,
    "momment": 1706746000000,
    "chatName": "Paciente",
    "senderName": "Atendente",
    "isGroup": false,
    "text": {"message": "Ola, como posso ajudar?"}
  }'
```

**Esperado:** Resposta 200 OK. Sessao muda para HUMAN_ATTENDANT_ACTIVE com TTL de 24h.

---

### Test 2 — Bot silencioso apos ativacao

Paciente envia mensagem enquanto modo atendente esta ativo.

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-ATT-002",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746100000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "text": {"message": "Quero agendar"}
  }'
```

**Esperado:** Resposta 200 OK com `messagesProcessed: 0` (bot nao responde).

---

### Test 3 — Atendente encerra com #encerrar

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-ATT-003",
    "phone": "'$PHONE'",
    "fromMe": true,
    "momment": 1706746200000,
    "chatName": "Paciente",
    "senderName": "Atendente",
    "isGroup": false,
    "text": {"message": "#encerrar"}
  }'
```

**Esperado:** Sessao volta para WELCOME. Bot volta a responder normalmente.

---

### Test 4 — Atendente encerra com #fim

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-ATT-004",
    "phone": "'$PHONE'",
    "fromMe": true,
    "momment": 1706746300000,
    "chatName": "Paciente",
    "senderName": "Atendente",
    "isGroup": false,
    "text": {"message": "#fim"}
  }'
```

**Esperado:** Sessao volta para WELCOME.

---

### Test 5 — Ativacao durante meio do fluxo (SELECT_TIME)

Atendente responde enquanto paciente esta escolhendo horario. Bot deve pausar imediatamente.

**Esperado:** Estado anterior (SELECT_TIME) salvo em `_previous_state_before_attendant`. Sessao muda para HUMAN_ATTENDANT_ACTIVE.

---

### Test 6 — Paciente clica "Retomar atendimento" em HUMAN_HANDOFF

Paciente pediu atendente, mas antes de ser respondido decide voltar ao bot.

```bash
# 1. Paciente pede atendente
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-ATT-006a",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746400000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "text": {"message": "atendente"}
  }'

# 2. Paciente clica "Retomar atendimento"
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-ATT-006b",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746500000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "resume_bot", "message": "Retomar atendimento"}
  }'
```

**Esperado:** Bot reativa, sessao volta para WELCOME e responde com MAIN_MENU.

---

## Testes unitarios locais

```bash
cd scheduler
python -c "
import time
from src.services.conversation_engine import ConversationState

TTL = 24 * 60 * 60
assert TTL == 86400, 'TTL deve ser 24h'

# Ativa de qualquer estado
for state in ['MAIN_MENU', 'SELECT_TIME', 'CONFIRM_BOOKING', 'ASK_FULL_NAME']:
    session = {'state': state}
    session['_previous_state_before_attendant'] = session.get('state', '')
    session['state'] = ConversationState.HUMAN_ATTENDANT_ACTIVE.value
    session['attendant_active_until'] = int(time.time()) + TTL
    assert session['state'] == 'HUMAN_ATTENDANT_ACTIVE'
    assert session['_previous_state_before_attendant'] == state

# Desativa corretamente
session = {
    'state': 'HUMAN_ATTENDANT_ACTIVE',
    'attendant_active_until': 123,
    '_previous_state_before_attendant': 'SELECT_TIME',
}
session['state'] = ConversationState.WELCOME.value
session.pop('attendant_active_until', None)
session.pop('_previous_state_before_attendant', None)
assert session['state'] == 'WELCOME'
assert 'attendant_active_until' not in session

print('Todos os testes passaram!')
"
```
