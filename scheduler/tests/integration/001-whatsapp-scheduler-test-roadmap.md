# Roteiro de Testes — 001 WhatsApp Clinic Scheduler

> Roteiro completo para validar a implementacao do sistema de agendamento via WhatsApp.
> Executar na ordem — testes posteriores dependem de dados criados nos anteriores.

---

## Setup

```bash
# Carregar variaveis de ambiente — NUNCA hardcode API keys
cd C:\Users\Rodri\Documents\dev-rods\Traffic-Manager\scheduler
source .env

# Variaveis base
BASE_URL="https://YOUR_API_GATEWAY_URL.execute-api.us-east-1.amazonaws.com"
STAGE="dev"
API_KEY="$SCHEDULER_API_KEY"

# Variaveis que serao preenchidas durante os testes
CLINIC_ID=""
SERVICE_ID=""
PROFESSIONAL_ID=""
RULE_ID=""
EXCEPTION_ID=""
TEMPLATE_ID=""
FAQ_ID=""
APPOINTMENT_ID=""
```

---

## Fase 1 — Database e Infraestrutura

### 1.1 Verificar schema PostgreSQL

| # | Teste | Como verificar | Esperado |
|---|-------|---------------|----------|
| 1 | Schema `scheduler` existe | Conectar no RDS e executar `SELECT schema_name FROM information_schema.schemata WHERE schema_name = 'scheduler';` | Retorna 1 linha |
| 2 | Todas as tabelas criadas | `SELECT table_name FROM information_schema.tables WHERE table_schema = 'scheduler' ORDER BY table_name;` | 9 tabelas: appointments, availability_exceptions, availability_rules, clinics, faq_items, message_templates, patients, professionals, services |
| 3 | Indices criados | `SELECT indexname FROM pg_indexes WHERE schemaname = 'scheduler';` | Indices: idx_appointments_clinic_date, idx_appointments_patient, idx_appointments_status, idx_patients_phone, idx_availability_rules_clinic, idx_availability_exceptions_clinic |

**Alternativa — rodar o script de setup:**
```bash
cd scheduler
python -m src.scripts.setup_database
```
Esperado: mensagens de sucesso para schema, tabelas e indices.

### 1.2 Verificar tabelas DynamoDB

| # | Teste | Como verificar | Esperado |
|---|-------|---------------|----------|
| 1 | ConversationSessions table | `aws dynamodb describe-table --table-name clinic-scheduler-infra-dev-conversation-sessions --profile traffic-manager` | Table status: ACTIVE, TTL enabled |
| 2 | MessageEvents table | `aws dynamodb describe-table --table-name clinic-scheduler-infra-dev-message-events --profile traffic-manager` | ACTIVE, 3 GSIs |
| 3 | ScheduledReminders table | `aws dynamodb describe-table --table-name clinic-scheduler-infra-dev-scheduled-reminders --profile traffic-manager` | ACTIVE, 1 GSI |

### 1.3 Verificar deploy das Lambdas

```bash
aws lambda list-functions --query "Functions[?starts_with(FunctionName, 'clinic-scheduler-infra-dev')].FunctionName" --profile traffic-manager --output table
```
Esperado: todas as funcoes listadas no serverless.yml.

---

## Fase 2 — Clinics CRUD

### 2.1 Criar clinica

| # | Teste | Expected Status | Descricao |
|---|-------|-----------------|-----------|
| 1 | Criar sem API key | 401 | Deve rejeitar |
| 2 | Criar sem body | 400 | Campos obrigatorios |
| 3 | Criar sem name | 400 | name obrigatorio |
| 4 | Criar sem business_hours | 400 | business_hours obrigatorio |
| 5 | Criar clinica valida | 201 | Sucesso, retorna clinicId |

**Teste 1 — Criar sem API key:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics" \
  -H "Content-Type: application/json" \
  -d '{"name": "Test Clinic"}'
```
Esperado: `401` — `{"message": "API key nao fornecida"}`

**Teste 2 — Criar sem body:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY"
```
Esperado: `400` — `{"status": "ERROR", "message": "Request body e obrigatorio"}`

**Teste 3 — Criar sem name:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"business_hours": {"mon": {"start": "09:00", "end": "18:00"}}}'
```
Esperado: `400` — erro indicando campo `name` obrigatorio

**Teste 4 — Criar sem business_hours:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"name": "Laser Beauty SP"}'
```
Esperado: `400` — erro indicando campo `business_hours` obrigatorio

**Teste 5 — Criar clinica valida (SALVAR clinicId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name": "Laser Beauty SP",
    "phone": "5511988880000",
    "address": "Rua Augusta, 1234 - Sao Paulo, SP",
    "business_hours": {
      "mon": {"start": "09:00", "end": "18:00"},
      "tue": {"start": "09:00", "end": "18:00"},
      "wed": {"start": "09:00", "end": "18:00"},
      "thu": {"start": "09:00", "end": "18:00"},
      "fri": {"start": "09:00", "end": "18:00"}
    },
    "buffer_minutes": 10,
    "timezone": "America/Sao_Paulo",
    "pre_session_instructions": "Evitar exposicao solar 48h antes. Nao usar cremes na area a ser tratada."
  }'
