# Spec — 001 WhatsApp Clinic Scheduler

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/001-whatsapp-scheduler.md`

---

## 1. Resumo

Implementação completa do projeto `scheduler/` no monorepo — um sistema de agendamento de consultas para clínicas via WhatsApp. Inclui: estrutura do projeto Serverless, tabelas DynamoDB, schema PostgreSQL, provider WhatsApp (z-api), motor de conversa (state machine), APIs admin (CRUD de clínicas, serviços, profissionais, disponibilidade, templates, FAQ), cálculo de disponibilidade, sistema de lembretes, rastreamento de mensagens, sync Google Sheets e relatório diário.

---

## 2. Arquivos a criar

### Raiz do projeto (`scheduler/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/serverless.yml` | Configuração Serverless Framework (provider, functions, resources, env vars) |
| `scheduler/Dockerfile` | Imagem Docker Lambda Python 3.9 |
| `scheduler/requirements.txt` | Dependências Python |
| `scheduler/package.json` | Dependências Node.js (plugins Serverless) |
| `scheduler/.gitignore` | Ignorar .env, node_modules, .serverless |

### Utils (`scheduler/src/utils/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/__init__.py` | Package init |
| `scheduler/src/utils/__init__.py` | Package init |
| `scheduler/src/utils/http.py` | parse_body, http_response, extract_*, require_api_key |
| `scheduler/src/utils/logging.py` | setup_logger, log_step, log_error com traceId |
| `scheduler/src/utils/auth.py` | Validação de API key para endpoints admin |
| `scheduler/src/utils/phone.py` | Normalização de telefone (formatos BR) |
| `scheduler/src/utils/decimal_utils.py` | Conversão Decimal ↔ float para DynamoDB/JSON |

### Providers (`scheduler/src/providers/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/providers/__init__.py` | Package init |
| `scheduler/src/providers/whatsapp_provider.py` | Interface abstrata (ABC) do provider WhatsApp |
| `scheduler/src/providers/zapi_provider.py` | Implementação z-api (envio, parse webhook, parse status) |

### Services (`scheduler/src/services/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/services/__init__.py` | Package init |
| `scheduler/src/services/db/__init__.py` | Package init |
| `scheduler/src/services/db/postgres.py` | PostgresService com connection pooling (schema scheduler) |
| `scheduler/src/services/conversation_engine.py` | State machine: definição de estados, transições, on_enter |
| `scheduler/src/services/availability_engine.py` | Cálculo de slots disponíveis (regras, exceções, conflitos) |
| `scheduler/src/services/appointment_service.py` | Criar, remarcar, cancelar agendamento + lock otimístico |
| `scheduler/src/services/reminder_service.py` | Criar, cancelar lembretes no DynamoDB |
| `scheduler/src/services/message_tracker.py` | Registrar eventos de mensagem no DynamoDB |
| `scheduler/src/services/sheets_sync.py` | Sync agendamentos → Google Sheets |
| `scheduler/src/services/template_service.py` | Resolver templates com placeholders e fallback padrão |

### Functions — Handlers (`scheduler/src/functions/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/functions/__init__.py` | Package init |
| `scheduler/src/functions/webhook/__init__.py` | Package init |
| `scheduler/src/functions/webhook/handler.py` | Recebe mensagens z-api, roteia para conversation_engine |
| `scheduler/src/functions/webhook/status_handler.py` | Recebe status updates z-api, atualiza MessageEvents |
| `scheduler/src/functions/send/__init__.py` | Package init |
| `scheduler/src/functions/send/handler.py` | Endpoint interno para enviar mensagem (text, buttons) |
| `scheduler/src/functions/appointment/__init__.py` | Package init |
| `scheduler/src/functions/appointment/create.py` | POST /appointments — criar agendamento via API |
| `scheduler/src/functions/appointment/list.py` | GET /appointments — listar agendamentos por clínica/data |
| `scheduler/src/functions/appointment/update.py` | PUT /appointments/{id} — atualizar status |
| `scheduler/src/functions/clinic/__init__.py` | Package init |
| `scheduler/src/functions/clinic/create.py` | POST /clinics |
| `scheduler/src/functions/clinic/list.py` | GET /clinics |
| `scheduler/src/functions/clinic/get.py` | GET /clinics/{clinicId} |
| `scheduler/src/functions/clinic/update.py` | PUT /clinics/{clinicId} |
| `scheduler/src/functions/service/__init__.py` | Package init |
| `scheduler/src/functions/service/create.py` | POST /clinics/{clinicId}/services |
| `scheduler/src/functions/service/list.py` | GET /clinics/{clinicId}/services |
| `scheduler/src/functions/service/update.py` | PUT /services/{serviceId} |
| `scheduler/src/functions/professional/__init__.py` | Package init |
| `scheduler/src/functions/professional/create.py` | POST /clinics/{clinicId}/professionals |
| `scheduler/src/functions/professional/list.py` | GET /clinics/{clinicId}/professionals |
| `scheduler/src/functions/availability/__init__.py` | Package init |
| `scheduler/src/functions/availability/rules.py` | POST/GET /clinics/{clinicId}/availability-rules |
| `scheduler/src/functions/availability/exceptions.py` | POST/GET /clinics/{clinicId}/availability-exceptions |
| `scheduler/src/functions/availability/slots.py` | GET /clinics/{clinicId}/available-slots?date=&serviceId= |
| `scheduler/src/functions/template/__init__.py` | Package init |
| `scheduler/src/functions/template/create.py` | POST /clinics/{clinicId}/templates |
| `scheduler/src/functions/template/list.py` | GET /clinics/{clinicId}/templates |
| `scheduler/src/functions/template/update.py` | PUT /templates/{templateId} |
| `scheduler/src/functions/faq/__init__.py` | Package init |
| `scheduler/src/functions/faq/create.py` | POST /clinics/{clinicId}/faq |
| `scheduler/src/functions/faq/list.py` | GET /clinics/{clinicId}/faq |
| `scheduler/src/functions/faq/update.py` | PUT /faq/{faqId} |
| `scheduler/src/functions/reminder/__init__.py` | Package init |
| `scheduler/src/functions/reminder/processor.py` | Cron Lambda: busca lembretes pendentes e envia |
| `scheduler/src/functions/report/__init__.py` | Package init |
| `scheduler/src/functions/report/daily.py` | Cron Lambda: envia agenda do dia seguinte para clínicas |

### Serverless — Function interfaces (`scheduler/sls/functions/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/sls/functions/webhook/interface.yml` | WhatsAppWebhook, WhatsAppStatusWebhook |
| `scheduler/sls/functions/send/interface.yml` | SendMessage |
| `scheduler/sls/functions/appointment/interface.yml` | CreateAppointment, ListAppointments, UpdateAppointment |
| `scheduler/sls/functions/clinic/interface.yml` | CreateClinic, ListClinics, GetClinic, UpdateClinic |
| `scheduler/sls/functions/service/interface.yml` | CreateService, ListServices, UpdateService |
| `scheduler/sls/functions/professional/interface.yml` | CreateProfessional, ListProfessionals |
| `scheduler/sls/functions/availability/interface.yml` | ManageAvailabilityRules, ManageAvailabilityExceptions, GetAvailableSlots |
| `scheduler/sls/functions/template/interface.yml` | CreateTemplate, ListTemplates, UpdateTemplate |
| `scheduler/sls/functions/faq/interface.yml` | CreateFaq, ListFaq, UpdateFaq |
| `scheduler/sls/functions/reminder/interface.yml` | ReminderProcessor (schedule event) |
| `scheduler/sls/functions/report/interface.yml` | DailyReportSender (schedule event) |

### Serverless — Resources (`scheduler/sls/resources/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/sls/resources/dynamodb/conversation-sessions-table.yml` | ConversationSessions table |
| `scheduler/sls/resources/dynamodb/message-events-table.yml` | MessageEvents table + 3 GSIs |
| `scheduler/sls/resources/dynamodb/scheduled-reminders-table.yml` | ScheduledReminders table + 1 GSI |

### Scripts (`scheduler/src/scripts/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/scripts/__init__.py` | Package init |
| `scheduler/src/scripts/setup_database.py` | Cria schema `scheduler` e todas as tabelas no RDS |
| `scheduler/src/scripts/seed_clinic.py` | Seed de uma clínica de exemplo (Laser Beauty) com serviços, regras, FAQ |

### Testes (`scheduler/tests/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/tests/mocks/webhook/text_message.json` | Mock de mensagem de texto recebida |
| `scheduler/tests/mocks/webhook/button_response.json` | Mock de resposta de botão recebida |
| `scheduler/tests/mocks/webhook/status_update.json` | Mock de status update (SENT, READ) |
| `scheduler/tests/mocks/appointment/create.json` | Mock de criação de agendamento |
| `scheduler/tests/mocks/clinic/create.json` | Mock de criação de clínica |

### Postman Collections (`scheduler/tests/postman/`)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/tests/postman/CLAUDE.md` | Padrões Postman do projeto scheduler |
| `scheduler/tests/postman/clinics.postman_collection.json` | CRUD de clínicas (Create, List, Get, Update) |
| `scheduler/tests/postman/services.postman_collection.json` | CRUD de serviços (Create, List, Update) |
| `scheduler/tests/postman/professionals.postman_collection.json` | CRUD de profissionais (Create, List) |
| `scheduler/tests/postman/availability.postman_collection.json` | Regras, exceções e consulta de slots disponíveis |
| `scheduler/tests/postman/appointments.postman_collection.json` | Agendamentos (Create, List, Update/Cancel) |
| `scheduler/tests/postman/templates.postman_collection.json` | Templates de mensagem (Create, List, Update) |
| `scheduler/tests/postman/faq.postman_collection.json` | FAQ items (Create, List, Update) |
| `scheduler/tests/postman/messaging.postman_collection.json` | Envio de mensagens e simulação de webhooks |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `CLAUDE.md` | Adicionar seção do projeto `scheduler/` com comandos de build/deploy e estrutura |
| `.gitignore` (raiz) | Adicionar `scheduler/.env`, `scheduler/node_modules/`, `scheduler/.serverless/` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

