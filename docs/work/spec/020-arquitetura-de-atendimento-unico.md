# Spec — 020 Um agente só, com três dimensões separadas

> Gerado na fase **Spec**, a partir de `docs/work/prd/020-arquitetura-de-atendimento-unico.md`.
> Cada fase do §8 do PRD é um PR. Nenhuma fase depende de a seguinte existir.

---

## 1. A forma da mudança

Hoje `session["state"]` carrega três coisas numa string. A Spec separa em três
campos que nunca se leem entre si, e põe uma **porta** na frente do agente que é
a única que decide se ele fala:

```
webhook / cron / painel
   └─ porta de atendimento (atendimento.py)   <- determinística, sem LLM
        ├─ pode_responder(clinic, session, phone)
        └─ pode_iniciar(clinic, session, phone, agora)
             └─ estado comercial (estado_comercial.py)  <- derivado de appointments
                  └─ Router (roteador.py)  intenção × estado -> skill + tools
                       └─ ConversationAgent  <- só redige
```

O agente deixa de ter opinião sobre atender ou não: `_is_attendant_active` sai
dele na fase 3. Quem o chama já passou pela porta.

### 1.1 Nomes que já existem e colidem

`elegibilidade_do_bot.pode_iniciar(lead, clinic)` já existe e responde outra
pergunta: *este lead pode ser abordado pelo botão do painel?* Ela continua, e
passa a **chamar** a nova `atendimento.pode_iniciar` como última guarda, no
lugar do `should_bot_reply` que chama hoje. Dois nomes iguais em módulos
distintos com a mesma semântica de "iniciar" é aceitável; dois com semânticas
diferentes não seria, e é por isso que a de lead não é renomeada para algo
vago.

### 1.2 O que é fato e o que é cache

| dado | onde mora | natureza |
|---|---|---|
| estado comercial | `scheduler.appointments` | **derivado** a cada mensagem, nunca gravado |
| estado de atendimento | `session["atendimento"]` | **gravado**, com transições condicionais |
| estado da conversa | `session["conversa"]` | gravado, dono é o Router |
| bloco `cliente` | montado por requisição | cache de requisição, não entra na sessão |

---

## 2. Arquivos, por fase

### Fase 1 — correção do cadastro

| arquivo | ação |
|---|---|
| `scheduler/src/services/identificacao_de_paciente.py` | **criar** |
| `scheduler/src/services/ai_tools.py` | modificar: tool `identificar_paciente`, contrato de `book_appointment`, guarda no executor |
| `scheduler/src/services/roteador.py` | modificar: pré-carga de `identificar_paciente` |
| `scheduler/src/services/conversation_agent.py` | modificar: `pede_cadastro` vale fora da campanha |
| `scheduler/tests/unit/test_identificacao_de_paciente.py` | criar |
| `scheduler/tests/unit/test_cadastro_pelo_bot.py` | modificar: caso da Yasmin |

### Fase 2 — porta de atendimento, cooldown, TTL por inatividade, janela de silêncio

| arquivo | ação |
|---|---|
| `scheduler/src/services/atendimento.py` | **criar**: a máquina e as duas perguntas |
| `scheduler/src/services/bot_policy.py` | modificar: `should_bot_reply` vira alias de `pode_responder` |
| `scheduler/src/services/business_hours.py` | modificar: `janela_de_silencio`, fuso da clínica |
| `scheduler/src/services/reminder_service.py` | modificar: fuso no `send_at` |
| `scheduler/src/functions/reminder/processor.py` | modificar: `pode_iniciar(transacional=True)`, cancelado não vai |
| `scheduler/src/functions/outbound/processor.py` | modificar: `pode_iniciar` no lugar de `bot_paused + should_bot_reply + is_open` |
| `scheduler/src/functions/send/handler.py` | modificar: `pode_iniciar` antes de enviar |
| `scheduler/src/services/conversation_resume.py` | modificar: `pode_iniciar` antes de `falar` |
| `scheduler/src/functions/webhook/handler.py` | modificar: `pode_responder`; renovação do TTL só pela clínica |
| `scheduler/src/functions/attendant/handler.py`, `list_active.py` | modificar: leem `atendimento` |
| `scheduler/src/services/status_da_conversa.py` | modificar: rótulo sai de `handler` |
| `scheduler/src/scripts/setup_database.py` | modificar: `clinics.janela_de_silencio`, `clinics.idade_maxima_da_pendencia_horas` |
| `scheduler/tests/unit/test_atendimento.py` | criar |
| `scheduler/tests/unit/test_business_hours.py`, `test_bot_policy.py`, `test_conversation_resume.py` | modificar |
| `scheduler/tests/unit/test_lembrete_no_fuso.py` | criar |

### Fase 3 — `handler` explícito, pendência, tarefa humana, retomada por vencimento

| arquivo | ação |
|---|---|
| `scheduler/src/services/atendimento.py` | modificar: `HUMAN_PENDING`, pendência, `avalia_vencimento` |
| `scheduler/src/services/retomada.py` | **criar**: as seis guardas + classificação fechada |
| `scheduler/src/functions/atendimento/expira.py` | **criar**: Lambda `ExpiraAtendimentos`, rate(60 minutes) |
| `scheduler/sls/functions/atendimento/interface.yml` | criar |
| `scheduler/sls/resources/dynamodb/conversation-sessions-table.yml` | modificar: GSI `handler-humanUntil-index` |
| `scheduler/src/scripts/setup_database.py` | modificar: tabela `scheduler.tarefas` |
| `scheduler/src/functions/tarefa/{list,close}.py` + `interface.yml` | criar |
| `scheduler/src/services/conversation_agent.py` | modificar: remove `_is_attendant_active`; `events_to_history` rotula humano |
| `scheduler/src/functions/webhook/handler.py` | modificar: `metadata.autor = "HUMANO"` no fromMe |
| `scheduler/src/services/bot_policy.py` | modificar: remove `PAUSAS_PERMANENTES` (decisão 9.1) |
| `frontend/src/pages/bot/*`, `frontend/src/services/bot.service.ts` | modificar: fila mostra `handler` e tarefas |
| `scheduler/tests/unit/test_retomada.py`, `test_expira_atendimentos.py` | criar |

