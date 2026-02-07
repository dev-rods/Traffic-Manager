# Integration Tests — 002 Fix Availability Bugs

> Spec: `docs/work/spec/002-fix-availability-bugs.md`

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

## Test 1 — Verify day_of_week mapping (availability rules match)

**Precondition:** Availability rule exists for the target day (e.g., `day_of_week=1` for Monday).

```bash
# 1a. List existing rules to confirm day_of_week values
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "x-api-key: $API_KEY" | python -m json.tool

# 1b. Query available slots for a Monday (should return slots if rule exists for day_of_week=1)
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-09&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY" | python -m json.tool
```

**Expected:** Response contains `"data": ["09:00", "10:00", ...]` (non-empty list).

---

## Test 2 — Verify Sunday fix (day_of_week=0)

**Precondition:** Availability rule with `day_of_week=0` (Sunday) exists.

```bash
# 2a. Create Sunday rule if missing
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 0, "start_time": "09:00", "end_time": "17:00"}'

# 2b. Query available slots for a Sunday (2026-02-08 is a Sunday)
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-08&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY" | python -m json.tool
```

**Expected:** Non-empty slots list. Before the fix, this always returned `[]` for Sundays.

---

## Test 3 — Session extraction: date button populates selected_date

Simulates the full scheduling flow via webhook. Each step requires the previous step's state.

```bash
# 3a. Start conversation (WELCOME -> MAIN_MENU)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T3-001\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"text\": {\"message\": \"Ola\"}
  }"

# 3b. Select "Agendar sessao" (MAIN_MENU -> SCHEDULE_MENU)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T3-002\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"schedule\", \"message\": \"Agendar sessao\"}
  }"

# 3c. Select "Ver dias disponiveis" (SCHEDULE_MENU -> AVAILABLE_DAYS)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T3-003\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"schedule_now\", \"message\": \"Ver dias disponiveis\"}
  }"

# 3d. Select a date (AVAILABLE_DAYS -> SELECT_TIME) — THIS IS THE KEY TEST
#     Replace 2026-02-09 with a date that appeared in the available days response
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T3-004\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"day_2026-02-09\", \"message\": \"2026-02-09\"}
  }"
```

**Expected (step 3d):** Response message shows available time slots (e.g., "1 - 09:00\n2 - 10:00\n..."), **NOT** "Nenhum horario disponivel".

---

## Test 4 — Session extraction: time button populates selected_time

Continue from Test 3.

```bash
# 4a. Select a time (SELECT_TIME -> INPUT_AREAS)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T4-001\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"time_09:00\", \"message\": \"09:00\"}
  }"
```

**Expected:** Transitions to INPUT_AREAS state and prompts user to enter treatment areas.

---

## Test 5 — Reschedule flow: newday/newtime extraction

**Precondition:** Patient has an active (CONFIRMED) appointment.

```bash
# 5a. Start conversation
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T5-001\",
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
    \"messageId\": \"MSG-T5-002\",
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
    \"messageId\": \"MSG-T5-003\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"newday_2026-02-10\", \"message\": \"2026-02-10\"}
  }"

# 5d. Select new time
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-T5-004\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonsResponseMessage\": {\"buttonId\": \"newtime_15:00\", \"message\": \"15:00\"}
  }"
```

**Expected (5c):** Shows available time slots for the new date, not "Nenhum horario disponivel".
**Expected (5d):** Transitions to CONFIRM_RESCHEDULE with correct date/time in confirmation message.

---

## Checklist

- [ ] Test 1: Weekday slots returned correctly
- [ ] Test 2: Sunday slots returned (was broken before fix)
- [ ] Test 3: Date button click shows time slots (was showing "Nenhum horario disponivel")
- [ ] Test 4: Time button click transitions to INPUT_AREAS
- [ ] Test 5: Reschedule flow extracts newday/newtime correctly
