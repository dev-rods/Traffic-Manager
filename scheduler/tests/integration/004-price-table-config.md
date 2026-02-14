# Integration Tests — 004 Price Table Configuration

> Guide for configuring the price table (services with pricing) via API.

## Setup

```bash
source scheduler/.env 2>/dev/null
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
API_KEY="YOUR_SCHEDULER_API_KEY"
CLINIC_ID="YOUR_CLINIC_ID"
```

---

## How the Price Table Works

The price table is displayed to patients in the WhatsApp conversation flow when they select **"Agendar sessao" > "Ver tabela de precos"**. It lists all active services with their name, duration, and price.

Prices are stored in **centavos** (`price_cents`) to avoid floating-point issues. For example, R$ 150.00 = `15000`.

If `price_cents` is not set (null/0), the service shows "Consultar" instead of a price.

---

## Test 1 — Create a service with price

```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name": "Depilacao a laser - Axilas",
    "duration_minutes": 30,
    "price_cents": 12000,
    "description": "Sessao de depilacao a laser na regiao das axilas"
  }'
```

**Expected:** HTTP 201, response includes `service.price_cents = 12000`.

---

## Test 2 — Create a service without price (shows "Consultar")

```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name": "Avaliacao inicial",
    "duration_minutes": 20,
    "description": "Consulta de avaliacao sem custo definido"
  }'
```

**Expected:** HTTP 201, response includes `service.price_cents = null`.

---

## Test 3 — Update a service price

```bash
SERVICE_ID="YOUR_SERVICE_ID"

curl -s -X PUT "$BASE_URL/$STAGE/services/$SERVICE_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "price_cents": 18000
  }'
```

**Expected:** HTTP 200, response includes `service.price_cents = 18000`.

---

## Test 4 — List all services (verify price table data)

```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "x-api-key: $API_KEY"
```

**Expected:** HTTP 200, array of services each with `name`, `duration_minutes`, `price_cents`.

---

## Test 5 — Deactivate a service (remove from price table)

```bash
SERVICE_ID="YOUR_SERVICE_ID"

curl -s -X PUT "$BASE_URL/$STAGE/services/$SERVICE_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "active": false
  }'
```

**Expected:** HTTP 200. Service no longer appears in the price table shown to patients.

---

## Test 6 — Verify price table display via WhatsApp flow

Simulate the patient flow to see the price table:

```bash
PHONE="5511999990000"
INSTANCE_ID="YOUR_INSTANCE_ID"

# 6a. Start conversation (WELCOME -> MAIN_MENU)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-PT-001\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"text\": {\"message\": \"Ola\"}
  }"

# 6b. Select "Agendar sessao" (MAIN_MENU -> SCHEDULE_MENU)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-PT-002\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonResponseMessage\": {\"selectedButtonId\": \"schedule\"}
  }"

# 6c. Select "Ver tabela de precos" (SCHEDULE_MENU -> PRICE_TABLE)
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d "{
    \"type\": \"ReceivedCallback\",
    \"instanceId\": \"$INSTANCE_ID\",
    \"messageId\": \"MSG-PT-003\",
    \"phone\": \"$PHONE\",
    \"fromMe\": false,
    \"momment\": $(date +%s)000,
    \"buttonResponseMessage\": {\"selectedButtonId\": \"price_table\"}
  }"
```

**Expected:** Bot sends a message listing all active services with formatted prices, e.g.:
```
- Depilacao a laser - Axilas (30min): R$ 120.00
- Avaliacao inicial (20min): Consultar
```

---

## Price Configuration Summary

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Service name displayed to patients |
| `duration_minutes` | integer | Yes | Duration in minutes |
| `price_cents` | integer | No | Price in centavos (e.g., 15000 = R$ 150.00). If null/0, shows "Consultar" |
| `description` | string | No | Internal description |
| `active` | boolean | No | Whether service appears in price table (default: true) |

### Common price examples

| Service | price_cents | Display |
|---------|-------------|---------|
| R$ 50.00 | `5000` | R$ 50.00 |
| R$ 120.00 | `12000` | R$ 120.00 |
| R$ 150.00 | `15000` | R$ 150.00 |
| R$ 250.50 | `25050` | R$ 250.50 |
| Not set | `null` | Consultar |