A implementação está dividida em **10 fases** sequenciais. Cada fase pode ser implementada e testada independentemente.

### Fase 1 — Scaffolding do projeto
1. `scheduler/serverless.yml`
2. `scheduler/Dockerfile`
3. `scheduler/requirements.txt`
4. `scheduler/package.json`
5. `scheduler/.gitignore`
6. Todos os `__init__.py`

### Fase 2 — Utilitários base
7. `scheduler/src/utils/http.py`
8. `scheduler/src/utils/logging.py`
9. `scheduler/src/utils/auth.py`
10. `scheduler/src/utils/phone.py`
11. `scheduler/src/utils/decimal_utils.py`

### Fase 3 — Database e resources
12. `scheduler/sls/resources/dynamodb/conversation-sessions-table.yml`
13. `scheduler/sls/resources/dynamodb/message-events-table.yml`
14. `scheduler/sls/resources/dynamodb/scheduled-reminders-table.yml`
15. `scheduler/src/services/db/postgres.py`
16. `scheduler/src/scripts/setup_database.py`

### Fase 4 — Admin APIs (CRUD)
17. `scheduler/sls/functions/clinic/interface.yml`
18. `scheduler/src/functions/clinic/create.py`
19. `scheduler/src/functions/clinic/list.py`
20. `scheduler/src/functions/clinic/get.py`
21. `scheduler/src/functions/clinic/update.py`
22. `scheduler/sls/functions/service/interface.yml`
23. `scheduler/src/functions/service/create.py`
24. `scheduler/src/functions/service/list.py`
25. `scheduler/src/functions/service/update.py`
26. `scheduler/sls/functions/professional/interface.yml`
27. `scheduler/src/functions/professional/create.py`
28. `scheduler/src/functions/professional/list.py`
29. `scheduler/sls/functions/availability/interface.yml`
30. `scheduler/src/functions/availability/rules.py`
31. `scheduler/src/functions/availability/exceptions.py`
32. `scheduler/sls/functions/template/interface.yml`
33. `scheduler/src/functions/template/create.py`
34. `scheduler/src/functions/template/list.py`
35. `scheduler/src/functions/template/update.py`
36. `scheduler/sls/functions/faq/interface.yml`
37. `scheduler/src/functions/faq/create.py`
38. `scheduler/src/functions/faq/list.py`
39. `scheduler/src/functions/faq/update.py`
40. `scheduler/src/scripts/seed_clinic.py`

### Fase 5 — Provider WhatsApp
41. `scheduler/src/providers/whatsapp_provider.py`
42. `scheduler/src/providers/zapi_provider.py`

### Fase 6 — Rastreamento de mensagens e envio
43. `scheduler/src/services/message_tracker.py`
44. `scheduler/sls/functions/send/interface.yml`
45. `scheduler/src/functions/send/handler.py`

### Fase 7 — Motor de conversa e webhook
46. `scheduler/src/services/template_service.py`
47. `scheduler/src/services/conversation_engine.py`
48. `scheduler/sls/functions/webhook/interface.yml`
49. `scheduler/src/functions/webhook/handler.py`
50. `scheduler/src/functions/webhook/status_handler.py`

### Fase 8 — Agendamento e disponibilidade
51. `scheduler/src/services/availability_engine.py`
52. `scheduler/src/services/appointment_service.py`
53. `scheduler/sls/functions/availability/interface.yml` (adicionar GetAvailableSlots)
54. `scheduler/src/functions/availability/slots.py`
55. `scheduler/sls/functions/appointment/interface.yml`
56. `scheduler/src/functions/appointment/create.py`
57. `scheduler/src/functions/appointment/list.py`
58. `scheduler/src/functions/appointment/update.py`

### Fase 9 — Lembretes e relatórios
59. `scheduler/src/services/reminder_service.py`
60. `scheduler/sls/functions/reminder/interface.yml`
61. `scheduler/src/functions/reminder/processor.py`
62. `scheduler/src/services/sheets_sync.py`
63. `scheduler/sls/functions/report/interface.yml`
64. `scheduler/src/functions/report/daily.py`

### Fase 10 — Testes, Postman, docs e cleanup
65. `scheduler/tests/mocks/webhook/text_message.json`
66. `scheduler/tests/mocks/webhook/button_response.json`
67. `scheduler/tests/mocks/webhook/status_update.json`
68. `scheduler/tests/mocks/appointment/create.json`
69. `scheduler/tests/mocks/clinic/create.json`
70. `scheduler/tests/postman/CLAUDE.md`
71. `scheduler/tests/postman/clinics.postman_collection.json`
72. `scheduler/tests/postman/services.postman_collection.json`
73. `scheduler/tests/postman/professionals.postman_collection.json`
74. `scheduler/tests/postman/availability.postman_collection.json`
75. `scheduler/tests/postman/appointments.postman_collection.json`
76. `scheduler/tests/postman/templates.postman_collection.json`
77. `scheduler/tests/postman/faq.postman_collection.json`
78. `scheduler/tests/postman/messaging.postman_collection.json`
79. Atualizar `CLAUDE.md`
80. Atualizar `.gitignore`

---

## 6. Detalhes por arquivo

---

### Fase 1 — Scaffolding

---

#### `scheduler/serverless.yml`

- **Criar**
- Service name: `clinic-scheduler-infra`
- Framework version: 3
- Custom vars:
  ```yaml
  custom:
    stage: ${opt:stage, self:provider.stage}
    resourcePrefix: ${self:service}-${self:custom.stage}
    accountId: "339712971032"
  ```
- Provider:
  - `name: aws`, `stage: dev`, `region: us-east-1`
  - `ecr.images.lambdaimage.path: .`
  - Environment variables:
    - `STAGE: ${self:custom.stage}`
    - `CONVERSATION_SESSIONS_TABLE: ${self:custom.resourcePrefix}-conversation-sessions`
    - `MESSAGE_EVENTS_TABLE: ${self:custom.resourcePrefix}-message-events`
    - `SCHEDULED_REMINDERS_TABLE: ${self:custom.resourcePrefix}-scheduled-reminders`
    - `RDS_HOST: ${ssm:/${self:custom.stage}/RDS_HOST}`
    - `RDS_PORT: ${ssm:/${self:custom.stage}/RDS_PORT}`
    - `RDS_DATABASE: ${ssm:/${self:custom.stage}/RDS_DATABASE}`
    - `RDS_USERNAME: ${ssm:/${self:custom.stage}/RDS_USERNAME}`
    - `RDS_PASSWORD: ${ssm:/${self:custom.stage}/RDS_PASSWORD}`
    - `SCHEDULER_API_KEY: ${ssm:/${self:custom.stage}/SCHEDULER_API_KEY}`
    - `GOOGLE_SHEETS_SERVICE_ACCOUNT: ${ssm:/${self:custom.stage}/GOOGLE_SHEETS_SERVICE_ACCOUNT}`
- Functions: imports de `sls/functions/*/interface.yml`
- Resources: imports de `sls/resources/dynamodb/*.yml`
- Plugins: `serverless-iam-roles-per-function`

#### `scheduler/Dockerfile`

- **Criar**
- Base: `public.ecr.aws/lambda/python:3.9`
- COPY requirements.txt → pip install
- COPY src/ → LAMBDA_TASK_ROOT/src/
- CMD: `src.functions.webhook.handler.handler` (overridden per function)

#### `scheduler/requirements.txt`

- **Criar**
- Dependências:
  ```
  boto3==1.26.161
  requests==2.31.0
  psycopg2-binary==2.9.9
  python-dotenv==1.0.0
  google-api-python-client==2.86.0
  google-auth==2.24.0
  ```

#### `scheduler/package.json`

- **Criar**
- Dependências: `serverless-iam-roles-per-function`

#### `scheduler/.gitignore`

- **Criar**
- Entradas: `.env`, `node_modules/`, `.serverless/`, `__pycache__/`, `*.pyc`

---

### Fase 2 — Utilitários

---

#### `scheduler/src/utils/http.py`

- **Criar** — Espelhar `infra/src/utils/http.py`
- Funções:
  - `parse_body(event) -> dict | None` — Parse JSON do body
  - `http_response(status_code, body, headers=None) -> dict` — Response com CORS headers, conversão Decimal→float
  - `extract_query_param(event, name) -> str | None`
  - `extract_path_param(event, name) -> str | None`
  - `extract_api_key(event, body=None) -> str | None` — Buscar em Authorization Bearer, x-api-key, query, body
  - `require_api_key(event, body=None) -> tuple[str|None, dict|None]` — Valida API key, retorna (key, error_response)

