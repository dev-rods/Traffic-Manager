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
│   ├── baseUrl
│   ├── apiKey
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
      "key": "baseUrl",
      "value": "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev",
      "type": "string"
    },
    {
      "key": "apiKey",
      "value": "YOUR_API_KEY_HERE",
      "type": "string"
    }
  ]
}
```

Add feature-specific variables as needed (clientId, campaignId, etc.).

## Request Structure

### Headers

All authenticated requests must include:
```json
{
  "header": [
    {
      "key": "x-api-key",
      "value": "{{apiKey}}",
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
| Collection file | `{feature}.postman_collection.json` | `recommendations.postman_collection.json` |
| Collection name | `Traffic Manager - {Feature}` | `Traffic Manager - Recommendations` |
| Request name | Action + Resource | `List Recommendations`, `Apply Recommendation` |
| Test case requests | Action + (Error Case) | `Apply Recommendation (Not Found)` |

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
4. Update `apiKey` variable with your actual API key

## Environment Variables

For team sharing, create a separate environment file:

```json
{
  "name": "Traffic Manager - Dev",
  "values": [
    {
      "key": "baseUrl",
      "value": "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev",
      "enabled": true
    },
    {
      "key": "apiKey",
      "value": "",
      "enabled": true,
      "type": "secret"
    }
  ]
}
```

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
    {"key": "baseUrl", "value": "https://nk0mrwvhca.execute-api.us-east-1.amazonaws.com/dev"},
    {"key": "apiKey", "value": "YOUR_API_KEY_HERE"}
  ],
  "item": [
    {
      "name": "Request Name",
      "event": [{"listen": "test", "script": {"exec": ["// tests"], "type": "text/javascript"}}],
      "request": {
        "method": "GET",
        "header": [{"key": "x-api-key", "value": "{{apiKey}}"}],
        "url": {"raw": "{{baseUrl}}/endpoint", "host": ["{{baseUrl}}"], "path": ["endpoint"]}
      },
      "response": []
    }
  ]
}
```

## Checklist Before Committing

- [ ] Collection file follows naming convention
- [ ] All endpoints are documented
- [ ] Test scripts validate responses
- [ ] Example responses included
- [ ] Variables use placeholders (no real API keys)
- [ ] Error cases are covered
- [ ] Collection imports successfully into Postman