```
Esperado: `201`
```json
{
  "status": "SUCCESS",
  "clinicId": "laserbeautysp-XXXXXX",
  "message": "Clinica criada com sucesso"
}
```
**Acao:** salvar `CLINIC_ID` do response para proximos testes.
```bash
CLINIC_ID="laserbeautysp-XXXXXX"   # substituir pelo valor real
```

### 2.2 Listar clinicas

**Teste 6 — Listar clinicas:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array contendo a clinica criada

### 2.3 Buscar clinica por ID

**Teste 7 — Buscar clinica existente:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — objeto completo da clinica com todos os campos

**Teste 8 — Buscar clinica inexistente:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/clinica-inexistente-000000" \
  -H "x-api-key: $API_KEY"
```
Esperado: `404`

### 2.4 Atualizar clinica

**Teste 9 — Atualizar telefone e buffer:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/clinics/$CLINIC_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"phone": "5511977770000", "buffer_minutes": 15}'
```
Esperado: `200` — dados atualizados

**Teste 10 — Configurar z-api:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/clinics/$CLINIC_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"zapi_instance_id": "INSTANCE_ID_AQUI", "zapi_instance_token": "TOKEN_AQUI"}'
```
Esperado: `200`

**Teste 11 — Configurar Google Sheets:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/clinics/$CLINIC_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"google_spreadsheet_id": "1BxiMVxxxxxxxxxx", "google_sheet_name": "Agenda"}'
```
Esperado: `200`

**Teste 12 — Verificar atualizacoes (GET apos PUT):**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — campos `phone`, `buffer_minutes`, `zapi_instance_id`, `google_spreadsheet_id` refletem os valores atualizados.

---

## Fase 3 — Services CRUD

### 3.1 Criar servico

**Teste 13 — Criar sem campos obrigatorios:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"name": "Incompleto"}'
```
Esperado: `400` — `duration_minutes` obrigatorio

**Teste 14 — Criar servico valido (SALVAR serviceId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name": "Depilacao a laser",
    "duration_minutes": 45,
    "price_cents": 15000,
    "description": "Sessao avulsa de depilacao a laser com Soprano Ice Platinum"
  }'
```
Esperado: `201` — retorna `serviceId`
```bash
SERVICE_ID="uuid-retornado"   # substituir
```

**Teste 15 — Criar segundo servico:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name": "Limpeza de pele",
    "duration_minutes": 60,
    "price_cents": 18000,
    "description": "Limpeza de pele profunda com peeling"
  }'
```
Esperado: `201`

### 3.2 Listar servicos

**Teste 16 — Listar servicos da clinica:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/services" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array com 2 servicos

### 3.3 Atualizar servico

**Teste 17 — Atualizar preco:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/services/$SERVICE_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"price_cents": 18000}'
```
Esperado: `200`

---

## Fase 4 — Professionals CRUD

**Teste 18 — Criar profissional (SALVAR professionalId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/professionals" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"name": "Dra. Ana Souza", "role": "Biomedica esteta"}'
```
Esperado: `201`
```bash
PROFESSIONAL_ID="uuid-retornado"
```

**Teste 19 — Criar segundo profissional:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/professionals" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"name": "Dra. Julia Lima", "role": "Dermatologista"}'
```
Esperado: `201`

**Teste 20 — Listar profissionais:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/professionals" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array com 2 profissionais

---

## Fase 5 — Availability Rules e Exceptions

### 5.1 Regras de disponibilidade

**Teste 21 — Criar regra com day_of_week invalido:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 7, "start_time": "09:00", "end_time": "18:00"}'
```
Esperado: `400` — day_of_week deve ser 0-6

**Teste 22 — Criar regra segunda-feira (SALVAR ruleId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 1, "start_time": "09:00", "end_time": "18:00"}'
```
Esperado: `201`
```bash
RULE_ID="uuid-retornado"
```

**Teste 23-26 — Criar regras terca a sexta:**
```bash
# Terca (2)
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 2, "start_time": "09:00", "end_time": "18:00"}'

# Quarta (3)
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 3, "start_time": "09:00", "end_time": "18:00"}'

# Quinta (4)
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 4, "start_time": "09:00", "end_time": "18:00"}'

# Sexta (5)
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"day_of_week": 5, "start_time": "09:00", "end_time": "18:00"}'
```
Esperado: `201` para cada

**Teste 27 — Listar regras:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-rules" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — 5 regras (seg-sex)

### 5.2 Excecoes de disponibilidade

**Teste 28 — Bloquear data (feriado):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-exceptions" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"exception_date": "2026-03-02", "exception_type": "BLOCKED", "reason": "Carnaval"}'
```
Esperado: `201`

**Teste 29 — Horario especial:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-exceptions" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "exception_date": "2026-02-14",
    "exception_type": "SPECIAL_HOURS",
    "start_time": "10:00",
    "end_time": "15:00",
    "reason": "Horario especial Dia dos Namorados"
  }'