#### `scheduler/src/utils/logging.py`

- **Criar** — Espelhar `infra/src/utils/logging.py`
- Funções:
  - `setup_logger(name, level=INFO) -> Logger`
  - `log_step(logger, trace_id, step, message, data=None)`
  - `log_error(logger, exception, event=None, trace_id=None)`
- Pattern de log: `[traceId: {trace_id}] [{step}] {message}`

#### `scheduler/src/utils/auth.py`

- **Criar**
- Classe `SchedulerAuth`:
  - `validate_api_key(api_key: str) -> bool` — Compara com `SCHEDULER_API_KEY` env var
- Mais simples que infra — uma API key global para endpoints admin no MVP

#### `scheduler/src/utils/phone.py`

- **Criar**
- Funções:
  - `normalize_phone(phone: str) -> str` — Remove formatação, garante formato `55DDDNNNNNNNNN`
  - `format_phone_display(phone: str) -> str` — Formata para exibição `(DD) NNNNN-NNNN`
  - `is_valid_br_phone(phone: str) -> bool` — Valida telefone brasileiro

#### `scheduler/src/utils/decimal_utils.py`

- **Criar** — Copiar de `infra/src/utils/decimal_utils.py`
- Funções:
  - `convert_decimal_to_json_serializable(obj) -> Any`

---

### Fase 3 — Database e resources

---

#### `scheduler/sls/resources/dynamodb/conversation-sessions-table.yml`

- **Criar**
```yaml
Resources:
  ConversationSessionsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: ${self:custom.resourcePrefix}-conversation-sessions
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
```

#### `scheduler/sls/resources/dynamodb/message-events-table.yml`

- **Criar**
```yaml
Resources:
  MessageEventsTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: ${self:custom.resourcePrefix}-message-events
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
        - AttributeName: clinicId
          AttributeType: S
        - AttributeName: statusTimestamp
          AttributeType: S
        - AttributeName: status
          AttributeType: S
        - AttributeName: conversationId
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: clinicId-statusTimestamp-index
          KeySchema:
            - AttributeName: clinicId
              KeyType: HASH
            - AttributeName: statusTimestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: status-statusTimestamp-index
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: statusTimestamp
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
        - IndexName: conversationId-index
          KeySchema:
            - AttributeName: conversationId
              KeyType: HASH
            - AttributeName: sk
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
```

#### `scheduler/sls/resources/dynamodb/scheduled-reminders-table.yml`

- **Criar**
```yaml
Resources:
  ScheduledRemindersTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: ${self:custom.resourcePrefix}-scheduled-reminders
      BillingMode: PAY_PER_REQUEST
      AttributeDefinitions:
        - AttributeName: pk
          AttributeType: S
        - AttributeName: sk
          AttributeType: S
        - AttributeName: status
          AttributeType: S
        - AttributeName: sendAt
          AttributeType: S
      KeySchema:
        - AttributeName: pk
          KeyType: HASH
        - AttributeName: sk
          KeyType: RANGE
      GlobalSecondaryIndexes:
        - IndexName: status-sendAt-index
          KeySchema:
            - AttributeName: status
              KeyType: HASH
            - AttributeName: sendAt
              KeyType: RANGE
          Projection:
            ProjectionType: ALL
      TimeToLiveSpecification:
        AttributeName: ttl
        Enabled: true
```

#### `scheduler/src/services/db/postgres.py`

- **Criar** — Espelhar `infra/src/services/postgres_service.py`
- Classe `PostgresService`:
  - Connection pool no nível do módulo (reusado entre invocações Lambda)
  - `SimpleConnectionPool(minconn=1, maxconn=5)`
  - `_get_connection()` — context manager
  - `execute_query(query, params) -> list[dict]` — SELECT com RealDictCursor
  - `execute_write(query, params) -> int` — INSERT/UPDATE/DELETE, retorna rowcount
  - `transaction()` — context manager com auto-commit/rollback
  - `health_check() -> dict`
- Conexão usando env vars: `RDS_HOST`, `RDS_PORT`, `RDS_DATABASE`, `RDS_USERNAME`, `RDS_PASSWORD`
- **Importante:** todas as queries devem usar `search_path` setado para `scheduler` ou qualificar tabelas como `scheduler.table_name`

#### `scheduler/src/scripts/setup_database.py`

- **Criar**
- Script standalone (executável localmente) que:
  1. Conecta ao RDS usando credenciais do `.env`
  2. `CREATE SCHEMA IF NOT EXISTS scheduler`
  3. Executa todos os CREATE TABLE do PRD seção 4.2 (clinics, services, professionals, availability_rules, availability_exceptions, patients, appointments, message_templates, faq_items)
  4. Executa todos os CREATE INDEX
  5. Imprime resultado de cada operação
- Usa `psycopg2` diretamente e `python-dotenv` para carregar `.env`

---

### Fase 4 — Admin APIs (CRUD)

---

#### `scheduler/sls/functions/clinic/interface.yml`

- **Criar**
- Funções:
  - `CreateClinic`: POST `/clinics`, handler `src.functions.clinic.create.handler`
  - `ListClinics`: GET `/clinics`, handler `src.functions.clinic.list.handler`
  - `GetClinic`: GET `/clinics/{clinicId}`, handler `src.functions.clinic.get.handler`
  - `UpdateClinic`: PUT `/clinics/{clinicId}`, handler `src.functions.clinic.update.handler`
- IAM: `ssm:GetParameter` (para RDS creds) + `logs:*`
- Sem DynamoDB — todas operações no RDS
- Memory: 512MB, timeout: 30s, cors: true

#### `scheduler/src/functions/clinic/create.py`

- **Criar**
- Handler `POST /clinics`:
  1. `require_api_key(event)` — validar API key admin
  2. `parse_body(event)` — extrair body
  3. Validar campos obrigatórios: `name`, `business_hours`
  4. Gerar `clinic_id` a partir do `name` (kebab-case + hash 6 chars, mesmo padrão do infra)
  5. INSERT em `scheduler.clinics`
  6. Retornar 201 com clinicId e dados

#### `scheduler/src/functions/clinic/list.py`

- **Criar**
- Handler `GET /clinics`:
  1. `require_api_key(event)`
  2. SELECT all from `scheduler.clinics` WHERE `active = true`
  3. Retornar 200 com lista

#### `scheduler/src/functions/clinic/get.py`

- **Criar**
- Handler `GET /clinics/{clinicId}`:
  1. `require_api_key(event)`
  2. `extract_path_param(event, 'clinicId')`
  3. SELECT from `scheduler.clinics` WHERE `clinic_id = :clinicId`
  4. Retornar 200 ou 404

#### `scheduler/src/functions/clinic/update.py`

- **Criar**
- Handler `PUT /clinics/{clinicId}`:
  1. `require_api_key(event)`, `parse_body(event)`
  2. Campos atualizáveis: `name`, `phone`, `address`, `timezone`, `business_hours`, `buffer_minutes`, `welcome_message`, `pre_session_instructions`, `zapi_instance_id`, `zapi_instance_token`, `google_spreadsheet_id`, `google_sheet_name`, `active`
  3. UPDATE dinâmico (só campos presentes no body)
  4. Retornar 200 com dados atualizados

#### `scheduler/sls/functions/service/interface.yml`

- **Criar**
- Funções:
  - `CreateService`: POST `/clinics/{clinicId}/services`
  - `ListServices`: GET `/clinics/{clinicId}/services`
  - `UpdateService`: PUT `/services/{serviceId}`
- Mesmo padrão de IAM (SSM + logs)

#### `scheduler/src/functions/service/create.py`

- **Criar**
- Handler `POST /clinics/{clinicId}/services`:
  1. Validar: `name`, `duration_minutes` obrigatórios
  2. Verificar que clinicId existe
  3. INSERT em `scheduler.services`
  4. Retornar 201

#### `scheduler/src/functions/service/list.py`

- **Criar**
- Handler `GET /clinics/{clinicId}/services`:
  1. SELECT from `scheduler.services` WHERE `clinic_id = :clinicId AND active = true`
  2. Retornar 200 com lista

#### `scheduler/src/functions/service/update.py`

- **Criar**
- Handler `PUT /services/{serviceId}`:
  1. UPDATE dinâmico (name, duration_minutes, price_cents, description, active)
  2. Retornar 200

#### `scheduler/sls/functions/professional/interface.yml`

- **Criar**
- `CreateProfessional`: POST `/clinics/{clinicId}/professionals`
- `ListProfessionals`: GET `/clinics/{clinicId}/professionals`

#### `scheduler/src/functions/professional/create.py`

- **Criar**
- Validar: `name` obrigatório
- INSERT em `scheduler.professionals`

#### `scheduler/src/functions/professional/list.py`

- **Criar**
- SELECT from `scheduler.professionals` WHERE `clinic_id = :clinicId AND active = true`

#### `scheduler/sls/functions/availability/interface.yml`

- **Criar**
- `ManageAvailabilityRules`: POST `/clinics/{clinicId}/availability-rules` e GET `/clinics/{clinicId}/availability-rules`
- `ManageAvailabilityExceptions`: POST `/clinics/{clinicId}/availability-exceptions` e GET `/clinics/{clinicId}/availability-exceptions`
- `GetAvailableSlots`: GET `/clinics/{clinicId}/available-slots`

