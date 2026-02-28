# Design: AI Conversation Engine (Fluxo Natural com LLM)

**Data:** 2026-02-28
**Status:** Aprovado
**Escopo:** scheduler/

---

## 1. Problema

O fluxo atual do scheduler é uma state machine determinística com 24 estados fixos. O usuário deve seguir uma sequência rígida de passos (menus, botões, números) para agendar. Qualquer resposta fora do padrão cai em `UNRECOGNIZED` e re-exibe os mesmos botões, causando abandono.

**Sintomas observados:**
- Usuários desistem no meio da conversa
- Input parsing frágil — espera números, palavras exatas ou cliques em botões
- FAQ é puramente menu-driven, sem busca semântica
- Sem memória entre conversas
- Zero inteligência artificial no scheduler

## 2. Solução

**Abordagem: AI Agent com Tools (Híbrido)**

Novo `AIConversationEngine` paralelo ao engine atual, roteado por flag `use_ai_flow` na tabela `clinics`. Usa GPT-4o-mini via function calling para:

- **Interpretar** mensagens em linguagem natural (intent + entidades)
- **Gerar** respostas personalizadas e naturais
- **Orquestrar** o fluxo via tools (consulta DB, disponibilidade, agendamento)
- **Apresentar** opções estruturadas com botões do WhatsApp

O LLM nunca inventa dados — só apresenta o que as tools retornam.

## 3. Arquitetura

```
Usuário (WhatsApp)
    │
    ▼
[Webhook Handler] ── mesma entry point atual
    │
    ▼
[Clinic Flag Check] ── use_ai_flow = true?
    │                         │
    │ false                   │ true
    ▼                         ▼
[ConversationEngine]    [AIConversationEngine]
(fluxo atual, intacto)  (novo fluxo com LLM)
    │                         │
    │                         ▼
    │                   [OpenAI GPT-4o-mini]
    │                   ── system prompt dinâmico
    │                   ── tools (function calling)
    │                   ── histórico de mensagens
    │                         │
    │                         ▼
    │                   [Tool Executor]
    │                   ── executa tools (DB, availability, booking)
    │                   ── retorna resultado para LLM
    │                   ── LLM gera resposta natural + botões
    │                         │
    ├─────────────────────────┤
    ▼                         ▼
[WhatsApp Provider] ── envia resposta (mesma interface)
```

### O que NÃO muda
- Webhook handler (só adiciona roteamento por flag)
- WhatsApp provider (mesma interface de envio)
- Serviços de domínio (AvailabilityEngine, AppointmentService, etc.)
- DynamoDB session (mesma tabela, estrutura adaptada)
- Human handoff (mesmo mecanismo)

### Componentes novos
1. **`AIConversationEngine`** — `scheduler/src/services/ai_conversation_engine.py`
2. **`OpenAIService`** — `scheduler/src/services/openai_service.py` (client GPT-4o-mini com function calling)
3. **`AITools`** — `scheduler/src/services/ai_tools.py` (definições de tools + executors)
4. **Flag `use_ai_flow`** na tabela `scheduler.clinics`
5. **Campo `display_name`** na tabela `scheduler.clinics`

## 4. Sessão e Histórico

A sessão DynamoDB muda de "acumulador de estados" para "memória da conversa":

```json
{
  "pk": "CLINIC#laser-beauty-sp",
  "sk": "PHONE#5511999999999",
  "session": {
    "conversation_history": [
      {"role": "user", "content": "oi, quero agendar"},
      {"role": "assistant", "content": "Olá! Que bom..."},
      {"role": "user", "content": "quero depilar perna sexta"}
    ],
    "collected_data": {
      "service_ids": ["uuid1"],
      "service_names": ["Depilação a Laser"],
      "area_ids": ["uuid2"],
      "area_names": ["Perna completa"],
      "date": null,
      "time": null,
      "full_name": "Maria Silva",
      "total_price_cents": null
    },
    "patient_name": "Maria Silva",
    "pending_confirmation": null,
    "turn_count": 3
  },
  "clinicId": "laser-beauty-sp",
  "phone": "5511999999999",
  "updatedAt": "2026-02-28T12:00:00Z"
}
```

- **`conversation_history`**: janela deslizante de últimas 20 mensagens
- **`collected_data`**: dados estruturados confirmados (injetados no system prompt a cada turno)
- **`turn_count`**: contador de turnos (safeguard: após 30 turnos → human handoff)
- **TTL**: mantém 30min de inatividade

## 5. Tools (Function Calling)

### Tools de consulta (read-only)

