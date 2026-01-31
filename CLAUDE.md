# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow de Desenvolvimento (Research → Spec → Code → Test → Document)

Siga este processo em **5 etapas** para novas features, refatorações e remoção de código.

| Fase | Input do usuário | Ação do Claude | Output |
|------|------------------|----------------|--------|
| **1. Pesquisa** | "Preciso implementar X" / "Refatorar Y" / "Eliminar código Z" | Pesquisar codebase (`infra/src/`, `infra/sls/`, `infra/docs/`), padrões em `CLAUDE.md`, dependências | `docs/work/prd/XXX-nome.md` (PRD) |
| **2. Spec** | "Leia `docs/work/prd/XXX-nome.md` e gere uma spec" | Ler o PRD e detalhar arquivos a criar/modificar/remover, alterações por arquivo, ordem de implementação | `docs/work/spec/XXX-nome.md` (Spec) |
| **3. Code** | "Implemente `docs/work/spec/XXX-nome.md`" | Implementar seguindo a Spec; respeitar `CLAUDE.md` (logging, naming, secrets) | Código no repositório |
| **4. Test** | "Teste os endpoints" | Executar testes manuais via curl (usando API_KEY do `.env`), verificar respostas | Testes passando |
| **5. Document** | "Crie a documentação" | Criar docs de integração e Postman request list | `tests/integration/{feature}.md`, `tests/postman/{feature}.postman_requests.json` |

- **Artefatos:** PRDs em `docs/work/prd/`, Specs em `docs/work/spec/`. Templates em `docs/work/_templates/`.
- **Nomes:** use ID único por task (ex: `001-refator-auth`, `002-remove-legacy`). Mesmo ID no PRD e na Spec.
- **Documentação pós-task:** atualizar o PRD com Status (Spec gerada, data de implementação) e registrar em `TASKS_LOG.md`.

### Pós-implementação (obrigatório)

Após implementar o código, sempre:

1. **Testar endpoints** - Executar curl commands usando `API_KEY` do arquivo `.env`
2. **Criar mocks** - Adicionar arquivos JSON em `tests/mocks/{domain}/` para testes locais
3. **Documentar testes** - Criar `tests/integration/{feature}.md` com casos de teste
4. **Criar Postman requests** - Criar `tests/postman/{feature}.postman_requests.json` seguindo o padrão em `tests/postman/CLAUDE.md`

Detalhes: `docs/work/README.md`.

---

## Project Overview

Traffic Manager is an AWS Lambda-based system for automated Google Ads campaign optimization using AI. It provides Lambda functions for campaign management, client management, and AI-powered optimization recommendations.

## Build & Deploy Commands

```bash
# Install dependencies
npm install                      # Node.js (Serverless plugins)
pip install -r requirements.txt  # Python dependencies

# Deploy (builds Docker, pushes to ECR, deploys Lambda)
serverless deploy --stage dev --aws-profile traffic-manager
serverless deploy --stage prod --aws-profile traffic-manager

# Manual Docker build (optional)
.\scripts\build-and-push-image.ps1 -stage dev -region us-east-1  # Windows
./scripts/build-and-push-image.sh dev us-east-1                  # Linux/Mac
```

## Testing Commands

```bash
# Invoke functions locally with mock data
serverless invoke local -s dev -f CampaignOrchestrator --aws-profile traffic-manager
serverless invoke local -s dev -f ScriptManager -p tests/mocks/scripts/manager/list_clients.json --aws-profile traffic-manager

# View function logs
serverless logs -f CampaignOrchestrator --stage dev --aws-profile traffic-manager

# Run standalone scripts
python src/scripts/list_clients.py
python src/scripts/manage_mcc_links.py
```

## Architecture

### Key Directories
- `infra/src/functions/` - Lambda handlers organized by domain (campaign, googleads, openai, etc.)
- `infra/src/services/` - Business logic (Google Ads client management, token management)
- `infra/src/utils/` - Utilities (encryption, auth, logging)
- `infra/sls/resources/` - CloudFormation resources (DynamoDB tables)
- `infra/tests/mocks/` - Mock payloads for local testing

