# Integration Tests — 008 Patient Soft-Delete

> Testes para soft-delete de pacientes e restore on recreate (REST + WhatsApp).

## Setup

```bash
source scheduler/.env
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
CLINIC_ID="clinic-test"
PHONE="5511999990000"
```

---

## Funcionalidades testadas

| Feature | Descricao |
|---------|-----------|
| DELETE patient | Soft-delete via DELETE /clinics/{id}/patients/{patientId} |
| DELETE idempotente | Re-delete em paciente ja deletado retorna 200 |
| DELETE 404 | Paciente inexistente retorna 404 |
| LIST exclui deletados | GET /patients nao retorna pacientes com deleted_at |
| UPDATE em deletado | PATCH em paciente deletado retorna 404 |
| Restore via POST | POST com phone de paciente deletado restaura (status=RESTORED) |
| Restore via WhatsApp | Mensagem do mesmo phone re-ativa o paciente |

---

## Cenarios de teste

### Test 1 — Criar e deletar paciente

```bash
# 1. Criar paciente novo
RESPONSE=$(curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Joao Teste","phone":"'$PHONE'","gender":"M"}')
echo "$RESPONSE" | jq

PATIENT_ID=$(echo "$RESPONSE" | jq -r '.patient.id')
echo "Patient ID: $PATIENT_ID"
```

**Esperado:** 201 com `status: "CREATED"` e patient com `deleted_at: null`.

```bash
# 2. Deletar paciente
curl -s -X DELETE "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients/$PATIENT_ID" \
  -H "x-api-key: $API_KEY" | jq
```

**Esperado:** 200 com `status: "SUCCESS"`, `message: "Paciente excluido"`.

---

### Test 2 — DELETE idempotente

```bash
# Re-deletar o mesmo paciente
curl -s -X DELETE "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients/$PATIENT_ID" \
  -H "x-api-key: $API_KEY" | jq
```

**Esperado:** 200 com `message: "Paciente ja estava excluido"`.

---

### Test 3 — DELETE em paciente inexistente

```bash
curl -s -X DELETE "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients/00000000-0000-0000-0000-000000000099" \
  -H "x-api-key: $API_KEY" | jq
```

**Esperado:** 404 com `message: "Paciente nao encontrado"`.

---

### Test 4 — LIST nao retorna deletados

```bash
curl -s "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients?search=$PHONE" \
  -H "x-api-key: $API_KEY" | jq '.items | length'
```

**Esperado:** `0` (paciente deletado nao aparece).

---

### Test 5 — UPDATE em paciente deletado

```bash
curl -s -X PATCH "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients/$PATIENT_ID" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Outro Nome"}' | jq
```

**Esperado:** 404.

---

### Test 6 — Restore via POST

```bash
RESPONSE=$(curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Joao Restaurado","phone":"'$PHONE'","gender":"M"}')
echo "$RESPONSE" | jq
```

**Esperado:** 200 com `status: "RESTORED"`, mesmo `id` do Test 1, `name: "Joao Restaurado"`, `deleted_at: null`.

---

### Test 7 — POST em paciente ativo (duplicado) retorna 409

```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Outro","phone":"'$PHONE'","gender":"F"}' | jq
```

**Esperado:** 409 com `message: "Ja existe um paciente com esse telefone"`.

---

### Test 8 — Restore via WhatsApp

```bash
# 1. Deletar paciente novamente
curl -s -X DELETE "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients/$PATIENT_ID" \
  -H "x-api-key: $API_KEY"

# 2. Enviar webhook WhatsApp do mesmo phone
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "instance-123",
    "messageId": "MSG-RESTORE-001",
    "phone": "'$PHONE'",
    "fromMe": false,
    "momment": 1714000000000,
    "chatName": "Paciente",
    "senderName": "Paciente",
    "isGroup": false,
    "text": {"message": "Oi"}
  }'

# 3. Confirmar via API que paciente voltou
curl -s "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients?search=$PHONE" \
  -H "x-api-key: $API_KEY" | jq '.items[0]'
```

**Esperado:**
- `_on_enter_welcome` trata como **novo** paciente (nome em branco apos delete) — saudacao generica.
- `_get_or_create_patient` (acionado durante o flow) restaura o registro existente. Verificar via SQL:

```sql
SELECT id, name, deleted_at FROM scheduler.patients WHERE phone = '5511999990000';
-- deleted_at deve ser NULL
```

---

### Test 9 — Histórico em appointments preservado

```bash
# Confirmar que appointments do paciente deletado ainda aparecem na agenda
curl -s "$BASE_URL/$STAGE/clinics/$CLINIC_ID/appointments?date=YYYY-MM-DD" \
  -H "x-api-key: $API_KEY" | jq '.items[] | select(.patient_phone == "'$PHONE'")'
```

**Esperado:** Appointments anteriores ao delete continuam visiveis com nome do paciente.

---

## Cleanup

```bash
# Deletar paciente do teste para deixar estado limpo
curl -s -X DELETE "$BASE_URL/$STAGE/clinics/$CLINIC_ID/patients/$PATIENT_ID" \
  -H "x-api-key: $API_KEY"
```