```
Esperado: `201`

**Teste 30 — Listar excecoes com filtro de data:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/availability-exceptions?from=2026-02-01&to=2026-03-31" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — 2 excecoes

---

## Fase 6 — Templates CRUD

**Teste 31 — Criar template de boas-vindas (SALVAR templateId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/templates" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "template_key": "WELCOME_NEW",
    "content": "Ola! Seja bem-vinda a {{clinic_name}}! Como posso te ajudar hoje?",
    "buttons": [
      {"id": "schedule", "label": "Agendar sessao"},
      {"id": "reschedule", "label": "Remarcar sessao"},
      {"id": "faq", "label": "Duvidas"}
    ]
  }'
```
Esperado: `201`
```bash
TEMPLATE_ID="uuid-retornado"
```

**Teste 32 — Criar template duplicado (mesma clinic + key):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/templates" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"template_key": "WELCOME_NEW", "content": "Duplicado"}'
```
Esperado: `409` — UNIQUE constraint violation

**Teste 33 — Listar templates:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/templates" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array com template criado

**Teste 34 — Filtrar por template_key:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/templates?template_key=WELCOME_NEW" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — retorna apenas o template WELCOME_NEW

**Teste 35 — Atualizar template:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/templates/$TEMPLATE_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"content": "Ola! Seja muito bem-vinda a {{clinic_name}}! Em que posso ajudar?"}'
```
Esperado: `200`

---

## Fase 7 — FAQ CRUD

**Teste 36 — Criar FAQ item (SALVAR faqId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/faq" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "question_key": "EQUIPMENT",
    "question_label": "Qual equipamento voces usam?",
    "answer": "Trabalhamos com o Soprano Ice Platinum, uma das tecnologias mais avancadas do mundo em depilacao a laser. Indolor e seguro para todos os tipos de pele.",
    "display_order": 1
  }'
```
Esperado: `201`
```bash
FAQ_ID="uuid-retornado"
```

**Teste 37 — Criar mais FAQ items:**
```bash
# Intervalo entre sessoes
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/faq" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "question_key": "SESSION_INTERVAL",
    "question_label": "Qual o intervalo entre sessoes?",
    "answer": "As sessoes tem intervalo medio de 30 dias, ou seja, voce realiza aproximadamente 1 sessao por mes.",
    "display_order": 2
  }'

# Formas de pagamento
curl -s -X POST "$BASE_URL/$STAGE/clinics/$CLINIC_ID/faq" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "question_key": "PAYMENT",
    "question_label": "Quais formas de pagamento?",
    "answer": "Aceitamos PIX, cartao de credito (ate 3x sem juros) e dinheiro.",
    "display_order": 3
  }'
```
Esperado: `201` para cada

**Teste 38 — Listar FAQ (ordenado por display_order):**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/faq" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — 3 items ordenados por display_order (1, 2, 3)

**Teste 39 — Atualizar FAQ:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/faq/$FAQ_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"answer": "Soprano Ice Platinum - tecnologia de ponta, indolor e segura para todos os fototipos.", "display_order": 1}'
```
Esperado: `200`

---

## Fase 8 — Calculo de Disponibilidade

> Estes testes validam o algoritmo de calculo de slots. Dependem das regras e excecoes criadas na Fase 5.

**Teste 40 — Consultar slots em dia util (com disponibilidade):**
```bash
# Escolher uma data que seja dia util (seg-sex) e que NAO seja uma excecao
# Exemplo: proxima segunda-feira
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-02&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200`
```json
{
  "slots": ["09:00", "09:55", "10:50", "11:45", "12:40", "13:35", "14:30", "15:25", "16:20", "17:15"]
}
```
Verificar:
- Slots comecam as 09:00 (start_time da regra)
- Intervalo entre slots = 45min (duracao) + 10min (buffer antigo) ou 15min (se ja atualizou) = 55min ou 60min
- Ultimo slot permite completar a sessao antes das 18:00
- Nenhum slot apos 17:15 (45min de sessao terminaria as 18:00)

**Teste 41 — Consultar slots em sabado (sem disponibilidade):**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-07&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — `{"slots": []}` (sabado nao tem regra)

**Teste 42 — Consultar slots em domingo (sem disponibilidade):**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-08&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — `{"slots": []}` (domingo nao tem regra)

**Teste 43 — Consultar slots em dia bloqueado (Carnaval):**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-03-02&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — `{"slots": []}` (BLOCKED exception)

**Teste 44 — Consultar slots em dia com horario especial:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-14&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — slots entre 10:00 e ~14:15 apenas (SPECIAL_HOURS 10:00-15:00)

**Teste 45 — Consultar dias disponiveis (proximo 14 dias):**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-days?serviceId=$SERVICE_ID&daysAhead=14" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — lista de datas (somente dias uteis, excluindo bloqueados)
> Nota: este endpoint pode nao existir como API REST separada — pode ser interno ao conversation engine. Verificar se foi implementado como endpoint.

---

## Fase 9 — Appointments CRUD

