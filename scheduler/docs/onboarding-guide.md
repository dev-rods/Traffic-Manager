# Trilha de Implantacao - Scheduler

Guia passo a passo para integrar uma nova clinica no sistema de agendamento via WhatsApp.

---

## Pre-requisitos

| Item | Descricao |
|------|-----------|
| **API Key** | `SCHEDULER_API_KEY` configurada no SSM (`/{stage}/SCHEDULER_API_KEY`) |
| **Base URL** | `https://{API_GATEWAY_ID}.execute-api.us-east-1.amazonaws.com/{stage}` |
| **z-api** | Instancia z-api criada e conectada ao WhatsApp da clinica |
| **Google Sheets** | (Opcional) Planilha criada e compartilhada com a service account |

**Headers obrigatorios em todas as chamadas (exceto webhooks):**

```
x-api-key: {API_KEY}
Content-Type: application/json
```

---

## Etapa 1 - Criar a Clinica

A clinica e o registro raiz. Tudo no sistema e vinculado a um `clinic_id`.

```
POST /clinics
```

```json
{
  "name": "Nome da Clinica",
  "phone": "5511999990000",
  "address": "Rua Exemplo, 123 - Sao Paulo/SP",
  "timezone": "America/Sao_Paulo",
  "buffer_minutes": 10,
  "business_hours": {
    "mon": { "start": "09:00", "end": "18:00" },
    "tue": { "start": "09:00", "end": "18:00" },
    "wed": { "start": "09:00", "end": "18:00" },
    "thu": { "start": "09:00", "end": "18:00" },
    "fri": { "start": "09:00", "end": "18:00" }
  },
  "welcome_message": "Mensagem personalizada de boas-vindas (opcional)",
  "pre_session_instructions": "Instrucoes pre-sessao enviadas apos confirmacao (opcional)"
}
```

**Resposta:** retorna o objeto com `clinicId` gerado automaticamente (formato kebab-case).

> Anote o `clinicId` - ele sera usado em todas as chamadas seguintes.

---

## Etapa 2 - Configurar Integracao z-api (WhatsApp)

Vincula a instancia z-api para envio/recebimento de mensagens WhatsApp.

```
PUT /clinics/{clinicId}
```

```json
{
  "zapi_instance_id": "INSTANCE_ID_DA_ZAPI",
  "zapi_instance_token": "TOKEN_DA_ZAPI"
}
```

### 2.1 - Configurar Webhooks na z-api

No painel da z-api, configure os seguintes webhooks:

| Webhook | URL |
|---------|-----|
| **ReceivedCallback** (mensagens recebidas) | `{BASE_URL}/webhook/whatsapp` |
| **MessageStatusCallback** (status de entrega) | `{BASE_URL}/webhook/whatsapp/status` |

> Estes endpoints NAO exigem API key.

---

## Etapa 3 - Configurar Google Sheets (Opcional)

Sincroniza agendamentos automaticamente com uma planilha Google.

```
PUT /clinics/{clinicId}
```

```json
{
  "google_spreadsheet_id": "ID_DA_PLANILHA",
  "google_sheet_name": "Nome da Aba"
}
```

> A planilha precisa estar compartilhada com a service account do sistema.

---

## Etapa 4 - Cadastrar Servicos

Servicos definem o que a clinica oferece. O `duration_minutes` e essencial para o calculo de horarios disponiveis.

```
POST /clinics/{clinicId}/services
```

```json
{
  "name": "Depilacao a Laser - Pernas",
  "duration_minutes": 45,
  "price_cents": 15000,
  "description": "Sessao avulsa com Soprano Ice Platinum"
}
```

Repita para cada servico oferecido. Exemplos comuns:

| Servico | Duracao | Preco (centavos) |
|---------|---------|-----------------|
| Depilacao Laser - Corpo Inteiro | 90 | 35000 |
| Depilacao Laser - Axilas | 20 | 8000 |
| Limpeza de Pele | 60 | 12000 |
| Consulta Avaliacao | 30 | 0 |

> Anote os `serviceId` retornados - serao usados para consultar disponibilidade.

**Listar servicos cadastrados:**

```
GET /clinics/{clinicId}/services
```

---

## Etapa 5 - Cadastrar Profissionais (Opcional)

Profissionais representam a equipe que realiza os atendimentos.

```
POST /clinics/{clinicId}/professionals
```

