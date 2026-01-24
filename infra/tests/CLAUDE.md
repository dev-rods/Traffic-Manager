# CLAUDE.md - Testing Standards

This file provides guidance to Claude Code for testing in the Traffic Manager project.

## Testing Strategy

### Test Types

| Type | Location | Purpose |
|------|----------|---------|
| Mock Data | `tests/mocks/` | JSON payloads for local Lambda invocation |
| Integration Tests | `tests/integration/` | Documented API endpoint tests |
| Unit Tests | `tests/unit/` | Python unit tests (pytest) |

### Directory Structure

```
tests/
├── CLAUDE.md              # This file
├── mocks/                 # Mock payloads organized by domain
│   ├── recommendations/   # Recommendations endpoint mocks
│   ├── optimizer/         # Optimizer endpoint mocks
│   ├── scripts/           # Script manager mocks
│   └── ...
├── integration/           # Integration test documentation
│   └── {feature}.md       # Test cases and curl commands
├── postman/               # Postman collections for API testing
│   ├── CLAUDE.md          # Postman collection standards
│   └── {feature}.postman_collection.json
└── unit/                  # Python unit tests (future)
```

## Testing Workflow

### 1. Local Testing with Mocks

Use `serverless invoke local` with mock JSON files:

```bash
# Invoke a function locally with mock data
serverless invoke local -s dev -f FunctionName -p tests/mocks/domain/mock_file.json --aws-profile traffic-manager
```

### 2. Integration Testing

After deploying to dev, run integration tests against live endpoints:

```bash
# See tests/integration/{feature}.md for curl commands
curl -X GET "https://{api-id}.execute-api.us-east-1.amazonaws.com/dev/endpoint" \
  -H "x-api-key: YOUR_API_KEY"
```

### 3. Documenting Tests

For each new feature, create:
1. **Mock files** in `tests/mocks/{domain}/` for local testing
2. **Integration doc** in `tests/integration/{feature}.md` with:
   - Test cases table
   - curl commands
   - Expected responses

## Mock File Format

### HTTP Event Mock (API Gateway)

```json
{
  "httpMethod": "POST",
  "path": "/endpoint/path",
  "pathParameters": {
    "paramName": "value"
  },
  "queryStringParameters": {
    "queryParam": "value"
  },
  "headers": {
    "Content-Type": "application/json",
    "x-api-key": "test-api-key"
  },
  "body": "{\"key\": \"value\"}",
  "requestContext": {
    "stage": "dev",
    "requestId": "test-request-id"
  }
}
```

### Direct Invocation Mock (Scheduled/Step Functions)

```json
{
  "clientId": "client-id",
  "campaignId": "123456789",
  "source": "test"
}
```

## Integration Test Documentation Format

Each `tests/integration/{feature}.md` should include:

```markdown
# {Feature} Integration Tests

## Endpoints
| Method | Path | Description |
|--------|------|-------------|

## Test Cases
| # | Test Case | Expected Status | Expected Response |
|---|-----------|-----------------|-------------------|

## Setup
Prerequisites and test data needed.

## Test Commands
Curl commands for each test case.

## Cleanup
Steps to clean up test data.
```

## Environment Variables for Testing

For local testing, ensure these are set:
- `RECOMMENDATIONS_TABLE`
- `CLIENTS_TABLE`
- `EXECUTION_HISTORY_TABLE`
- Other tables as needed

## Best Practices

1. **Use real client/campaign IDs** in integration tests for dev environment
2. **Always test validation cases** (missing params, wrong IDs, already applied)
3. **Use `dryRun: true`** when testing mutations to avoid side effects
4. **Document expected responses** for each test case
5. **Keep mock data up-to-date** with API changes

## Running Tests Before PR

Before creating a PR, ensure:
1. All integration tests pass in dev
2. Mock files are created for new endpoints
3. Integration documentation is complete
4. Postman collection is created/updated (see `tests/postman/CLAUDE.md`)

## Postman Collections

After thorough testing, create a Postman collection for the feature:
- Location: `tests/postman/{feature}.postman_collection.json`
- Standards: See `tests/postman/CLAUDE.md`
- Include: All endpoints, test scripts, example responses
