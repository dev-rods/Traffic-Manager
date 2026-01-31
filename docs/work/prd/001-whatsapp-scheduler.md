# PRD — 001 WhatsApp Clinic Scheduler

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Construir um sistema de agendamento de consultas para clínicas, operando via WhatsApp como canal principal de comunicação. O sistema permite que pacientes agendem, remarquem e tirem dúvidas sobre sessões por meio de um fluxo automatizado de conversa com botões interativos e respostas padronizadas.

O projeto é um **novo serviço** dentro do monorepo (`scheduler/`), independente do projeto `infra/`, com deploy, stack CloudFormation e codebase próprios. Compartilha apenas a instância RDS PostgreSQL existente (schema separado).

---

## 2. Contexto

### Problema
Clínicas de estética (e futuramente outros segmentos) dependem de agendamento manual via WhatsApp — uma pessoa responde mensagens, consulta agenda, e confirma horários. Isso gera:
- Tempo de resposta lento (paciente desiste)
- Erros de agendamento (conflitos de horário)
- Falta de lembretes (no-show alto)
- Sem padronização na comunicação

### Solução
Chatbot automatizado no WhatsApp que guia o paciente por um fluxo de agendamento completo, com cálculo inteligente de horários disponíveis, lembretes automáticos e fallback para atendimento humano.

