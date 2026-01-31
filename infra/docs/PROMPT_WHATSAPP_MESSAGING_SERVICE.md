# Prompt: Inicializar projeto WhatsApp Messaging Service (do zero)

Use este documento como **especificação completa** para um LLM iniciar do zero um novo projeto de **backend de mensageria WhatsApp**, seguindo a mesma arquitetura, convenções e padrões de desenvolvimento da pasta `infra/` existente neste repositório.

**Escopo:** Somente **backend Lambda-oriented**. Não há portal, frontend nem interface web — apenas APIs, webhooks e persistência.

---

## 1. Objetivo do sistema

Backend **serverless** (Lambda) para:

- **Conversas WhatsApp:** gestão da comunicação via Meta Cloud API (envio e recepção).
- **Criação e envio de mensagens** (texto, imagem, áudio, vídeo, documento, templates de texto, templates com botões, listas interativas, etc.).
- **Criação e gestão de template messages** (CRUD via API).
- **Registro de eventos de mensagens:** persistir eventos recebidos no webhook (mensagens entrantes, callbacks de botão, status de entrega, etc.) e, se desejado, logs de mensagens enviadas.
- **Multi-tenant** por `clientId`: os mesmos **clientIds** já existentes na base (tabela **Clients** ou equivalente) — o sistema atende apenas esses clientes, validando `clientId` em todas as operações.

Fluxo geral: **senders** (Lambdas/APIs que enviam mensagens), **listeners** (webhook que recebe mensagens/callbacks do WhatsApp, registra eventos e processa, ex.: if/else por botão), **CRUD de templates** e **persistência de eventos**.

---

## 2. Arquitetura de referência (copiar da `infra/`)

### 2.1 Serverless Framework

- **Framework:** Serverless Framework **3**.
- **Provider:** AWS.
- **Runtime:** Python (Lambdas em **Python**).
- **Container:** Lambdas via **imagem Docker** no ECR (padrão `provider.ecr.images` + `path: .`).
- **Plugin:** `serverless-iam-roles-per-function` (IAM por função).

Estrutura do `serverless.yml`:

```yaml
service: <nome-do-servico>-infra

frameworkVersion: "3"

custom:
  stage: ${opt:stage, self:provider.stage}
  resourcePrefix: ${self:service}-${self:custom.stage}
  accountId: "<account-id>"
  awsId: "<account-id>"

provider:
  name: aws
  stage: ${opt:stage, 'dev'}
  region: ${opt:region, 'us-east-1'}
  ecr:
    images:
      lambdaimage:
        path: .
  environment:
    STAGE: ${self:custom.stage}
    # Tabelas DynamoDB
    CLIENTS_TABLE: ${self:custom.resourcePrefix}-clients
    # ... demais env vars (RDS, SSM, etc.)

functions:
  - ${file(sls/functions/<dominio>/interface.yml)}

resources:
  - ${file(sls/resources/dynamodb/<tabela>.yml)}
  # - ${file(sls/resources/rds/postgres-database.yml)}  # se houver RDS

plugins:
  - serverless-iam-roles-per-function
```

### 2.2 Estrutura de pastas (espelhar `infra/`)

```
infra/
├── serverless.yml
├── Dockerfile
├── requirements.txt
├── package.json
├── sls/
│   ├── functions/
│   │   ├── webhook/          # listener WhatsApp (entrada)
│   │   │   └── interface.yml
│   │   ├── send/             # senders (enviar mensagem, enviar template, etc.)
│   │   │   └── interface.yml
│   │   ├── templates/        # CRUD template messages
│   │   │   └── interface.yml
│   │   └── ...               # outros domínios (ex.: config WhatsApp por clientId)
│   └── resources/
│       ├── dynamodb/
│       │   ├── <tabela>.yml
│       │   └── ...
│       └── rds/              # se usar Postgres
│           └── postgres-database.yml
├── src/
│   ├── functions/            # handlers por domínio
│   │   ├── webhook/
│   │   ├── send/
│   │   ├── templates/
│   │   └── ...
│   ├── services/             # lógica de negócio reutilizável
│   ├── utils/                # auth, http, logging, etc.
│   └── scripts/              # scripts locais (opcional)
├── tests/
│   ├── mocks/
│   │   └── <dominio>/
│   ├── integration/
│   └── postman/
│       └── CLAUDE.md
├── docs/
│   └── work/
│       ├── prd/
│       └── spec/
└── scripts/                  # build Docker, etc. (opcional)
```

