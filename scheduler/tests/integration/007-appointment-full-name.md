# Integration Tests — 007 Appointment Full Name, Global Commands e UX Improvements

> Guia de testes para a feature de nome completo no agendamento, comandos globais expandidos e melhorias de navegacao.

## Setup

```bash
source scheduler/.env 2>/dev/null
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
CLINIC_ID="YOUR_CLINIC_ID"
PHONE="5511999990000"
```

---

## Funcionalidades testadas

| Feature | Descricao |
|---------|-----------|
| ASK_FULL_NAME | Novo estado que pede nome completo antes da confirmacao |
| Casing preservado | Nome digitado mantem maiusculas/minusculas originais |
| Back do CONFIRM_BOOKING | Voltar da confirmacao pula ASK_FULL_NAME e vai para SELECT_TIME |
| full_name limpo no back | Sessao limpa full_name ao voltar, re-pede na proxima passagem |
| Comandos globais expandidos | Novos sinonimos para voltar, menu e atendente |
| Hints em free_text | Templates de texto livre mostram dica de navegacao |

---

## Cenarios de teste — Via webhook WhatsApp

> Todos os testes abaixo sao feitos enviando mensagens ao webhook.
> O webhook NAO requer API key.

### Test 1 — Nome completo com casing preservado

Simula usuario digitando nome com letras maiusculas no estado ASK_FULL_NAME.

```bash
# Enviar nome com casing misto
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-001",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746000000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "text": {"message": "André Conceição Silva"}
  }'
```

**Esperado:** Resposta de CONFIRM_BOOKING com nome exibido como `*André Conceição Silva*` (nao `*andré conceição silva*`).

---

### Test 2 — Voltar da confirmacao vai para SELECT_TIME

Quando usuario esta em CONFIRM_BOOKING e clica "Voltar", deve ir para SELECT_TIME (com botoes de horario), nao para ASK_FULL_NAME.

```bash
# Clicar botao "Voltar" na confirmacao
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-002",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746100000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "referenceMessageId": "MSG-PREV",
    "buttonsResponseMessage": {"buttonId": "back", "message": "Voltar"}
  }'
```

**Esperado:** Resposta de SELECT_TIME com botoes de horarios disponiveis (nao campo de texto para nome).

---

### Test 3 — Comando global "volta" (novo sinonimo)

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-003",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746200000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "text": {"message": "volta"}
  }'
```

**Esperado:** Navega para o estado anterior (mesmo comportamento de "voltar").

---

### Test 4 — Comando global "menu principal"

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-004",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746300000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "text": {"message": "menu principal"}
  }'
```

**Esperado:** Navega para MAIN_MENU com opcoes de agendar, remarcar, cancelar, etc.

---

### Test 5 — Comando global "ajuda" (novo sinonimo de humano)

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-005",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746400000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "text": {"message": "ajuda"}
  }'
```

**Esperado:** Navega para HUMAN_HANDOFF com mensagem de encaminhamento para atendente.

---

### Test 6 — Comando global "falar com atendente"

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-006",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746500000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "text": {"message": "falar com atendente"}
  }'
```

**Esperado:** Navega para HUMAN_HANDOFF.

---

### Test 7 — Comando "voltar" em estado free_text (ASK_FULL_NAME)

Verifica que digitar "voltar" no campo de nome nao eh interpretado como nome.

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-TEST-007",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1706746600000,
    "chatName": "Test User",
    "senderName": "Test User",
    "isGroup": false,
    "text": {"message": "voltar"}
  }'
```

**Esperado:** Navega para SELECT_TIME (anterior do ASK_FULL_NAME), nao salva "voltar" como nome.

---

### Test 8 — Hints visiveis em templates free_text

Ao entrar em ASK_FULL_NAME, SELECT_SERVICES ou SELECT_AREAS, a mensagem deve incluir a dica:
`_Digite "voltar" para retornar ou "menu" para o início._`

**Verificacao:** Observar no WhatsApp que a dica aparece em italico abaixo do texto principal.

---

## Tabela de comandos globais

| Comando | Acao | Novos sinonimos |
|---------|------|-----------------|
| voltar | Navega para estado anterior | volta, anterior, retornar, 0 |
| menu | Navega para MAIN_MENU | menu principal, inicio, reiniciar, começo |
| humano | Navega para HUMAN_HANDOFF | ajuda, suporte, falar com atendente, atendente humano, falar com humano |

---

## Testes unitarios locais

Os testes abaixo podem ser executados localmente sem API Gateway:

```bash
cd scheduler
python -c "
from src.services.conversation_engine import ConversationEngine, ConversationState, STATE_CONFIG
from src.providers.whatsapp_provider import IncomingMessage

def make_msg(content, button_id=None):
    return IncomingMessage(
        phone='5511999990000', content=content, message_id='test',
        sender_name='Test', timestamp=1706745600000, message_type='TEXT',
        button_id=button_id
    )

engine = ConversationEngine.__new__(ConversationEngine)
session = {'state': ConversationState.ASK_FULL_NAME.value}

# Casing preservado
assert engine._identify_input(make_msg('Andre Silva'), session) == 'Andre Silva'
# Voltar funciona em free_text
assert engine._identify_input(make_msg('Voltar'), session) == 'back'
# Novos sinonimos
assert engine._identify_input(make_msg('volta'), session) == 'back'
assert engine._identify_input(make_msg('menu principal'), session) == 'main_menu'
assert engine._identify_input(make_msg('ajuda'), session) == 'human'
# CONFIRM_BOOKING.previous == SELECT_TIME
assert STATE_CONFIG[ConversationState.CONFIRM_BOOKING]['previous'] == ConversationState.SELECT_TIME
# full_name salvo com casing
s = {}
engine._get_free_text_next_state(ConversationState.ASK_FULL_NAME, 'Maria Santos', s)
assert s['full_name'] == 'Maria Santos'

print('Todos os testes passaram!')
"
```
