# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Workflow de Desenvolvimento (Research → Spec → Code)

Siga este processo em **3 etapas** para novas features, refatorações e remoção de código.

| Fase | Input do usuário | Ação do Claude | Output |
|------|------------------|----------------|--------|
| **1. Pesquisa** | "Preciso implementar X" / "Refatorar Y" / "Eliminar código Z" | Pesquisar codebase (`infra/src/`, `infra/sls/`, `infra/docs/`), padrões em `CLAUDE.md`, dependências | `docs/work/prd/XXX-nome.md` (PRD) |
| **2. Spec** | "Leia `docs/work/prd/XXX-nome.md` e gere uma spec" | Ler o PRD e detalhar arquivos a criar/modificar/remover, alterações por arquivo, ordem de implementação | `docs/work/spec/XXX-nome.md` (Spec) |
| **3. Code** | "Implemente `docs/work/spec/XXX-nome.md`" | Implementar seguindo a Spec; respeitar `CLAUDE.md` (logging, naming, secrets) | Código no repositório |

- **Artefatos:** PRDs em `docs/work/prd/`, Specs em `docs/work/spec/`. Templates em `docs/work/_templates/`.
- **Nomes:** use ID único por task (ex: `001-refator-auth`, `002-remove-legacy`). Mesmo ID no PRD e na Spec.
- **Documentação pós-task:** atualizar o PRD com Status (Spec gerada, data de implementação) e registrar em `TASKS_LOG.md`.

Detalhes: `docs/work/README.md`.

---

## Project Overview

Traffic Manager is an AWS Lambda-based system for automated Google Ads campaign optimization using AI. It orchestrates campaign creation (FIRST_RUN) and ongoing optimization (IMPROVE) through Step Functions workflows.

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

### Execution Flow (Step Functions)
1. **CampaignOrchestrator** - Determines FIRST_RUN vs IMPROVE, validates client access
2. **FetchCampaignTemplate** (FIRST_RUN) or **FetchCampaignMetrics** (IMPROVE) - Gets template/metrics
3. **CallOpenAI** - Sends to OpenAI for AI optimization recommendations
4. **ParseOpenAIResponse** - Transforms AI output to Google Ads payload
5. **ApplyGoogleAdsChanges** - Applies mutations via Google Ads API
6. **CampaignRecorder** - Records final execution state

### Key Directories
- `infra/src/functions/` - Lambda handlers organized by domain (campaign, googleads, openai, etc.)
- `infra/src/services/` - Business logic (Google Ads client management, token management)
- `infra/src/utils/` - Utilities (encryption, auth, logging)
- `infra/sls/resources/` - CloudFormation resources (DynamoDB tables, Step Functions, IAM)
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

## Naming Conventions
- Client IDs: lowercase kebab-case (e.g., `empresarods-abc123`)
- Lambda functions: PascalCase in serverless.yml (e.g., `CampaignOrchestrator`)
- Handlers: Python module paths (e.g., `src.functions.campaign.orchestrator.handler`)
- DynamoDB tables: `${resourcePrefix}-${tableName}` prefix
