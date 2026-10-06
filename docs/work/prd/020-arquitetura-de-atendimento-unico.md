# PRD — 020 Um agente só, com três dimensões separadas

> Gerado na fase **Research**. Use como input para a fase Spec.
>
> Este PRD **substitui parte do 019** (ver §9.1) e absorve o risco 5.1 dele.

---

## 1. Objetivo

Um único agente atende lead novo e cliente recorrente, decidindo o fluxo pelo
**estado comercial do cliente** cruzado com a **intenção da mensagem**, enquanto
o **estado de atendimento** (quem responde: bot ou pessoa) corre em paralelo e
independente.

Hoje essas três coisas estão fundidas, e o efeito prático é que o bot trata todo
mundo como lead novo - inclusive quem já fez 13 sessões.

---

## 2. Contexto

### 2.1 A recorrência já é a maioria, e o bot não a representa

Medido em produção (Essência, 05/10/2026), pacientes com ao menos uma sessão
passada confirmada:

| sessões feitas | pacientes |
|---|---|
| 1 | 60 |
| 2 | 39 |
| 3 | 32 |
| 4 | 24 |
| 5 | 20 |
| 6 | 17 |
| 7 | 5 |
| 8 | 3 |
| 13 | 1 |
| **total** | **200** |

**140 dos 200 (70%) têm duas sessões ou mais.** O funil que o agente foi feito
para atender - Google Ads → site → WhatsApp → primeiro agendamento - é hoje a
minoria do volume de conversa, e é o único caso que o agente sabe conduzir.

### 2.2 O agente não tem como saber quem é a pessoa

As 16 tools do agente (`src/services/ai_tools.py`):

```
list_services      check_availability   sem_consulta_necessaria  lookup_appointments
list_areas         get_time_slots       calculate_duration       get_faq_answer
get_clinic_info    book_appointment     reschedule_appointment   cancel_appointment
request_human_handoff   present_options  calculate_discount      calculate_patient_age
```

**Nenhuma identifica o paciente.** A única leitura de `scheduler.patients` no
executor é `SELECT birth_date` para calcular idade (`ai_tools.py:822`).

Consequência direta, e é o ponto que o André mandou corrigir: a tool
`book_appointment` declara

> *"Requires all data to be collected: service areas, date, time, and the patient
> registration data (full name, birth date, CPF, email)"*

com `required: ["service_area_pairs", "date", "time", "full_name"]`. O contrato
exige cadastro **sempre**, e nada informa ao modelo que a pessoa já é paciente.
Por isso a Yasmin, que tinha acabado de marcar, recebeu *"Para finalizar o
cadastro, me envia: Nome completo, Data de nascimento, CPF, E-mail"*.

Isto não é falha do prompt. É o contrato da ferramenta pedindo o que já existe no
banco.

### 2.3 Onde as três dimensões estão fundidas hoje

`ConversationState` (`conversation_engine.py:37`) tem 30 valores num enum só, e
misturam coisas de naturezas diferentes:

```
SELECT_TIME, CONFIRM_BOOKING, FAQ_ANSWER   <- passo do fluxo
HUMAN_HANDOFF, HUMAN_ATTENDANT_ACTIVE      <- QUEM responde
BOOKED, CANCELLED, RESCHEDULED             <- resultado
```

Não existe nenhum campo para **estado comercial**. Ele simplesmente não é um
conceito no código: deriva-se, quando se deriva, de consultas ad-hoc.

### 2.4 O engine legado não atende ninguém - isto é uma oportunidade

| clínica | `use_agent` | `bot_paused` | política |
|---|---|---|---|
| Essência Estética | **True** | False | LEADS_ONLY |
| Clinica do rods | **True** | False | ALL |
| Depilação Premium | False | **True** | ALL |
| Nobre Laser SJC | False | **True** | OFF |

As duas clínicas com bot ligado estão no **agente**. As duas no engine legado
têm o bot pausado. Os 30 estados do `ConversationState` são código morto em
produção.