| Tool | Parâmetros | Retorno | Serviço existente |
|---|---|---|---|
| `list_services` | `clinic_id` | Serviços com nome, descrição, preço base + flag `single_service` | PostgreSQL `scheduler.services` |
| `list_areas` | `clinic_id, service_ids[]` | Áreas disponíveis com preços | PostgreSQL `scheduler.service_areas` |
| `check_availability` | `clinic_id, service_area_pairs[], preferred_date?` | Dias disponíveis (próximos 14 dias) | `AvailabilityEngine` |
| `get_time_slots` | `clinic_id, service_area_pairs[], date` | Horários disponíveis no dia | `AvailabilityEngine` |
| `lookup_appointments` | `clinic_id, phone` | Agendamentos ativos do paciente | `AppointmentService` |
| `get_faq_answer` | `clinic_id, question` | Busca nos faq_items + resposta | PostgreSQL `scheduler.faq_items` |
| `get_clinic_info` | `clinic_id` | Nome, endereço, telefone, horário | PostgreSQL `scheduler.clinics` |

### Tools de ação (write)

| Tool | Parâmetros | Retorno | Serviço existente |
|---|---|---|---|
| `book_appointment` | `clinic_id, phone, full_name, service_area_pairs[], date, time` | Confirmação com ID + detalhes | `AppointmentService.create` |
| `reschedule_appointment` | `appointment_id, new_date, new_time` | Confirmação da remarcação | `AppointmentService.reschedule` |
| `cancel_appointment` | `appointment_id` | Confirmação do cancelamento | `AppointmentService.cancel` |
| `request_human_handoff` | `clinic_id, phone, reason` | Ativa handoff (24h TTL) | Session update |

### Tool especial: `present_options`

Sinaliza ao sistema que a resposta deve incluir botões do WhatsApp:

```json
{
  "name": "present_options",
  "parameters": {
    "message": "Para depilação a laser na perna completa, temos esses horários:",
    "options": [
      {"id": "slot_0900", "label": "09:00"},
      {"id": "slot_1030", "label": "10:30"},
      {"id": "slot_1400", "label": "14:00"}
    ]
  }
}
```

### Regras de segurança nas tools
- `book_appointment` exige que `check_availability` tenha sido chamada previamente (validação server-side)
- `reschedule/cancel` exigem que `lookup_appointments` tenha retornado o appointment_id
- Preços são SEMPRE calculados server-side
- Todas as tools de ação logam no DynamoDB para auditoria

## 6. System Prompt

Montado dinamicamente por conversa com dados da clínica:

```
Você é a assistente virtual da {{clinic_display_name}}, especializada em
agendamento de sessões. Seu objetivo é ajudar o cliente de forma simpática,
objetiva e eficiente, sempre buscando converter a conversa em um agendamento.

IDENTIDADE:
- Clínica: {{clinic_display_name}}
- Endereço: {{clinic_address}}
- Horário de funcionamento: {{clinic_hours}}
- WhatsApp: {{clinic_phone}}

DADOS JÁ COLETADOS NESTA CONVERSA:
{{collected_data_summary}}

CONTEXTO DA CLÍNICA:
- Serviços disponíveis: {{services_count}}
{{#if single_service}}
- ATENÇÃO: Esta clínica oferece APENAS o serviço "{{single_service_name}}".
  NÃO pergunte qual serviço o cliente deseja. Assuma este serviço
  automaticamente e vá direto para a escolha de áreas.
{{/if}}

REGRAS ABSOLUTAS:
1. NUNCA invente preços, horários, datas ou serviços — use APENAS dados
   retornados pelas tools
2. NUNCA confirme um agendamento sem chamar book_appointment
3. Quando mostrar opções (serviços, áreas, datas, horários), SEMPRE use
   present_options para gerar botões
4. SEMPRE liste TODAS as opções retornadas — não omita nenhuma
5. Preços são sempre calculados pelas tools, NUNCA calcule você mesma
6. Se o cliente perguntar algo que você não sabe, use get_faq_answer.
   Se ainda não souber, ofereça request_human_handoff
7. Se o cliente pedir para falar com humano, chame request_human_handoff
   imediatamente
8. Se após 2 tentativas você NÃO conseguir entender o que o cliente quer,
   chame request_human_handoff com reason="incompreensão" e responda:
   "Desculpe, não consegui entender sua solicitação. Vou te transferir
   para um atendente que poderá te ajudar melhor. Aguarde um momento! 😊"
9. Se a clínica tem apenas 1 serviço, NUNCA pergunte qual serviço.
   Pule direto para a seleção de áreas chamando list_areas com o serviço único.

COMPORTAMENTO:
- Seja simpática mas concisa — mensagens curtas, diretas
- Tente sempre direcionar a conversa para agendamento
- Se o cliente mandou informação ambígua, pergunte para confirmar
- Se o cliente informar múltiplos dados de uma vez
  (ex: "quero depilar perna sexta de manhã"), processe TUDO e avance o
  máximo possível no fluxo
- Use emojis com moderação (máx 1-2 por mensagem)
- Responda SEMPRE em português brasileiro

FLUXO TÍPICO (guia, não regra rígida):
1. Saudação → perguntar o que deseja
2. Identificar serviço → list_services (skip se serviço único)
3. Identificar áreas → list_areas
4. Verificar disponibilidade → check_availability + get_time_slots
5. Coletar nome completo (se não tiver)
6. Mostrar resumo → pedir confirmação
7. Agendar → book_appointment
```