### Data Stores (DynamoDB)
- `Clients` - Client info with encrypted Google Ads credentials
- `ExecutionHistory` - Trace of each optimization run
- `CampaignTemplates` - Templates for new campaign creation
- `CampaignMetadata` - Campaign tracking data

### External Integrations
- Google Ads API (campaign management)
- OpenAI API (optimization recommendations)
- Google OAuth 2.0 (authentication)

## Code Patterns

### Logging with trace correlation
```python
logger.info(f"[traceId: {trace_id}] Message with context")
```

### Google Ads client initialization
```python
from google.ads.googleads.client import GoogleAdsClient
google_ads_config = {
    'developer_token': config['developerToken'],
    'client_id': config['clientId'],
    'client_secret': config['clientSecret'],
    'refresh_token': config['refreshToken'],
    'use_proto_plus': True,
}
client = GoogleAdsClient.load_from_dict(google_ads_config)
```

### Secrets management
- Secrets stored in AWS Systems Manager (SSM) under `/${stage}/KEY_NAME`
- Client credentials encrypted with Fernet in DynamoDB
- **NEVER hardcode API keys** in code, documentation, or markdown files
- Use `.env` file for local testing (already in `.gitignore`)
- In bash tests, load API key from `.env`: `source .env && curl -H "x-api-key: $API_KEY" ...`

## Naming Conventions
- Client IDs: lowercase kebab-case (e.g., `empresarods-abc123`)
- Lambda functions: PascalCase in serverless.yml (e.g., `CampaignOrchestrator`)
- Handlers: Python module paths (e.g., `src.functions.campaign.orchestrator.handler`)
- DynamoDB tables: `${resourcePrefix}-${tableName}` prefix

---

## Scheduler Project

WhatsApp-based clinic appointment scheduling system. Located in `scheduler/` directory (separate project in monorepo).

### Build & Deploy

```bash
cd scheduler && npm install && pip install -r requirements.txt
cd scheduler && serverless deploy --stage dev --aws-profile traffic-manager
cd scheduler && serverless deploy --stage prod --aws-profile traffic-manager
```

### Key Directories
- `scheduler/src/functions/` - Lambda handlers by domain (webhook, send, clinic, service, professional, availability, appointment, template, faq, reminder, report)
- `scheduler/src/services/` - Business logic (conversation_engine, availability_engine, appointment_service, message_tracker, reminder_service, sheets_sync, template_service)
- `scheduler/src/providers/` - WhatsApp provider abstraction (z-api implementation)
- `scheduler/src/utils/` - Utilities (http, auth, logging, phone, decimal)
- `scheduler/sls/functions/` - Serverless function interface files
- `scheduler/sls/resources/` - DynamoDB table definitions
- `scheduler/tests/mocks/` - Mock payloads for local testing
- `scheduler/tests/postman/` - Postman collections for API documentation

### Data Stores
- **DynamoDB**: ConversationSessions (TTL 30min), MessageEvents (3 GSIs, TTL 90d), ScheduledReminders (1 GSI, TTL 48h)
- **PostgreSQL RDS** (shared instance, schema `scheduler`): clinics, services, professionals, availability_rules, availability_exceptions, patients, appointments, message_templates, faq_items

### External Integrations
- z-api (WhatsApp messaging)
- Google Sheets API (appointment sync)

### Scheduler Naming Conventions
- clinic_id: lowercase kebab-case (e.g., `laser-beauty-sp-abc123`)
- Lambda functions: PascalCase in interface.yml (e.g., `WhatsAppWebhook`, `CreateClinic`)
- Handlers: `src.functions.{domain}.{module}.handler`
- DynamoDB tables: `clinic-scheduler-infra-{stage}-{table-name}`
- RDS tables: `scheduler.{table_name}` (schema-qualified)
- Secrets: SSM `/${stage}/KEY_NAME` (SCHEDULER_API_KEY, ZAPI_CLIENT_TOKEN, RDS_*, GOOGLE_SHEETS_SERVICE_ACCOUNT)