Isso muda o custo do trabalho: não é migrar duas máquinas de estado, é construir
uma e **apagar** a outra.

### 2.5 O que já existe e serve de base

- **`src/services/roteador.py`** - `PADROES` (regex de intenção, determinístico),
  `intencoes()` e `TOOLS_POR_INTENCAO` com pré-carga obrigatória de tools. É uma
  semente real do Router, já em produção.
- **`src/services/bot_policy.py`** - `should_bot_reply`, `esta_pausado`, as cinco
  pausas e o vocabulário de motivos de handoff (`MOTIVOS_LEGIVEIS`, PR #88).
- **`src/services/fora_do_escopo.py`** - guarda determinística rodando **antes**
  do modelo. É o padrão de "policy antes do LLM" que o nível 2 vai generalizar.
- **`src/services/intent_classifier.py`** - classificador por LLM, hoje com 8
  intenções (`schedule, reschedule, cancel, faq, human, greeting, price_inquiry,
  unknown`) e `confidence: high|low`. Usado como fallback do casamento
  determinístico.
- **`campanha.py`** - marca com `expira_em` e `esta_viva()`, que **falha
  fechada**. É o precedente de marca com prazo.

---

## 3. As três dimensões

A regra central: **cada dimensão tem seu campo, sua máquina e seu dono.** O que
hoje é um `state` string vira três campos que não se leem entre si.

### 3.1 Estado comercial — derivado, não armazenado

```
NEW_LEAD            sem agendamento algum
FIRST_BOOKING       tem agendamento futuro, zero sessões feitas
ACTIVE_CUSTOMER     >= 1 sessão feita e tem agendamento futuro
DUE_FOR_NEXT        >= 1 sessão feita, sem agendamento futuro, dentro da janela de retorno
INACTIVE            >= 1 sessão feita, sem agendamento futuro, fora da janela
```

**Decisão de desenho: derivar de `appointments`, não gravar em coluna.** Um campo
`commercial_status` seria um cache de algo que o banco já sabe, e cache de estado
comercial envelhece em silêncio - a pessoa faz a sessão e o campo não muda até
alguém rodar um job. O repo já tem essa cicatriz: `uploaded_at` virou "compra
enviada" por acidente histórico (PRD 017 §4.1).

O custo é uma consulta por mensagem recebida. É uma, indexada por
`(clinic_id, patient_id)`, no mesmo lugar onde já se consulta `leads` hoje.

A janela de retorno (`DUE_FOR_NEXT` vs `INACTIVE`) é **parâmetro por clínica**,
não constante: depende do intervalo entre sessões do protocolo.

### 3.2 Estado de atendimento — a máquina que precisa existir

```
        ┌──────────────────────────────────────────────┐
        │                                              │
        ▼                                              │
   BOT_ACTIVE ──(humano responde / handoff)──▶ HUMAN_ACTIVE
        ▲                                              │
        │                                    (TTL de inatividade vence)
        │                                              ▼
        │                                       HUMAN_EXPIRED
        │                                              │
        │                            ┌─────────────────┴─────────────────┐
        │                            │                                   │
        │                   tem pendência?                        não tem
        │                            │                                   │
        │                            ▼                                   ▼
        │                     HUMAN_PENDING ───(pessoa resolve)──▶   COOLDOWN
        │                     (tarefa na fila,                          │
        │                      bot não assume)                 (cliente escreve)
        │                                                               │
        └───────────────────────────────────────────────────────────────┘
```

| estado | quem responde | o bot pode iniciar? | o bot pode responder? |
|---|---|---|---|
| `BOT_ACTIVE` | bot | **sim** | sim |
| `HUMAN_ACTIVE` | pessoa | não | **não** |
| `HUMAN_EXPIRED` | ninguém (transitório) | não | não |
| `HUMAN_PENDING` | pessoa (tarefa aberta) | não | **não** |
| `COOLDOWN` | bot, só reativo | **não** | **sim** |

`COOLDOWN` é a resposta à exigência do André: *"o bot pode responder se o cliente
iniciar uma nova conversa, mas não dispara mensagens automaticamente"*. É a
distinção entre **responder** e **iniciar**, que hoje não existe em lugar nenhum
do código - `should_bot_reply` responde uma pergunta só.

### 3.3 Transições, com evento e condição

| de | evento | condição | para | efeito |
|---|---|---|---|---|
| `BOT_ACTIVE` | mensagem de pessoa da clínica no WhatsApp | — | `HUMAN_ACTIVE` | `human_until = agora + TTL` |
| `BOT_ACTIVE` | "Pausar bot" no painel | — | `HUMAN_ACTIVE` | idem |
| `BOT_ACTIVE` | `request_human_handoff` do agente | — | `HUMAN_ACTIVE` | grava motivo + `pending_intent`, **cria tarefa** |
| `BOT_ACTIVE` | guarda de risco nível 3 | determinística | `HUMAN_ACTIVE` | idem, sem passar pelo modelo |
| `HUMAN_ACTIVE` | qualquer mensagem (de quem for) | — | `HUMAN_ACTIVE` | **renova** `human_until` |
| `HUMAN_ACTIVE` | relógio | `agora > human_until` | `HUMAN_EXPIRED` | — |
| `HUMAN_EXPIRED` | avaliação | há `pending_intent` **ou** tarefa `OPEN` | `HUMAN_PENDING` | alerta na fila |
| `HUMAN_EXPIRED` | avaliação | sem pendência | `COOLDOWN` | `cooldown_until = agora + C` |
| `HUMAN_PENDING` | tarefa fechada no painel | — | `COOLDOWN` | — |
| `HUMAN_PENDING` | "Retomar bot" | explícito | `BOT_ACTIVE` | limpa pendência |
| `COOLDOWN` | mensagem do cliente | — | `BOT_ACTIVE` | atende normalmente |
| `COOLDOWN` | relógio | `agora > cooldown_until` | `BOT_ACTIVE` | — |
| qualquer | "Retomar bot" | explícito | `BOT_ACTIVE` | limpa tudo |

**Condição de saída de `HUMAN_ACTIVE` é só o relógio.** Nenhuma mensagem tira a
conversa do humano - ela só renova. Isso é deliberado: hoje o `HANDOFF` vence em
24h absolutas e a conversa volta ao bot mesmo que a atendente tenha respondido
há 10 minutos.

### 3.4 TTL por inatividade, renovável

```
human_until = ultima_interacao_relevante + TTL_HUMANO     (24h)
```

"Interação relevante" = mensagem do cliente **ou** da clínica naquela conversa.
Hoje o cálculo é `handoff_at + 24h`, fixo no momento do handoff - então um
atendimento que dura dois dias volta ao bot no meio.

**O retorno ao bot precisa do contexto do atendimento humano.** Isso já existe
parcialmente: `conversation_resume.py` tem `ha_pergunta_em_aberto` e
`EVENTOS_PARA_CONTEXTO`, usados pelo `_agendar_retomada` do painel. A Spec deve
reusar esse caminho em vez de criar outro - e o `agent_history` tem de receber as
mensagens humanas, senão o bot volta cego e repete o que a atendente já disse.

### 3.5 Cooldown

```
cooldown_until = fim_do_atendimento_humano + COOLDOWN     (sugestão: 24h)
```

Durante o cooldown o bot **não dispara nada** - nem lembrete de retorno, nem
campanha, nem "como posso ajudar?". Se o cliente escrever, o bot atende
normalmente e o cooldown termina.

Isto exige **separar as duas perguntas** que hoje são uma:

```python
pode_responder(clinic, state, phone)   # reativo
pode_iniciar(clinic, state, phone)     # proativo: campanha, lembrete, retomada
```

`should_bot_reply` passa a ser `pode_responder`. Todo caminho de envio proativo
(`outbound/processor.py`, `reminder_service`, `/send` com campanha) passa a
consultar `pode_iniciar`.

### 3.6 Pendência: o bot não reassume assunto em aberto

```json
{
  "pending_intent": "RESCHEDULE",
  "pending_since": "2026-10-05T14:02:00Z",
  "pending_task_id": "..."
}
```

Gravada no handoff, limpa **só** quando a tarefa é fechada ou alguém clica
"Retomar bot". `HUMAN_EXPIRED` com pendência vai para `HUMAN_PENDING`, não para
o bot - é a exigência 6 do André.

---

## 4. Intenção, fallback e risco

### 4.1 A classificação é em camadas, e a primeira é determinística

```
1. casamento determinístico  (roteador.PADROES)        -> intenção + confiança alta
2. guardas de escopo/risco   (fora_do_escopo, nível 3) -> decide sem LLM
3. classificador LLM         (intent_classifier)       -> intenção + confidence
4. ambíguo? -> PERGUNTA DE DESAMBIGUAÇÃO (até N vezes)
5. ainda ambíguo -> handoff com motivo `incompreensao`
```

O passo 4 é o que não existe hoje: o agente vai direto de "não entendi" para
handoff ou para uma resposta genérica. O exemplo do André:

> **Cliente:** "Quero marcar aquele negócio."
> **Agente:** "Só para eu te ajudar certinho: você quer agendar uma nova sessão,
> remarcar uma que já está marcada, ou tirar uma dúvida?"

**`N = 2` tentativas**, contadas na sessão (`tentativas_de_desambiguacao`). O
contador zera a cada intenção resolvida. Sem contador, um cliente confuso entra
em laço - e o repo já tem a cicatriz disso em `recusas_de_area` e no motivo
`areas_em_laco`.

### 4.2 Intenções

Hoje são 8. O desenho pede 13. Mapeamento:

| intenção nova | existe hoje? |
|---|---|
| `FIRST_BOOKING` | não - hoje é `schedule` sem distinção |
| `SCHEDULE` | `schedule` |
| `RESCHEDULE` | `reschedule` |
| `CANCEL` | `cancel` |
| `PRICE_INFORMATION` | `price_inquiry` |
| `TECHNOLOGY_FAQ` | dentro de `faq` |
| `PREPARATION` | dentro de `faq` |
| `AFTERCARE` | dentro de `faq` |
| `NEXT_SESSION` | não |
| `PAYMENT` | não |
| `COMPLAINT` | não |
| `MEDICAL_QUESTION` | não |
| `OTHER` | `unknown` |

**`FIRST_BOOKING` não é intenção - é (SCHEDULE × NEW_LEAD).** Manter como
intenção separada volta a fundir as dimensões. Fica `SCHEDULE`, e o Router
escolhe a skill pelo estado comercial.

As quatro novas que importam: `MEDICAL_QUESTION`, `COMPLAINT` e `PAYMENT` são
gatilhos de nível 3 - precisam existir **para poder transferir**. `NEXT_SESSION`
é o que permite atender os 140 recorrentes.

### 4.3 Níveis de autonomia, e risco vence confiança

| nível | o que é | quem responde | como |
|---|---|---|---|
| **1** | preço, área, duração, tecnologia, endereço, horário, agendar, remarcar, cancelar, FAQ | bot | tool + LLM redige |
| **2** | contraindicação, gravidez, medicamento, pele, preparo, pós-sessão | bot | **texto de policy aprovado**, LLM só escolhe qual - não redige |
| **3** | reclamação, reembolso, pagamento, problema pós-procedimento, questão médica fora da base, negociação fora da regra, ameaça | **pessoa** | handoff determinístico |

```python
# A ordem é a regra. Risco é avaliado ANTES de olhar confiança.
if nivel_de_risco(intencao, texto) == 3:
    return handoff(motivo=intencao)          # confiança não entra na decisão
if nivel == 2:
    return resposta_de_policy(intencao)      # sem geração livre
return skill(intencao, estado_comercial)
```

**Nível 2 é generalização do `fora_do_escopo`**, que já faz exatamente isso para
procedimento fora de escopo: decide sem o modelo e devolve texto fixo. A
diferença é que o nível 2 deixa o LLM **escolher** a policy, e não redigir a
resposta.

O nível 3 tem de ser determinístico por padrão - uma lista de termos, como
`fora_do_escopo.PROCEDIMENTOS` - porque depender do modelo para classificar
risco é depender dele para decidir quando não confiar nele.

---

## 5. Memória estruturada

O que a sessão guarda hoje (lido de produção): `agent_history`, `state`, `mode`,
`bot_enabled`, `lead_id`, `bot_pausado_por`, `attendant_active_until`,
`recusas_de_area`, `respaldo_anterior`, `efeito_na_ultima_rodada`,
`_previous_state_before_attendant`, `handoff_reason`.

Proposta - **três blocos que não se leem entre si**:

```json
{
  "cliente": {
    "patient_id": "...", "lead_id": "...", "nome": "...",
    "sessoes_feitas": 3, "ultima_sessao": "2026-09-12",
    "areas_tratadas": ["axila", "virilha"],
    "agendamento_futuro": {"id": "...", "data": "...", "hora": "..."},
    "cadastro_completo": true
  },
  "atendimento": {
    "handler": "BOT_ACTIVE",
    "human_until": null, "cooldown_until": null,
    "handoff_reason": null, "pending_intent": null, "pending_task_id": null
  },
  "conversa": {
    "intencao": "SCHEDULE", "passo": "ESCOLHENDO_HORARIO",
    "tentativas_de_desambiguacao": 0,
    "historico": []
  }
}
```

O bloco `cliente` é **derivado e recarregado a cada mensagem**, não acumulado -
ver §3.1. É cache de requisição, não estado.

---

## 6. Router / Orchestrator

Responsabilidade única: **decidir quem executa, e nunca executar**.

```
webhook
  └─ 1. resolve o cliente        (telefone -> patient_id | lead_id)
     2. carrega estado           (comercial derivado + atendimento + conversa)
     3. porta de atendimento     pode_responder()?  -> não: registra e sai
     4. agrega a rajada          (debounce 68s, já existe)
     5. guardas determinísticas  fora_do_escopo, risco nível 3
     6. classifica intenção      determinístico -> LLM -> desambiguação
     7. política                 nível 1 | 2 | 3
     8. despacha a skill         (intenção × estado comercial)
     9. tools                    pré-carga obrigatória (roteador, já existe)
    10. resposta
```

Skills, e qual estado comercial cada uma atende:

| skill | estados comerciais |
|---|---|
| `PrimeiroAgendamento` | `NEW_LEAD` |
| `Agendamento` | `ACTIVE_CUSTOMER`, `DUE_FOR_NEXT`, `INACTIVE` |
| `Remarcacao` / `Cancelamento` | qualquer com agendamento futuro |
| `ProximaSessao` | `DUE_FOR_NEXT` |
| `Preco` / `TecnologiaFAQ` / `Preparo` / `PosSessao` | qualquer |
| `HandoffHumano` | qualquer |

`PrimeiroAgendamento` e `Agendamento` são skills distintas **porque pedem coisas
diferentes**: a primeira coleta cadastro, a segunda não. É aí que o bug do §2.2
se resolve estruturalmente, e não por instrução no prompt.

### 6.1 Determinístico vs LLM

| determinístico (código) | do LLM |
|---|---|
| estado comercial | classificar intenção quando o regex não casa |
| porta de atendimento, TTL, cooldown | redigir a resposta no nível 1 |
| nível de risco e handoff do nível 3 | escolher qual policy do nível 2 se aplica |
| escolha da policy do nível 2 (o texto) | formular a pergunta de desambiguação |
| escolha da skill | extrair entidades (áreas, datas) |
| preço, desconto, duração, disponibilidade | — |
| se pede cadastro ou não | — |
| criar tarefa humana | — |

A regra que o repo já segue e que isto preserva: **o modelo nunca decide se pode
responder, nem calcula número.** Ele interpreta e redige.

---

## 7. A correção do cadastro (fatia 1, independente)

Pequena, de valor imediato, e não depende da arquitetura:

1. Tool nova `identificar_paciente(phone)` → `{patient_id, nome, cadastro_completo,
   sessoes_feitas, ultima_sessao, agendamento_futuro}`. Entra na **pré-carga
   obrigatória** do `roteador` para as intenções de agendamento, então chega ao
   modelo antes de ele escrever.
2. `book_appointment`: `full_name` sai de `required` quando há `patient_id`. A
   descrição deixa de exigir cadastro incondicionalmente e passa a dizer: *se
   `cadastro_completo`, não peça nada disso*.
3. Guarda determinística: o executor **recusa** pedir cadastro de paciente com
   `cadastro_completo = true` - porque instrução o modelo contorna, e esse é o
   princípio do `fora_do_escopo`.
4. Teste com os dados reais da Yasmin: paciente cadastrada agendando segunda
   sessão não recebe pergunta de CPF.

---

## 8. Faseamento

Nada aqui exige big-bang, e um big-bang seria errado: a Essência tem 523
agendamentos em 30 dias passando por esse caminho.

| fase | entrega | depende de |
|---|---|---|
| **1** | correção do cadastro (§7) | nada |
| **2** | `pode_responder` / `pode_iniciar` separados + cooldown + TTL por inatividade | — |
| **3** | estado de atendimento explícito (`handler`) + pendência + tarefa humana | 2, PR #88 |
| **4** | estado comercial derivado + `identificar_paciente` no Router | 1 |
| **5** | níveis 1/2/3 e policies do nível 2 | 4 |
| **6** | desambiguação com contador | 5 |
| **7** | skills separadas e Router despachando | 4, 5 |
| **8** | apagar `conversation_engine` e os 30 estados | 7 |

A fase 2 é a que absorve o PRD 019 inteiro. A fase 8 é possível **porque** o
engine legado não atende ninguém (§2.4).

---

## 9. Decisões a tomar, riscos

### 9.1 Isto substitui o desenho do PRD 019

O 019 ia escrever **pausa permanente** quando a caixa do disparo está desmarcada,
e o risco 5.1 era "pausa sem prazo cala o bot para sempre", com duas saídas ruins
(prazo arbitrário, ou pausar só quem tem sessão - que eu medi: 286 de 320, ou
seja, não resolvia).

A regra do André - **TTL de 24h por inatividade, independente do fluxo, mais
cooldown** - dissolve o 5.1: não existe pausa permanente a limitar. É melhor que
as duas opções que eu havia proposto.

**Mas tem uma consequência que precisa ser decidida, não assumida:**
`PAUSA_CONTATO_MANUAL` e `PAUSA_CHAT_ANTERIOR` são **permanentes hoje de
propósito** - elas dizem *quem começou a conversa*, e o docstring de
`esta_pausado` argumenta que isso "não para de ser verdade amanhã".

Com TTL de inatividade elas passam a vencer. O argumento a favor: são **2912**
conversas anteriores a nós, e pausá-las para sempre significa 2912 conversas
nunca automatizadas - o oposto de "o humano é a exceção". O argumento contra: o
bot pode entrar numa conversa que uma pessoa conduz.

O **cooldown é o que torna isso aceitável**: o bot não inicia, só responde a quem
escreveu. Mas a decisão é do André, e ela reverte uma decisão anterior dele
(06/09/2026) - por isso está nomeada aqui em vez de embutida.

### 9.2 `bot_enabled` permanente continua sendo um problema

Quatro caminhos escrevem `bot_enabled = True` e **nenhum** o remove:
`webhook:307`, `attendant/handler:168` (o "Retomar bot", em qualquer política),
`outbound/processor:166` e `mark_conversation_eligible`. A tabela de sessões não
tem TTL (`TimeToLiveStatus: DISABLED`).

Na arquitetura nova, `bot_enabled` deveria desaparecer: ele é uma proxy de
"elegibilidade" que o **estado comercial** passa a responder melhor. Mas remover
muda quem o bot atende hoje - fatia própria, com medição antes.

### 9.3 Três tabelas sem TTL, e a documentação errada

`conversation-sessions`, `message-events` e `scheduled-reminders` estão com
`TimeToLiveStatus: DISABLED`; só `outbound-queue` tem TTL. O `CLAUDE.md` afirma
"TTL 30min", "TTL 90d" e "TTL 48h" para as três primeiras. **As três estão
erradas**, e o PRD 019 herdou o erro ao falar em "extrair antes de 29/12/2026" -
não há prazo.

Isso é retenção crescendo sem limite, e precisa de fatia própria. Para esta
arquitetura importa porque o estado do atendimento passa a depender de prazos: se
alguém ligar TTL depois, `human_until` e `cooldown_until` desaparecem com o item.

### 9.4 Riscos de execução

- **A fase 2 mexe no caminho de toda mensagem.** `should_bot_reply` é chamado em
  6 lugares; virar duas funções exige revisar os seis.
- **Nível 2 precisa das policies escritas antes do código.** O conteúdo é
  clínico, não técnico, e é a clínica que aprova. Sem isso a fase 5 não começa.
- **Tarefa humana precisa de dono na UI.** A fila do #88 mostra conversas, não
  tarefas. `HUMAN_PENDING` sem alguém olhando é conversa esquecida com cara de
  resolvida.
- **O estado comercial derivado custa uma consulta por mensagem.** Medir antes de
  assumir que é barato: hoje o webhook já faz 2-3 consultas por mensagem.

---

## 10. Critérios de aceite

- [ ] Paciente cadastrado agendando nova sessão **não** recebe pergunta de
      cadastro - teste com os dados reais da Yasmin
- [ ] `pode_responder` e `pode_iniciar` são funções distintas, e todo envio
      proativo usa a segunda
- [ ] `human_until` é renovado a cada interação relevante
- [ ] Handoff com `pending_intent` **não** volta ao bot quando o TTL vence
- [ ] Durante o cooldown o bot não dispara nada, e responde se o cliente escrever
- [ ] Intenção ambígua gera desambiguação, e só vai a handoff depois de 2
      tentativas
- [ ] Intenção de nível 3 vai a handoff **independentemente da confiança** -
      teste com confiança alta
- [ ] Nível 2 responde com texto de policy, sem geração livre
- [ ] Estado comercial é derivado, e `ACTIVE_CUSTOMER` não entra no fluxo de
      primeira venda
- [ ] As três dimensões são campos distintos, e nenhuma função lê duas delas para
      decidir uma coisa
- [ ] Decisão de 9.1 registrada (pausas permanentes passam a vencer, ou não)
- [ ] `conversation_engine` apagado, ou com data marcada para apagar

---

## 11. Referências

- `src/services/bot_policy.py` — `should_bot_reply`, `esta_pausado`, as 5 pausas
- `src/services/roteador.py` — a semente do Router já em produção
- `src/services/fora_do_escopo.py` — o padrão "policy antes do LLM"
- `src/services/conversation_resume.py` — contexto para o bot voltar sem repetir
- `src/services/ai_tools.py:239` — o contrato que exige cadastro sempre
- `src/services/conversation_engine.py:37` — os 30 estados fundidos
- `docs/work/prd/019-pausa-explicita-do-bot.md` — substituído em parte (§9.1)
- `docs/work/prd/018-so-depilacao-a-laser.md` — a guarda determinística

---

## Status (preencher após conclusão)

- [x] Pendente
- [ ] Spec gerada
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