### 2.3 Padrão de funções (interface.yml)

Cada domínio em `sls/functions/<dominio>/interface.yml`. Uma ou mais funções por arquivo. Exemplo:

```yaml
WhatsAppWebhook:
  image:
    name: lambdaimage
    command: ["src.functions.webhook.whatsapp.handler"]
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-WhatsAppWebhook-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - dynamodb:GetItem
        - dynamodb:PutItem
        - dynamodb:Query
      Resource: !GetAtt <Tabela>.Arn
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
    - http:
        path: webhook/whatsapp
        method: post
        cors: true
```

- **Handler:** `src.functions.<dominio>.<modulo>.handler`.
- **Imagem:** `lambdaimage` (Dockerfile na raiz).
- **IAM:** apenas as ações DynamoDB/RDS/SQS/SSM necessárias + `logs`.
- **Events:** `http` (path, method, cors) ou `sqs` / outros, conforme o caso.

### 2.4 Dockerfile

Seguir o padrão do `infra` atual:

```dockerfile
FROM public.ecr.aws/lambda/python:3.9

COPY requirements.txt ${LAMBDA_TASK_ROOT}
RUN pip install --no-cache-dir -r requirements.txt -t ${LAMBDA_TASK_ROOT}

COPY src/ ${LAMBDA_TASK_ROOT}/src/

CMD [ "src.functions.webhook.whatsapp.handler" ]
```

O `command` em cada função sobrescreve o `CMD`. Manter Python 3.9 ou o mesmo já usado no projeto de referência.

---

## 3. Dados: DynamoDB vs RDS

- **Regra:** Para cada entidade, **avaliar** se o modelo é relacional (muitos relacionamentos, FKs, JOINs, transações) ou documento/chave-valor (acesso por PK/GSI, sem JOINs).
- **DynamoDB:**  
  - Boas opções: **registro de eventos de mensagens** (payloads do webhook — mensagens recebidas, callbacks de botão, status de entrega/leitura — e logs de envio), mapeamento `phone_number_id`/`waba_id` → `clientId`, cache de sessão/estado por conversa, templates se o modelo for “um doc por template” com poucas relações.
  - Usar `BillingMode: PAY_PER_REQUEST`, `AttributeDefinitions`, `KeySchema` e `GlobalSecondaryIndexes` quando precisar de queries por `clientId`, `createdAt`, etc. (ex.: GSI `clientId-createdAt-index`).
- **RDS (PostgreSQL):**  
  - Boas opções: **template messages** (estrutura rica: variáveis, botões, múltiplos componentes, histórico de versões, aprovação Meta), **configuração WhatsApp por cliente** (clientId, waba_id, phone_number_id, token, etc.) com integridade referencial, e qualquer fluxo que exija transações ou JOINs.
- **Clients (clientId):**  
  - O sistema deve **reutilizar os mesmos clientIds**. Isso implica:
    - **Mesmo stack:** Se o novo serviço for adicionado ao mesmo `serverless.yml` (mesmo `resources`), usar `!GetAtt ClientsTable.Arn` e `CLIENTS_TABLE` já existentes.
    - **Stack separada:** Se for outro projeto/stack, injetar o nome ou ARN da tabela `Clients` via env (ex.: `EXISTING_CLIENTS_TABLE` ou `CLIENTS_TABLE_ARN`), com IAM permitindo `dynamodb:GetItem`/`Query` nessa tabela. **Somente leitura** para validar existência de `clientId` e metadados.
  - Em todo request (exceto webhook puro da Meta), validar `clientId` e, se for o caso, `apiKey`/token associado ao cliente.

---

## 4. Comunicação WhatsApp (Meta Cloud API)

### 4.1 Escopo da integração

- **Envio (senders):**  
  - Texto, imagem, áudio, vídeo, documento.  
  - Template messages: texto, com botões (quick_reply, URL, call), listas interativas, etc.  
  - Chamadas à Meta Cloud API (POST para enviar mensagens, uso de `messaging_product`, `recipient`, `type`, `template`, `interactive`, etc.).
