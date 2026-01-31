# Postman Collections - Clinic Scheduler

## Conventions

- **Naming**: `{domain}.postman_collection.json`
- **Collection name**: `Clinic Scheduler - {Domain}`
- **Schema**: Postman Collection v2.1.0

## Variables (all collections)

| Variable | Default | Description |
|----------|---------|-------------|
| `BASE_URL` | `https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com` | API Gateway base URL |
| `ENVIRONMENT` | `dev` | Stage (dev/prod) |
| `API_KEY` | `YOUR_API_KEY_HERE` | Scheduler API key |
| `clinicId` | `` | Auto-set by Create Clinic test |

## Headers

All authenticated requests must include:
- `x-api-key: {{API_KEY}}`
- `Content-Type: application/json`

Exception: Webhook endpoints (`/webhook/whatsapp` and `/webhook/whatsapp/status`) do not require API key.

## URL Pattern

`{{BASE_URL}}/{{ENVIRONMENT}}/path`

## Test Scripts

Every request must include test scripts that:
1. Validate HTTP status code
2. Validate response structure (`status` field)
3. Set collection variables when creating resources (e.g., `clinicId`, `serviceId`)

## Response Examples

Each request should include response examples for:
- Success case
- Common error cases (400, 404, 409)