### Fase 4 — estado comercial e `identificar_paciente` no Router

| arquivo | ação |
|---|---|
| `scheduler/src/services/estado_comercial.py` | **criar** |
| `scheduler/src/services/roteador.py` | modificar: recebe estado comercial |
| `scheduler/src/services/conversation_agent.py` | modificar: bloco `cliente` montado por requisição |
| `scheduler/src/scripts/setup_database.py` | modificar: índice em `appointments` (a coluna `janela_de_retorno_dias` entrou em 09/10 e saiu no mesmo dia, ver §3.15) |
| `scheduler/tests/unit/test_estado_comercial.py` | criar |

### Fase 5 — níveis 1/2/3

| arquivo | ação |
|---|---|
| `scheduler/src/services/nivel_de_risco.py` | **criar**: termos do nível 3, `detecta(texto, clinic)` |
| `scheduler/src/services/policy_do_faq.py` | **criar**: itens do FAQ da clínica, definição da tool com `enum`, montagem das bolhas |
| `scheduler/src/services/bot_policy.py` | modificar: motivos do nível 3 + texto legível; `TEXTO_DE_RISCO` |
| `scheduler/src/services/ai_tools.py` | modificar: tool `responder_com_faq` substitui `get_faq_answer`; `get_tool_definitions(format, faq=None)` |
| `scheduler/src/services/conversation_agent.py` | modificar: guarda do nível 3 antes do modelo (ao lado de `fora_do_escopo`); bolhas do FAQ separadas do texto do modelo em `_build_outgoing` |
| `scheduler/tests/unit/test_nivel_de_risco.py`, `test_policy_do_faq.py`, `test_niveis_no_agente.py` | criar |

Sem migration, sem mudança no painel: **todo item do FAQ é literal** (decisão
de 10/10/2026). Ordem: 1) FAQ literal no agente; 2) nível 3. Cada passo é
deployável sozinho; o nível 3 entra por último porque é o que mais tira
conversa do bot.

### Fase 6 — desambiguação com contador

| arquivo | ação |
|---|---|
| `scheduler/src/services/desambiguacao.py` | **criar** |
| `scheduler/src/services/conversation_agent.py` | modificar |
| `scheduler/tests/unit/test_desambiguacao.py` | criar |

### Fase 7 — skills e Router despachando

| arquivo | ação |
|---|---|
| `scheduler/src/services/skills/__init__.py` | **criar**: três skills por estado comercial (ver §3.19; a lista por intenção caiu) |
| `scheduler/src/services/roteador.py` | modificar: `despacha()` |
| `scheduler/src/services/conversation_agent.py` | modificar: tools filtradas pela skill; bloco da skill no prompt |
| `scheduler/tests/unit/test_skills.py` | criar |

### Fase 8 — apagar o engine legado

| arquivo | ação |
|---|---|
| `scheduler/src/services/conversation_engine.py` | **remover** |
| `scheduler/src/services/intent_classifier.py` | remover (só o engine usa) |
| `scheduler/src/services/openai_service.py` | remover **se** nenhum outro caminho importar |
| `scheduler/src/functions/webhook/handler.py` | modificar: `_executar_engine` só monta o agente |
| `scheduler/src/functions/attendant/handler.py` | modificar: sem `ConversationState` |
| `scheduler/tests/unit/test_conversation_engine.py` | remover |

---

## 3. Detalhes por arquivo

### 3.1 `services/identificacao_de_paciente.py` (fase 1)

```python
def identificar(db, clinic_id, phone) -> dict
```

Consulta `scheduler.patients` com `phone = ANY(variantes_do_numero(phone))` e
`deleted_at IS NULL`, mais um agregado de `appointments` (`COUNT` com
`status = 'CONFIRMED' AND appointment_date < CURRENT_DATE`, `MAX` dessa data,
e o próximo `CONFIRMED` futuro). Devolve:

```json
{"encontrado": true, "patient_id": "...", "nome": "...",
 "cadastro_completo": true, "sessoes_feitas": 3, "ultima_sessao": "2026-09-12",
 "agendamento_futuro": {"id": "...", "data": "...", "hora": "..."} | null}
```

- `cadastro_completo` = `name`, `birth_date`, `cpf` e `email` todos não nulos.
  É a mesma régua de `utils/cadastro.py`; importar de lá, não copiar.
- **Mais de uma linha** (variantes diferentes do número apontando para
  pacientes diferentes): devolve `{"encontrado": false, "ambiguo": true,
  "candidatos": [nomes]}`. O executor trata `ambiguo` como "pergunte quem é",
  nunca como identificado. `UNIQUE(clinic_id, phone)` protege o caso simples,
  não as variantes.
- Não devolve CPF, e-mail nem data de nascimento: o bot não precisa ver o dado
  para saber que ele existe (ver `test_bot_nao_ve_prontuario`).

### 3.2 `services/ai_tools.py` (fase 1)

- Tool `identificar_paciente` sem argumentos; o executor chama 3.1.
- `book_appointment`: `full_name` sai de `required`. A descrição passa a dizer:
  *"Se `identificar_paciente` devolveu `cadastro_completo: true`, não peça
  nome, CPF, nascimento nem e-mail - já estão no cadastro."*
- `_tool_book_appointment`: sem `full_name`, usa o nome do paciente
  identificado; sem paciente e sem nome, erro como hoje.