```json
{
  "name": "Dra. Maria Silva",
  "role": "Esteticista"
}
```

> Se a clinica tem apenas 1 profissional ou nao precisa vincular agendamentos a profissionais, esta etapa pode ser pulada. Os agendamentos serao criados sem profissional vinculado.

**Listar profissionais:**

```
GET /clinics/{clinicId}/professionals
```

---

## Etapa 6 - Configurar Regras de Disponibilidade

Define os horarios de funcionamento da clinica para cada dia da semana. O sistema usa estas regras para gerar os horarios disponiveis automaticamente.

```
POST /clinics/{clinicId}/availability-rules
```

### Mapeamento de dias da semana

| Valor | Dia |
|-------|-----|
| 0 | Domingo |
| 1 | Segunda-feira |
| 2 | Terca-feira |
| 3 | Quarta-feira |
| 4 | Quinta-feira |
| 5 | Sexta-feira |
| 6 | Sabado |

### Exemplo: clinica que funciona segunda a sexta, 09h-18h

Envie uma requisicao para cada dia:

```json
{ "day_of_week": 1, "start_time": "09:00", "end_time": "18:00" }
```

```json
{ "day_of_week": 2, "start_time": "09:00", "end_time": "18:00" }
```

```json
{ "day_of_week": 3, "start_time": "09:00", "end_time": "18:00" }
```

```json
{ "day_of_week": 4, "start_time": "09:00", "end_time": "18:00" }
```

```json
{ "day_of_week": 5, "start_time": "09:00", "end_time": "18:00" }
```

### Exemplo: clinica que tambem abre sabado de manha

```json
{ "day_of_week": 6, "start_time": "09:00", "end_time": "13:00" }
```

> Apenas 1 regra por dia da semana. Dias sem regra = clinica fechada naquele dia.

**Listar regras:**

```
GET /clinics/{clinicId}/availability-rules
```

---

## Etapa 7 - Cadastrar Excecoes de Disponibilidade

Excecoes sobrescrevem as regras regulares para datas especificas.

```
POST /clinics/{clinicId}/availability-exceptions
```

### 7.1 - Dias bloqueados (feriados, ferias, etc.)

A clinica NAO atende nesta data:

```json
{
  "exception_date": "2026-02-16",
  "exception_type": "BLOCKED",
  "reason": "Carnaval"
}
```

### 7.2 - Horario especial

A clinica atende em horario diferente do habitual:

```json
{
  "exception_date": "2026-02-13",
  "exception_type": "SPECIAL_HOURS",
  "start_time": "08:00",
  "end_time": "12:00",
  "reason": "Vespera de feriado"
}
```

### Feriados nacionais comuns para cadastrar

| Data | Feriado |
|------|---------|
| 2026-01-01 | Confraternizacao Universal |
| 2026-02-16 | Carnaval |
| 2026-02-17 | Carnaval |
| 2026-04-03 | Sexta-feira Santa |
| 2026-04-21 | Tiradentes |
| 2026-05-01 | Dia do Trabalho |
| 2026-06-04 | Corpus Christi |
| 2026-09-07 | Independencia |
| 2026-10-12 | Nossa Sra. Aparecida |
| 2026-11-02 | Finados |
| 2026-11-15 | Proclamacao da Republica |
| 2026-12-25 | Natal |

> Cadastre tambem feriados municipais/estaduais conforme a localidade da clinica.

**Listar excecoes:**

```
GET /clinics/{clinicId}/availability-exceptions
```

**Filtrar por periodo:**

```
GET /clinics/{clinicId}/availability-exceptions?from_date=2026-01-01&to_date=2026-12-31
```

---

## Etapa 8 - Cadastrar FAQ

Perguntas frequentes que o bot responde automaticamente durante a conversa.

```
POST /clinics/{clinicId}/faq
```

### FAQs recomendadas

**1. Equipamento/Metodo**
```json
{
  "question_key": "EQUIPMENT",
  "question_label": "Qual equipamento voces usam?",
  "answer": "Utilizamos o Soprano Ice Platinum, referencia mundial em depilacao a laser. O aparelho possui tecnologia que combina tres comprimentos de onda para maior eficacia e conforto.",
  "display_order": 1
}
```