### 9.1 Criar agendamento

**Teste 46 — Criar sem campos obrigatorios:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/appointments" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"clinicId": "'$CLINIC_ID'"}'
```
Esperado: `400` — campos obrigatorios ausentes

**Teste 47 — Criar agendamento valido (SALVAR appointmentId):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/appointments" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clinicId": "'$CLINIC_ID'",
    "phone": "5511999990000",
    "serviceId": "'$SERVICE_ID'",
    "date": "2026-02-16",
    "time": "09:00",
    "areas": "Pernas e axilas"
  }'
```
Esperado: `201`
```json
{
  "status": "SUCCESS",
  "appointmentId": "uuid",
  "message": "Agendamento criado com sucesso"
}
```
```bash
APPOINTMENT_ID="uuid-retornado"
```

Verificar tambem:
- Paciente criado automaticamente em `scheduler.patients` (phone: 5511999990000)
- Lembrete criado em DynamoDB ScheduledReminders (status=PENDING, send_at = 2026-02-15T09:00 - ajustado por timezone)
- Se Google Sheets configurado: linha adicionada na planilha

**Teste 48 — Criar agendamento no mesmo horario (conflito):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/appointments" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clinicId": "'$CLINIC_ID'",
    "phone": "5511888880000",
    "serviceId": "'$SERVICE_ID'",
    "date": "2026-02-16",
    "time": "09:00",
    "areas": "Costas"
  }'
```
Esperado: `409` — conflito de horario

**Teste 49 — Criar agendamento em horario adjacente (sem conflito):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/appointments" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clinicId": "'$CLINIC_ID'",
    "phone": "5511888880000",
    "serviceId": "'$SERVICE_ID'",
    "date": "2026-02-16",
    "time": "10:00",
    "areas": "Costas"
  }'
```
Esperado: `201` — horario das 10:00 nao conflita com 09:00-09:45

### 9.2 Listar agendamentos

**Teste 50 — Listar por data:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/appointments?date=2026-02-16" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — 2 agendamentos, com dados do paciente (JOIN)

**Teste 51 — Listar por data e status:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/appointments?date=2026-02-16&status=CONFIRMED" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — 2 agendamentos com status CONFIRMED

**Teste 52 — Listar data sem agendamentos:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/appointments?date=2026-02-20" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array vazio

### 9.3 Atualizar agendamento

**Teste 53 — Adicionar notas:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/appointments/$APPOINTMENT_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"notes": "Paciente com alergia a creme anestesico"}'
```
Esperado: `200`

**Teste 54 — Cancelar agendamento:**
```bash
curl -s -X PUT "$BASE_URL/$STAGE/appointments/$APPOINTMENT_ID" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"status": "CANCELLED"}'
```
Esperado: `200` — status atualizado para CANCELLED

Verificar:
- Lembrete no DynamoDB atualizado para status=CANCELLED
- Se Google Sheets configurado: status atualizado na planilha

**Teste 55 — Verificar que slot foi liberado apos cancelamento:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-16&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — slot das 09:00 aparece novamente como disponivel

### 9.4 Verificar impacto na disponibilidade

**Teste 56 — Slots apos agendamento (deve excluir horario ocupado):**
```bash
# Primeiro, recriar o agendamento das 09:00 (se foi cancelado no teste 54, pular este)
# Verificar se o slot das 10:00 ja esta ocupado pelo teste 49
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID/available-slots?date=2026-02-16&serviceId=$SERVICE_ID" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — slot das 10:00 NAO aparece (ocupado pelo agendamento do teste 49)

---

## Fase 10 — Envio de Mensagens (Send)

> Requer z-api configurado na clinica (teste 10). Se nao tiver z-api real, estes testes retornarao erro de provider.

**Teste 57 — Enviar mensagem de texto:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/send" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clinicId": "'$CLINIC_ID'",
    "phone": "5511999990000",
    "type": "text",
    "content": "Ola! Esta e uma mensagem de teste do sistema de agendamento."
  }'
```
Esperado: `200`
```json
{
  "status": "SUCCESS",
  "messageId": "uuid",
  "providerStatus": "SENT"
}
```

Verificar:
- MessageEvents no DynamoDB tem registro com direction=OUTBOUND, status=SENT
- Se z-api real: mensagem chega no WhatsApp

**Teste 58 — Enviar mensagem com botoes:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/send" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "clinicId": "'$CLINIC_ID'",
    "phone": "5511999990000",
    "type": "buttons",
    "content": "Escolha uma opcao:",
    "buttons": [
      {"id": "opt1", "label": "Opcao 1"},
      {"id": "opt2", "label": "Opcao 2"},
      {"id": "opt3", "label": "Opcao 3"}
    ]
  }'
```
Esperado: `200` — mensagem enviada (ou fallback para texto numerado)