Nota: `ManageAvailabilityRules` e `ManageAvailabilityExceptions` usam o mesmo handler com switch por method (GET vs POST). Alternativa: separar em handlers distintos. Preferir handlers separados para manter padrão do projeto.

Ajuste: usar handlers separados:
- `CreateAvailabilityRule`: POST `/clinics/{clinicId}/availability-rules`
- `ListAvailabilityRules`: GET `/clinics/{clinicId}/availability-rules`
- `CreateAvailabilityException`: POST `/clinics/{clinicId}/availability-exceptions`
- `ListAvailabilityExceptions`: GET `/clinics/{clinicId}/availability-exceptions`
- `GetAvailableSlots`: GET `/clinics/{clinicId}/available-slots`

#### `scheduler/src/functions/availability/rules.py`

- **Criar**
- Dois handlers no mesmo módulo (create_handler, list_handler) referenciados separadamente no interface.yml:
  - `create_handler`: Validar `day_of_week` (0-6), `start_time`, `end_time`. INSERT em `scheduler.availability_rules`
  - `list_handler`: SELECT WHERE `clinic_id = :clinicId AND active = true`

#### `scheduler/src/functions/availability/exceptions.py`

- **Criar**
- Dois handlers (create_handler, list_handler):
  - `create_handler`: Validar `exception_date`, `exception_type` (BLOCKED|SPECIAL_HOURS). INSERT em `scheduler.availability_exceptions`
  - `list_handler`: SELECT WHERE `clinic_id = :clinicId`. Filtro opcional por `?from=&to=` (date range)

#### `scheduler/src/functions/availability/slots.py`

- **Criar**
- Handler `GET /clinics/{clinicId}/available-slots?date=YYYY-MM-DD&serviceId=UUID`:
  1. `require_api_key(event)`
  2. Extrair query params: `date`, `serviceId`
  3. Chamar `availability_engine.get_available_slots(clinicId, date, serviceId)`
  4. Retornar 200 com lista de slots `[{"time": "09:00"}, {"time": "10:00"}, ...]`

#### `scheduler/sls/functions/template/interface.yml`

- **Criar**
- `CreateTemplate`: POST `/clinics/{clinicId}/templates`
- `ListTemplates`: GET `/clinics/{clinicId}/templates`
- `UpdateTemplate`: PUT `/templates/{templateId}`

#### `scheduler/src/functions/template/create.py`, `list.py`, `update.py`

- **Criar** — CRUD padrão em `scheduler.message_templates`
- create: Validar `template_key`, `content`. INSERT com UNIQUE constraint (clinic_id, template_key)
- list: SELECT WHERE clinic_id, opcionalmente filtrar por template_key
- update: UPDATE content, buttons, active

#### `scheduler/sls/functions/faq/interface.yml`

- **Criar**
- `CreateFaq`: POST `/clinics/{clinicId}/faq`
- `ListFaq`: GET `/clinics/{clinicId}/faq`
- `UpdateFaq`: PUT `/faq/{faqId}`

#### `scheduler/src/functions/faq/create.py`, `list.py`, `update.py`

- **Criar** — CRUD padrão em `scheduler.faq_items`
- create: Validar `question_key`, `question_label`, `answer`
- list: SELECT WHERE clinic_id, ORDER BY display_order
- update: UPDATE question_label, answer, display_order, active

#### `scheduler/src/scripts/seed_clinic.py`

- **Criar**
- Script standalone que popula dados iniciais para Laser Beauty:
  1. Criar clínica `laser-beauty-sp`
  2. Criar serviço "Depilação a laser" (duration: 45min, price: 15000 centavos)
  3. Criar profissional "Biomédica esteta"
  4. Criar regras de disponibilidade (seg-sex 9:00-18:00)
  5. Criar 5 FAQ items (equipamento, intervalo, datas, pagamento, equipe)
  6. Criar templates padrão (WELCOME, MAIN_MENU, etc.)

---

### Fase 5 — Provider WhatsApp

---

#### `scheduler/src/providers/whatsapp_provider.py`

- **Criar**
- Classe abstrata `WhatsAppProvider(ABC)`:
  ```python
  @abstractmethod
  def send_text(self, phone: str, message: str) -> ProviderResponse: ...

  @abstractmethod
  def send_buttons(self, phone: str, message: str, buttons: list[dict]) -> ProviderResponse: ...

  @abstractmethod
  def send_list(self, phone: str, message: str, button_text: str, sections: list[dict]) -> ProviderResponse: ...

  @abstractmethod
  def parse_incoming_message(self, raw_payload: dict) -> IncomingMessage: ...

  @abstractmethod
  def parse_status_update(self, raw_payload: dict) -> MessageStatusUpdate: ...
  ```
- Dataclasses:
  - `ProviderResponse(success: bool, provider_message_id: str, raw_response: dict, error: str|None)`
  - `IncomingMessage(message_id: str, phone: str, sender_name: str, timestamp: int, message_type: str, content: str, button_id: str|None, button_text: str|None, reference_message_id: str|None, raw_payload: dict)`
  - `MessageStatusUpdate(message_ids: list[str], phone: str, status: str, timestamp: int, raw_payload: dict)`
- Factory function: `get_provider(clinic: dict) -> WhatsAppProvider` — retorna ZApiProvider baseado nos dados da clínica

#### `scheduler/src/providers/zapi_provider.py`

- **Criar**
- Classe `ZApiProvider(WhatsAppProvider)`:
  - `__init__(self, instance_id: str, instance_token: str, client_token: str)`
  - Base URL: `https://api.z-api.io/instances/{instance_id}/token/{instance_token}`
  - Headers: `{"Client-Token": client_token, "Content-Type": "application/json"}`
  - `send_text`: POST `/send-text` body: `{"phone": phone, "message": message}`
  - `send_buttons`: POST `/send-button-list` body: `{"phone": phone, "message": message, "buttonList": {"buttons": [{"id": id, "label": label}]}}`
    - Se a request falhar com erro de botão, fazer fallback para `send_text` com texto numerado
  - `send_list`: POST `/send-option-list` (se z-api suportar) ou fallback para texto numerado
  - `parse_incoming_message`: Extrair do payload z-api:
    - `type: ReceivedCallback`
    - Texto: `payload["text"]["message"]`
    - Botão: `payload["buttonsResponseMessage"]["buttonId"]` + `payload["buttonsResponseMessage"]["message"]`
    - `phone`, `senderName`, `momment`, `messageId`
  - `parse_status_update`: Extrair do payload z-api:
    - `type: MessageStatusCallback`
    - `status` (SENT, RECEIVED, READ), `ids[]`, `phone`, `momment`

---

### Fase 6 — Rastreamento de mensagens e envio

---

#### `scheduler/src/services/message_tracker.py`

- **Criar**
- Classe `MessageTracker`:
  - `__init__()`: inicializar DynamoDB resource, tabela `MESSAGE_EVENTS_TABLE`
  - `track_outbound(clinic_id, phone, message_id, conversation_id, message_type, content, status, provider, provider_message_id, provider_response, metadata)`:
    - PutItem em MessageEvents com PK, SK, todos os atributos, TTL (90 dias)
  - `track_inbound(clinic_id, phone, message_id, conversation_id, incoming_message: IncomingMessage, conversation_state, metadata)`:
    - PutItem com status=RECEIVED, direction=INBOUND
  - `update_status(clinic_id, phone, message_id, new_status, timestamp, raw_payload)`:
    - PutItem novo evento (append, não update — mantém histórico)
  - `get_conversation_messages(clinic_id, phone, limit=50) -> list`:
    - Query PK=CLINIC#clinicId#PHONE#phone, ordenado por SK

#### `scheduler/sls/functions/send/interface.yml`

- **Criar**
- `SendMessage`:
  - handler: `src.functions.send.handler.handler`
  - POST `/send` (endpoint interno, protegido por API key)
  - IAM: DynamoDB PutItem em MessageEventsTable + SSM + logs
  - Memory: 512MB, timeout: 30s

#### `scheduler/src/functions/send/handler.py`

- **Criar**
- Handler `POST /send`:
  1. `require_api_key(event)`, `parse_body(event)`
  2. Validar: `clinicId`, `phone`, `type` (text|buttons|list), `content`
  3. Buscar clínica no RDS (obter zapi_instance_id, zapi_instance_token)
  4. Instanciar provider: `get_provider(clinic)`
  5. `message_tracker.track_outbound(status=QUEUED)`
  6. Enviar via provider (send_text ou send_buttons)
  7. `message_tracker.track_outbound(status=SENT, provider_response=response.raw_response)`
  8. Se falha: `message_tracker.track_outbound(status=FAILED, error=response.error)`
  9. Retornar 200 com messageId e status

---

### Fase 7 — Motor de conversa e webhook

---

#### `scheduler/src/services/template_service.py`