- **Guarda no executor:** o resultado de `identificar_paciente` fica em
  `ctx["paciente"]`. `pede_cadastro(texto)` (hoje só em campanha) passa a rodar
  sempre que `ctx["paciente"]["cadastro_completo"]` for `True`. Mesma trava de
  PARE uma vez, mesmo bloqueio final com `MOTIVO_INSISTIU_CADASTRO`.

### 3.3 `services/roteador.py` (fase 1, depois fase 4 e 7)

- Fase 1: `TOOLS_POR_INTENCAO[AGENDAMENTO_PROPRIO]` e `[DISPONIBILIDADE]` ganham
  `identificar_paciente` **na frente**. Pré-carga é por ordem; a identidade
  tem de chegar antes de `lookup_appointments` para o modelo ler as duas juntas.
- Fase 4: `tools_obrigatorias(intencoes, estado_comercial)`. Para
  `NEW_LEAD` a pré-carga de `identificar_paciente` é dispensável (já se sabe
  que não há cadastro), mas fica: custa uma consulta e elimina um ramo.
- Fase 7: `despacha(intencao, estado_comercial) -> Skill`. Tabela do PRD §6
  como dict; par sem skill cai em `duvidas` (nunca em `primeiro_agendamento`).

### 3.4 `services/atendimento.py` (fase 2, estendido na 3)

> **Entregue em 06/10/2026 (fase 2).** Diferenças em relação ao texto abaixo:
> `estado()` deriva `COOLDOWN` direto do vencimento de `human_until` (sem
> `HUMAN_EXPIRED` materializado - ele só vai existir quando a avaliação da
> fase 3 precisar dele); `HUMAN_PENDING` é reconhecido mas nenhuma transição
> o produz ainda; `grava_atendimento` grava só o bloco e a projeção legada,
> condicionado à versão, e em conflito descarta a transição com log em vez de
> reaplicar; os campos legados continuam escritos como projeção para o
> painel. `elegibilidade_do_bot` usa `pode_responder`, não `pode_iniciar`: o
> botão enfileira para a próxima abertura, e a janela de silêncio de agora não
> é motivo para desabilitá-lo.


Módulo puro, sem I/O, como `bot_policy`. É a única fonte das duas perguntas.

```python
BOT_ACTIVE, HUMAN_ACTIVE, HUMAN_EXPIRED, HUMAN_PENDING, COOLDOWN = ...
CAMPO = "atendimento"

def estado(session, agora) -> str
    # efetivo: HUMAN_ACTIVE com human_until vencido devolve HUMAN_EXPIRED;
    # COOLDOWN com cooldown_until vencido devolve BOT_ACTIVE. Nunca grava.

def pode_responder(clinic, session, phone, agora=None) -> bool
def pode_iniciar(clinic, session, phone, agora=None, *, transacional=False) -> bool

def entrega_a_humano(session, agora, *, motivo, por, pending_intent=None) -> session
def renova_por_mensagem_da_clinica(session, agora) -> session
def registra_fala_do_cliente(session, agora) -> session       # NÃO renova
def retoma_pelo_painel(session) -> session                     # limpa tudo
def avalia_vencimento(session, agora) -> (session, acao)       # fase 3
```

`pode_responder`, na ordem:

1. `clinic.bot_paused` -> não.
2. `estado(session) in (HUMAN_ACTIVE, HUMAN_PENDING)` -> não.
3. política da clínica (`ALL`, `PILOT`, `LEADS_ONLY`, `OFF`), **copiada** de
   `should_bot_reply` com `bot_enabled` e campanha. Nesta fase `bot_enabled`
   continua; sai na fase 4 (PRD §9.2).

`pode_iniciar`, na ordem:

1. tudo de `pode_responder`.
2. `estado(session) == COOLDOWN` -> não (exceto `transacional=True`).
3. `business_hours.em_silencio(clinic, agora)` -> não. **Sempre**, inclusive
   transacional.

`transacional=True` é o lembrete de 24h e nada mais. Documentar no docstring
que ele existe para **uma** chamada; um segundo chamador é cheiro de que a
mensagem não é transacional.

Bloco gravado em `session["atendimento"]`:

```json
{"handler": "HUMAN_ACTIVE", "human_until": 1759700000, "cooldown_until": null,
 "pausado_por": "ATENDENTE", "handoff_reason": null,
 "pending_intent": null, "pending_task_id": null, "pending_since": null,
 "ultima_fala_cliente_em": 1759690000, "retomada_em": null, "versao": 7}
```

Epoch UTC em todos os instantes. `pausado_por` absorve `bot_pausado_por`
(`ATENDENTE`, `HANDOFF`, `INSTABILIDADE`, `CONTATO_MANUAL`, `CHAT_ANTERIOR`);
os cinco viram `HUMAN_ACTIVE` com `human_until`. `PAUSAS_PERMANENTES` deixa de
existir na fase 3 (decisão 9.1). `INSTABILIDADE` entra como
`entrega_a_humano(motivo=MOTIVO_INSTABILIDADE, por="INSTABILIDADE")`:
`entrega_por_instabilidade` de `bot_policy` passa a delegar aqui.

**Escrita condicional.** `versao` sobe a cada transição, e quem grava usa
`ConditionExpression: session.atendimento.versao = :esperada`. Duas Lambdas
escrevem a mesma sessão (processamento assíncrono do webhook e
`ExpiraAtendimentos`); sem isso `COOLDOWN` sobrescreve `HUMAN_ACTIVE` em
silêncio. Em `ConditionalCheckFailedException`: reler, reaplicar a transição
uma vez, desistir com log `ERROR`. Helper `grava_atendimento(table, clinic_id,
phone, session)` em `session_store.py`, ao lado de `mark_conversation_eligible`.

**Compatibilidade na leitura.** Durante a fase 2, sessão sem o bloco
`atendimento` é lida por `migra_do_legado(session)`: `attendant_active_until`
vira `human_until`, `bot_pausado_por` vira `pausado_por` com `handler =
HUMAN_ACTIVE`. Pura, chamada por `estado()`. Nenhum script de migração em
massa: a sessão migra quando é lida, e as que nunca mais forem lidas não
importam.