**Teste 59 — Enviar para clinica inexistente:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/send" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{"clinicId": "clinica-falsa-000000", "phone": "5511999990000", "type": "text", "content": "Teste"}'
```
Esperado: `404` — clinica nao encontrada

---

## Fase 11 — Webhook de Recebimento de Mensagens

> Simula o z-api enviando mensagens recebidas para o sistema.

**Teste 60 — Simular mensagem de texto (primeira interacao):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "MSG-TEST-001",
    "phone": "5511999990000",
    "fromMe": false,
    "momment": 1738300800000,
    "chatName": "Maria Silva",
    "senderName": "Maria Silva",
    "isGroup": false,
    "text": {"message": "Ola"}
  }'
```
Esperado: `200`

Verificar:
- ConversationSessions no DynamoDB tem sessao criada (state=MAIN_MENU ou WELCOME)
- MessageEvents tem registro INBOUND (direction=INBOUND, status=RECEIVED)
- MessageEvents tem registro(s) OUTBOUND da resposta de boas-vindas
- Se z-api real: paciente recebe mensagem de boas-vindas com botoes do menu principal

**Teste 61 — Simular resposta de botao (Agendar sessao):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "MSG-TEST-002",
    "phone": "5511999990000",
    "fromMe": false,
    "momment": 1738300810000,
    "chatName": "Maria Silva",
    "senderName": "Maria Silva",
    "isGroup": false,
    "referenceMessageId": "MSG-RESP-001",
    "buttonsResponseMessage": {
      "buttonId": "schedule",
      "message": "Agendar sessao"
    }
  }'
```
Esperado: `200`

Verificar:
- ConversationSessions atualizado (state=SCHEDULE_MENU)
- Paciente recebe menu de agendamento (ver precos / ver dias disponiveis)

**Teste 62 — Simular resposta numerica (fallback):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "MSG-TEST-003",
    "phone": "5511777770000",
    "fromMe": false,
    "momment": 1738300820000,
    "chatName": "Joao Teste",
    "senderName": "Joao Teste",
    "isGroup": false,
    "text": {"message": "1"}
  }'
```
Esperado: `200` — sistema interpreta "1" como primeiro botao do menu

**Teste 63 — Ignorar mensagem de grupo:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "MSG-TEST-004",
    "phone": "5511999990000",
    "fromMe": false,
    "momment": 1738300830000,
    "isGroup": true,
    "text": {"message": "Mensagem de grupo"}
  }'
```
Esperado: `200` — processamento ignorado, sem sessao criada

**Teste 64 — Ignorar mensagem propria (fromMe):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "MSG-TEST-005",
    "phone": "5511999990000",
    "fromMe": true,
    "momment": 1738300840000,
    "text": {"message": "Minha propria mensagem"}
  }'
```
Esperado: `200` — processamento ignorado

**Teste 65 — Mensagem nao reconhecida:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "MSG-TEST-006",
    "phone": "5511999990000",
    "fromMe": false,
    "momment": 1738300850000,
    "senderName": "Maria Silva",
    "isGroup": false,
    "text": {"message": "asdfghjkl texto aleatorio"}
  }'
```
Esperado: `200` — paciente recebe mensagem UNRECOGNIZED com opcoes de menu ou falar com atendente

---

## Fase 12 — Webhook de Status de Mensagens

**Teste 66 — Simular status SENT:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp/status" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "MessageStatusCallback",
    "status": "SENT",
    "ids": ["MSG-RESP-001"],
    "momment": 1738300860000,
    "phone": "5511999990000",
    "instanceId": "INSTANCE_ID_DA_CLINICA"
  }'
```
Esperado: `200`

Verificar: MessageEvents tem novo registro com status=SENT para MSG-RESP-001

**Teste 67 — Simular status READ:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp/status" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "MessageStatusCallback",
    "status": "READ",
    "ids": ["MSG-RESP-001"],
    "momment": 1738300870000,
    "phone": "5511999990000",
    "instanceId": "INSTANCE_ID_DA_CLINICA"
  }'
```
Esperado: `200`

Verificar: MessageEvents tem registros SENT → READ para MSG-RESP-001 (historico completo)

---

## Fase 13 — Fluxo Completo de Conversa (End-to-End)

> Este e o teste mais importante. Simula um paciente passando por todo o fluxo de agendamento via webhook.
> Cada passo depende do anterior. Substituir `INSTANCE_ID_DA_CLINICA` pelo valor real.

### 13.1 Fluxo de agendamento completo

```
Paciente envia "Ola"
  → Sistema responde com boas-vindas + menu principal
Paciente clica "Agendar sessao"
  → Sistema mostra menu de agendamento (ver precos / ver dias)
Paciente clica "Ver dias disponiveis"
  → Sistema mostra dias disponiveis (proximos 14 dias)
Paciente seleciona uma data
  → Sistema mostra horarios disponiveis para a data
Paciente seleciona um horario
  → Sistema pede as areas
Paciente digita "Pernas e axilas"
  → Sistema mostra resumo para confirmacao
Paciente confirma
  → Sistema confirma agendamento com detalhes
```

**Passo 1 — Ola (nova conversa):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-001",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301000000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "text": {"message": "Ola"}
  }'
```
Verificar: state = MAIN_MENU, resposta com boas-vindas