- **Recepção (listeners):**  
  - **Webhook HTTP** (`POST /webhook/whatsapp` ou similar) para:
    - `messages` (texto, botão, lista, mídia).
    - `message_template_status_update`, `message_delivery`, etc., se forem úteis.
  - Validar assinatura do webhook (HMAC) usando o token do app Meta.  
  - **Registrar eventos de mensagens:** persistir cada evento recebido (mensagem, callback, status) em DynamoDB ou RDS antes ou em paralelo ao processamento.  
  - Responder **200 rapidamente**; processar o payload de forma assíncrona (in-line ou via SQS) para não estourar timeout.  
  - Mapear cada evento a um `clientId` (via `phone_number_id` / `waba_id` em tabela de config) e executar o fluxo (if/else por tipo de mensagem, botão, etc.).
- **Templates:**  
  - Configuração interna (CRUD) de template messages.  
  - Envio usando `template` (nome, idioma, componentes, botões, variáveis).  
  - Considerar que templates precisam ser **aprovados** na Meta; o sistema armazena a definição e o nome aprovado.

### 4.2 Tipos de mensagem a suportar (envio e, quando fizer sentido, recepção)

- `text`
- `image`, `audio`, `video`, `document`
- `template` (texto, botões: quick_reply, url, phone_number, listas, etc.)
- `interactive` (botões, lista)
- `reaction` (se for necessário)

Na recepção: tratar `text`, `button` (payload), `interactive` (list_reply, button_reply), e tipos de mídia conforme a necessidade do fluxo (if/else por botão ou por tipo).

### 4.3 Secrets e configuração

- **Tokens e chaves** da Meta (token do app, `verify_token` do webhook) em **AWS Systems Manager Parameter Store**: `/${stage}/WHATSAPP_*` ou similar.  
- **Nunca** hardcodar em código ou em `.md`.  
- Em ambiente local, usar `.env` (no `.gitignore`) e, em testes, `source .env` antes de `curl`.

---

## 5. Fluxos principais

### 5.1 Sender (enviar mensagem)

- **Entrada:** API HTTP (ou invocação interna) com `clientId`, `to` (número), `type` (text, image, template, interactive, etc.) e payload conforme o tipo.
- **Validação:** `clientId` existe (Clients); cliente tem config WhatsApp (WABA, `phone_number_id`, token) ativa.
- **Ação:** Montar o JSON da Meta Cloud API e fazer POST. Tratar erros (rate limit, template não aprovado, etc.) e, se desejado, registrar em DynamoDB/RDS (log de envio).
- **Resposta:** `http_response(200, {"status":"SUCCESS", ...})` ou erro 4xx/5xx.

### 5.2 Listener (webhook WhatsApp)

- **Entrada:** `POST /webhook/whatsapp` com body da Meta.  
- **Verificação de assinatura** (header `X-Hub-Signature-256` ou equivalente). Se inválida, retornar 401/403.  
- **GET no webhook (verificação Meta):** Se `hub.mode=subscribe` e `hub.verify_token` correto, retornar `hub.challenge`.  
- **POST:** Extrair `phone_number_id`, `contacts`, `messages`, `message.type`, `button`, `interactive`, etc.  
- **Registrar evento:** Persistir o evento de mensagem (payload relevante) em DynamoDB ou RDS (tabela de eventos) antes ou em paralelo ao processamento.  
- **Resolver `clientId`:** Tabela de config (Dynamo ou RDS) por `phone_number_id` (ou waba_id).  
- **Processamento:** Fluxo if/else (ex.: `button.payload`, `interactive.list_reply.id`, `text.body`) e **enviar a resposta** via serviço de envio (reutilizando o sender) ou montando a chamada à Meta.  
- Responder **200** logo; se o processamento for pesado, enfileirar em **SQS** e tratar em outra Lambda.

### 5.3 Template messages (CRUD e uso)

- **Criar/atualizar template:**  
  - Body: nome, idioma, categoria, componentes (header, body, buttons, etc.).  
  - Persistir em RDS (ou Dynamo, se o modelo for simples).  
  - Opcional: submissão à Meta para aprovação (pode ser manual ou via API de criação de templates, conforme o plano).
