# CLAUDE.md - Postman Request List Standards

This file provides guidance for creating and maintaining Postman request lists for the Traffic Manager API.

## Important: Request Lists, Not Collections

We create **request lists** that can be imported into an existing Postman collection, NOT standalone collections. This allows us to maintain a single organized collection with all Traffic Manager endpoints.

## When to Create Postman Request Lists

Create or update request lists after:
1. Implementing new API endpoints
2. Completing integration testing
3. Changing endpoint contracts (request/response formats)

## File Structure

Each feature should have its own request list file: `{feature}.postman_requests.json`

### Required Elements

```
Request List (item array)
└── item[] (array of requests)
    └── {Request}
        ├── name
        ├── request (method, headers, body, url)
        ├── event (test scripts)
        └── response (example responses)
```

## Base URL Format

**IMPORTANT:** All URLs must use the format `{{BASE_URL}}/{{ENVIRONMENT}}/endpoint`

- `{{BASE_URL}}`: The API Gateway base URL (e.g., `https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com`)
- `{{ENVIRONMENT}}`: The deployment stage (e.g., `dev`, `prod`)

These variables are defined at the collection level, not in each request list.

## Collection Variables (defined at collection level)

The main collection defines these variables:

```json
{
  "variable": [
    {
      "key": "BASE_URL",
      "value": "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com",
      "type": "string"
    },
    {
      "key": "ENVIRONMENT",
      "value": "dev",
      "type": "string"
    },
    {
      "key": "API_KEY",
      "value": "YOUR_API_KEY_HERE",
      "type": "string"
    }
  ]
}
```

Feature-specific variables (clientId, leadId, etc.) should also be added to the main collection.

## Request Structure

### URL Format

All URLs must follow this pattern:
```json
{
  "url": {
    "raw": "{{BASE_URL}}/{{ENVIRONMENT}}/endpoint",
    "host": ["{{BASE_URL}}"],
    "path": ["{{ENVIRONMENT}}", "endpoint"]
  }
}
```

For endpoints with path parameters:
```json
{
  "url": {
    "raw": "{{BASE_URL}}/{{ENVIRONMENT}}/leads/{{leadId}}",
    "host": ["{{BASE_URL}}"],
    "path": ["{{ENVIRONMENT}}", "leads", "{{leadId}}"]
  }
}
```

### Headers

All authenticated requests must include:
```json
{
  "header": [
    {
      "key": "x-api-key",
      "value": "{{API_KEY}}",
      "type": "text"
    },
    {
      "key": "Content-Type",
      "value": "application/json",
      "type": "text"
    }
  ]
}
```

### Test Scripts

Include test scripts for each request:

```javascript
// Basic status check
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

// Response structure validation
pm.test("Response has expected structure", function () {
    var jsonData = pm.response.json();
    pm.expect(jsonData.status).to.eql("SUCCESS");
    pm.expect(jsonData).to.have.property('data');
});

// Save variables for chained requests
var jsonData = pm.response.json();
if (jsonData.id) {
    pm.collectionVariables.set("resourceId", jsonData.id);
}
```

### Example Responses

Always include example responses for:
1. Success case (200)
2. Validation errors (400)
3. Not found (404)
4. Conflict/Already exists (409)
5. Server error (500) if applicable

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Request list file | `{feature}.postman_requests.json` | `leads.postman_requests.json` |
| Request name | Action + Resource | `List Leads`, `Create Lead` |
| Test case requests | Action + (Error Case) | `Create Lead (Missing Fields)` |

## Request Organization

Organize requests in logical order:
1. Create/Generate operations first
2. List/Get operations
3. Update/Apply operations
4. Delete operations
5. Error test cases at the end

## Workflow for New Features

1. **After implementing endpoints:**
   - Run integration tests (see `tests/integration/{feature}.md`)
   - Document all test cases

2. **Create Postman request list:**
   ```bash
   # Create request list file
   tests/postman/{feature}.postman_requests.json
   ```