**Passo 2 — Agendar sessao:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-002",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301010000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "schedule", "message": "Agendar sessao"}
  }'
```
Verificar: state = SCHEDULE_MENU

**Passo 3 — Ver dias disponiveis:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-003",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301020000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "available_days", "message": "Ver dias disponiveis"}
  }'
```
Verificar: state = AVAILABLE_DAYS, resposta lista datas

**Passo 4 — Selecionar data (responder com a data):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-004",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301030000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "date_2026-02-16", "message": "16/02 (Seg)"}
  }'
```
Verificar: state = SELECT_TIME, resposta lista horarios

**Passo 5 — Selecionar horario:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-005",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301040000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "time_14:00", "message": "14:00"}
  }'
```
Verificar: state = INPUT_AREAS

**Passo 6 — Informar areas (texto livre):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-006",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301050000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "text": {"message": "Pernas e axilas"}
  }'
```
Verificar: state = CONFIRM_BOOKING, resposta mostra resumo

**Passo 7 — Confirmar agendamento:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "E2E-007",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738301060000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "confirm", "message": "Confirmar"}
  }'
```
Verificar:
- state = BOOKED (ou volta para MAIN_MENU)
- Agendamento criado no RDS (scheduler.appointments)
- Paciente criado no RDS (scheduler.patients, phone=5511666660000)
- Lembrete criado no DynamoDB (ScheduledReminders, status=PENDING)
- Se Sheets configurado: linha adicionada
- Resposta com confirmacao, endereco e instrucoes pre-sessao

### 13.2 Fluxo de remarcacao

> Usar o mesmo telefone do fluxo 13.1 (5511666660000) que agora tem agendamento ativo.

**Passo 1 — Nova conversa (paciente retornando):**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "RESC-001",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738302000000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "text": {"message": "Oi"}
  }'
```
Verificar: boas-vindas personalizada ("Ola, Ana!" em vez de generico)

**Passo 2 — Remarcar sessao:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "RESC-002",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738302010000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "reschedule", "message": "Remarcar sessao"}
  }'
```
Verificar: state = SHOW_CURRENT_APPOINTMENT, mostra agendamento atual (16/02 14:00)

**Passo 3 — Selecionar nova data:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "RESC-003",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738302020000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "date_2026-02-17", "message": "17/02 (Ter)"}
  }'
```

**Passo 4 — Selecionar novo horario:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "RESC-004",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738302030000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "time_11:00", "message": "11:00"}
  }'
```

**Passo 5 — Confirmar remarcacao:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "RESC-005",
    "phone": "5511666660000",
    "fromMe": false,
    "momment": 1738302040000,
    "senderName": "Ana Costa",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "confirm", "message": "Confirmar"}
  }'
```
Verificar:
- Agendamento antigo: data/horario atualizados (17/02 11:00)
- Lembrete antigo: status=CANCELLED
- Novo lembrete criado (send_at = 16/02 11:00 timezone)
- Se Sheets: linha atualizada
- Slot antigo (16/02 14:00) liberado

### 13.3 Fluxo de FAQ

**Passo 1 — Menu principal → Duvidas:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "FAQ-001",
    "phone": "5511555550000",
    "fromMe": false,
    "momment": 1738303000000,
    "senderName": "Julia Santos",
    "isGroup": false,
    "text": {"message": "Ola"}
  }'
```

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "FAQ-002",
    "phone": "5511555550000",
    "fromMe": false,
    "momment": 1738303010000,
    "senderName": "Julia Santos",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "faq", "message": "Duvidas sobre sessao"}
  }'
```
Verificar: state = FAQ_MENU, mostra botoes com as perguntas cadastradas

**Passo 2 — Selecionar pergunta:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "FAQ-003",
    "phone": "5511555550000",
    "fromMe": false,
    "momment": 1738303020000,
    "senderName": "Julia Santos",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "faq_EQUIPMENT", "message": "Qual equipamento voces usam?"}
  }'
```
Verificar: state = FAQ_ANSWER, resposta com o conteudo da FAQ "Soprano Ice Platinum..."

### 13.4 Fluxo de atendente humano

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "HUMAN-001",
    "phone": "5511444440000",
    "fromMe": false,
    "momment": 1738304000000,
    "senderName": "Carlos Teste",
    "isGroup": false,
    "text": {"message": "Ola"}
  }'
```

```bash
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "HUMAN-002",
    "phone": "5511444440000",
    "fromMe": false,
    "momment": 1738304010000,
    "senderName": "Carlos Teste",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "human", "message": "Falar com atendente"}
  }'
```
Verificar: state = HUMAN_HANDOFF, mensagem sobre horario comercial

### 13.5 Navegacao "Voltar"

```bash
# Iniciar conversa e ir ate SCHEDULE_MENU
# (passos 1 e 2 do fluxo 13.1)