**Personalização por clínica:**
- System prompt base é configurável via tabela `message_templates` (chave `AI_SYSTEM_PROMPT`)
- Se existir override na DB, substitui o prompt padrão
- Variáveis `{{...}}` são sempre injetadas dinamicamente pelo sistema

## 7. Custo e Limites

### Custo por volume (GPT-4o-mini)

| Volume mensal | Custo USD | Custo BRL (~5.0) |
|---|---|---|
| 100 conversas | ~$0.30 | ~R$ 1,50 |
| 1.000 conversas | ~$3.00 | ~R$ 15 |
| 10.000 conversas | ~$30.00 | ~R$ 150 |
| 50.000 conversas | ~$150.00 | ~R$ 750 |

### Composição por chamada
- System prompt + tools: ~1.200 tokens
- Histórico (20 msgs): ~1.000 tokens
- Resposta: ~100-300 tokens
- Total: ~2.500-3.000 tokens por turno (~2% do context window de 128K)

### Safeguards
- Janela deslizante de 20 mensagens (tokens nunca estouram)
- `collected_data` preservado no system prompt mesmo quando mensagens saem da janela
- Limite de 30 turnos por conversa → human handoff automático
- Log de tokens consumidos por conversa no DynamoDB
- Fallback: se API falhar (timeout/erro), responde com mensagem padrão + botões do engine atual

### Latência
- GPT-4o-mini: ~500-800ms por chamada
- Tool execution: ~100-200ms
- Total: ~1-1.5s por mensagem
- Envio de "typing indicator" via z-api enquanto processa

## 8. Migração de Banco

### Nova coluna na tabela clinics

```sql
-- Migration: add display_name and use_ai_flow to clinics
ALTER TABLE scheduler.clinics
ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);

ALTER TABLE scheduler.clinics
ADD COLUMN IF NOT EXISTS use_ai_flow BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN scheduler.clinics.display_name IS
  'Nome fantasia da clínica (exibido para o paciente). Fallback: campo name';
COMMENT ON COLUMN scheduler.clinics.use_ai_flow IS
  'Se true, usa AIConversationEngine ao invés do fluxo determinístico';
```

Lógica no código:
```python
clinic_display_name = clinic.get('display_name') or clinic.get('name')
```

### SSM Parameter

```
/${stage}/OPENAI_API_KEY  ← já existe no projeto infra, pode ser compartilhado
```

## 9. Rollout

1. **Fase 1**: Deploy com `use_ai_flow = false` para todas as clínicas (sem impacto)
2. **Fase 2**: Ativar para 1 clínica de teste, validar por 1 semana
3. **Fase 3**: Ativar gradualmente para demais clínicas
4. **Rollback**: `UPDATE scheduler.clinics SET use_ai_flow = false WHERE clinic_id = 'X'` → instantâneo

## 10. Trade-offs

| Aspecto | Fluxo Atual | Fluxo AI |
|---|---|---|
| **UX** | Rígido, menus fixos | Natural, fluido |
| **Conversão** | Usuários desistem | LLM guia para agendamento |
| **FAQ** | Menu-driven | Busca semântica |
| **Custo** | Zero (sem LLM) | ~R$15/mês p/ 1k conversas |
| **Latência** | Instantâneo | +1-1.5s por msg |
| **Manutenção** | Templates manuais | Prompt engineering |
| **Debug** | State machine previsível | Logs de conversa + tools |
| **Risco** | Zero alucinação | Mitigado por tools + validação |
| **Rollback** | N/A | Flag por clínica, instantâneo |