**2. Contraindicacoes**
```json
{
  "question_key": "CONTRAINDICATIONS",
  "question_label": "Quais sao as contraindicacoes?",
  "answer": "Gestantes, pessoas com infeccoes ativas na pele, uso recente de isotretinoina (Roacutan) e bronzeamento recente. Consulte nossa equipe para avaliacao individual.",
  "display_order": 2
}
```

**3. Preparo pre-sessao**
```json
{
  "question_key": "PREPARATION",
  "question_label": "Como me preparar para a sessao?",
  "answer": "Raspe a area 24h antes da sessao. Evite exposicao solar por 48h. Nao use cremes ou desodorante na area no dia. Use roupas confortaveis.",
  "display_order": 3
}
```

**4. Numero de sessoes**
```json
{
  "question_key": "SESSIONS",
  "question_label": "Quantas sessoes sao necessarias?",
  "answer": "Em media, sao necessarias de 8 a 12 sessoes, com intervalos de 30 a 45 dias entre elas. O numero varia conforme o tipo de pele, area e resposta individual.",
  "display_order": 4
}
```

**5. Formas de pagamento**
```json
{
  "question_key": "PAYMENT",
  "question_label": "Quais as formas de pagamento?",
  "answer": "Aceitamos Pix, cartao de credito (ate 6x sem juros), cartao de debito e dinheiro.",
  "display_order": 5
}
```

**6. Politica de cancelamento**
```json
{
  "question_key": "CANCELLATION",
  "question_label": "Qual a politica de cancelamento?",
  "answer": "Cancelamentos devem ser feitos com no minimo 24h de antecedencia. Faltas sem aviso previo podem ser cobradas.",
  "display_order": 6
}
```

> Adapte as perguntas e respostas de acordo com o negocio da clinica.

**Listar FAQs:**

```
GET /clinics/{clinicId}/faq
```

---

## Etapa 9 - Personalizar Templates de Mensagem (Opcional)

O sistema possui templates padrao para todas as mensagens do fluxo de conversa. So e necessario criar templates customizados se a clinica quiser personalizar o texto.

```
POST /clinics/{clinicId}/templates
```

### Templates disponiveis

| Key | Quando e usado | Variaveis |
|-----|---------------|-----------|
| `WELCOME_NEW` | Primeiro contato de um paciente novo | `{{clinic_name}}` |
| `WELCOME_RETURNING` | Paciente que ja tem cadastro | `{{patient_name}}`, `{{clinic_name}}` |
| `MAIN_MENU` | Menu principal de opcoes | - |
| `SCHEDULE_MENU` | Submenu de agendamento | - |
| `PRICE_TABLE` | Tabela de precos | `{{price_table}}` |
| `AVAILABLE_DAYS` | Lista de dias disponiveis | `{{days_list}}` |
| `SELECT_TIME` | Horarios disponiveis no dia | `{{date}}`, `{{times_list}}` |
| `INPUT_AREAS` | Solicita areas de tratamento | - |
| `CONFIRM_BOOKING` | Confirmacao pre-agendamento | `{{date}}`, `{{time}}`, `{{service}}`, `{{areas}}`, `{{clinic_name}}`, `{{address}}` |
| `BOOKED` | Agendamento confirmado | `{{date}}`, `{{time}}`, `{{pre_session_instructions}}` |
| `RESCHEDULE_FOUND` | Agendamento encontrado para remarcar | `{{date}}`, `{{time}}`, `{{service}}` |
| `RESCHEDULE_NOT_FOUND` | Nenhum agendamento ativo encontrado | - |
| `RESCHEDULED` | Remarcacao confirmada | `{{date}}`, `{{time}}` |
| `FAQ_MENU` | Menu de duvidas frequentes | - |
| `HUMAN_HANDOFF` | Encaminhamento para atendente | - |
| `UNRECOGNIZED` | Mensagem nao reconhecida | - |
| `REMINDER_24H` | Lembrete 24h antes | `{{time}}`, `{{clinic_name}}` |

### Exemplo de template customizado

```json
{
  "template_key": "WELCOME_NEW",
  "content": "Oi! Bem-vinda ao {{clinic_name}}! Sou a assistente virtual e vou te ajudar com agendamentos e duvidas. O que deseja fazer?",
  "buttons": [
    { "id": "schedule", "label": "Agendar sessao" },
    { "id": "faq", "label": "Duvidas frequentes" },
    { "id": "prices", "label": "Ver precos" },
    { "id": "human", "label": "Falar com atendente" }
  ]
}
```