- **Criar**
- Classe `TemplateService`:
  - `__init__(self, db: PostgresService)`
  - `get_template(clinic_id: str, template_key: str) -> dict`:
    - SELECT from `scheduler.message_templates` WHERE clinic_id e template_key
    - Se não encontrar, retornar template padrão (hardcoded fallback)
  - `render_template(template: dict, variables: dict) -> str`:
    - Substituir `{{key}}` por `variables[key]`
  - Templates padrão (fallback) definidos como constante no módulo:
    ```python
    DEFAULT_TEMPLATES = {
        "WELCOME_NEW": "Olá! Seja bem-vinda à {{clinic_name}}! Como posso te ajudar hoje?",
        "WELCOME_RETURNING": "Olá, {{patient_name}}! Bem-vinda de volta à {{clinic_name}}! Como posso te ajudar?",
        "MAIN_MENU": "Escolha uma opção:",
        "SCHEDULE_MENU": "O que você gostaria de fazer?",
        "PRICE_TABLE": "{{price_table}}",
        "AVAILABLE_DAYS": "Dias disponíveis para agendamento:\n{{days_list}}",
        "SELECT_TIME": "Horários disponíveis para {{date}}:\n{{times_list}}",
        "INPUT_AREAS": "Por favor, digite a(s) área(s) que deseja tratar.\nExemplo: Pernas e axilas",
        "CONFIRM_BOOKING": "Confirme seu agendamento:\n📅 {{date}} às {{time}}\n💆 {{service}}\n📍 {{areas}}\n🏥 {{clinic_name}} - {{address}}",
        "BOOKED": "Agendamento confirmado! ✅\nTe esperamos no dia {{date}} às {{time}}.\n\n{{pre_session_instructions}}",
        "RESCHEDULE_FOUND": "Encontramos seu agendamento:\n📅 {{date}} às {{time}}\n💆 {{service}}\n\nPara qual dia deseja remarcar?",
        "RESCHEDULE_NOT_FOUND": "Não encontramos um agendamento ativo para este número.",
        "RESCHEDULED": "Agendamento remarcado com sucesso! ✅\nNova data: {{date}} às {{time}}",
        "FAQ_MENU": "Qual sua dúvida?",
        "HUMAN_HANDOFF": "Entendi! Vamos encaminhar sua mensagem para nossa equipe. Entraremos em contato o mais rápido possível dentro do horário comercial. 🕐",
        "UNRECOGNIZED": "Desculpe, não entendi sua mensagem. O que deseja fazer?",
        "REMINDER_24H": "Lembrete: Amanhã às {{time}} você tem sessão na {{clinic_name}}. Responda OK para confirmar. 📅",
    }
    ```

#### `scheduler/src/services/conversation_engine.py`

- **Criar**
- Este é o arquivo mais complexo do projeto. Estrutura:

- **Enum `ConversationState`**: todos os estados possíveis
  ```python
  class ConversationState(str, Enum):
      WELCOME = "WELCOME"
      MAIN_MENU = "MAIN_MENU"
      SCHEDULE_MENU = "SCHEDULE_MENU"
      PRICE_TABLE = "PRICE_TABLE"
      AVAILABLE_DAYS = "AVAILABLE_DAYS"
      SELECT_DATE = "SELECT_DATE"
      SELECT_TIME = "SELECT_TIME"
      INPUT_AREAS = "INPUT_AREAS"
      CONFIRM_BOOKING = "CONFIRM_BOOKING"
      BOOKED = "BOOKED"
      RESCHEDULE_LOOKUP = "RESCHEDULE_LOOKUP"
      SHOW_CURRENT_APPOINTMENT = "SHOW_CURRENT_APPOINTMENT"
      SELECT_NEW_DATE = "SELECT_NEW_DATE"
      SELECT_NEW_TIME = "SELECT_NEW_TIME"
      CONFIRM_RESCHEDULE = "CONFIRM_RESCHEDULE"
      RESCHEDULED = "RESCHEDULED"
      FAQ_MENU = "FAQ_MENU"
      FAQ_ANSWER = "FAQ_ANSWER"
      HUMAN_HANDOFF = "HUMAN_HANDOFF"
      UNRECOGNIZED = "UNRECOGNIZED"
  ```

- **Classe `ConversationEngine`**:
  - `__init__(self, db: PostgresService, template_service: TemplateService, availability_engine, appointment_service, provider: WhatsAppProvider, message_tracker: MessageTracker)`
  - `process_message(clinic_id: str, incoming: IncomingMessage) -> list[OutgoingMessage]`:
    1. Carregar sessão do DynamoDB (ou criar nova se não existe / expirada)
    2. Identificar input do paciente (button_id ou texto)
    3. Checar se é "voltar" → transicionar para previousState
    4. Checar se é input esperado para o estado atual → transicionar
    5. Se não reconhecido → UNRECOGNIZED
    6. Executar `on_enter` do novo estado (buscar dados, criar agendamento, etc.)
    7. Renderizar template do novo estado
    8. Montar mensagens de resposta (texto + botões)
    9. Salvar sessão atualizada no DynamoDB
    10. Retornar lista de mensagens a enviar

  - `_load_session(clinic_id, phone) -> dict`:
    - GetItem DynamoDB ConversationSessions
    - Se não encontrar ou TTL expirado, retornar sessão nova (state=WELCOME)

  - `_save_session(clinic_id, phone, session)`:
    - PutItem DynamoDB com TTL = now() + 30min

  - `_get_state_config(state: ConversationState) -> dict`:
    - Retorna configuração do estado: template_key, buttons, transitions, fallback, previous

  - **Handlers on_enter** (métodos privados):
    - `_on_enter_welcome(clinic_id, phone)`: buscar paciente no RDS, personalizar boas-vindas
    - `_on_enter_price_table(clinic_id)`: buscar serviços e montar tabela de preços
    - `_on_enter_available_days(clinic_id, session)`: buscar próximos 14 dias com disponibilidade
    - `_on_enter_select_time(clinic_id, session)`: chamar availability_engine para slots
    - `_on_enter_confirm_booking(clinic_id, session)`: montar resumo
    - `_on_enter_booked(clinic_id, session)`: chamar appointment_service.create_appointment
    - `_on_enter_reschedule_lookup(clinic_id, phone)`: buscar agendamento ativo
    - `_on_enter_faq_menu(clinic_id)`: buscar FAQ items
    - `_on_enter_faq_answer(clinic_id, session)`: buscar resposta da FAQ selecionada

  - **Definição estática dos estados** (dicionário ou método):
    ```python
    STATE_CONFIG = {
        ConversationState.MAIN_MENU: {
            "template_key": "MAIN_MENU",
            "buttons": [
                {"id": "schedule", "label": "Agendar sessão"},
                {"id": "reschedule", "label": "Remarcar sessão"},
                {"id": "faq", "label": "Dúvidas sobre sessão"},
            ],
            "transitions": {
                "schedule": ConversationState.SCHEDULE_MENU,
                "reschedule": ConversationState.RESCHEDULE_LOOKUP,
                "faq": ConversationState.FAQ_MENU,
                "human": ConversationState.HUMAN_HANDOFF,
            },
            "fallback": ConversationState.UNRECOGNIZED,
            "previous": None,  # Sem voltar do menu principal
        },
        # ... demais estados
    }
    ```

  - **Suporte a fallback numérico**: se o input for "1", "2", "3", etc., mapear para o botão correspondente pela ordem

#### `scheduler/sls/functions/webhook/interface.yml`

- **Criar**
- Funções:
  - `WhatsAppWebhook`:
    - handler: `src.functions.webhook.handler.handler`
    - POST `/webhook/whatsapp`
    - cors: true
    - **Sem API key** — autenticação é feita pelo payload do z-api (validação de instanceId)
    - IAM: DynamoDB GetItem/PutItem/Query em ConversationSessionsTable e MessageEventsTable + SSM + logs
  - `WhatsAppStatusWebhook`:
    - handler: `src.functions.webhook.status_handler.handler`
    - POST `/webhook/whatsapp/status`
    - IAM: DynamoDB PutItem em MessageEventsTable + logs

#### `scheduler/src/functions/webhook/handler.py`

- **Criar**
- Handler `POST /webhook/whatsapp`:
  1. `parse_body(event)` — extrair payload do z-api
  2. Validar que `type == "ReceivedCallback"` e `fromMe == false`
  3. Ignorar mensagens de grupo (`isGroup == true`)
  4. Extrair `instanceId` → buscar clínica no RDS por `zapi_instance_id`
  5. Se clínica não encontrada → log warning, retornar 200 (não reprocessar)
  6. Instanciar provider, conversation_engine, message_tracker
  7. `provider.parse_incoming_message(payload)` → IncomingMessage
  8. `message_tracker.track_inbound(...)` — registrar mensagem recebida
  9. `conversation_engine.process_message(clinic_id, incoming)` → list[OutgoingMessage]
  10. Para cada OutgoingMessage:
      - `message_tracker.track_outbound(status=QUEUED)`
      - Enviar via provider
      - `message_tracker.track_outbound(status=SENT|FAILED)`
  11. Retornar 200 (sempre, mesmo em erro interno — para z-api não reenviar)

#### `scheduler/src/functions/webhook/status_handler.py`

- **Criar**
- Handler `POST /webhook/whatsapp/status`:
  1. `parse_body(event)`
  2. Validar `type == "MessageStatusCallback"`
  3. Extrair `status`, `ids[]`, `phone`, `momment`
  4. Para cada messageId em ids:
      - Buscar clinicId pelo instanceId ou phone (pode precisar de lookup)
      - `message_tracker.update_status(clinic_id, phone, message_id, status, timestamp, raw_payload)`
  5. Retornar 200