- **Listar templates:** Por `clientId`, filtros (idioma, status na Meta se armazenado).  
- **Enviar usando template:** Endpoint ou uso interno: `clientId`, `to`, `templateName`, `language`, `components` (variáveis, botões dinâmicos). O sender monta o `template` no payload da Meta e envia.

---

## 6. Convenções de código e padrões (igual à `infra/`)

### 6.1 Handlers (Python)

- Assinatura: `def handler(event, context):`.  
- Usar `src.utils.http`: `parse_body`, `extract_query_param`, `extract_path_param`, `http_response`, `require_api_key` (ou `extract_api_key` + validação de `clientId`).  
- Respostas: `http_response(status_code, {"status":"SUCCESS"|"ERROR", "message":..., ...})`.  
- Logging: `logger.info(f"[traceId: {trace_id}] ...")` quando houver `trace_id`; `logger.error(..., exc_info=True)` em falhas.  
- Em reutilização de `ClientAuth` ou equivalente: validar `apiKey` → obter/validar `clientId`; para webhook, só assinatura Meta + lookup `clientId` por `phone_number_id`.

### 6.2 Naming

- **clientId:** lowercase kebab-case (ex.: `empresarods-abc123`).  
- **Lambda functions:** PascalCase no `serverless.yml` (ex.: `WhatsAppWebhook`, `SendTextMessage`).  
- **Handlers:** `src.functions.<dominio>.<modulo>.handler`.  
- **Tabelas DynamoDB:** `${resourcePrefix}-<nome>` (ex.: `...-whatsapp-events`).  
- **Arquivos de recurso:** `sls/resources/dynamodb/<nome>-table.yml`, `sls/resources/rds/postgres-database.yml`.

### 6.3 Autenticação em APIs REST

- `x-api-key` ou `Authorization: Bearer <key>`.  
- Validar e, a partir daí, obter/validar `clientId` (por exemplo, se a apiKey for por cliente, buscar em Clients; se for global, ainda exigir `clientId` no body/query/path e checar existência em Clients).  
- Webhook Meta: **apenas** verificação de assinatura HMAC; sem `x-api-key`.

### 6.4 Utilitários

- Manter ou recriar `src.utils.http` (parse_body, http_response, extract_*, require_api_key se fizer sentido).  
- `src.utils.decimal_utils.convert_decimal_to_json_serializable` ao retornar itens DynamoDB no body.  
- `src.utils.auth` (ou equivalente) para validar apiKey e/ou `clientId` em Clients.  
- Novo: `src.services.whatsapp_client` (ou similar) para chamadas à Meta (envio, e talvez leitura de status de template).

---

## 7. Workflow de desenvolvimento (Research → Spec → Code → Test → Document)

Seguir o fluxo em 5 etapas, como no `CLAUDE.md` do repositório:

1. **Pesquisa** → PRD em `docs/work/prd/XXX-nome.md`.  
2. **Spec** → Spec em `docs/work/spec/XXX-nome.md` (arquivos a criar/alterar, ordem).  
3. **Code** → Implementar conforme a spec; respeitar logging, naming, secrets.  
4. **Test** → Testes manuais (curl com `API_KEY` do `.env`), `serverless invoke local`.  
5. **Document** → `tests/integration/<feature>.md`, `tests/postman/<feature>.postman_collection.json`, mocks em `tests/mocks/<dominio>/`.

Pós-implementação:

- Testar endpoints com `curl` e `API_KEY` do `.env`.  
- Criar mocks em `tests/mocks/<dominio>/`.  
- Documentar em `tests/integration/<feature>.md`.  
- Criar/atualizar Postman em `tests/postman/` seguindo `tests/postman/CLAUDE.md` (BASE_URL, ENVIRONMENT, API_KEY, estrutura de requests e testes).

---

## 8. Build, deploy e testes (comandos)

- `npm install`, `pip install -r requirements.txt`.  
- `serverless deploy --stage dev --aws-profile <profile>`.  
- `serverless invoke local -s dev -f <FunctionName> -p tests/mocks/<dominio>/<arquivo>.json`.  
- `serverless logs -f <FunctionName> --stage dev`.

---

## 9. Checklist de entregas iniciais (para o LLM)

Ao iniciar o projeto do zero, o LLM deve produzir (na primeira iteração ou em etapas claras):