# Clicar "Voltar" no SCHEDULE_MENU
curl -s -X POST "$BASE_URL/$STAGE/webhook/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "ReceivedCallback",
    "instanceId": "INSTANCE_ID_DA_CLINICA",
    "messageId": "BACK-001",
    "phone": "5511333330000",
    "fromMe": false,
    "momment": 1738305000000,
    "senderName": "Pedro Voltar",
    "isGroup": false,
    "buttonsResponseMessage": {"buttonId": "back", "message": "Voltar"}
  }'
```
Verificar: state volta para MAIN_MENU

---

## Fase 14 — Sistema de Lembretes

> O ReminderProcessor roda automaticamente a cada 15 minutos via EventBridge.
> Para testar manualmente, invocar a Lambda diretamente.

**Teste 68 — Invocar ReminderProcessor manualmente:**
```bash
aws lambda invoke --function-name clinic-scheduler-infra-dev-ReminderProcessor \
  --profile traffic-manager \
  --payload '{}' \
  response.json && cat response.json
```
Esperado:
```json
{
  "processed": N,
  "sent": X,
  "failed": Y
}
```

**Teste 69 — Verificar lembretes pendentes no DynamoDB:**
```bash
aws dynamodb query \
  --table-name clinic-scheduler-infra-dev-scheduled-reminders \
  --index-name status-sendAt-index \
  --key-condition-expression "#s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":status": {"S": "PENDING"}}' \
  --profile traffic-manager
```
Esperado: lista de lembretes pendentes com sendAt e appointmentId

**Teste 70 — Verificar que lembrete de agendamento cancelado esta CANCELLED:**
```bash
# Buscar lembretes do agendamento cancelado no teste 54
aws dynamodb scan \
  --table-name clinic-scheduler-infra-dev-scheduled-reminders \
  --filter-expression "appointmentId = :aid" \
  --expression-attribute-values '{":aid": {"S": "APPOINTMENT_ID_CANCELADO"}}' \
  --profile traffic-manager
```
Esperado: status = CANCELLED

---

## Fase 15 — Google Sheets Sync

> Requer Google Sheets service account configurado e planilha compartilhada.

| # | Teste | Como verificar | Esperado |
|---|-------|---------------|----------|
| 1 | Agendamento criado → linha na planilha | Abrir planilha da clinica apos criar agendamento (teste 47) | Linha com Data, Horario, Paciente, Telefone, Servico, Areas, Status=CONFIRMED |
| 2 | Agendamento cancelado → status atualizado | Abrir planilha apos cancelar (teste 54) | Status da linha atualizado para CANCELLED |
| 3 | Remarcacao → linha atualizada | Abrir planilha apos remarcar (fase 13.2) | Data e horario atualizados na linha existente |
| 4 | Coluna appointment_id presente | Verificar ultima coluna | ID do agendamento para correlacao futura |
| 5 | Clinica sem planilha → sem erro | Criar clinica sem google_spreadsheet_id e agendar | Agendamento criado normalmente, sem erro no log |

---

## Fase 16 — Relatorio Diario

> O DailyReportSender roda automaticamente as 23:00 UTC (20:00 BRT).

**Teste 71 — Invocar DailyReportSender manualmente:**
```bash
aws lambda invoke --function-name clinic-scheduler-infra-dev-DailyReportSender \
  --profile traffic-manager \
  --payload '{}' \
  response.json && cat response.json
```
Esperado: relatorio enviado para o numero da clinica

Verificar:
- Mensagem recebida no WhatsApp da clinica com formato:
  ```
  Agenda de amanha (DD/MM):

  HH:MM - Paciente | Servico | Areas
  ...

  Total: N sessoes agendadas
  ```
- Se nenhum agendamento para amanha: nenhuma mensagem enviada

---

## Fase 17 — Rastreamento de Mensagens (Validacao)

**Teste 72 — Consultar historico de mensagens por telefone:**
```bash
aws dynamodb query \
  --table-name clinic-scheduler-infra-dev-message-events \
  --key-condition-expression "pk = :pk" \
  --expression-attribute-values '{":pk": {"S": "CLINIC#'$CLINIC_ID'#PHONE#5511666660000"}}' \
  --profile traffic-manager \
  --output json | python -c "import json,sys; data=json.load(sys.stdin); [print(f\"{i['direction']['S']} | {i.get('status',{}).get('S','?')} | {i.get('content',{}).get('S','')[:50]}\") for i in data['Items']]"
```
Esperado: historico cronologico de todas as mensagens trocadas (INBOUND + OUTBOUND)

**Teste 73 — Verificar GSI de mensagens com falha:**
```bash
aws dynamodb query \
  --table-name clinic-scheduler-infra-dev-message-events \
  --index-name status-statusTimestamp-index \
  --key-condition-expression "#s = :status" \
  --expression-attribute-names '{"#s": "status"}' \
  --expression-attribute-values '{":status": {"S": "FAILED"}}' \
  --profile traffic-manager
