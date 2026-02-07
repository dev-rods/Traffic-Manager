# Integration Tests — 003 Date Format BR (DD/MM/YYYY)

> Spec: `docs/work/spec/003-date-format-br.md`

## Setup

```bash
source scheduler/.env 2>/dev/null
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
API_KEY="YOUR_SCHEDULER_API_KEY"
CLINIC_ID="YOUR_CLINIC_ID"
SERVICE_ID="YOUR_SERVICE_ID"
PHONE="5511999990000"
INSTANCE_ID="YOUR_INSTANCE_ID"
```

---

## Test 1 — Available days display DD/MM/YYYY (button labels + text list)

Simulates the scheduling flow up to AVAILABLE_DAYS to verify dates are in Brazilian format.

```bash
# 1a. Start conversation (WELCOME -> MAIN_MENU)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-001\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"text\": {\"message\": \"Ola\"}
  }"

# 1b. Select "Agendar sessao" (MAIN_MENU -> SCHEDULE_MENU)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-002\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"schedule\", \"message\": \"Agendar sessao\"}
  }"

# 1c. Select "Agendar agora" (SCHEDULE_MENU -> AVAILABLE_DAYS)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-003\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"schedule_now\", \"message\": \"Agendar agora\"}
  }"
```

**Expected (step 1c):**
- WhatsApp message text contains dates as `DD/MM/YYYY` (e.g., `1 - 10/02/2026`)
- Button labels show `DD/MM/YYYY` (e.g., `10/02/2026`), NOT `2026-02-10`
- Button IDs remain in ISO format (e.g., `day_2026-02-10`) — internal, not visible to user

---

## Test 2 — Select Time shows DD/MM/YYYY in header

Continue from Test 1. Click a date button to reach SELECT_TIME.

```bash
# 2a. Select a date (AVAILABLE_DAYS -> SELECT_TIME)
#     Replace 2026-02-09 with a date from step 1c response
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-004\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"day_2026-02-09\", \"message\": \"09/02/2026\"}
  }"
```

**Expected:** Message says `Horarios disponiveis para 09/02/2026:` (DD/MM/YYYY), NOT `2026-02-09`.

---

## Test 3 — Confirm Booking shows DD/MM/YYYY

Continue from Test 2 through time selection and area input.

```bash
# 3a. Select time (SELECT_TIME -> INPUT_AREAS)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-005\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"time_09:00\", \"message\": \"09:00\"}
  }"

# 3b. Enter areas (INPUT_AREAS -> CONFIRM_BOOKING)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-006\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"text\": {\"message\": \"Pernas e axilas\"}
  }"
```

**Expected (step 3b):** Confirmation message shows `09/02/2026 as 09:00` (DD/MM/YYYY), NOT `2026-02-09`.

---

## Test 4 — Booked message shows DD/MM/YYYY

Continue from Test 3.

```bash
# 4a. Confirm (CONFIRM_BOOKING -> BOOKED)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-007\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"confirm\", \"message\": \"Confirmar\"}
  }"
```

**Expected:** Message says `Te esperamos no dia 09/02/2026 as 09:00` (DD/MM/YYYY).

---

## Test 5 — Reschedule flow shows DD/MM/YYYY

**Precondition:** Patient has an active (CONFIRMED) appointment.

```bash
# 5a. Start conversation
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-R01\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"text\": {\"message\": \"Ola\"}
  }"

# 5b. Select "Remarcar sessao"
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-R02\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"reschedule\", \"message\": \"Remarcar sessao\"}
  }"

# 5c. Select new date
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-R03\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"newday_2026-02-10\", \"message\": \"10/02/2026\"}
  }"

# 5d. Select new time
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-R04\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"newtime_15:00\", \"message\": \"15:00\"}
  }"

# 5e. Confirm reschedule
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-D3-R05\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"confirm\", \"message\": \"Confirmar\"}
  }"
```

**Expected (5b):** "Encontramos seu agendamento: **DD/MM/YYYY** as HH:MM" + reschedule day buttons with DD/MM/YYYY labels
**Expected (5c):** "Horarios disponiveis para **10/02/2026**:"
**Expected (5d):** Confirmation with "**10/02/2026** as 15:00"
**Expected (5e):** "Agendamento remarcado! Nova data: **10/02/2026** as 15:00"

---

## Checklist

- [ ] Test 1: Available days text list shows DD/MM/YYYY
- [ ] Test 1: Available days button labels show DD/MM/YYYY
- [ ] Test 2: Select Time header shows DD/MM/YYYY
- [ ] Test 3: Confirm Booking shows DD/MM/YYYY
- [ ] Test 4: Booked message shows DD/MM/YYYY
- [ ] Test 5b: Reschedule lookup shows current appointment date in DD/MM/YYYY
- [ ] Test 5b: Reschedule day buttons show DD/MM/YYYY labels
- [ ] Test 5c: Select New Time header shows DD/MM/YYYY
- [ ] Test 5d: Confirm Reschedule shows DD/MM/YYYY
- [ ] Test 5e: Rescheduled message shows DD/MM/YYYY
- [ ] All flows: Internal btn_id stays YYYY-MM-DD (verify via CloudWatch logs)