3. **Include in request list:**
   - All CRUD operations
   - Query parameter variations
   - Error cases (validation, not found, conflicts)
   - Example responses from actual tests

4. **Import into Postman:**
   - Open the main Traffic Manager collection
   - Right-click and select "Import"
   - Select the `.postman_requests.json` file
   - Requests will be added to the collection

5. **Test the requests:**
   - Run each request manually or use collection runner
   - Verify all tests pass

6. **Commit with feature:**
   ```bash
   git add tests/postman/{feature}.postman_requests.json
   ```

## Importing Request Lists

To import requests into the main collection:
1. Open Postman
2. Open the "Traffic Manager" collection
3. Click "Import" button
4. Select the `.postman_requests.json` file
5. Requests will be added to the collection

## Environment Setup

The main collection uses these variables (set at collection level):

| Variable | Description | Example |
|----------|-------------|---------|
| `BASE_URL` | API Gateway URL (without stage) | `https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com` |
| `ENVIRONMENT` | Deployment stage | `dev` or `prod` |
| `API_KEY` | Your API key | (from .env file) |

To switch environments, simply change the `ENVIRONMENT` variable value.

## Example Request List Template

```json
{
  "item": [
    {
      "name": "Create Lead",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test(\"Status code is 201\", function () {",
              "    pm.response.to.have.status(201);",
              "});",
              "",
              "pm.test(\"Response has leadId\", function () {",
              "    var jsonData = pm.response.json();",
              "    pm.expect(jsonData.status).to.eql(\"SUCCESS\");",
              "    pm.expect(jsonData).to.have.property('leadId');",
              "});",
              "",
              "// Save leadId for next requests",
              "var jsonData = pm.response.json();",
              "if (jsonData.leadId) {",
              "    pm.collectionVariables.set(\"leadId\", jsonData.leadId);",
              "}"
            ],
            "type": "text/javascript"
          }
        }
      ],
      "request": {
        "method": "POST",
        "header": [
          {"key": "x-api-key", "value": "{{API_KEY}}", "type": "text"},
          {"key": "Content-Type", "value": "application/json", "type": "text"}
        ],
        "body": {
          "mode": "raw",
          "raw": "{\n    \"clientId\": \"{{clientId}}\",\n    \"name\": \"Test Lead\",\n    \"email\": \"test@example.com\"\n}"
        },
        "url": {
          "raw": "{{BASE_URL}}/{{ENVIRONMENT}}/leads",
          "host": ["{{BASE_URL}}"],
          "path": ["{{ENVIRONMENT}}", "leads"]
        }
      },
      "response": []
    },
    {
      "name": "List Leads",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test(\"Status code is 200\", function () {",
              "    pm.response.to.have.status(200);",
              "});",
              "",
              "pm.test(\"Response has leads array\", function () {",
              "    var jsonData = pm.response.json();",
              "    pm.expect(jsonData.leads).to.be.an('array');",
              "});"
            ],
            "type": "text/javascript"
          }
        }
      ],
      "request": {
        "method": "GET",
        "header": [
          {"key": "x-api-key", "value": "{{API_KEY}}", "type": "text"}
        ],
        "url": {
          "raw": "{{BASE_URL}}/{{ENVIRONMENT}}/leads?clientId={{clientId}}",
          "host": ["{{BASE_URL}}"],
          "path": ["{{ENVIRONMENT}}", "leads"],
          "query": [
            {"key": "clientId", "value": "{{clientId}}"}
          ]
        }
      },
      "response": []
    }
  ]
}
```

## Checklist Before Committing

- [ ] Request list file follows naming convention (`{feature}.postman_requests.json`)
- [ ] All endpoints are documented
- [ ] URLs use `{{BASE_URL}}/{{ENVIRONMENT}}/...` format
- [ ] Headers use `{{API_KEY}}` (not hardcoded)
- [ ] Test scripts validate responses
- [ ] Example responses included
- [ ] Error cases are covered
- [ ] Requests import successfully into Postman collection