---

### Fase 8 — Agendamento e disponibilidade

---

#### `scheduler/src/services/availability_engine.py`

- **Criar**
- Classe `AvailabilityEngine`:
  - `__init__(self, db: PostgresService)`
  - `get_available_slots(clinic_id: str, date: str, service_id: str) -> list[str]`:
    1. Buscar serviço → `duration_minutes`
    2. Buscar clínica → `buffer_minutes`
    3. Buscar `availability_rules` para `day_of_week` da data
    4. Se nenhuma regra ativa → retornar lista vazia
    5. Buscar `availability_exceptions` para a data:
       - Se BLOCKED → retornar lista vazia
       - Se SPECIAL_HOURS → usar start_time/end_time da exceção
    6. Calcular slot_duration = duration_minutes + buffer_minutes
    7. Gerar slots de start_time a end_time - duration_minutes (step = slot_duration)
    8. Buscar appointments da data (status = CONFIRMED)
    9. Remover slots que conflitam com appointments existentes
    10. Retornar lista de horários `["09:00", "10:00", ...]`

  - `get_available_days(clinic_id: str, service_id: str, days_ahead: int = 14) -> list[str]`:
    1. Para cada dia nos próximos `days_ahead`:
       - Chamar `get_available_slots(clinic_id, date, service_id)`
       - Se tem slots → incluir na lista
    2. Retornar datas com disponibilidade `["2026-02-03", "2026-02-05", ...]`

  - `get_available_slots_for_areas(clinic_id: str, date: str, areas_text: str) -> list[str]`:
    1. Parse do texto de áreas (fuzzy match contra serviços cadastrados)
    2. Somar durações dos serviços identificados
    3. Gerar slots com a duração total + buffer
    4. Retornar slots disponíveis
    - Nota: se não conseguir identificar áreas como serviços, usar duração do serviço principal da clínica como fallback

  - `_check_conflict(existing_appointments, slot_start, slot_end) -> bool`:
    - Verificar se o slot (start→end) colide com algum appointment existente

#### `scheduler/src/services/appointment_service.py`

- **Criar**
- Classe `AppointmentService`:
  - `__init__(self, db: PostgresService, reminder_service: ReminderService, sheets_sync: SheetsSync)`
  - `create_appointment(clinic_id, phone, service_id, date, time, areas, professional_id=None) -> dict`:
    1. Buscar ou criar paciente em `scheduler.patients`
    2. Calcular end_time = time + duration_minutes do serviço
    3. Verificar conflito: SELECT from appointments WHERE clinic_id, date, time overlaps
    4. Se conflito → raise ConflictError
    5. INSERT em `scheduler.appointments`
    6. `reminder_service.schedule_reminder(appointment)` — criar lembrete 24h antes
    7. `sheets_sync.sync_appointment(appointment, "CREATED")` — sync para Google Sheets
    8. Retornar appointment criado

  - `reschedule_appointment(appointment_id, new_date, new_time) -> dict`:
    1. SELECT appointment com lock otimístico (verificar version)
    2. Verificar conflito no novo horário
    3. UPDATE appointment (date, time, end_time, version+1)
    4. `reminder_service.cancel_reminder(appointment_id)` — cancelar lembrete antigo
    5. `reminder_service.schedule_reminder(updated_appointment)` — criar novo lembrete
    6. `sheets_sync.sync_appointment(appointment, "RESCHEDULED")`
    7. Retornar appointment atualizado

  - `cancel_appointment(appointment_id) -> dict`:
    1. UPDATE status = CANCELLED
    2. `reminder_service.cancel_reminder(appointment_id)`
    3. `sheets_sync.sync_appointment(appointment, "CANCELLED")`

  - `get_active_appointment_by_phone(clinic_id, phone) -> dict | None`:
    1. Buscar paciente por phone
    2. SELECT from appointments WHERE patient_id, status=CONFIRMED, date >= today
    3. Retornar o mais próximo ou None

#### `scheduler/src/functions/availability/slots.py`

- **Criar**
- Handler `GET /clinics/{clinicId}/available-slots?date=YYYY-MM-DD&serviceId=UUID`:
  1. `require_api_key(event)`
  2. Extrair `clinicId`, `date`, `serviceId`
  3. `availability_engine.get_available_slots(clinicId, date, serviceId)`
  4. Retornar 200 com `{"slots": ["09:00", "10:00", ...]}`

#### `scheduler/sls/functions/appointment/interface.yml`

- **Criar**
- `CreateAppointment`: POST `/appointments`, IAM: DynamoDB (ScheduledReminders PutItem) + SSM + logs
- `ListAppointments`: GET `/clinics/{clinicId}/appointments?date=YYYY-MM-DD`, IAM: SSM + logs
- `UpdateAppointment`: PUT `/appointments/{appointmentId}`, IAM: DynamoDB (ScheduledReminders PutItem/UpdateItem) + SSM + logs

#### `scheduler/src/functions/appointment/create.py`

- **Criar**
- Handler `POST /appointments`:
  1. `require_api_key(event)`, `parse_body(event)`
  2. Validar: clinicId, phone, serviceId, date, time, areas
  3. `appointment_service.create_appointment(...)`
  4. Retornar 201

#### `scheduler/src/functions/appointment/list.py`

- **Criar**
- Handler `GET /clinics/{clinicId}/appointments?date=YYYY-MM-DD&status=CONFIRMED`:
  1. `require_api_key(event)`
  2. SELECT from appointments com filtros de date e status
  3. JOIN com patients para incluir nome e telefone
  4. Retornar 200

#### `scheduler/src/functions/appointment/update.py`

- **Criar**
- Handler `PUT /appointments/{appointmentId}`:
  1. `require_api_key(event)`, `parse_body(event)`
  2. Campos: `status`, `notes`
  3. Se status mudando para CANCELLED → `appointment_service.cancel_appointment()`
  4. Senão → UPDATE direto
  5. Retornar 200

---

### Fase 9 — Lembretes e relatórios

---

#### `scheduler/src/services/reminder_service.py`

- **Criar**
- Classe `ReminderService`:
  - `__init__()`: DynamoDB table `SCHEDULED_REMINDERS_TABLE`
  - `schedule_reminder(appointment: dict)`:
    1. Calcular `send_at = appointment_date + start_time - 24h` (converter para UTC)
    2. Gerar reminderId (UUID)
    3. PutItem: PK=REMINDER#reminderId, SK=SEND_AT#iso, status=PENDING, appointmentId, clinicId, phoneNumber, patientName, reminderType=REMINDER_24H, TTL=send_at+48h
  - `cancel_reminder(appointment_id: str)`:
    1. Query por appointmentId (pode precisar de GSI ou scan limitado)
    2. Update status=CANCELLED para cada reminder encontrado
  - `get_pending_reminders(now: str) -> list`:
    1. Query GSI status-sendAt-index: status=PENDING, sendAt <= now
    2. Retornar lista
  - `mark_sent(reminder_id: str)`: Update status=SENT
  - `mark_failed(reminder_id: str, error: str)`: Update status=FAILED

#### `scheduler/sls/functions/reminder/interface.yml`

- **Criar**
```yaml
ReminderProcessor:
  image:
    name: lambdaimage
    command: ["src.functions.reminder.processor.handler"]
  memorySize: 512
  timeout: 60
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-ReminderProcessor-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:Query
        - dynamodb:UpdateItem
      Resource:
        - !GetAtt ScheduledRemindersTable.Arn
        - !Sub "${ScheduledRemindersTable.Arn}/index/*"
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource: !GetAtt MessageEventsTable.Arn
    - Effect: Allow
      Action: ssm:GetParameter
      Resource: "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - schedule:
        rate: rate(15 minutes)
        enabled: true
```

#### `scheduler/src/functions/reminder/processor.py`

- **Criar**
- Handler (invocado por EventBridge schedule):
  1. `reminder_service.get_pending_reminders(now=datetime.utcnow().isoformat())`
  2. Para cada lembrete:
     a. Buscar clínica no RDS (para provider config e clinic_name)
     b. Instanciar provider
     c. Renderizar template REMINDER_24H com variáveis
     d. Enviar mensagem via provider
     e. `message_tracker.track_outbound(...)` — registrar
     f. Se sucesso: `reminder_service.mark_sent(reminder_id)`
     g. Se falha: `reminder_service.mark_failed(reminder_id, error)`
  3. Log total: `[traceId: {id}] Processed {n} reminders: {sent} sent, {failed} failed`
  4. Retornar `{"processed": n, "sent": sent, "failed": failed}`

#### `scheduler/src/services/sheets_sync.py`

