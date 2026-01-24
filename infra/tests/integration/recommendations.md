# Recommendations Integration Tests

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/recommendations` | List recommendations for a client |
| POST | `/recommendations/{recommendationId}/apply` | Apply a specific recommendation |

## Test Data

```json
{
  "clientId": "empresarodsteste-bd5f23",
  "campaignId": "22656250465",
  "apiKey": "ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0"
}
```

## Test Cases

### GET /recommendations

| # | Test Case | Query Params | Expected Status | Expected Response |
|---|-----------|--------------|-----------------|-------------------|
| 1 | List without API key | `clientId=X` | 401 | `{"message": "API key nao fornecida"}` |
| 2 | List without clientId | - | 400 | `{"status": "ERROR", "message": "clientId e obrigatorio..."}` |
| 3 | List all for client | `clientId=X` | 200 | `{"status": "SUCCESS", "recommendations": [...], "count": N}` |
| 4 | Filter by campaignId | `clientId=X&campaignId=Y` | 200 | Filtered results |
| 5 | Filter by status | `clientId=X&status=PENDING` | 200 | Only PENDING recommendations |
| 6 | No results | `clientId=nonexistent` | 200 | `{"status": "SUCCESS", "recommendations": [], "count": 0}` |

### POST /recommendations/{recommendationId}/apply

| # | Test Case | Body | Expected Status | Expected Response |
|---|-----------|------|-----------------|-------------------|
| 1 | Apply without API key | `{}` | 401 | `{"message": "API key nao fornecida"}` |
| 2 | Apply without body params | `{}` | 400 | `{"status": "ERROR", "message": "clientId e campaignId sao obrigatorios..."}` |
| 3 | Apply non-existent ID | Valid body | 404 | `{"status": "NOT_FOUND", ...}` |
| 4 | Apply with wrong clientId | Mismatched clientId | 400 | `{"status": "MISMATCH", ...}` |
| 5 | Apply with wrong campaignId | Mismatched campaignId | 400 | `{"status": "MISMATCH", ...}` |
| 6 | Apply already applied | Previously applied rec | 409 | `{"status": "ALREADY_APPLIED", ...}` |
| 7 | Apply with dryRun | `{"...", "dryRun": true}` | 200 | Operations with `dryRun: true` |
| 8 | Apply NO_DATA action | Rec with NO_DATA action | 400 | `{"status": "ERROR", "message": "Acao desconhecida: NO_DATA"}` |
| 9 | Apply valid action | Valid INCREASE_CPC rec | 200 | `{"status": "SUCCESS", "operations": [...]}` |

---

## Test Commands

### Setup: Generate a Recommendation First

```bash
# Generate recommendations for the test client
curl -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/optimizer" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "empresarodsteste-bd5f23", "campaignId": "22656250465"}'
```

Expected response:
```json
{
  "status": "SUCCESS",
  "timestamp": "2026-01-24T19:17:53.061016",
  "totalRecommendations": 1,
  "recommendations": [{
    "recommendationId": "865016fd-dd1f-4710-914a-59e50df48a88",
    "clientId": "empresarodsteste-bd5f23",
    "campaignId": "22656250465",
    "campaignName": "Campaign #1",
    "action": "NO_DATA",
    "currentCpa": 0.0,
    "healthyCpa": 136.08
  }]
}
```

---

### Test 1: List without API key

```bash
curl -s "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations?clientId=empresarodsteste-bd5f23"
```

Expected: `{"message": "API key nao fornecida"}`

---

### Test 2: List without clientId

```bash
curl -s "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0"
```

Expected: `{"status": "ERROR", "message": "clientId e obrigatorio como query parameter"}`

---

### Test 3: List all recommendations for client

```bash
curl -s "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations?clientId=empresarodsteste-bd5f23" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0"
```

Expected:
```json
{
  "status": "SUCCESS",
  "recommendations": [{
    "recommendationId": "865016fd-dd1f-4710-914a-59e50df48a88",
    "clientId": "empresarodsteste-bd5f23",
    "campaignId": "22656250465",
    "status": "PENDING",
    "action": "NO_DATA",
    ...
  }],
  "count": 1
}
```

---

### Test 4: Filter by campaignId

```bash
curl -s "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations?clientId=empresarodsteste-bd5f23&campaignId=22656250465" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0"
```

Expected: Same as Test 3, filtered to specific campaign

---

### Test 5: Filter by status

```bash
curl -s "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations?clientId=empresarodsteste-bd5f23&status=PENDING" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0"
```

Expected: Only recommendations with `status: PENDING`

---

### Test 6: Apply non-existent recommendation

```bash
curl -s -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations/non-existent-id/apply" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "empresarodsteste-bd5f23", "campaignId": "22656250465"}'
```

Expected:
```json
{
  "status": "NOT_FOUND",
  "recommendationId": "non-existent-id",
  "message": "Recomendacao nao encontrada"
}
```

---

### Test 7: Apply with wrong clientId

```bash
curl -s -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations/865016fd-dd1f-4710-914a-59e50df48a88/apply" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "wrong-client", "campaignId": "22656250465"}'
```

Expected:
```json
{
  "status": "MISMATCH",
  "message": "clientId ou campaignId nao correspondem a recomendacao"
}
```

---

### Test 8: Apply with dryRun

```bash
curl -s -X POST "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev/recommendations/{recommendationId}/apply" \
  -H "x-api-key: ae9bfaa64f0110468e69d36e00ad04efca63805bb0b419f27a9105e6c37b5ce0" \
  -H "Content-Type: application/json" \
  -d '{"clientId": "empresarodsteste-bd5f23", "campaignId": "22656250465", "dryRun": true}'
```

Expected: Operations with `dryRun: true` in details

---

## Test Results Log

### 2026-01-24 - Initial Implementation

| Test | Status | Notes |
|------|--------|-------|
| List without API key | PASS | Returns 401 |
| List without clientId | PASS | Returns 400 |
| List all for client | PASS | Returns recommendations array |
| Filter by campaignId | PASS | Filters correctly |
| Filter by status | PASS | Filters correctly |
| Apply non-existent ID | PASS | Returns 404 NOT_FOUND |
| Apply wrong clientId | PASS | Returns 400 MISMATCH |
| Apply NO_DATA action | PASS | Returns 400 "Acao desconhecida" |

---

## Cleanup

To clean up test recommendations:
1. Use AWS Console to delete items from `traffic-manager-infra-dev-recommendations` table
2. Or let them remain as historical test data