```
Esperado: lista de mensagens com status FAILED (pode ser vazia se nenhuma falhou)

---

## Fase 18 — Multi-tenant (Isolamento)

> Validar que dados de uma clinica nao vazam para outra.

**Teste 74 — Criar segunda clinica:**
```bash
curl -s -X POST "$BASE_URL/$STAGE/clinics" \
  -H "Content-Type: application/json" \
  -H "x-api-key: $API_KEY" \
  -d '{
    "name": "Estetica Premium RJ",
    "phone": "5521988880000",
    "address": "Av. Atlantica, 500 - Rio de Janeiro, RJ",
    "business_hours": {
      "mon": {"start": "10:00", "end": "19:00"},
      "tue": {"start": "10:00", "end": "19:00"},
      "wed": {"start": "10:00", "end": "19:00"}
    },
    "buffer_minutes": 15,
    "timezone": "America/Sao_Paulo"
  }'
```
```bash
CLINIC_ID_2="esteticapremiumrj-XXXXXX"   # substituir
```

**Teste 75 — Servicos da clinica 2 sao independentes:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID_2/services" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array vazio (clinica 2 nao tem servicos)

**Teste 76 — FAQ da clinica 2 sao independentes:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID_2/faq" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array vazio

**Teste 77 — Agendamentos da clinica 2 sao independentes:**
```bash
curl -s -X GET "$BASE_URL/$STAGE/clinics/$CLINIC_ID_2/appointments?date=2026-02-16" \
  -H "x-api-key: $API_KEY"
```
Esperado: `200` — array vazio (agendamentos da clinica 1 nao aparecem)

---

## Checklist Final — Criterios de Aceite do PRD

### Fluxos de conversa
- [ ] Paciente recebe boas-vindas ao enviar primeira mensagem (teste 60)
- [ ] Menu principal com 3 opcoes + falar com atendente (teste 61)
- [ ] Fluxo agendamento completo: servico → data → horario → areas → confirmacao (fase 13.1)
- [ ] Fluxo remarcacao: busca → atual → nova data/horario → confirmacao (fase 13.2)
- [ ] FAQ interativo com respostas configuraveis (fase 13.3)
- [ ] Botao "voltar" funciona (fase 13.5)
- [ ] Mensagens nao reconhecidas → menu ou atendente (teste 65)
- [ ] Falar com atendente → mensagem sobre horario comercial (fase 13.4)

### Agendamento
- [ ] Horarios calculados corretamente: duracao + buffer (teste 40)
- [ ] Nao agendar horario ocupado (teste 48)
- [ ] Confirmacao com resumo completo (passo 7 da fase 13.1)

### Lembretes
- [ ] Lembrete criado 24h antes (verificar DynamoDB apos criar agendamento)
- [ ] Lembrete cancelado se agendamento cancelado (teste 70)

### Multi-tenant
- [ ] Dados isolados por clinicId (fase 18)

### Rastreamento
- [ ] OUTBOUND registrado: QUEUED → SENT → DELIVERED → READ (testes 66-67)
- [ ] INBOUND registrado: RECEIVED (teste 72)
- [ ] Provider response raw salvo (verificar DynamoDB)

### Google Sheets + Relatorio
- [ ] Criado → linha adicionada (fase 15, item 1)
- [ ] Remarcado → linha atualizada (fase 15, item 3)
- [ ] Cancelado → status atualizado (fase 15, item 2)
- [ ] Relatorio diario enviado as 20h (fase 16)
- [ ] Clinica sem planilha → sem erro (fase 15, item 5)

### Admin API
- [ ] CRUD clinica (fase 2)
- [ ] CRUD servicos (fase 3)
- [ ] CRUD profissionais (fase 4)
- [ ] CRUD regras de disponibilidade (fase 5.1)
- [ ] CRUD excecoes de disponibilidade (fase 5.2)
- [ ] CRUD templates (fase 6)
- [ ] CRUD FAQ (fase 7)
- [ ] Listagem agendamentos por clinica/data (teste 50-51)

### Infraestrutura
- [ ] Deploy independente do projeto infra (fase 1.3)
- [ ] Provider WhatsApp abstraido (verificar que handlers usam interface, nao z-api direto)
- [ ] Secrets em SSM (verificar serverless.yml)

---

## Cleanup (apos todos os testes)

```bash
# Opcional: remover dados de teste do RDS
# Conectar ao RDS e executar:
# DELETE FROM scheduler.appointments WHERE clinic_id LIKE '%teste%';
# DELETE FROM scheduler.patients WHERE clinic_id LIKE '%teste%';
# DELETE FROM scheduler.clinics WHERE clinic_id = 'esteticapremiumrj-XXXXXX';

# Opcional: limpar DynamoDB (cuidado em prod!)
# Os itens com TTL serao limpos automaticamente
```

---

## Notas

- Substituir `YOUR_API_GATEWAY_URL` pela URL real do API Gateway apos deploy
- Substituir `INSTANCE_ID_DA_CLINICA` pelo zapi_instance_id configurado
- Os testes da fase 10+ (envio real) requerem z-api ativo
- Os testes da fase 15 requerem Google Sheets service account
- Button IDs nos testes da fase 13 podem variar dependendo da implementacao — ajustar conforme os IDs reais usados no conversation_engine
- Datas nos testes devem ser ajustadas para datas futuras reais no momento da execucao