- **Criar**
- Classe `SheetsSync`:
  - `__init__()`:
    - Carregar credenciais da service account do SSM (`GOOGLE_SHEETS_SERVICE_ACCOUNT`)
    - `google.oauth2.service_account.Credentials.from_service_account_info()`
    - `googleapiclient.discovery.build('sheets', 'v4', credentials=creds)`
  - `sync_appointment(appointment: dict, action: str)`:
    1. Buscar clinic no RDS → `google_spreadsheet_id`, `google_sheet_name`
    2. Se spreadsheet_id não configurado → return (sem erro)
    3. Formatar linha: `[date, time, patient_name, phone, service, areas, status, "", appointment_id, datetime.utcnow()]`
    4. Se action == "CREATED": append row
    5. Se action == "RESCHEDULED" ou "CANCELLED": buscar linha por appointment_id → update
  - `_find_row_by_appointment_id(spreadsheet_id, sheet_name, appointment_id) -> int | None`:
    - Ler coluna appointment_id, retornar row number
  - `_append_row(spreadsheet_id, sheet_name, values)`:
    - `sheets.spreadsheets().values().append(...)`
  - `_update_row(spreadsheet_id, sheet_name, row_number, values)`:
    - `sheets.spreadsheets().values().update(...)`
- **Tratamento de erro**: try/except em todas as operações Sheets. Se falhar, logar warning e continuar. O agendamento no RDS não deve falhar por causa do Sheets.

#### `scheduler/sls/functions/report/interface.yml`

- **Criar**
```yaml
DailyReportSender:
  image:
    name: lambdaimage
    command: ["src.functions.report.daily.handler"]
  memorySize: 512
  timeout: 120
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-DailyReport-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:PutItem
      Resource: !GetAtt MessageEventsTable.Arn
    - Effect: Allow
      Action: ssm:GetParameter
      Resource: "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - schedule:
        rate: cron(0 23 * * ? *)
        enabled: true
```
Nota: `cron(0 23 * * ? *)` = 23:00 UTC = 20:00 BRT. Se clínicas em fusos diferentes, seria necessário executar mais vezes e filtrar por timezone. Para o MVP, cron às 23:00 UTC cobre o BRT.

#### `scheduler/src/functions/report/daily.py`

- **Criar**
- Handler (invocado por EventBridge schedule):
  1. Buscar todas as clínicas ativas no RDS
  2. Para cada clínica:
     a. Calcular amanhã no timezone da clínica
     b. SELECT appointments WHERE clinic_id, date=amanhã, status=CONFIRMED ORDER BY start_time
     c. JOIN com patients e services
     d. Se nenhum agendamento → pular (não enviar relatório vazio)
     e. Montar mensagem formatada:
        ```
        📋 Agenda de amanhã ({data}):

        {hora} - {paciente} | {servico} | {areas}
        ...

        Total: {n} sessões agendadas
        ```
     f. Instanciar provider da clínica
     g. Enviar mensagem para `clinic.phone`
     h. `message_tracker.track_outbound(...)` — registrar
  3. Log resumo

---

### Fase 10 — Testes, mocks e docs

---

#### `scheduler/tests/mocks/webhook/text_message.json`

- **Criar**
```json
{
  "body": "{\"type\":\"ReceivedCallback\",\"instanceId\":\"instance-123\",\"messageId\":\"MSG001\",\"phone\":\"5511999990000\",\"fromMe\":false,\"momment\":1706745600000,\"chatName\":\"Maria Silva\",\"senderName\":\"Maria Silva\",\"isGroup\":false,\"text\":{\"message\":\"Olá\"}}"
}
```

#### `scheduler/tests/mocks/webhook/button_response.json`

- **Criar**
```json
{
  "body": "{\"type\":\"ReceivedCallback\",\"instanceId\":\"instance-123\",\"messageId\":\"MSG002\",\"phone\":\"5511999990000\",\"fromMe\":false,\"momment\":1706745700000,\"chatName\":\"Maria Silva\",\"senderName\":\"Maria Silva\",\"isGroup\":false,\"referenceMessageId\":\"MSG001\",\"buttonsResponseMessage\":{\"buttonId\":\"schedule\",\"message\":\"Agendar sessão\"}}"
}
```

#### `scheduler/tests/mocks/webhook/status_update.json`

- **Criar**
```json
{
  "body": "{\"type\":\"MessageStatusCallback\",\"status\":\"READ\",\"ids\":[\"MSG001\"],\"momment\":1706745800000,\"phone\":\"5511999990000\",\"instanceId\":\"instance-123\"}"
}
```

#### `scheduler/tests/mocks/appointment/create.json`

- **Criar**
```json
{
  "body": "{\"clinicId\":\"laser-beauty-sp\",\"phone\":\"5511999990000\",\"serviceId\":\"uuid-service-1\",\"date\":\"2026-02-15\",\"time\":\"09:00\",\"areas\":\"Pernas e axilas\"}",
  "headers": {"x-api-key": "test-api-key"}
}
```

#### `scheduler/tests/mocks/clinic/create.json`

- **Criar**
```json
{
  "body": "{\"name\":\"Laser Beauty SP\",\"phone\":\"5511988880000\",\"address\":\"Rua Exemplo, 123 - SP\",\"business_hours\":{\"mon\":{\"start\":\"09:00\",\"end\":\"18:00\"},\"tue\":{\"start\":\"09:00\",\"end\":\"18:00\"},\"wed\":{\"start\":\"09:00\",\"end\":\"18:00\"},\"thu\":{\"start\":\"09:00\",\"end\":\"18:00\"},\"fri\":{\"start\":\"09:00\",\"end\":\"18:00\"}},\"buffer_minutes\":10}",
  "headers": {"x-api-key": "test-api-key"}
}
```

#### `scheduler/tests/postman/CLAUDE.md`

- **Criar**
- Padrões Postman para o projeto scheduler:
  - Naming: `{domain}.postman_collection.json`
  - Collection name: `Clinic Scheduler - {Domain}`
  - Variables padrão: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`
  - Headers obrigatórios: `x-api-key: {{API_KEY}}`, `Content-Type: application/json`
  - Toda request deve ter test scripts validando status code e estrutura
  - Response examples incluídos (sucesso + erros)
  - URLs no formato `{{BASE_URL}}/{{ENVIRONMENT}}/path`

#### `scheduler/tests/postman/clinics.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Clinics`
- Variables:
  ```json
  [
    {"key": "BASE_URL", "value": "https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"},
    {"key": "ENVIRONMENT", "value": "dev"},
    {"key": "API_KEY", "value": "YOUR_API_KEY_HERE"},
    {"key": "clinicId", "value": ""}
  ]
  ```
- Requests:
  1. **Create Clinic** — POST `/clinics`
     - Body: `{"name": "Laser Beauty SP", "phone": "5511988880000", "address": "Rua Exemplo, 123", "business_hours": {"mon": {"start": "09:00", "end": "18:00"}, ...}, "buffer_minutes": 10}`
     - Test: status 201, response has `clinicId`, set `clinicId` variable
     - Response examples: Success (201), Missing Fields (400)
  2. **List Clinics** — GET `/clinics`
     - Test: status 200, response is array
     - Response examples: Success (200)
  3. **Get Clinic** — GET `/clinics/{{clinicId}}`
     - Test: status 200, response has `clinic_id`
     - Response examples: Success (200), Not Found (404)
  4. **Update Clinic** — PUT `/clinics/{{clinicId}}`
     - Body: `{"phone": "5511977770000", "buffer_minutes": 15}`
     - Test: status 200
     - Response examples: Success (200), Not Found (404)
  5. **Update Clinic - Set Google Sheets** — PUT `/clinics/{{clinicId}}`
     - Body: `{"google_spreadsheet_id": "1BxiMV...abc", "google_sheet_name": "Agenda"}`
     - Test: status 200
  6. **Update Clinic - Set z-api** — PUT `/clinics/{{clinicId}}`
     - Body: `{"zapi_instance_id": "instance-123", "zapi_instance_token": "token-abc"}`
     - Test: status 200

#### `scheduler/tests/postman/services.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Services`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`, `serviceId`
- Requests:
  1. **Create Service** — POST `/clinics/{{clinicId}}/services`
     - Body: `{"name": "Depilação a laser", "duration_minutes": 45, "price_cents": 15000, "description": "Sessão avulsa de depilação a laser com Soprano Ice"}`
     - Test: status 201, set `serviceId`
     - Response examples: Success (201), Missing Fields (400), Clinic Not Found (404)
  2. **List Services** — GET `/clinics/{{clinicId}}/services`
     - Test: status 200, array with service objects
  3. **Update Service** — PUT `/services/{{serviceId}}`
     - Body: `{"price_cents": 18000, "active": true}`
     - Test: status 200
  4. **Create Service (Missing Fields)** — POST `/clinics/{{clinicId}}/services`
     - Body: `{"name": "Incompleto"}`  (sem duration_minutes)
     - Test: status 400

#### `scheduler/tests/postman/professionals.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Professionals`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`, `professionalId`
- Requests:
  1. **Create Professional** — POST `/clinics/{{clinicId}}/professionals`
     - Body: `{"name": "Dra. Ana Souza", "role": "Biomédica esteta"}`
     - Test: status 201, set `professionalId`
  2. **List Professionals** — GET `/clinics/{{clinicId}}/professionals`
     - Test: status 200