1. **`serverless.yml`** com `custom`, `provider` (incl. `ecr.images`), `environment`, `functions` (refs a `sls/functions/*/interface.yml`), `resources` (DynamoDB e, se aplicável, RDS), e `plugins`.  
2. **Dockerfile** e `requirements.txt` (incl. `boto3`, `requests`, e deps para HTTP/criptografia para o webhook).  
3. **Tabelas DynamoDB** (e RDS, se for o caso), incluindo tabela (ou modelo) para **registro de eventos de mensagens**, com justificativa breve (por que Dynamo vs RDS) em comentário no `yml` ou em `docs/work/prd`.  
4. **Funções:**  
   - Webhook WhatsApp (GET verify + POST handler, validação de assinatura, **registro do evento de mensagem**, roteamento para `clientId` e início do fluxo if/else). Opcional: SQS + Lambda consumer para processar o payload de forma assíncrona.  
   - Ao menos um **sender** (ex.: enviar texto ou template simples).  
   - Ao menos um **CRUD de templates** (criar e listar, com persistência em RDS ou Dynamo, conforme a análise).  
5. **Serviço** de chamada à Meta (`WhatsAppCloudApi` ou similar) em `src/services/`.  
6. **Reuso/validação de `clientId`:** Leitura da tabela `Clients` (mesmo nome/ARN da stack de referência) ou configuração para apontar para a tabela existente.  
7. **SSM:** Parâmetros `/${stage}/WHATSAPP_*` (ou convenção definida) e documentação de quais são necessários.  
8. **Testes:** Mocks para `serverless invoke local` do webhook e do sender; um `tests/integration/whatsapp-webhook.md` (ou equivalente) e um esboço de Postman para enviar mensagem e para o webhook.  
9. **Documentação:** `README.md` ou `docs/` com variáveis de ambiente, como rodar local, e como configurar o webhook na Meta (URL, `verify_token`).

---

## 10. Referências no repositório

- `infra/serverless.yml` — estrutura do provider, `ecr`, `environment`, `functions`, `resources`.  
- `infra/sls/functions/*/interface.yml` — padrão de `image`, `command`, `iamRoleStatements`, `events`.  
- `infra/sls/resources/dynamodb/*.yml` — `KeySchema`, GSI (ex.: `clientId-createdAt-index`).  
- `infra/sls/resources/rds/postgres-database.yml` — RDS Postgres.  
- `infra/src/utils/http.py` — `parse_body`, `http_response`, `require_api_key`, `extract_*`.  
- `infra/src/utils/auth.py` — `ClientAuth`, validação de apiKey.  
- `infra/src/functions/leads/create.py` e `list.py` — uso de DynamoDB, `http_response`, `require_api_key`, GSI.  
- `infra/src/functions/form_submission/handler.py` — webhook HTTP, `parse_body`, resposta.  
- `infra/tests/postman/CLAUDE.md` — padrão de coleções Postman.  
- `CLAUDE.md` (raiz do repositório) — workflow Research → Spec → Code → Test → Document, logging, naming, secrets.

---

## 11. Resumo para o LLM

- **Escopo:** Apenas **backend Lambda-oriented**. Nenhum portal, frontend ou interface web.  
- **Stack:** Serverless Framework 3, AWS, Lambdas em **Python** via **Docker (ECR)**.  
- **Dados:** Escolher DynamoDB vs RDS por entidade; **Clients** compartilhada (mesmos `clientId`); **registro de eventos de mensagens** (entrantes, callbacks, status) em Dynamo ou RDS.  
- **WhatsApp:** **Conversas** (envio e recepção), **senders** (texto, mídia, template, interactive), **listener** (webhook: verify + POST, assinatura, **registro de eventos**, mapeamento para `clientId`, fluxo if/else), **CRUD de template messages**.  
- **Padrões:** `sls/functions`, `sls/resources`, `src/functions`, `src/services`, `src/utils`; `http_response`, `require_api_key`, logging com `[traceId]`; secrets em SSM; IAM por função; testes em `tests/mocks`, `tests/integration`, Postman.  
- **Entregas:** serverless.yml, Dockerfile, tabelas (incl. eventos de mensagens), webhook, sender, CRUD templates, serviço Meta, validação `clientId`, mocks, integração e Postman, README/docs de setup e webhook Meta.
