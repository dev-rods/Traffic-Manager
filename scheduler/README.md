# Clinic Scheduler

Sistema de agendamento de sessoes para clinicas via WhatsApp, com fluxo conversacional automatizado, integracao com Google Sheets e gerenciamento completo de disponibilidade.

## Arquitetura

- **Runtime:** Python 3.8 + AWS Lambda (Serverless Framework v3)
- **Banco relacional:** PostgreSQL (RDS) — schema `scheduler`
- **Sessoes:** DynamoDB (ConversationSessions, MessageEvents, ScheduledReminders)
- **Mensageria:** z-api (WhatsApp Business)
- **Sync:** Google Sheets API (bidirecional)

## Estrutura do projeto

```
scheduler/
├── src/
│   ├── functions/          # Lambda handlers por dominio
│   │   ├── webhook/        # Recebe mensagens WhatsApp (z-api callbacks)
│   │   ├── send/           # Envio de mensagens
│   │   ├── clinic/         # CRUD de clinicas
│   │   ├── service/        # CRUD de servicos
│   │   ├── area/           # CRUD de areas corporais
│   │   ├── service_area/   # Associacao servico-area
│   │   ├── professional/   # CRUD de profissionais
│   │   ├── availability/   # Regras e excecoes de disponibilidade
│   │   ├── appointment/    # CRUD de agendamentos
│   │   ├── template/       # Templates de mensagem
│   │   ├── faq/            # Perguntas frequentes
│   │   ├── discount_rules/ # Regras de desconto
│   │   ├── sheets/         # Webhook e sync Google Sheets
│   │   ├── reminder/       # Lembretes automaticos (24h antes)
│   │   └── report/         # Relatorios diarios
│   ├── services/           # Logica de negocio
│   │   ├── conversation_engine.py  # Maquina de estados do chat
│   │   ├── availability_engine.py  # Motor de disponibilidade
│   │   ├── appointment_service.py  # Criacao/atualizacao de agendamentos
│   │   ├── template_service.py     # Renderizacao de templates
│   │   ├── message_tracker.py      # Rastreamento de mensagens
│   │   ├── reminder_service.py     # Servico de lembretes
│   │   ├── sheets_sync.py          # Sincronizacao Google Sheets
│   │   └── db/                     # Conexao PostgreSQL
│   ├── providers/          # Abstracoes de providers
│   │   └── whatsapp_provider.py    # Implementacao z-api
│   ├── utils/              # Utilitarios (http, auth, logging, phone, decimal)
│   └── scripts/            # Scripts de setup e migracao
├── sls/
│   ├── functions/          # Definicoes de funcoes Serverless (interface.yml)
│   └── resources/          # Recursos CloudFormation (DynamoDB)
├── tests/
│   ├── mocks/              # Payloads mock para testes locais
│   ├── integration/        # Documentacao de testes de integracao
│   ├── postman/            # Colecoes Postman para testes de API
│   └── unit/               # Testes unitarios
└── docs/work/              # PRDs e Specs de features
```

## Fluxo conversacional (WhatsApp)

### Agendamento

```
WELCOME → MAIN_MENU → SELECT_SERVICES (auto-skip se 1 servico)
  → SELECT_AREAS (texto livre, com precos)
  → CONFIRM_AREAS
  → AVAILABLE_DAYS (botoes dinamicos)
  → SELECT_TIME (botoes dinamicos)
  → ASK_FULL_NAME (texto livre)
  → CONFIRM_BOOKING
  → BOOKED → FAREWELL
```

### Remarcacao

```
MAIN_MENU → RESCHEDULE_LOOKUP → SELECT_APPOINTMENT
  → SHOW_CURRENT_APPOINTMENT → SELECT_NEW_TIME
  → CONFIRM_RESCHEDULE → RESCHEDULED
```

### Cancelamento

```
MAIN_MENU → CANCEL_LOOKUP → SELECT_CANCEL_APPOINTMENT
  → CONFIRM_CANCEL → CANCELLED
```

### Comandos globais

Reconhecidos em qualquer etapa do fluxo:

| Comando | Sinonimos | Acao |
|---------|-----------|------|
| Voltar | volta, anterior, retornar, back, 0 | Navega para o estado anterior |
| Menu | menu principal, inicio, reiniciar, começo, oi, ola | Volta ao menu principal |
| Atendente | humano, ajuda, suporte, falar com atendente, falar com humano | Transfere para atendente humano |