### Validação
Protótipo visual validado no Figma (Laser Beauty): [Figma Prototype](https://print-cream-02081339.figma.site/)

---

## 3. Escopo

### Dentro do escopo (MVP)

**Fluxos de conversa:**
- Boas-vindas contextual (paciente novo vs. retorno)
- Menu principal: Agendar sessão, Remarcar sessão, Dúvidas sobre sessão
- Agendar sessão: Ver tabela de preços → Ver dias disponíveis → Selecionar data → Selecionar horário → Informar áreas (texto livre, múltiplas) → Confirmação
- Remarcar sessão: Buscar agendamento por telefone → Mostrar agendamento atual → Selecionar nova data → Selecionar novo horário → Confirmação
- FAQ interativo: 5 dúvidas comuns com respostas configuráveis por clínica
- Falar com atendente: Mensagem informando resposta dentro do horário comercial (não instantâneo)
- Navegação "Voltar" em todos os passos
- Tratamento de mensagens não reconhecidas → opção de menu inicial ou falar com atendente

**Sistema de agendamento:**
- Cálculo inteligente de horários disponíveis baseado em duração do serviço + buffer configurável
- Suporte a múltiplas áreas por agendamento (soma de durações)
- Lock otimístico para evitar conflitos de agendamento simultâneo
- Confirmação com resumo (serviço, data, horário, endereço, recomendações pré-sessão)

**Lembretes:**
- Lembrete 24h antes: "Lembrete: amanhã às X na [Clínica]. Responda OK para confirmar."
- Lambda com EventBridge Scheduler (cron a cada 15 minutos)

**Infraestrutura:**
- Projeto independente no monorepo (`scheduler/`)
- Multi-tenant desde o início (isolamento por `clinicId`)
- Abstração de provider WhatsApp (z-api inicialmente, Meta oficial futuramente)
- Fallback de botões para mensagens numeradas (ex: "1 - Agendar, 2 - Remarcar")
- Rastreamento completo de mensagens (status, timestamps, provider response)
- Templates padrão com override por clínica

**Visualização de agenda (Google Sheets + Relatório):**
- Sync automático RDS → Google Sheets por clínica (cada clínica tem sua planilha)
- Ao criar, remarcar ou cancelar agendamento: atualizar linha na planilha em tempo real
- Relatório diário via WhatsApp para a clínica: agenda do dia seguinte enviada toda noite
- Fluxo unidirecional no MVP (sistema → planilha), mas arquitetado para bidirecional futuro
- Planilha com colunas: Data, Horário, Paciente, Telefone, Serviço, Áreas, Status, Obs
- Clínica pode adicionar notas manuais na coluna Obs (não reflete no sistema no MVP)

**Admin (API REST):**
- CRUD de clínicas (configuração, horários, timezone)
- CRUD de serviços (nome, duração, preço, ativo/inativo)
- CRUD de profissionais
- CRUD de regras de disponibilidade
- CRUD de exceções de disponibilidade (feriados, bloqueios)
- Listagem/gestão de agendamentos
- Configuração de templates de mensagem por clínica

### Fora do escopo (v2+)

- Lista de espera automática (notificar quando horário liberar)
- Mensagem pós-sessão (feedback + oferta de próxima)
- Lembrete de retorno (30 dias após última sessão)
- Preferência de horário salva por paciente
- Dashboard admin web (React/Next.js)
- Integração de pagamento (Stripe/Mercado Pago)
- Migração para WhatsApp oficial Meta Cloud API (provider já abstraído)
- Lembrete de 48h antes e 2h antes (apenas 24h no MVP)
- Política de no-show (bloqueio após N faltas)
- Múltiplos profissionais com agendas paralelas
- Envio de mídia (imagens, documentos)
- Sync bidirecional Google Sheets → sistema (clínica bloqueia horário direto na planilha)

---

## 4. Arquitetura

### 4.1 Estrutura do monorepo

```
Traffic-Manager/                    # monorepo root
├── infra/                          # projeto existente (Google Ads)
├── scheduler/                      # NOVO projeto (Agendamento WhatsApp)
│   ├── serverless.yml
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── package.json
│   ├── .env                        # local (gitignored)
│   ├── src/
│   │   ├── functions/
│   │   │   ├── webhook/            # Recebimento de mensagens WhatsApp
│   │   │   ├── send/               # Envio de mensagens
│   │   │   ├── conversation/       # Motor de conversa (state machine)
│   │   │   ├── appointment/        # CRUD agendamentos
│   │   │   ├── availability/       # Cálculo de disponibilidade
│   │   │   ├── clinic/             # CRUD clínicas (admin)
│   │   │   ├── service/            # CRUD serviços (admin)
│   │   │   ├── professional/       # CRUD profissionais (admin)
│   │   │   ├── reminder/           # Processamento de lembretes
│   │   │   ├── report/             # Relatório diário de agenda
│   │   │   └── template/           # CRUD templates de mensagem
│   │   ├── services/
│   │   │   ├── conversation_engine.py    # State machine da conversa
│   │   │   ├── availability_engine.py    # Cálculo de slots disponíveis
│   │   │   ├── appointment_service.py    # Lógica de agendamento
│   │   │   ├── reminder_service.py       # Lógica de lembretes
│   │   │   ├── sheets_sync.py            # Sync RDS → Google Sheets
│   │   │   ├── message_tracker.py        # Rastreamento de mensagens
│   │   │   └── db/
│   │   │       └── postgres.py           # Conexão RDS (schema scheduler)
│   │   ├── providers/
│   │   │   ├── whatsapp_provider.py      # Interface abstrata
│   │   │   ├── zapi_provider.py          # Implementação z-api
│   │   │   └── meta_provider.py          # Implementação Meta (futuro)
│   │   └── utils/
│   │       ├── http.py
│   │       ├── auth.py
│   │       ├── logging.py
│   │       └── phone.py                  # Normalização de telefone
│   ├── sls/
│   │   ├── functions/
│   │   │   ├── webhook/interface.yml
│   │   │   ├── send/interface.yml
│   │   │   ├── appointment/interface.yml
│   │   │   ├── availability/interface.yml
│   │   │   ├── clinic/interface.yml
│   │   │   ├── service/interface.yml
│   │   │   ├── professional/interface.yml
│   │   │   ├── reminder/interface.yml
│   │   │   └── template/interface.yml
│   │   └── resources/
│   │       └── dynamodb/
│   │           ├── conversation-sessions-table.yml
│   │           ├── message-events-table.yml
│   │           └── scheduled-reminders-table.yml
│   └── tests/
│       ├── mocks/
│       ├── integration/
│       └── postman/
├── docs/
│   └── work/
│       ├── prd/001-whatsapp-scheduler.md   # Este documento
│       └── spec/001-whatsapp-scheduler.md  # A ser gerado
├── CLAUDE.md
└── TASKS_LOG.md
```

### 4.2 Modelo de dados

#### DynamoDB (acesso por chave, alto volume, TTL)

**ConversationSessions** — Estado da conversa ativa por telefone
```
PK: CLINIC#{clinicId}#PHONE#{phoneNumber}
SK: SESSION

Atributos:
- clinicId, phoneNumber
- currentState          # ex: MAIN_MENU, SELECT_DATE, SELECT_TIME
- previousState         # para navegação "voltar"
- stateData             # dados acumulados no fluxo (serviço escolhido, data, etc.)
- patientId             # FK para patients no RDS (se já cadastrado)
- createdAt, updatedAt
- ttl                   # 30 minutos de inatividade → expiração
```

**MessageEvents** — Log de todas as mensagens trocadas
```
PK: CLINIC#{clinicId}#PHONE#{phoneNumber}
SK: MSG#{messageId}#EVENT#{timestamp}

Atributos:
- messageId, clinicId, conversationId
- phoneNumber
- direction             # INBOUND | OUTBOUND
- messageType           # TEXT | BUTTON_RESPONSE | LIST_RESPONSE | TEMPLATE | INTERACTIVE
- content               # Corpo da mensagem
- status                # QUEUED | SENT | DELIVERED | READ | FAILED | RECEIVED
- statusTimestamp       # ISO 8601 UTC
- provider              # ZAPI | META
- providerMessageId     # zaapId / messageId do provider
- providerResponse      # JSON raw da resposta do provider
- errorDetails          # Se FAILED: código e mensagem
- metadata              # conversationState, templateId, buttonsOffered, triggerEvent
- createdAt
- ttl                   # 90 dias (configurável)

GSIs:
- GSI1: PK=clinicId, SK=statusTimestamp  → mensagens por clínica em ordem
- GSI2: PK=status, SK=statusTimestamp    → monitoramento de FAILED
- GSI3: PK=conversationId               → conversa bidirecional agrupada
```

**ScheduledReminders** — Fila de lembretes pendentes
```
PK: REMINDER#{reminderId}
SK: SEND_AT#{iso_timestamp}

Atributos:
- reminderId, appointmentId, clinicId
- phoneNumber, patientName
- sendAt                # Quando disparar (appointment_datetime - 24h)
- reminderType          # REMINDER_24H (extensível para 48H, 2H no futuro)
- status                # PENDING | SENT | FAILED | CANCELLED
- messageTemplate       # Template a usar
- createdAt
- ttl                   # sendAt + 48h (limpeza automática)

GSI:
- GSI1: PK=status, SK=sendAt  → Lambda busca PENDING onde sendAt <= now()
```

#### RDS PostgreSQL (schema `scheduler` na instância existente)

```sql
-- Clínicas (tenants)
CREATE TABLE scheduler.clinics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) UNIQUE NOT NULL,    -- kebab-case, ex: laser-beauty-sp
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(20),                          -- Número WhatsApp da clínica
    address TEXT,
    timezone VARCHAR(50) DEFAULT 'America/Sao_Paulo',
    business_hours JSONB NOT NULL,              -- {"mon": {"start": "09:00", "end": "18:00"}, ...}
    buffer_minutes INTEGER DEFAULT 10,          -- Intervalo entre sessões
    welcome_message TEXT,                       -- Override da mensagem de boas-vindas
    pre_session_instructions TEXT,              -- Recomendações pré-sessão
    zapi_instance_id VARCHAR(255),              -- ID da instância z-api
    zapi_instance_token VARCHAR(255),           -- Token da instância z-api
    google_spreadsheet_id VARCHAR(255),         -- ID da planilha Google Sheets da clínica
    google_sheet_name VARCHAR(100) DEFAULT 'Agenda',  -- Nome da aba
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Serviços oferecidos
CREATE TABLE scheduler.services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    name VARCHAR(255) NOT NULL,                -- Ex: "Depilação a laser"
    duration_minutes INTEGER NOT NULL,         -- Duração da sessão
    price_cents INTEGER,                       -- Preço em centavos (ex: 15000 = R$150)
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Profissionais
CREATE TABLE scheduler.professionals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    name VARCHAR(255) NOT NULL,
    role VARCHAR(100),                         -- Ex: "Biomédica esteta"
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Regras de disponibilidade
CREATE TABLE scheduler.availability_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    professional_id UUID REFERENCES scheduler.professionals(id),
    day_of_week INTEGER NOT NULL,              -- 0=dom, 1=seg, ..., 6=sab
    start_time TIME NOT NULL,                  -- Ex: 09:00
    end_time TIME NOT NULL,                    -- Ex: 18:00
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Exceções de disponibilidade (feriados, bloqueios, datas especiais)
CREATE TABLE scheduler.availability_exceptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    exception_date DATE NOT NULL,
    exception_type VARCHAR(20) NOT NULL,       -- BLOCKED | SPECIAL_HOURS
    start_time TIME,                           -- Só para SPECIAL_HOURS
    end_time TIME,                             -- Só para SPECIAL_HOURS
    reason VARCHAR(255),                       -- Ex: "Feriado", "Manutenção do equipamento"
    created_at TIMESTAMP DEFAULT NOW()
);

-- Pacientes
CREATE TABLE scheduler.patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    phone VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clinic_id, phone)
);

-- Agendamentos
CREATE TABLE scheduler.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    patient_id UUID REFERENCES scheduler.patients(id),
    professional_id UUID REFERENCES scheduler.professionals(id),
    service_id UUID REFERENCES scheduler.services(id),
    appointment_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,                    -- Calculado: start_time + duração do serviço
    areas TEXT,                                -- Texto livre: "Pernas e axilas"
    status VARCHAR(20) DEFAULT 'CONFIRMED',    -- CONFIRMED | CANCELLED | COMPLETED | NO_SHOW
    notes TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    version INTEGER DEFAULT 1                  -- Lock otimístico
);

-- Templates de mensagem (override por clínica)
CREATE TABLE scheduler.message_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    template_key VARCHAR(100) NOT NULL,        -- Ex: WELCOME, MAIN_MENU, FAQ_EQUIPMENT
    content TEXT NOT NULL,                     -- Texto com placeholders: {{nome}}, {{data}}
    buttons JSONB,                             -- [{"id": "1", "label": "Agendar sessão"}]
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clinic_id, template_key)
);

-- FAQ configurável por clínica
CREATE TABLE scheduler.faq_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    question_key VARCHAR(100) NOT NULL,        -- Ex: EQUIPMENT, SESSION_INTERVAL
    question_label VARCHAR(255) NOT NULL,      -- Texto do botão: "Qual equipamento?"
    answer TEXT NOT NULL,                      -- Resposta completa
    display_order INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    UNIQUE(clinic_id, question_key)
);

-- Índices
CREATE INDEX idx_appointments_clinic_date ON scheduler.appointments(clinic_id, appointment_date);
CREATE INDEX idx_appointments_patient ON scheduler.appointments(patient_id);
CREATE INDEX idx_appointments_status ON scheduler.appointments(clinic_id, status);
CREATE INDEX idx_patients_phone ON scheduler.patients(clinic_id, phone);
CREATE INDEX idx_availability_rules_clinic ON scheduler.availability_rules(clinic_id, day_of_week);
CREATE INDEX idx_availability_exceptions_clinic ON scheduler.availability_exceptions(clinic_id, exception_date);
```

### 4.3 Máquina de estados da conversa

```
WELCOME
  └→ MAIN_MENU
       ├→ SCHEDULE_MENU
       │    ├→ PRICE_TABLE → SCHEDULE_MENU
       │    └→ AVAILABLE_DAYS → SELECT_DATE → SELECT_TIME → INPUT_AREAS → CONFIRM_BOOKING → BOOKED → MAIN_MENU
       ├→ RESCHEDULE_LOOKUP → SHOW_CURRENT_APPOINTMENT → SELECT_NEW_DATE → SELECT_NEW_TIME → CONFIRM_RESCHEDULE → RESCHEDULED → MAIN_MENU
       ├→ FAQ_MENU → FAQ_ANSWER → FAQ_MENU | MAIN_MENU
       └→ HUMAN_HANDOFF (terminal — notifica clínica)

Qualquer estado:
  - "Voltar" → previousState
  - Input não reconhecido → UNRECOGNIZED → MAIN_MENU | HUMAN_HANDOFF
```

Cada estado define:
- `message`: template de mensagem a enviar
- `expected_inputs`: inputs válidos (button IDs, text patterns)
- `transitions`: mapa de input → próximo estado
- `fallback_state`: estado para input não reconhecido
- `previous_state`: estado para o botão "voltar"
- `on_enter`: ação ao entrar no estado (ex: buscar horários, criar agendamento)

### 4.4 Abstração do provider WhatsApp

```python
# Interface abstrata
class WhatsAppProvider(ABC):
    def send_text(self, phone: str, message: str) -> ProviderResponse
    def send_buttons(self, phone: str, message: str, buttons: list[Button]) -> ProviderResponse
    def send_list(self, phone: str, message: str, sections: list[Section]) -> ProviderResponse
    def parse_webhook(self, raw_payload: dict) -> IncomingMessage
    def parse_status_webhook(self, raw_payload: dict) -> MessageStatus
```

**z-api (MVP):**
- Envio: `POST /instances/{id}/token/{token}/send-text`, `/send-button-list`
- Recebimento: webhook POST com `type: ReceivedCallback`
- Status: webhook POST com `type: MessageStatusCallback`
- Resposta de botão: `buttonsResponseMessage.buttonId` + `referenceMessageId`
- Status possíveis: `SENT` → `RECEIVED` → `READ` (+ `PLAYED` para áudio)

**Fallback de botões**: se botões falharem (instabilidade z-api), enviar texto numerado e aceitar resposta numérica:
```
Como posso te ajudar?
1 - Agendar sessão
2 - Remarcar sessão
3 - Dúvidas sobre sessão
4 - Falar com atendente
```

### 4.5 Cálculo de disponibilidade

**Algoritmo para gerar slots:**
1. Receber `clinicId`, `date`, `serviceId` (ou lista de áreas com durações)
2. Buscar `availability_rules` para o `day_of_week` da data
3. Buscar `availability_exceptions` para a data (BLOCKED → sem slots; SPECIAL_HOURS → usar horários especiais)
4. Calcular duração total: soma das durações dos serviços/áreas selecionados
5. Calcular intervalo do slot: `duração_total + buffer_minutes` da clínica
6. Gerar slots de `start_time` até `end_time - duração_total`
7. Buscar `appointments` existentes para a data (status = CONFIRMED)
8. Remover slots que colidem com agendamentos existentes
9. Retornar slots disponíveis

**Lock otimístico no agendamento:**
```sql
UPDATE scheduler.appointments
SET status = 'CONFIRMED', version = version + 1
WHERE id = :id AND version = :expected_version;
-- Se rowcount = 0 → conflito → informar paciente
```

Na criação: INSERT com verificação de conflito via query antes + constraint de horário.

### 4.6 Sistema de lembretes

- Ao criar agendamento: calcular `sendAt = appointment_datetime - 24h` e inserir em `ScheduledReminders` (DynamoDB)
- Lambda `ReminderProcessor` com EventBridge rule (cron `rate(15 minutes)`)
- A cada execução: query GSI1 (`status=PENDING`, `sendAt <= now()`)
- Para cada lembrete: enviar mensagem via provider, atualizar status para SENT ou FAILED
- Se agendamento for cancelado/remarcado: atualizar status do lembrete para CANCELLED

### 4.7 Rastreamento de mensagens

Toda mensagem (INBOUND e OUTBOUND) gera registros em `MessageEvents` (DynamoDB):

**OUTBOUND:**
```
QUEUED → SENT → DELIVERED → READ
           └→ FAILED
```
Cada transição = novo registro com timestamp. O `providerResponse` salva o JSON raw do z-api para debug.

**INBOUND:**
```
RECEIVED (registro único com conteúdo e metadata do estado da conversa no momento)
```

**Debug facilitado por:**
- Query por telefone: conversa inteira em ordem cronológica
- Query por messageId: todos os status de uma mensagem
- GSI de FAILED: monitoramento em tempo real de falhas
- `metadata.conversationState`: estado da conversa no momento do envio/recebimento
- `providerResponse`: resposta raw do provider para investigação

### 4.8 Google Sheets sync + Relatório diário

**Sync RDS → Google Sheets (tempo real):**

Fluxo unidirecional: toda criação, remarcação ou cancelamento de agendamento dispara sync para a planilha da clínica.

```
appointment_service.py → cria/atualiza no RDS → sheets_sync.py → Google Sheets API
```

- Autenticação via **Google Service Account** (credenciais em SSM: `/${stage}/GOOGLE_SHEETS_SERVICE_ACCOUNT`)
- Cada clínica tem `google_spreadsheet_id` configurado na tabela `clinics`
- A planilha deve ser compartilhada com o email da service account (permissão de editor)
- Sync síncrono na mesma Lambda (latência aceitável para MVP, volume baixo)
- Operações: buscar linha pelo `appointment_id` → atualizar, ou append nova linha
- Colunas: Data | Horário | Paciente | Telefone | Serviço | Áreas | Status | Obs

**Preparação para bidirecional (v2+):**
- Coluna `appointment_id` (oculta ou no final) na planilha para correlação
- Coluna `last_synced_at` para detectar alterações manuais
- No futuro: Lambda com cron que lê a planilha, compara com RDS e aplica mudanças (ex: clínica bloqueou horário na sheet)

**Relatório diário via WhatsApp:**

Lambda `DailyReportSender` com EventBridge rule (cron: todo dia às 20:00 no timezone da clínica):

1. Para cada clínica ativa: query de agendamentos do dia seguinte
2. Montar mensagem formatada:
```
📋 Agenda de amanhã (01/02):

09:00 - Maria Silva | Depilação laser | Pernas, axilas
10:15 - Ana Costa | Depilação laser | Virilha
14:00 - (livre)
15:00 - Julia Santos | Depilação laser | Costas

Total: 3 sessões agendadas
```
3. Enviar via provider WhatsApp para o número da clínica (`clinics.phone`)

---

## 5. Dependências e riscos

### Dependências
- **RDS PostgreSQL**: instância existente no projeto `infra` (schema `scheduler` a ser criado)
- **z-api**: conta ativa com instância configurada por clínica
- **AWS**: Lambda, DynamoDB, API Gateway, EventBridge, SSM, CloudWatch
- **Serverless Framework 3**: mesmo padrão do projeto `infra`
- **Google Sheets API**: service account com acesso às planilhas das clínicas
- **Google API Python Client**: `google-api-python-client`, `google-auth` (já usados no projeto `infra`)

### Riscos
| Risco | Impacto | Mitigação |
|-------|---------|-----------|
| Instabilidade de botões z-api | Fluxo quebra para pacientes | Fallback para mensagens numeradas |
| Conflito de agendamento simultâneo | Dois pacientes no mesmo horário | Lock otimístico + verificação pré-insert |
| z-api fora do ar | Sistema não envia/recebe | Log de falhas, retry com backoff, monitoramento via GSI de FAILED |
| Sessão de conversa expira no meio do fluxo | Paciente precisa recomeçar | TTL de 30min + mensagem amigável ao retornar |
| RDS compartilhado sob carga | Latência afeta ambos os projetos | Schema separado, connection pooling, monitorar performance |
| Rate limiting do WhatsApp | Mensagens não entregues | Debounce de 3-5s, queue de envio |
| Google Sheets API fora do ar | Planilha desatualizada | Retry com backoff; RDS é fonte da verdade, planilha é eventual |
| Google Sheets quota (300 req/min) | Sync falha em pico | Volume do MVP é baixo; se crescer, mudar para async via SQS |

---

## 6. Critérios de aceite

### Fluxos de conversa
- [ ] Paciente recebe mensagem de boas-vindas ao enviar primeira mensagem
- [ ] Menu principal oferece 3 opções + falar com atendente
- [ ] Fluxo de agendamento completo: serviço → data → horário → áreas → confirmação
- [ ] Fluxo de remarcação: busca por telefone → agendamento atual → nova data/horário → confirmação
- [ ] FAQ interativo com dúvidas configuráveis e respostas
- [ ] Botão "voltar" funciona em todos os passos
- [ ] Mensagens não reconhecidas oferecem menu ou atendente
- [ ] Falar com atendente: mensagem sobre horário comercial

### Agendamento
- [ ] Horários disponíveis calculados corretamente (duração + buffer)
- [ ] Múltiplas áreas somam durações
- [ ] Não é possível agendar horário já ocupado (lock otimístico)
- [ ] Confirmação exibe resumo completo (serviço, data, horário, endereço)

### Lembretes
- [ ] Lembrete enviado 24h antes do agendamento
- [ ] Lembrete cancelado se agendamento for cancelado/remarcado

### Multi-tenant
- [ ] Cada clínica tem serviços, horários e templates independentes
- [ ] Dados isolados por clinicId em todas as tabelas

### Rastreamento
- [ ] Toda mensagem OUTBOUND registrada com ciclo QUEUED→SENT→DELIVERED→READ
- [ ] Toda mensagem INBOUND registrada com status RECEIVED
- [ ] Provider response raw salvo para debug
- [ ] Estado da conversa salvo como metadata em cada mensagem

### Google Sheets + Relatório
- [ ] Agendamento criado → linha adicionada na planilha da clínica
- [ ] Agendamento remarcado → linha atualizada na planilha
- [ ] Agendamento cancelado → status atualizado na planilha
- [ ] Coluna `appointment_id` presente para correlação (preparação bidirecional)
- [ ] Relatório diário enviado via WhatsApp às 20h com agenda do dia seguinte
- [ ] Clínica sem planilha configurada → sync ignorado sem erro

### Admin API
- [ ] CRUD de clínica funcional via API REST (incluindo `google_spreadsheet_id`)
- [ ] CRUD de serviços funcional via API REST
- [ ] CRUD de regras de disponibilidade funcional via API REST
- [ ] Listagem de agendamentos por clínica/data

### Infraestrutura
- [ ] Deploy independente do projeto `infra`
- [ ] Provider WhatsApp abstraído (troca z-api/Meta sem alterar lógica de negócio)
- [ ] Secrets em SSM (z-api tokens, API keys)

---

## 7. Referências

- `CLAUDE.md` — padrões do projeto
- `infra/docs/PROMPT_WHATSAPP_MESSAGING_SERVICE.md` — spec de referência para mensageria WhatsApp
- `infra/docs/FLUXOS_WHATSAPP_SCHEDULING_FIGMA.md` — mapeamento de fluxos do protótipo
- Protótipo Figma: https://print-cream-02081339.figma.site/
- z-api docs: https://developer.z-api.io/en/
- z-api button status: https://developer.z-api.io/en/tips/button-status
- z-api webhooks: https://developer.z-api.io/en/webhooks/introduction

---

## Status (preencher após conclusão)

- [x] PRD criado: 2026-01-31
- [x] Spec gerada: `spec/001-whatsapp-scheduler.md` (2026-01-31)
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