### 3.5 `services/bot_policy.py` (fase 2 e 3)

- Fase 2: `should_bot_reply = pode_responder` com `DeprecationWarning` no
  docstring e nenhum chamador novo. `esta_pausado` idem, delegando a
  `estado() in (HUMAN_ACTIVE, HUMAN_PENDING)`.
- Fase 3: remove `should_bot_reply`, `esta_pausado`, `PAUSAS_PERMANENTES`,
  `TTL_DO_ATENDIMENTO` (vai para `atendimento.TTL_HUMANO`). Ficam os motivos
  (`MOTIVOS_LEGIVEIS` etc.), que são vocabulário, não política.

### 3.6 `services/business_hours.py` (fase 2)

```python
def fuso(clinic) -> tzinfo                         # clinics.timezone, default CLINIC_TZ
def em_silencio(clinic, agora_utc) -> bool
def fim_do_silencio(clinic, agora_utc) -> datetime  # próximo instante fora da janela
```

`janela_de_silencio` vem de `clinics.janela_de_silencio` (JSONB
`{"start": "22:59", "end": "04:59"}`), default no código quando `NULL`. A
janela cruza a meia-noite: `em_silencio` é `hora >= start or hora < end`
quando `start > end`. Inclusiva no início, exclusiva no fim, como `is_open`:
22:59:00 está em silêncio, 04:59:00 está fora.

`CLINIC_TZ` deixa de ser constante usada direto por `outbound_queue` e
`outbound/processor`; passa por `fuso(clinic)`. Hoje uma clínica fora de
Brasília já teria o horário comercial errado.

### 3.7 `services/reminder_service.py` e `functions/reminder/processor.py` (feito antes da fase 2)

**O lembrete nunca foi ligado** (ver PRD §3.5, correção de 06/10/2026). O
código latente foi corrigido em PR próprio, antes da fase 2:

- `schedule_reminder(appointment, clinic)` monta a sessão com `fuso(clinic)` e
  grava `sendAt` em UTC. `AppointmentService._fuso_da_clinica` lê o `timezone`.
- `business_hours.em_silencio` / `fim_do_silencio` / `fuso` já existem, com a
  janela padrão `SILENCIO_PADRAO` e leitura de `clinics.janela_de_silencio`
  quando a coluna existir (fase 2 a cria).
- Processador: sessão não `CONFIRMED` -> `mark_failed("agendamento_nao_confirmado")`;
  janela de silêncio -> `ReminderService.adia(pk, sk, novo_send_at, motivo)`,
  que só move o atributo `sendAt` (o índice lê o atributo; o `sk` não é
  consultado por ninguém).

O que **fica** para a fase 2 neste arquivo: trocar a conferência de janela por
`pode_iniciar(clinic, session, phone, transacional=True)`, que acrescenta
`bot_paused` e política. Ligar o lembrete não é desta Spec.

### 3.8 `functions/outbound/processor.py` e `functions/send/handler.py` (fase 2)

- Processor: as três guardas (`bot_paused`, `should_bot_reply`, `is_open`)
  viram `pode_iniciar(clinic, sessao_real, phone)` seguido de
  `is_open(...)`. A janela de silêncio e o horário comercial são regras
  distintas: a primeira é da plataforma, a segunda da clínica.
- `/send`: antes de `provider.send_text`, `pode_iniciar(clinic, sessao,
  phone)`; recusa com 409 e `{"motivo": "janela_de_silencio" | "cooldown" |
  "atendimento_humano"}`. Campanha em massa às 23h não sai.

### 3.9 `functions/webhook/handler.py` (fase 2 e 3)

- Linha 337: `pode_responder(clinic, session, incoming.phone)`.
- Mensagem do cliente com `estado == HUMAN_ACTIVE`: `registra_fala_do_cliente`
  e grava. **Não** renova `human_until`.
- Ramo `fromMe` humano: `_activate_attendant_mode` vira
  `renova_por_mensagem_da_clinica` quando já é `HUMAN_ACTIVE`, ou
  `entrega_a_humano(por="ATENDENTE")` quando não é. O `track_outbound` da
  mensagem humana passa `metadata={"autor": "HUMANO"}` (fase 3).
- Primeira vez com `whatsapp_chats` existente (`CHAT_ANTERIOR`) e lead com
  `first_contact_channel = HUMANO` (`CONTATO_MANUAL`): `entrega_a_humano` com
  `human_until` a partir da última mensagem conhecida no espelho
  (`whatsapp_chats.last_message_at`, ou agora se ausente). Vence como qualquer
  outra (9.1).

### 3.10 `services/conversation_resume.py` e `functions/attendant/handler.py` (fase 2 e 3)

- Fase 2: `responder_se_ficou_em_aberto` chama `pode_iniciar` antes de
  `falar`. Hoje não confere `bot_paused` nem política.
- Fase 3: o guard inteiro sai daqui e passa a ser `retomada.pode_retomar`
  (3.12). `_agendar_retomada` do painel chama a mesma função. Um só lugar
  decide se há o que responder.
- "Retomar bot" vira `retoma_pelo_painel(session)` + `grava_atendimento`.
  `bot_enabled = True` continua até a fase 4.

### 3.11 `functions/atendimento/expira.py` (fase 3)

Lambda `ExpiraAtendimentos`, `rate(60 minutes)` (era 10; o André pediu 60 em 08/10/2026: o cron vazio custa centavos e a espera extra é aceitável), mesmo padrão de
`outbound/processor`:

1. `query` no GSI `handler-humanUntil-index` com `handler = HUMAN_ACTIVE AND
   humanUntil <= agora`, limite 50 por execução.
2. Para cada: `avalia_vencimento(session, agora)` devolve `(session, acao)`
   com `acao in {"pendente", "retomar", "calar"}`.