### Modo atendente humano

Quando o paciente solicita atendente ou o atendente responde manualmente:

1. **Paciente clica "Falar com atendente"** → estado `HUMAN_HANDOFF`, bot silencia
2. **Atendente responde pelo WhatsApp** (`fromMe=true`) → estado `HUMAN_ATTENDANT_ACTIVE`, TTL 24h
3. **Bot fica silencioso** enquanto TTL estiver ativo (cada msg do atendente renova 24h)
4. **Para reativar o bot**, o atendente digita `#encerrar` ou `#fim`
5. **Se o TTL expirar** (24h sem msg do atendente), o bot retoma automaticamente

Qualquer mensagem enviada pelo atendente (em qualquer estado da conversa) ativa o modo atendente.

## Build & Deploy

```bash
# Instalar dependencias
cd scheduler && npm install && pip install -r requirements.txt

# Deploy
cd scheduler && serverless deploy --stage dev --aws-profile dev-andre
cd scheduler && serverless deploy --stage prod --aws-profile dev-andre

# Rodar migracoes do banco
cd scheduler && python src/scripts/setup_database.py

# Ver logs de uma funcao
cd scheduler && serverless logs -f WhatsAppWebhook --stage dev --aws-profile dev-andre
```

## Banco de dados

### PostgreSQL (RDS) — schema `scheduler`

| Tabela | Descricao |
|--------|-----------|
| clinics | Clinicas com config de z-api, Google Sheets, limites |
| services | Servicos oferecidos por clinica |
| areas | Areas corporais |
| service_areas | Associacao servico-area com duracao e preco |
| professionals | Profissionais por clinica |
| availability_rules | Regras de disponibilidade (dia da semana ou data especifica) |
| availability_exceptions | Excecoes de disponibilidade (bloqueios, feriados) |
| patients | Pacientes por clinica (identificados por telefone) |
| appointments | Agendamentos com status, preco, desconto, full_name |
| appointment_services | Servicos de cada agendamento |
| appointment_service_areas | Areas de cada agendamento |
| message_templates | Templates de mensagem personalizaveis por clinica |
| faq_items | Perguntas frequentes por clinica |
| discount_rules | Regras de desconto por clinica |

### DynamoDB

| Tabela | TTL | Descricao |
|--------|-----|-----------|
| ConversationSessions | - | Sessoes de conversa (estado, selecoes, dados temporarios) |
| MessageEvents | 90 dias | Historico de mensagens enviadas/recebidas (3 GSIs) |
| ScheduledReminders | 48h | Lembretes agendados (1 GSI) |

## Integracoes externas

| Servico | Uso |
|---------|-----|
| z-api | Envio/recebimento de mensagens WhatsApp |
| Google Sheets API | Sync bidirecional de agendamentos |
| AWS SSM | Armazenamento de secrets (API keys, tokens) |

## Scripts utilitarios

```bash
# Setup/migracoes do banco (idempotente)
python -m src.scripts.setup_database

# Criar planilhas Google Sheets para clinica
python -m src.scripts.create_spreadsheets
```

## Convencoes

- **clinic_id:** kebab-case (ex: `clinica-premium-abc123`)
- **Lambda functions:** PascalCase no serverless (ex: `WhatsAppWebhook`)
- **Handlers:** `src.functions.{dominio}.{modulo}.handler`
- **DynamoDB tables:** `clinic-scheduler-infra-{stage}-{nome}`
- **RDS tables:** `scheduler.{nome_tabela}`
- **Secrets:** SSM `/${stage}/KEY_NAME`

## Testes

```bash
# Testes unitarios locais (sem infra)
cd scheduler && python -c "
from src.services.conversation_engine import ConversationEngine, ConversationState, STATE_CONFIG
from src.providers.whatsapp_provider import IncomingMessage
# ... testes inline
"

# Invoke local com mock
cd scheduler && serverless invoke local -s dev -f WhatsAppWebhook -p tests/mocks/webhook/text_message.json

# Testes de integracao (curl contra API)
# Ver docs em tests/integration/

# Colecoes Postman
# Ver tests/postman/
```
