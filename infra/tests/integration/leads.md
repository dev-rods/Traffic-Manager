# Leads Integration Tests

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/leads` | Create a new lead |
| GET | `/leads` | List leads for a client |
| GET | `/leads/{leadId}` | Get a specific lead by ID |

## Test Data

```bash
# Load from .env file - NEVER hardcode API keys
source .env
CLIENT_ID="empresarodsteste-bd5f23"
BASE_URL="https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev"
```

## Test Cases

### POST /leads

| # | Test Case | Body | Expected Status | Expected Response |
|---|-----------|------|-----------------|-------------------|
| 1 | Create without API key | Valid body | 401 | `{"message": "API key nao fornecida"}` |
| 2 | Create without body | - | 400 | `{"status": "ERROR", "message": "Request body e obrigatorio"}` |
| 3 | Create without clientId | Missing clientId | 400 | `{"status": "ERROR", "message": "Campos obrigatorios ausentes: clientId"}` |
| 4 | Create without name | Missing name | 400 | `{"status": "ERROR", "message": "Campos obrigatorios ausentes: name"}` |
| 5 | Create without email | Missing email | 400 | `{"status": "ERROR", "message": "Campos obrigatorios ausentes: email"}` |
| 6 | Create valid lead | All required fields | 201 | `{"status": "SUCCESS", "leadId": "uuid", ...}` |
| 7 | Create with all fields | All fields including optional | 201 | Full lead object returned |

### GET /leads

| # | Test Case | Query Params | Expected Status | Expected Response |
|---|-----------|--------------|-----------------|-------------------|
| 1 | List without API key | `clientId=X` | 401 | `{"message": "API key nao fornecida"}` |
| 2 | List without clientId | - | 400 | `{"status": "ERROR", "message": "clientId e obrigatorio..."}` |
| 3 | List all for client | `clientId=X` | 200 | `{"status": "SUCCESS", "leads": [...], "count": N}` |
| 4 | List with limit | `clientId=X&limit=5` | 200 | Max 5 results |
| 5 | List with date filter | `clientId=X&startDate=Y` | 200 | Filtered results |
| 6 | No results | `clientId=nonexistent` | 200 | `{"status": "SUCCESS", "leads": [], "count": 0}` |

### GET /leads/{leadId}

| # | Test Case | Path | Expected Status | Expected Response |
|---|-----------|------|-----------------|-------------------|
| 1 | Get without API key | Valid leadId | 401 | `{"message": "API key nao fornecida"}` |
| 2 | Get non-existent | `/leads/non-existent-id` | 404 | `{"status": "NOT_FOUND", ...}` |
| 3 | Get valid lead | `/leads/{validId}` | 200 | `{"status": "SUCCESS", "lead": {...}}` |

---

## Test Commands

### Setup

```bash
# Load environment variables
cd /path/to/Traffic-Manager/infra
source .env

# Set test variables
CLIENT_ID="empresarodsteste-bd5f23"
BASE_URL="https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev"
```

---

### Test 1: Create without API key

```bash
curl -s -X POST "$BASE_URL/leads" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "test", "name": "Test", "email": "test@example.com"}'
```

Expected: `{"message": "API key nao fornecida"}`

---

### Test 2: Create without body

```bash
curl -s -X POST "$BASE_URL/leads" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json"
```

Expected: `{"status": "ERROR", "message": "Request body e obrigatorio"}`

---

### Test 3: Create without required fields

```bash
curl -s -X POST "$BASE_URL/leads" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test"}'
```

Expected: `{"status": "ERROR", "message": "Campos obrigatorios ausentes: clientId, email"}`

---

### Test 4: Create valid lead (minimal)

```bash
curl -s -X POST "$BASE_URL/leads" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"clientId\": \"$CLIENT_ID\", \"name\": \"Test Lead\", \"email\": \"test@example.com\"}"
```

Expected:
```json
{
  "status": "SUCCESS",
  "message": "Lead registrado com sucesso",
  "leadId": "uuid-here",
  "lead": {
    "leadId": "uuid-here",
    "clientId": "empresarodsteste-bd5f23",
    "name": "Test Lead",
    "email": "test@example.com",
    "phone": "",
    "location": "",
    "source": "web-form",
    "createdAt": "2026-01-24T...",
    "metadata": {}
  }
}
```

---

### Test 5: Create valid lead (all fields)

```bash
curl -s -X POST "$BASE_URL/leads" \
  -H "x-api-key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"clientId\": \"$CLIENT_ID\",
    \"name\": \"John Doe\",
    \"email\": \"john@example.com\",
    \"phone\": \"+55 11 99999-9999\",
    \"location\": \"Sao Paulo, SP\",
    \"source\": \"landing-page\",
    \"metadata\": {\"campaign\": \"google-ads\"}
  }"
```

Expected: 201 with full lead object

---

### Test 6: List without clientId

```bash
curl -s "$BASE_URL/leads" \
  -H "x-api-key: $API_KEY"
```

Expected: `{"status": "ERROR", "message": "clientId e obrigatorio como query parameter"}`

---

### Test 7: List leads for client

```bash
curl -s "$BASE_URL/leads?clientId=$CLIENT_ID" \
  -H "x-api-key: $API_KEY"
```

Expected:
```json
{
  "status": "SUCCESS",
  "leads": [...],
  "count": N,
  "clientId": "empresarodsteste-bd5f23"
}
```

---

### Test 8: List with limit

```bash
curl -s "$BASE_URL/leads?clientId=$CLIENT_ID&limit=5" \
  -H "x-api-key: $API_KEY"
```

Expected: Maximum 5 results

---

### Test 9: Get non-existent lead

```bash
curl -s "$BASE_URL/leads/non-existent-id" \
  -H "x-api-key: $API_KEY"
```

Expected:
```json
{
  "status": "NOT_FOUND",
  "message": "Lead nao encontrado",
  "leadId": "non-existent-id"
}
```

---

### Test 10: Get valid lead

```bash
# Replace with actual leadId from create test
LEAD_ID="6140ecf2-2ef1-49e0-884e-2762f6c019da"

curl -s "$BASE_URL/leads/$LEAD_ID" \
  -H "x-api-key: $API_KEY"
```

Expected:
```json
{
  "status": "SUCCESS",
  "lead": {
    "leadId": "6140ecf2-2ef1-49e0-884e-2762f6c019da",
    "clientId": "empresarodsteste-bd5f23",
    "name": "John Doe",
    "email": "john@example.com",
    ...
  }
}
```

---

## Test Results Log

### 2026-01-24 - Initial Implementation

| Test | Status | Notes |
|------|--------|-------|
| Create without API key | PASS | Returns 401 |
| Create valid lead | PASS | Returns 201 with leadId |
| List leads for client | PASS | Returns leads array |
| Get lead by ID | PASS | Returns lead object |

---

## Cleanup

To clean up test leads:
1. Use AWS Console to delete items from `traffic-manager-infra-dev-leads` table
2. Or let them remain as historical test data