#### `scheduler/tests/postman/availability.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Availability`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`, `serviceId`, `ruleId`, `exceptionId`
- Requests:
  1. **Create Availability Rule** — POST `/clinics/{{clinicId}}/availability-rules`
     - Body: `{"day_of_week": 1, "start_time": "09:00", "end_time": "18:00"}`
     - Test: status 201, set `ruleId`
     - Response examples: Success (201), Invalid day_of_week (400)
  2. **List Availability Rules** — GET `/clinics/{{clinicId}}/availability-rules`
     - Test: status 200
  3. **Create Availability Exception (Block)** — POST `/clinics/{{clinicId}}/availability-exceptions`
     - Body: `{"exception_date": "2026-02-20", "exception_type": "BLOCKED", "reason": "Feriado"}`
     - Test: status 201
  4. **Create Availability Exception (Special Hours)** — POST `/clinics/{{clinicId}}/availability-exceptions`
     - Body: `{"exception_date": "2026-02-14", "exception_type": "SPECIAL_HOURS", "start_time": "10:00", "end_time": "15:00", "reason": "Horário especial Valentine's Day"}`
     - Test: status 201
  5. **List Availability Exceptions** — GET `/clinics/{{clinicId}}/availability-exceptions?from=2026-02-01&to=2026-02-28`
     - Test: status 200
  6. **Get Available Slots** — GET `/clinics/{{clinicId}}/available-slots?date=2026-02-15&serviceId={{serviceId}}`
     - Test: status 200, response has `slots` array
     - Response examples: Success with slots (200), No availability (200 with empty slots), Blocked day (200 with empty slots)

#### `scheduler/tests/postman/appointments.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Appointments`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`, `serviceId`, `appointmentId`
- Requests:
  1. **Create Appointment** — POST `/appointments`
     - Body: `{"clinicId": "{{clinicId}}", "phone": "5511999990000", "serviceId": "{{serviceId}}", "date": "2026-02-15", "time": "09:00", "areas": "Pernas e axilas"}`
     - Test: status 201, response has `appointmentId`, set `appointmentId`
     - Response examples: Success (201), Time Conflict (409), Missing Fields (400)
  2. **List Appointments** — GET `/clinics/{{clinicId}}/appointments?date=2026-02-15`
     - Test: status 200, array with patient info
  3. **List Appointments (by status)** — GET `/clinics/{{clinicId}}/appointments?date=2026-02-15&status=CONFIRMED`
     - Test: status 200
  4. **Update Appointment (add notes)** — PUT `/appointments/{{appointmentId}}`
     - Body: `{"notes": "Paciente com alergia a creme anestésico"}`
     - Test: status 200
  5. **Cancel Appointment** — PUT `/appointments/{{appointmentId}}`
     - Body: `{"status": "CANCELLED"}`
     - Test: status 200, response has status CANCELLED
     - Response examples: Success (200), Not Found (404)
  6. **Create Appointment (Conflict)** — POST `/appointments`
     - Body: mesmo horário de um appointment existente
     - Test: status 409

#### `scheduler/tests/postman/templates.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Message Templates`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`, `templateId`
- Requests:
  1. **Create Template** — POST `/clinics/{{clinicId}}/templates`
     - Body: `{"template_key": "WELCOME_NEW", "content": "Olá! Bem-vinda à {{clinic_name}}! Como posso ajudar?", "buttons": [{"id": "schedule", "label": "Agendar sessão"}, {"id": "reschedule", "label": "Remarcar"}, {"id": "faq", "label": "Dúvidas"}]}`
     - Test: status 201, set `templateId`
     - Response examples: Success (201), Duplicate Key (409)
  2. **List Templates** — GET `/clinics/{{clinicId}}/templates`
     - Test: status 200
  3. **List Templates (by key)** — GET `/clinics/{{clinicId}}/templates?template_key=WELCOME_NEW`
     - Test: status 200
  4. **Update Template** — PUT `/templates/{{templateId}}`
     - Body: `{"content": "Olá! Seja muito bem-vinda à {{clinic_name}}!", "active": true}`
     - Test: status 200

#### `scheduler/tests/postman/faq.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - FAQ`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`, `faqId`
- Requests:
  1. **Create FAQ Item** — POST `/clinics/{{clinicId}}/faq`
     - Body: `{"question_key": "EQUIPMENT", "question_label": "Qual equipamento vocês usam?", "answer": "Trabalhamos com o Soprano Ice Platinum, uma das tecnologias mais avançadas do mundo em depilação a laser.", "display_order": 1}`
     - Test: status 201, set `faqId`
  2. **Create FAQ Item (Session Interval)** — POST `/clinics/{{clinicId}}/faq`
     - Body: `{"question_key": "SESSION_INTERVAL", "question_label": "Qual o intervalo entre sessões?", "answer": "As sessões têm intervalo médio de 30 dias, ou seja, você realiza aproximadamente 1 sessão por mês.", "display_order": 2}`
     - Test: status 201
  3. **List FAQ** — GET `/clinics/{{clinicId}}/faq`
     - Test: status 200, array ordered by display_order
  4. **Update FAQ Item** — PUT `/faq/{{faqId}}`
     - Body: `{"answer": "Resposta atualizada", "display_order": 5}`
     - Test: status 200

#### `scheduler/tests/postman/messaging.postman_collection.json`

- **Criar**
- Collection name: `Clinic Scheduler - Messaging`
- Variables: `BASE_URL`, `ENVIRONMENT`, `API_KEY`, `clinicId`
- Requests:
  1. **Send Text Message** — POST `/send`
     - Body: `{"clinicId": "{{clinicId}}", "phone": "5511999990000", "type": "text", "content": "Olá! Esta é uma mensagem de teste."}`
     - Test: status 200, response has `messageId`
     - Response examples: Success (200), Clinic Not Found (404), Provider Error (502)
  2. **Send Button Message** — POST `/send`
     - Body: `{"clinicId": "{{clinicId}}", "phone": "5511999990000", "type": "buttons", "content": "Escolha uma opção:", "buttons": [{"id": "1", "label": "Opção 1"}, {"id": "2", "label": "Opção 2"}]}`
     - Test: status 200
  3. **Simulate Incoming Text (webhook test)** — POST `/webhook/whatsapp`
     - Body: `{"type": "ReceivedCallback", "instanceId": "instance-123", "messageId": "MSG-TEST-001", "phone": "5511999990000", "fromMe": false, "momment": 1706745600000, "senderName": "Maria Silva", "isGroup": false, "text": {"message": "Olá"}}`
     - Headers: sem x-api-key (webhook não usa)
     - Test: status 200
  4. **Simulate Button Response (webhook test)** — POST `/webhook/whatsapp`
     - Body: `{"type": "ReceivedCallback", "instanceId": "instance-123", "messageId": "MSG-TEST-002", "phone": "5511999990000", "fromMe": false, "momment": 1706745700000, "senderName": "Maria Silva", "isGroup": false, "referenceMessageId": "MSG-TEST-001", "buttonsResponseMessage": {"buttonId": "schedule", "message": "Agendar sessão"}}`
     - Test: status 200
  5. **Simulate Status Update (webhook test)** — POST `/webhook/whatsapp/status`
     - Body: `{"type": "MessageStatusCallback", "status": "READ", "ids": ["MSG-TEST-001"], "momment": 1706745800000, "phone": "5511999990000", "instanceId": "instance-123"}`
     - Test: status 200

#### Atualizar `CLAUDE.md`

- **Modificar**
- Adicionar seção `## Scheduler Project` com:
  - Descrição: "WhatsApp-based clinic appointment scheduling system"
  - Diretório: `scheduler/`
  - Comandos de deploy:
    ```bash
    cd scheduler && npm install && pip install -r requirements.txt
    cd scheduler && serverless deploy --stage dev --aws-profile traffic-manager
    ```
  - Estrutura de pastas (resumo)
  - Tabelas DynamoDB e schema RDS

#### Atualizar `.gitignore`

- **Modificar**
- Adicionar entradas para `scheduler/`:
  ```
  scheduler/.env
  scheduler/node_modules/
  scheduler/.serverless/
  ```

---

## 7. Convenções a respeitar

- **Logging**: `[traceId: {trace_id}] [{step}] {message}` (ver `CLAUDE.md`)
- **Naming**:
  - clinic_id: lowercase kebab-case (ex: `laser-beauty-sp`)
  - Lambda functions: PascalCase no interface.yml (ex: `WhatsAppWebhook`, `CreateClinic`)
  - Handlers: `src.functions.{domain}.{module}.handler` (ou `create_handler`, `list_handler` quando múltiplos no mesmo módulo)
  - Tabelas DynamoDB: `${resourcePrefix}-{domain}` (ex: `clinic-scheduler-infra-dev-conversation-sessions`)
  - Tabelas RDS: `scheduler.{table_name}` (schema-qualified)
- **Secrets**: SSM `/${stage}/KEY` — nunca hardcodar
- **Responses**: `{"status": "SUCCESS|ERROR", "message": "...", ...data}` com CORS headers
- **HTTP codes**: 200 (OK), 201 (Created), 400 (Validation error), 404 (Not found), 409 (Conflict), 500 (Internal error)
- **IDs**: UUID v4 para todos os registros
- **Timestamps**: ISO 8601 UTC no banco, convertido para timezone da clínica na apresentação
- **DynamoDB**: PAY_PER_REQUEST, TTL habilitado, Decimal para números
- **RDS**: Connection pooling no nível do módulo, transactions com context manager
- **Provider WhatsApp**: Sempre usar a interface abstrata, nunca chamar z-api diretamente nos handlers
- **Google Sheets**: Operações sempre em try/except — falha no Sheets nunca deve impedir operação no RDS
