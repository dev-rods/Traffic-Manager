# CLAUDE.md - Postman Collection Standards

This file provides guidance for creating and maintaining Postman collections for the Traffic Manager API.

## When to Create Postman Collections

Create or update Postman collections after:
1. Implementing new API endpoints
2. Completing integration testing
3. Changing endpoint contracts (request/response formats)

## Collection Structure

Each feature should have its own collection file: `{feature}.postman_collection.json`

### Required Elements

```
Collection
├── info
│   ├── name: "Traffic Manager - {Feature}"
│   ├── description: Overview of endpoints
│   └── schema: Postman 2.1.0
├── variable (collection variables)
│   ├── BASE_URL
│   ├── ENVIRONMENT
│   ├── API_KEY
│   └── {feature-specific variables}
└── item (requests)
    └── {Request}
        ├── name
        ├── request (method, headers, body, url)
        ├── event (test scripts)
        └── response (example responses)
```

## Collection Variables

Always define these base variables:

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

Add feature-specific variables as needed (clientId, campaignId, leadId, etc.).

## URL Format

All URLs must use the format `{{BASE_URL}}/{{ENVIRONMENT}}/endpoint`

```json
{
  "url": {
    "raw": "{{BASE_URL}}/{{ENVIRONMENT}}/leads",
    "host": ["{{BASE_URL}}"],
    "path": ["{{ENVIRONMENT}}", "leads"]
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

## Request Structure

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
1. Success case (200/201)
2. Validation errors (400)
3. Not found (404)
4. Conflict/Already exists (409)
5. Server error (500) if applicable

## Naming Conventions

| Element | Convention | Example |
|---------|------------|---------|
| Collection file | `{feature}.postman_collection.json` | `leads.postman_collection.json` |
| Collection name | `Traffic Manager - {Feature}` | `Traffic Manager - Leads` |
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

2. **Create Postman collection:**
   ```bash
   # Create collection file
   tests/postman/{feature}.postman_collection.json
   ```

3. **Include in collection:**
   - All CRUD operations
   - Query parameter variations
   - Error cases (validation, not found, conflicts)
   - Example responses from actual tests

4. **Test the collection:**
   - Import into Postman
   - Run collection runner
   - Verify all tests pass

5. **Commit with feature:**
   ```bash
   git add tests/postman/{feature}.postman_collection.json
   ```

## Importing Collections

To import into Postman:
1. Open Postman
2. Click "Import" button
3. Select the `.postman_collection.json` file
4. Update `API_KEY` variable with your actual API key

## Environment Setup

The collection uses these variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `BASE_URL` | API Gateway URL (without stage) | `https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com` |
| `ENVIRONMENT` | Deployment stage | `dev` or `prod` |
| `API_KEY` | Your API key | (from .env file) |

To switch environments, simply change the `ENVIRONMENT` variable value.

## Example Collection Template

```json
{
  "info": {
    "_postman_id": "{feature}-collection",
    "name": "Traffic Manager - {Feature}",
    "description": "Description of the feature endpoints.",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "variable": [
    {"key": "BASE_URL", "value": "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com"},
    {"key": "ENVIRONMENT", "value": "dev"},
    {"key": "API_KEY", "value": "YOUR_API_KEY_HERE"}
  ],
  "item": [
    {
      "name": "Create Resource",
      "event": [
        {
          "listen": "test",
          "script": {
            "exec": [
              "pm.test(\"Status code is 201\", function () {",
              "    pm.response.to.have.status(201);",
              "});"
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
          "raw": "{\n    \"field\": \"value\"\n}"
        },
        "url": {
          "raw": "{{BASE_URL}}/{{ENVIRONMENT}}/endpoint",
          "host": ["{{BASE_URL}}"],
          "path": ["{{ENVIRONMENT}}", "endpoint"]
        }
      },
      "response": []
    }
  ]
}
```

## Checklist Before Committing

- [ ] Collection file follows naming convention (`{feature}.postman_collection.json`)
- [ ] All endpoints are documented
- [ ] URLs use `{{BASE_URL}}/{{ENVIRONMENT}}/...` format
- [ ] Headers use `{{API_KEY}}` (not hardcoded)
- [ ] Test scripts validate responses
- [ ] Example responses included
- [ ] Error cases are covered
- [ ] Collection imports successfully into Postman