> Se nao customizar, o sistema usa os templates padrao automaticamente.

**Listar templates:**

```
GET /clinics/{clinicId}/templates
```

---

## Etapa 10 - Validacao e Teste

Apos completar o cadastro, valide que tudo esta funcionando.

### 10.1 - Verificar disponibilidade

```
GET /clinics/{clinicId}/available-slots?date=2026-02-10&serviceId={serviceId}
```

Deve retornar os horarios disponiveis para o dia/servico informados.

### 10.2 - Criar agendamento de teste

```
POST /appointments
```

```json
{
  "clinicId": "{clinicId}",
  "phone": "5511999990000",
  "serviceId": "{serviceId}",
  "date": "2026-02-10",
  "time": "09:00"
}
```

### 10.3 - Enviar mensagem de teste

```
POST /send
```

```json
{
  "clinicId": "{clinicId}",
  "phone": "5511999990000",
  "type": "text",
  "content": "Teste de integracao - mensagem enviada com sucesso!"
}
```

### 10.4 - Testar fluxo completo via WhatsApp

1. Envie "Oi" para o numero da clinica no WhatsApp
2. O bot deve responder com a mensagem de boas-vindas + menu
3. Selecione "Agendar sessao" e siga o fluxo completo
4. Verifique se o agendamento aparece na planilha Google (se configurada)
5. Verifique os agendamentos via API:

```
GET /clinics/{clinicId}/appointments?date=2026-02-10
```

### 10.5 - Cancelar agendamento de teste

```
PUT /appointments/{appointmentId}
```

```json
{
  "status": "CANCELLED",
  "notes": "Teste de implantacao"
}
```

---

## Checklist de Implantacao

- [ ] Clinica criada
- [ ] z-api configurada (instance_id + token)
- [ ] Webhooks configurados na z-api (ReceivedCallback + MessageStatusCallback)
- [ ] Google Sheets vinculado (se aplicavel)
- [ ] Servicos cadastrados (com duracao e preco)
- [ ] Profissionais cadastrados (se aplicavel)
- [ ] Regras de disponibilidade configuradas (1 por dia da semana)
- [ ] Feriados e excecoes cadastrados
- [ ] FAQs cadastradas
- [ ] Templates personalizados (se necessario)
- [ ] Disponibilidade validada (GET /available-slots)
- [ ] Agendamento de teste criado e cancelado
- [ ] Mensagem de teste enviada via API
- [ ] Fluxo completo testado via WhatsApp
- [ ] Planilha Google sincronizando (se aplicavel)

---

## Referencia Rapida de Endpoints

| Acao | Metodo | Path |
|------|--------|------|
| Criar clinica | POST | `/clinics` |
| Atualizar clinica | PUT | `/clinics/{clinicId}` |
| Listar clinicas | GET | `/clinics` |
| Criar servico | POST | `/clinics/{clinicId}/services` |
| Listar servicos | GET | `/clinics/{clinicId}/services` |
| Atualizar servico | PUT | `/services/{serviceId}` |
| Criar profissional | POST | `/clinics/{clinicId}/professionals` |
| Listar profissionais | GET | `/clinics/{clinicId}/professionals` |
| Criar regra disponibilidade | POST | `/clinics/{clinicId}/availability-rules` |
| Listar regras | GET | `/clinics/{clinicId}/availability-rules` |
| Criar excecao | POST | `/clinics/{clinicId}/availability-exceptions` |
| Listar excecoes | GET | `/clinics/{clinicId}/availability-exceptions` |
| Consultar horarios | GET | `/clinics/{clinicId}/available-slots?date=YYYY-MM-DD&serviceId=UUID` |
| Criar agendamento | POST | `/appointments` |
| Listar agendamentos | GET | `/clinics/{clinicId}/appointments` |
| Atualizar agendamento | PUT | `/appointments/{appointmentId}` |
| Criar FAQ | POST | `/clinics/{clinicId}/faq` |
| Listar FAQs | GET | `/clinics/{clinicId}/faq` |
| Atualizar FAQ | PUT | `/faq/{faqId}` |
| Criar template | POST | `/clinics/{clinicId}/templates` |
| Listar templates | GET | `/clinics/{clinicId}/templates` |
| Atualizar template | PUT | `/templates/{templateId}` |
| Enviar mensagem | POST | `/send` |
| Ver fila mensagens | GET | `/clinics/{clinicId}/queue` |