3. `pendente` -> `HUMAN_PENDING`, cria tarefa (3.13), alerta na fila.
4. `retomar` -> `retomada.responder(...)` (3.12); independente do resultado,
   `COOLDOWN` e `retomada_em = agora`.
5. `calar` -> `COOLDOWN`; se a última fala era do cliente, alerta na fila com
   motivo `sem_resposta_humana`.
6. `grava_atendimento` condicional; conflito pula o item, a próxima execução
   o pega.

Os atributos `handler` e `humanUntil` vão na **raiz** do item (a GSI não
indexa caminho aninhado); `grava_atendimento` os espelha a partir de
`session.atendimento`. Documentar no `session_store` que são cópia e que a
sessão é a fonte.

Custo de CloudFormation: 1 Lambda + role + log group + regra de evento, cerca
de 6 recursos. O stack está em 440/500 (ver memória "limite do
CloudFormation"); cabe, mas registrar em `KANBAN.md`.

### 3.12 `services/retomada.py` (fase 3)

```python
IDADE_MAXIMA_PADRAO_HORAS = 72

def pode_retomar(session, eventos, efeitos_depois, clinic, agora) -> (bool, motivo)
def classifica(anthropic, historico) -> {"pendente": bool, "o_que": str}
def responder(clinic_id, phone, *, db, provider, tracker) -> bool
```

`pode_retomar` aplica as seis guardas do PRD §3.7 **nesta ordem**, e devolve o
motivo da primeira que falhar (vira log e rótulo na fila):

| guarda | fonte | motivo |
|---|---|---|
| última fala é do cliente | `eventos` (MessageEvents, 20 últimos) | `ultima_fala_nao_e_do_cliente` |
| não é fecho social | `roteador.SOCIAL` | `fecho_social` |
| idade <= `clinics.idade_maxima_da_pendencia_horas` | `eventos[-1].sk` | `pendencia_velha` |
| nenhum efeito depois | `appointments.updated_at > fala` (consulta própria) | `resolvido_fora` |
| `retomada_em is None` | sessão | `ja_retomado` |
| `pode_iniciar` | `atendimento` | `porta_fechada` |

`classifica` é **uma** chamada sem tools, `max_tokens=80`, saída JSON com
schema fechado. Qualquer parse falho é `pendente: False`. Prompt diz que a
pergunta pode ter mais de 24h e que datas relativas nela não valem mais.

`responder` usa `agent_runner.falar` com gatilho `__RETOMAR_CONVERSA__` e um
bloco a mais no turno do usuário:

```
═══ RETOMADA ═══
A última mensagem desta pessoa ficou sem resposta há {horas}h. Reconheça o
atraso em uma frase. Se ela mencionou data relativa ("amanhã", "sábado"),
NÃO a resolva: pergunte a data de novo. O que ela perguntou: {o_que}.
```

### 3.13 Tarefa humana (fase 3)

Tabela nova em `setup_database.py`, idempotente:

```sql
CREATE TABLE IF NOT EXISTS scheduler.tarefas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    phone VARCHAR(20) NOT NULL,
    intent VARCHAR(40) NOT NULL,
    motivo VARCHAR(40) NOT NULL,
    status VARCHAR(10) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'CLOSED')),
    aberta_em TIMESTAMPTZ DEFAULT NOW(),
    fechada_em TIMESTAMPTZ,
    fechada_por VARCHAR(100)
);
CREATE INDEX IF NOT EXISTS idx_tarefas_abertas ON scheduler.tarefas (clinic_id) WHERE status = 'OPEN';
```

Endpoints `GET /clinics/{id}/tarefas` e `POST /clinics/{id}/tarefas/{id}/close`.
Fechar a tarefa chama `atendimento` para `HUMAN_PENDING -> COOLDOWN` e limpa
`pending_*`. A fila do painel (`pages/bot`) ganha a coluna "tarefa aberta" e o
botão de fechar; sem isso `HUMAN_PENDING` é conversa esquecida (PRD §9.4).

### 3.14 `conversation_agent.py` — histórico humano rotulado (fase 3)

`events_to_history`: evento `OUTBOUND` com `metadata.autor == "HUMANO"`, ou
sem `providerMessageId` e `status == SENT` (as 52 mensagens antigas), vira
turno **user** com prefixo `[atendente da clínica]: `. O system prompt ganha
três linhas: *mensagens com esse prefixo são compromissos da clínica, não
seus; não os repita, não os contradiga, não os estenda.*

Remove `_is_attendant_active`. `process_message` assume que a porta já foi
consultada; o único check que fica é `assert` em log se `estado() in
(HUMAN_ACTIVE, HUMAN_PENDING)`, para pegar chamador que pulou a porta.

### 3.15 `services/estado_comercial.py` (fase 4)

```python
NEW_LEAD, FIRST_BOOKING, ACTIVE_CUSTOMER, NO_NEXT_BOOKING = ...

def deriva(sessoes_feitas, tem_futuro) -> str      # pura
def do_paciente(paciente) -> str                   # pura, do dict de identificar()
def bloco(paciente, estado) -> str                 # o QUEM É para o turno da pessoa
def sem_bloco(history) -> list                     # o histórico sem o QUEM É, para gravar
```

> **Como ficou (09/10/2026):** sem segunda consulta. `identificar()` (fase 1) já
> traz sessões feitas, última sessão e agendamento futuro na sua única consulta,
> então `do_paciente` recebe esse dict e deriva. O log mede a identificação:
> `[EstadoComercial] {phone}: {estado} | identificacao em {ms}ms`. As travas que
> leem a conversa (`_turnos_para_trava`) passaram a ler só a fala da pessoa
> (`fala_da_pessoa`), porque o bloco QUEM É contém a palavra "valor" e a trava
> de valor a tomava como pergunta dela.
>
> **Revisão do André, no mesmo dia:** a janela de retorno e o estado
> `DUE_FOR_NEXT` caíram (PRD §3.1). A coluna `clinics.janela_de_retorno_dias`
> foi criada e removida por migration no mesmo dia. O bloco QUEM É diz, para
> quem já é paciente, que as áreas são perguntadas e confirmadas como sempre.

- "Sessão feita" = `status = 'CONFIRMED' AND appointment_date < CURRENT_DATE`,
  a mesma régua dos PRDs 016/017. `NO_SHOW` e `CANCELLED` não contam.
- "Futuro" = `CONFIRMED AND appointment_date >= CURRENT_DATE`.
- Sem `patient_id` -> `NEW_LEAD`, sem consulta.
- Índice: `CREATE INDEX IF NOT EXISTS idx_appointments_estado_comercial ON
  scheduler.appointments (clinic_id, patient_id, status, appointment_date)`.
- Medir: logar `[EstadoComercial] {phone}: {estado} em {ms}ms` por um ciclo
  antes de ligar a fase 7 (PRD §9.4).

O bloco `cliente` do PRD §5 é montado em `process_message` a partir de 3.1 e
daqui, entra no turno do usuário como `═══ QUEM É ═══` (depois do calendário,
antes dos dados consultados) e **não é gravado** na sessão.

### 3.16 `services/nivel_de_risco.py` (fase 5)

> **Como ficou (10/10/2026):** a colisão com o FAQ vale **só para o grupo
> médico**, e a consulta ao FAQ é canônica ("gestante lactante gravidez
> medicamentos roacutan...", não a frase da pessoa), porque "grávida" não casa
> "gestante" no ranker. Os outros grupos vão a pessoa sempre: "ficou com
> ferida" é problema real mesmo que o FAQ de contraindicações cite "feridas".
> Ordem de precedência quando mais de um grupo casa: ameaça, reclamação,
> reembolso, pós-sessão, médico. Quem sai antes do modelo (nível 3 e também
> `fora_do_escopo`) passa a abrir a pendência, como o handoff do bot: a fila
> vê a tarefa. Coluna `clinics.bot_termos_de_risco` (texto, não regex; vira
> reclamação). Sem tela no painel por enquanto, como `bot_procedimentos_fora_do_escopo`.

Espelho de `fora_do_escopo.py`: lista `TERMOS` de regex normalizados, com nome
do motivo; `detecta(texto, clinic) -> motivo | None`; termos extras por clínica
em `clinics.bot_termos_de_risco` (mesmo padrão de
`bot_procedimentos_fora_do_escopo`). Grupos (decisão de 09/10/2026: pagamento
**não** está aqui; pix, parcelamento e forma de pagamento são FAQ):

```
reclamacao     reclama|absurdo|pessim|horrivel|procon|advogad|processo|reclame aqui
reembolso      reembols|estorn|devolv.*dinheiro|cancelar.*pagamento|nao caiu
pos_sessao     queim|bolha|mancha|ferid|inflam|alerg|doendo muito
medico         remedio|medicament|gravid|gestante|amament|roacutan|isotretino
ameaca         vou (expor|denunciar|postar)
```

**Onde roda:** em `process_message`, antes do modelo, no mesmo ponto em que
`fora_do_escopo.detecta` roda hoje (linha ~378), lendo só a fala da pessoa
(`fala_da_pessoa`). Casou: `entrega_a_humano(session, motivo)`, abre a
pendência (como o handoff do bot já faz), responde o texto fixo
`bot_policy.TEXTO_DE_RISCO` ("Vou passar para uma especialista te atender
agora 😊") e **não chama o modelo**. Nenhum destes motivos entra em
`MOTIVOS_DO_MODELO`.

**Regra de colisão:** `gravid` e `medicament` aparecem aqui **e** no FAQ. Se a
mensagem casa um termo de risco e também casa um item do FAQ da clínica com
`busca_no_faq` acima do piso, vale o FAQ (a clínica escreveu a resposta): a
guarda deixa passar e o modelo escolhe o item. Se casa só o risco, nível 3.
Isso exige carregar os itens antes do modelo - é a mesma consulta que monta
o `enum` da tool (3.17), feita uma vez por mensagem.

Novos motivos em `bot_policy`: `MOTIVO_RECLAMACAO`, `MOTIVO_REEMBOLSO`,
`MOTIVO_POS_SESSAO`, `MOTIVO_MEDICO`, `MOTIVO_AMEACA`, com texto legível para a
fila ("Reclamação", "Pediu reembolso", "Problema depois da sessão", "Questão
médica fora do FAQ", "Ameaçou expor"). A fila já mostra motivo e pendência
(fase 3); nada novo no painel para o nível 3.

### 3.17 `services/policy_do_faq.py` e a tool do FAQ (fase 5)

> **Como ficou (10/10/2026):** a tool **mantém o nome `get_faq_answer`**, com
> o contrato novo (`question_key` em `enum`, sem texto livre). Renomear
> exigiria migrar o `AI_SYSTEM_PROMPT` da Essência e da Nobre Laser no banco,
> que citam o nome oito vezes cada. O bloco "COMO RESPONDER DÚVIDAS" do código,
> anexado a todo prompt, passou a mandar não repetir o item; os prompts do
> banco ainda dizem "responda com o que ela devolver" - o descarte por
> repetição cobre isso, e o log `[FAQ] ... descartei` mede quanto acontece.
> `busca_no_faq` deixa de ser o caminho do FAQ e fica para a regra de colisão
> do nível 3 (§3.16).

**Todo item do FAQ é literal** (André, 10/10/2026). Não há coluna `nivel`,
não há seletor no painel, não há lista de chaves no código. A clínica
escreve a resposta e ela vai como está.

- `policy_do_faq.itens(db, clinic_id) -> list`: os itens ativos da clínica,
  uma consulta por mensagem (reaproveitada pela guarda do nível 3).
- `policy_do_faq.definicao_da_tool(itens) -> dict | None`: a tool
  `get_faq_answer(question_key)` com `enum` dos `question_key` e a
  descrição listando o `question_label` de cada um ("escolha o item que
  responde a pergunta; se nenhum responde, NÃO chame esta tool - diga que vai
  confirmar com a equipe"). Sem itens, a tool não existe. **Substitui**
  `get_faq_answer`: o ranker `busca_no_faq` deixa de ser o caminho do FAQ e
  fica só como teste de cobertura do catálogo (ou sai na fase 8).
- `get_tool_definitions(format, faq=None)` anexa essa definição. O prefixo
  cacheado passa a variar por clínica (as tools são parte do prefixo) -
  aceitável: o cache é por conversa, e dentro da clínica a lista só muda
  quando ela edita o FAQ.
- O executor devolve `{"faq": question_key, "entregue": True}` e empilha o
  item em `ctx["faq_escolhido"]` (lista). O modelo recebe no resultado:
  "O texto deste item vai à pessoa como mensagem própria; NÃO o repita nem o
  resuma na sua resposta. Responda só o que sobrou da pergunta, se sobrou."
- Em `_build_outgoing`: primeiro uma `OutgoingMessage` por item escolhido,
  com `answer` byte a byte, na ordem das chamadas; depois, se o modelo
  escreveu algo, a mensagem dele (passando pelas guardas de sempre). Nunca
  na mesma bolha. Se o texto do modelo repete o item (comparação normalizada,
  contém >= 60% das frases do item), é descartado com log `WARNING`
  `[FAQ] {phone}: o modelo repetiu o item {key}; descartei` - a bolha literal
  basta.
- Chamada com `question_key` fora do `enum` (o modelo pode inventar): o
  executor devolve erro e o item não é entregue; se nada mais responder, cai
  no caminho de "nenhum item": handoff `faq_sem_resposta`.
- Mais de dois itens no mesmo turno: handoff `faq_sem_resposta` (pergunta
  confusa; o desempate não é do modelo). Um ou dois: cada um em sua bolha.
- Painel: nada muda. `faq_items` continua `question_key`, `question_label`,
  `answer`, `display_order`, `active`.

**Exemplos de conversa (PRD §4.3, revisados com o André em 09 e 10/10):**

- Nível 1, segue como hoje: "Quanto fica axila e virilha?" -> tools + o modelo
  redige.
- Nível 2, qualquer FAQ: "Estou grávida de 4 meses, posso fazer?" -> o modelo
  escolhe `CONTRAINDICATIONS`; a pessoa recebe o texto da Essência, palavra
  por palavra, numa bolha. "Posso pagar no pix?" -> idem, com o item de
  pagamento, se a clínica o escreveu. "Qual o intervalo e tem horário dia
  21?" -> bolha 1: o item `SESSION_INTERVAL` literal; bolha 2: os horários
  do dia 21, consultados, redigidos pelo modelo. "Tenho uma doença de pele
  rara, pode?" -> nenhum item -> pessoa, com `faq_sem_resposta`.
- Nível 3: "Isso é um absurdo, vou no Procon" -> `reclamacao`, pessoa, o
  modelo não vê. "Quero meu dinheiro de volta" / "fiz o pix e não caiu" ->
  `reembolso`. "A axila ficou queimada, está com bolha" -> `pos_sessao`.
  "Vou postar isso no Instagram" -> `ameaca`.

### 3.18 `services/desambiguacao.py` (fase 6)

> **Como ficou (10/10/2026):** medido em prod, zero handoffs por `incompreensao`
> em 30 dias; a fase entrou como proteção. Quem percebe a ambiguidade é o
> modelo (ele já pergunta sozinho hoje); o que virou código é a pergunta, as
> opções e o limite. Tool `pedir_esclarecimento(candidatas)` com `enum`
> (agendar, remarcar, cancelar, duvida, até 3): o executor registra a
> tentativa na sessão (`session["conversa"]["tentativas_de_desambiguacao"]`)
> e devolve a pergunta como `present_options` com texto fixo; a fala do
> modelo junto dela é descartada. Na terceira seguida devolve handoff
> `incompreensao`, com texto fixo de esgotamento, e a pendência abre como em
> todo handoff. `request_human_handoff(reason=incompreensao)` antes de esgotar
> vira a pergunta - desistir cedo não é permitido. Zera com tool de efeito ou
> item do FAQ entregue. Não há classificador antes do modelo: o roteador
> determinístico continua só decidindo as consultas obrigatórias.

```python
MAX_TENTATIVAS = 2
def precisa(intencoes_detectadas, classificacao) -> bool
def pergunta(candidatas) -> OutgoingMessage    # present_options, texto fixo
def registra_tentativa(session) -> int
def zera(session) -> None
```

Determinístico: a pergunta é template com as intenções candidatas como botões
(`Agendar`, `Remarcar`, `Tirar dúvida`). Contador em
`session["conversa"]["tentativas_de_desambiguacao"]`; zera a cada intenção
resolvida (tool com efeito ou resposta de policy). Na terceira ambiguidade,
`entrega_a_humano(motivo=MOTIVO_INCOMPREENSAO)`.

### 3.19 `services/skills/` (fase 7)

> **Como ficou (10/10/2026):** um módulo só, `services/skills/__init__.py`,
> com três `Skill` (dataclass: `nome`, `estados`, `tools_vetadas`, `bloco`)
> e `despacha(estado)`. Por estado comercial, não por intenção (ver nota no
> PRD §6). O que a skill muda em código: `skill.filtra(get_tool_definitions(...))`
> tira `reschedule_appointment` e `cancel_appointment` de quem não tem sessão
> marcada, e `skill.bloco` ("QUEM VOCÊ ESTÁ ATENDENDO") entra no system
> prompt depois dos blocos do código e antes da sobreposição da campanha (que
> o substitui: duas condutas ao mesmo tempo seria pior que uma). Cadastro e
> valor continuam decididos pelos fatos da pessoa (`sem_passo_de_cadastro`,
> `sem_valor_no_roteiro`), não pela skill: a skill não pode "esquecer" o
> cadastro de uma paciente encontrada com cadastro incompleto. `roteador.despacha`
> aponta para `skills.despacha`, para o Router ser o único lugar que decide
> quem executa. Estado desconhecido cai em `primeiro_agendamento`, a mais
> restrita.

Cada skill é um módulo com três coisas, nada mais:

```python
NOME = "primeiro_agendamento"
ESTADOS = {NEW_LEAD}
TOOLS = [...]                        # subconjunto permitido
def bloco_do_prompt(clinic, cliente) -> str
```

`ConversationAgent._build_system_prompt` monta a parte fixa (clínica, áreas,
datas, descontos) e **anexa** `bloco_do_prompt` da skill despachada; a lista
de tools passada à API é `skill.TOOLS`. `primeiro_agendamento` é a única que
inclui o roteiro de cadastro; `agendamento` não tem `full_name` no contrato.
A diferença do §2.2 do PRD fica no código, não na instrução.

### 3.20 Fase 8

- Confirmar em produção, no dia, que nenhuma clínica ativa tem
  `use_agent = false` com `bot_paused = false`. Se tiver, ligar `use_agent`
  antes do deploy, não depois.
- `_executar_engine` perde o `else`. `USE_AGENT_MODE` sai do ambiente.
- `grep -rn "ConversationState\|conversation_engine\|intent_classifier"` tem
  de voltar vazio antes do commit.

---

## 4. Ordem de implementação

1. **Fase 1** (PR próprio, deploy, teste com a Yasmin).
2. **Fase 2**: `atendimento.py` + testes puros primeiro; depois os sete
   chamadores, um commit cada; `business_hours` e o lembrete por último.
   Deploy com `should_bot_reply` ainda existindo.
3. **Fase 3**: tabela `tarefas` e GSI (deploy de infra isolado); depois
   `ExpiraAtendimentos` desligado (`enabled: false` no schedule); depois
   `retomada.py`; ligar o cron com `limit=5` por um dia e ler os logs antes
   de subir o limite.
4. **Fase 4**: módulo puro, índice, medição de latência, só então o bloco no
   prompt.
5. **Fase 5**: a tool `responder_com_faq` e as bolhas literais primeiro (sem migration, sem painel), medir um ciclo; depois a guarda do nível 3, que é o que mais tira conversa do bot.
6. **Fase 6** e **7** juntas no mesmo PR se a 5 estiver estável há uma semana.
7. **Fase 8** depois de uma semana da 7 sem handoff `incompreensao` acima do
   patamar de hoje.

---

## 5. Testes

Todos em `scheduler/tests/unit`, `unittest`, sem rede, no padrão de
`test_conversation_resume.py`. Os que o PRD §10 exige, com o arquivo:

| critério do PRD | teste |
|---|---|
| Yasmin não recebe pedido de CPF | `test_cadastro_pelo_bot.py::test_paciente_cadastrada_nao_recebe_pedido_de_cpf` |
| duas funções, cinco chamadores | `test_atendimento.py::test_todo_caminho_proativo_passa_pela_porta` (AST sobre os cinco arquivos, não `assertIn`) |
| só a clínica renova | `test_atendimento.py::test_mensagem_do_cliente_nao_renova` |
| pendência não volta ao bot | `test_expira_atendimentos.py::test_pending_intent_vai_para_human_pending` |
| cooldown não dispara, responde | `test_atendimento.py::test_cooldown_responde_mas_nao_inicia` |
| limites da janela | `test_business_hours.py::test_silencio_nos_quatro_limites` (22:58:59, 22:59:00, 04:59:59, 05:00:00, e DST de 15/11) |
| item elegível 22:58 processado 23:01 | `test_fila_nao_envia_duas_vezes.py::test_relogio_do_envio_manda` |
| lembrete 07:15 | `test_lembrete_no_fuso.py` |
| retomada: cada guarda | `test_retomada.py`, um teste por linha da tabela de 3.12, mais o caso positivo |
| "amanhã" com 30h repergunta | `test_retomada.py::test_data_relativa_envelhece` (dublagem do agente, ver `dublagem_agente.py`) |
| humano rotulado | `test_agent_history_rebuild.py::test_fala_da_atendente_vira_turno_rotulado` |
| nível 3 vence confiança | `test_nivel_de_risco.py::test_reembolso_com_confianca_alta_vai_a_handoff` |
| nível 2 byte a byte | `test_policy_do_faq.py::test_resposta_e_o_answer_do_item` com `faq_real.py` |
| ACTIVE_CUSTOMER fora da primeira venda | `test_estado_comercial.py` + `test_roteador.py::test_active_customer_nao_cai_em_primeiro_agendamento` |
| 9.1 | `test_bot_policy.py::test_nao_existe_pausa_permanente` (AST: o nome não existe) e `test_retomada.py::test_conversa_anterior_a_nos_nao_e_retomada` |
| engine apagado | `test_catalogo_real_e_alcancavel.py` continua verde sem o engine |

---

## 6. Convenções a respeitar

- Logging com prefixo de módulo entre colchetes, como o repo faz
  (`[Atendimento]`, `[Retomada]`, `[EstadoComercial]`).
- Migrações idempotentes; `CREATE TABLE` em sincronia com o `ALTER`
  (`CLAUDE.md`).
- Funções de regra são puras e vivem em `services/`; I/O fica nos handlers
  e em `session_store`.
- Toda trava nova tem **teste do caso positivo** (memória "check que nunca
  passa") e nenhum teste confere regra por `assertIn` no fonte.
- Branch por fase, PR contra `main`, sem commit direto.
