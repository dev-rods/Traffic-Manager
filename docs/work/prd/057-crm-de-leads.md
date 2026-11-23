# PRD - 057 CRM de leads: estágio por lead, classificador e fila semanal

> Gerado na fase **Research** em 24/10/2026, a partir de um discovery com o André,
> como PRD 026. Guardado sem implementar; o número 026 foi usado pelo check-in.
> **Revisado em 21/11/2026** sobre a main de hoje (seção 2.4): as regras dos PRDs
> 039, 047, 053 e 054, posteriores ao discovery, têm precedência sobre o texto
> original onde conflitam.
> Vale como PRD e como spec de desenho: as decisões abaixo já foram tomadas.
> A fase Spec detalha arquivo por arquivo.

---

## 1. Objetivo

Dar à Essência (e a qualquer clínica) uma **fila de trabalho semanal** sobre os
leads: cada lead tem um **estágio** derivado dos dados ou do julgamento de um
modelo, a atendente **filtra por estágio e origem**, **corrige** o que o modelo
errou e **dispara mensagem em lote** para um grupo (ex.: todos que sumiram na
última semana). Objetivo de negócio: remarketing e reativação. Medir funil não é
objetivo agora, mas o histórico de transições fica gravado desde o dia 1 para
quando for.

---

## 2. Contexto

### 2.1 O que existe

- `scheduler.leads`: 552 leads da Essência desde 27/04/2026. Origens: 148
  `landing-page`, 398 `whatsapp` (número desconhecido que chamou a clínica),
  6 `harmonizacao`. 138 com `booked = true`.
- Campos de contato já gravados: `first_contact_at` e `first_contact_channel`
  (BOT ou HUMANO) quando nós abordamos; `conversation_started_at` quando o lead
  respondeu. A listagem (`src/functions/lead/list.py` +
  `src/services/status_da_conversa.py`) enriquece cada lead com quem conduz a
  conversa (sessão do DynamoDB) e se existe chat no WhatsApp (espelho
  `scheduler.whatsapp_chats`, sincronizado 1x por dia às 6h BRT).
- **MessageEvents** (DynamoDB, TTL 60 dias) guarda as mensagens dos dois lados,
  com `direction` INBOUND/OUTBOUND, `content` e autor. Inclui as mensagens que
  a atendente manda pelo celular (chegam como `fromMe`, metadata
  `autor: HUMANO`). É a fonte de direção da última mensagem e da transcrição.
- O espelho do z-api só diz que existe conversa, `last_message_at` e
  `unread_count`. O conteúdo não vem (`/chat-messages` devolve 400 nesta
  instância).
- Página `/leads` do painel: KPIs, filtro "Convertidos / Não convertidos",
  botões "Iniciar pelo bot" e "Marcar como contatado". **Esconde leads de
  origem `whatsapp`** de propósito (`excludeSource=whatsapp`): foi feita para
  medir o site contra o Google Ads.
- Disparo em lote: `BatchMessageModal` + `CampanhaDoBot` em `pages/pacientes`,
  sobre pacientes; o backend enfileira em `OutboundProcessor` e respeita bot
  pausado e janela de silêncio.
- Agenda: status `CONFIRMED`, `CANCELLED`, `NO_SHOW` (PRD 016). A recepção quase
  não marca falta.

### 2.2 O problema

Hoje a única pergunta que a tela responde é "agendou ou não". Para trabalhar a
base é preciso saber **em que pé está cada conversa** e **por que a pessoa não
agendou**, e isso não existe em lugar nenhum. Os leads de WhatsApp, 72% da base,
nem aparecem.

### 2.3 Decisões do discovery (24/10/2026)

| Decisão | Escolha |
|---|---|
| Para quem | Fila semanal da recepção (remarketing/reativação). Funil analítico depois. |
| Quem decide "não agendou" | Modelo classifica; atendente corrige à mão quando errar; motivo em frase curta. |
| Prazo de "parado" | 7 dias, configurável por clínica (`clinics.crm_dias_parado`). Vale para SUMIU e para o desfecho. |
| Escopo de origem | Todas, com filtro. Leads só de WhatsApp passam por **triagem** "é lead ou não" (fornecedor, pessoal, spam). Triagem cedo; desfecho após 7 dias. |
| Ações na fila | Ver, corrigir estágio, selecionar e disparar em lote. Sem notas e lembretes (fase 2 se precisar). |
| Falta e cancelamento | Só `NO_SHOW` marcado conta como FALTOU. CANCELOU é estágio próprio. Nada de inferir falta. |
| Arquitetura | Estágio gravado no lead, recalculado por job diário (A), mais log de transições append-only sem leitura (concessão de C). |

### 2.4 Revisão de 21/11/2026 (o que mudou na main desde o discovery)

| Mudança desde 24/10 | Efeito neste PRD |
|---|---|
| **PRD 054** (desfecho): remarcar deixa o agendamento antigo `CANCELLED` com `rescheduled_to_id` apontando para o novo; cancelar nas últimas 24 h antes da abertura da agenda vira `NO_SHOW` em silêncio. | Agendamento com `rescheduled_to_id` é remarcação, **não conta** para CANCELOU. O fato da agenda é decidido pelo **agendamento mais recente** que não seja remarcação (5.2). |
| **PRD 039** (silenciar contato): o silêncio vence tudo até o lembrete. Hoje a rota `POST /send` não consulta `contatos_silenciados`, nem quando é campanha. | O disparo em lote da fila (e o de pacientes, que é a mesma rota) passa a recusar contato silenciado com motivo `silenciado`. A regra posterior vence (8.3). |
| **PRD 047 e a dívida de auth**: STAFF tem sessão própria (`require_acesso` + `PERMISSOES_DO_STAFF`), ADMIN segue pela chave mestra. | O PATCH com `usuario_id` e a página `/crm` para STAFF saem como escrito. `GET /leads` passa a `require_acesso("crm.ler")`; a chave mestra continua entrando como ADMIN. `POST /send` continua ADMIN: STAFF vê e corrige a fila, mas não dispara (9). |
| **PRD 053** (pop-up da agenda): o painel passou a usar o `decide` do backend em vez de regra local. | Os estágios editáveis e os da agenda vêm de uma lista única no backend, espelhada em `pages/crm/estagios.ts` com teste de paridade. |
| **Sem endpoint de lote**: o disparo de pacientes é um `POST /send` por destinatário, feito pelo painel. | Item 8.3 sai do backend: o modal aceita qualquer destinatário com `id`, `name`, `phone`. |
| **`setup_database.py`** tem uma lista só, `SQL_STATEMENTS`, não `MIGRATIONS`. | Nomes na seção 10. |
| **Status da agenda** são só `CONFIRMED`, `CANCELLED`, `NO_SHOW`. Sessão feita = `CONFIRMED` com data passada. | AGENDOU cobre confirmado futuro e sessão já feita. |
| **Função limite** (PRD 055): `LIMITE_DE_FUNCOES = 104`, 86 hoje; dev com 418 recursos de 500. | Duas funções novas cabem. Rotas sem `cors:` (o teste proíbe). |
| **Dados de dev em 21/11**: Premium 61 leads de WhatsApp, Rods 4, Essência 6; `whatsapp_chats` com 4.332 linhas. | O backfill de dev é o teste de carga do job. |
| TTL do MessageEvents | Mantém 60 dias. Lead antigo sem transcrição entra como HISTORICO. |
| Tela | Página **nova** `/crm`. A `/leads` continua como está. |

#### Revisão de 22/11/2026 (três furos achados ao revisar a classificação em dev)

| Furo | Correção |
|---|---|
| AGUARDANDO_NOS era pegajoso: "ok, obrigada" ficava como "a bola está com a clínica" para sempre, porque o desfecho só rodava para SUMIU. Na Premium de dev eram 22 de 61. | AGUARDANDO_NOS parado há mais de N dias também vai ao modelo (6.2). |
| CANCELOU e FALTOU engoliam a volta do lead: mensagem nova depois do horário aparecia sem urgência. | Mensagem do lead posterior ao horário do agendamento devolve a decisão às regras de conversa (5.2). |
| Ramo morto: o desfecho aceitava INICIADA_SEM_RESPOSTA mas exigia fala do lead. Efeito: cadastro de 40 dias sem resposta pesava como o de ontem. | INICIADA_SEM_RESPOSTA parado há mais de N dias vira SUMIU (5.1); o gate deixa de citar INICIADA. |

---

## 3. Escopo

### Dentro do escopo

1. Colunas de estágio em `leads`, tabela `lead_stage_events`, coluna
   `crm_dias_parado` em `clinics`. Migrations idempotentes.
2. Módulo de **regras de estágio** (determinístico, testável sem I/O).
3. Módulo **classificador** (triagem e desfecho) via Anthropic API, Haiku 4.5.
4. Lambda agendada **`ClassificaLeads`** (diária, 7h BRT) com `dryRun`.
5. `GET /leads` com `stage=`, `source=` e totais por estágio.
6. `PATCH /leads/{leadId}/stage` para correção manual.
7. Disparo em lote aceitando `leadIds`.
8. Página `/crm` no painel: chips de estágio, filtros, lista, correção,
   seleção e disparo.
9. Backfill em prod: dryRun com distribuição para o André, depois real.
10. Testes unitários (backend e frontend) e roteiro E2E em dev.

### Fora do escopo

- Funil analítico, gráficos, tempo por estágio (o log já grava, ninguém lê).
- Notas livres e lembrete "voltar a falar em dd/mm".
- Inferir falta por ausência de registro de sessão.
- Mudar o TTL do MessageEvents.
- Alterar a página `/leads`.
- Classificar motivo para lead que nunca respondeu (não há decisão a ler).

---

## 4. Modelo de dados

### 4.1 `scheduler.leads` - colunas novas

| Coluna | Tipo | Valores |
|---|---|---|
| `stage` | VARCHAR(32) NULL | ver 5.1. NULL = ainda não processado |
| `stage_reason` | VARCHAR(120) NULL | frase curta; só em NAO_AGENDOU e NAO_E_LEAD |
| `stage_source` | VARCHAR(16) NULL | `REGRA`, `MODELO`, `MANUAL`, `HISTORICO` |
| `stage_updated_at` | TIMESTAMPTZ NULL | |
| `triagem_feita_em` | TIMESTAMPTZ NULL | marca que a triagem rodou (LEAD ou NAO_E_LEAD) |
| `desfecho_tentado_em` | TIMESTAMPTZ NULL | marca que o desfecho rodou (NAO_AGENDOU ou AINDA_ABERTO) |

CHECK em `stage` e `stage_source` com os valores fechados, via bloco
`DO $$ IF NOT EXISTS`. Índice `(clinic_id, stage)`.

### 4.2 `scheduler.lead_stage_events` - nova, append-only

| Coluna | Tipo |
|---|---|
| `id` | UUID PK |
| `clinic_id` | VARCHAR(100) NOT NULL |
| `lead_id` | UUID NOT NULL (FK leads) |
| `de` | VARCHAR(32) NULL |
| `para` | VARCHAR(32) NOT NULL |
| `fonte` | VARCHAR(16) NOT NULL |
| `motivo` | VARCHAR(120) NULL |
| `usuario_id` | UUID NULL (só MANUAL) |
| `criado_em` | TIMESTAMPTZ NOT NULL DEFAULT NOW() |

Índice `(lead_id, criado_em)`. Nenhum endpoint lê dela nesta entrega. Uma linha
por mudança efetiva de estágio ou de motivo; estágio igual não gera linha.
Tentativa de desfecho que volta `AINDA_ABERTO` também gera linha
(`para` = estágio atual, `motivo` = "ainda_aberto"), porque é a medida de erro
do classificador no futuro.

### 4.3 `scheduler.clinics`

`crm_dias_parado INTEGER NOT NULL DEFAULT 7`.

---

## 5. Regras de estágio

### 5.1 Estágios

Fila (ordem de exibição na tela):

1. `AGUARDANDO_NOS` - última mensagem é do lead
2. `SUMIU` - a conversa parou há mais de N dias: última mensagem nossa depois de
   o lead ter falado, ou só mensagens nossas (revisão de 22/11; antes
   INICIADA_SEM_RESPOSTA não envelhecia)
3. `INICIADA_SEM_RESPOSTA` - só mensagens nossas, há N dias ou menos
4. `SEM_CONVERSA` - nenhuma mensagem de nenhum lado
5. `EM_ANDAMENTO` - última mensagem é nossa há menos de N dias
6. `NAO_AGENDOU` - decidido pelo modelo ou pela atendente
7. `CANCELOU` - o agendamento mais recente foi cancelado (e não era remarcação)
   e o lead não escreveu depois do horário dele
8. `FALTOU` - o agendamento mais recente é `NO_SHOW` e o lead não escreveu
   depois do horário dele
9. `AGENDOU` - o agendamento mais recente é `CONFIRMED` (futuro ou sessão feita)

Fora da vista padrão: `NAO_E_LEAD`, e `stage_source = HISTORICO`.

### 5.2 Precedência

Avaliar nesta ordem; a primeira que casar vence:

```
FATO DA AGENDA  (AGENDOU | FALTOU | CANCELOU: o agendamento mais recente decide)
NAO_E_LEAD  (se stage atual é NAO_E_LEAD, fonte MODELO ou MANUAL)
MANUAL      (se stage_source = MANUAL, mantém o que está)
NAO_AGENDOU (se stage atual é NAO_AGENDOU, fonte MODELO)
SEM_CONVERSA
INICIADA_SEM_RESPOSTA
SUMIU
AGUARDANDO_NOS
EM_ANDAMENTO
```

- Fatos da agenda (FALTOU, CANCELOU, AGENDOU) vencem **inclusive** MANUAL e
  NAO_E_LEAD. Exceção única e proposital: agendar é fato, não julgamento.
- **Fato que não fecha a porta (revisão de 22/11):** CANCELOU e FALTOU ficam
  para trás quando a última mensagem é do lead e é **posterior à data e hora
  do agendamento**. Quem cancelou e perguntou "consigo remarcar?" é
  AGUARDANDO_NOS, não um cancelamento parado. AGENDOU não tem essa saída. O
  marco é o horário do agendamento porque a tabela não guarda quando foi
  cancelado; mensagem entre o cancelamento e a data ainda aparece como
  CANCELOU.
- **Qual fato (revisão 21/11, PRD 054):** agendamentos com `rescheduled_to_id`
  são remarcações e ficam de fora. Entre os que sobram, o de data e hora mais
  recentes decide: `CONFIRMED` → AGENDOU, `NO_SHOW` → FALTOU, `CANCELLED` →
  CANCELOU. Assim quem faltou e remarcou é AGENDOU, e quem remarcou três vezes
  não vira CANCELOU. O `NO_SHOW` silencioso das últimas 24 h conta como falta,
  como a 054 manda.
- MANUAL trava tudo o que é julgamento ou regra de conversa. Só sai por outra
  correção manual ou por fato da agenda.
- NAO_AGENDOU e NAO_E_LEAD (fonte MODELO) caem se chegar **mensagem nova do
  lead** depois de `stage_updated_at`: a regra reavalia e o desfecho pode rodar
  de novo quando voltar a parar.
- **Entrega do bot (PRD 058, 22/11):** o aviso de handoff ("vou confirmar com
  uma especialista") é OUTBOUND, mas não é resposta. Se a sessão segue entregue
  pelo bot e nenhuma pessoa da clínica falou depois, o lead é AGUARDANDO_NOS
  com o motivo "bot pediu ajuda em DD/MM e ninguém assumiu"; isso conta como
  fala do lead para CANCELOU/FALTOU, derruba NAO_AGENDOU do modelo e o job não
  pergunta o desfecho. Detalhes em `prd/058-handoff-do-bot-no-crm.md`.

### 5.3 Fonte da conversa

1. **MessageEvents**: consulta por `pk = CLINIC#{clinic}#PHONE#{telefone}`
   descendente, filtrando `direction IN (INBOUND, OUTBOUND)`, pegando a última
   mensagem e se existe alguma INBOUND. Usa `variantes_do_numero` como a
   listagem já faz. Para o classificador, as últimas 40 mensagens.
2. **Fallback, espelho z-api**: se não há evento mas `whatsapp_chats` tem o
   telefone, considera que houve conversa: `unread_count > 0` ->
   AGUARDANDO_NOS; senão EM_ANDAMENTO ou SUMIU pelo `last_message_at`. Sem
   transcrição: `stage_source = HISTORICO` quando `last_message_at` é anterior
   a (hoje - 60 dias); senão REGRA.
3. Sem nada: SEM_CONVERSA, a menos que `first_contact_at` esteja preenchido,
   caso em que é INICIADA_SEM_RESPOSTA.

"Nossa" mensagem = OUTBOUND de qualquer autor (bot, atendente, disparo). O
autor (BOT, HUMANO, SISTEMA) só entra para a entrega do bot (PRD 058).

---

## 6. Classificador (`src/services/classificador_de_lead.py`)

### 6.1 Triagem

- Quem: lead com `source = 'whatsapp'`, `triagem_feita_em IS NULL`, com pelo
  menos 3 mensagens INBOUND. Lead de `landing-page` e `harmonizacao` nunca
  passam (triagem considerada feita na criação).
- Entrada: transcrição (até 40 mensagens), nome da clínica e o que ela faz.
- Saída JSON: `{"classe": "LEAD" | "NAO_E_LEAD", "motivo": "<= 8 palavras"}`.
- Efeito: `NAO_E_LEAD` grava `stage`, `stage_reason`, `stage_source = MODELO`.
  `LEAD` só grava `triagem_feita_em`.

### 6.2 Desfecho

- Quem: lead em `SUMIU` ou `AGUARDANDO_NOS` parado há mais de N dias, com ao
  menos 1 mensagem INBOUND, `desfecho_tentado_em IS NULL` ou anterior à última
  mensagem do lead, transcrição disponível. (Revisão de 22/11: antes era
  `INICIADA_SEM_RESPOSTA`, que por definição não tem fala do lead e nunca
  disparava; e AGUARDANDO_NOS ficava preso em "ok, obrigada" para sempre. O
  prompt passa a citar o encerramento com agradecimento como razão.)
- Saída JSON: `{"classe": "NAO_AGENDOU" | "AINDA_ABERTO", "motivo": "<= 8 palavras"}`.
- Efeito: `NAO_AGENDOU` grava estágio com fonte MODELO. `AINDA_ABERTO` só
  grava `desfecho_tentado_em` e o evento de tentativa.

### 6.3 Regras comuns

- Modelo `claude-haiku-4-5-20251001`, `max_tokens` baixo, temperatura 0.
- Resposta que não é JSON válido ou classe fora do enum: descarta, loga com
  traceId, não marca como tentado (tenta na noite seguinte).
- Motivo truncado em 120 caracteres, sem quebra de linha.
- **Teto por execução**: `CRM_MAX_CHAMADAS_MODELO` (env, padrão 200) por
  invocação da Lambda, somando triagem e desfecho. Excedeu, loga e para; o
  resto fica para a próxima noite.
- Chave da API no SSM como o agente de conversa já usa. Sem chamada real nos
  testes unitários: o cliente é injetado.

---

## 7. Job `ClassificaLeads`

- `src/functions/lead/classifica_estagios.py`, interface em
  `sls/functions/lead/interface.yml`, `schedule: cron(0 10 * * ? *)` (7h BRT,
  1h depois do sync de conversas). Timeout 300s, 1024 MB.
- Payload opcional: `{"clinicId": "...", "dryRun": true, "maxChamadasModelo": 900}`.
  `dryRun` calcula e devolve a distribuição por estágio sem escrever nada.
  `maxChamadasModelo` sobe o teto só naquela invocação (backfill da primeira
  rodada; o cron usa o da env). O retorno separa `descartes` (resposta
  inválida do modelo) de `adiados` (o teto deixou para a próxima noite).
- Por clínica ativa: carrega leads; lê a última mensagem de cada um no
  MessageEvents (uma query por lead, `Limit` pequeno, em paralelo moderado);
  carrega agendamentos por telefone/paciente; aplica regras; roda triagem e
  desfecho dentro do teto; grava `stage*` e `lead_stage_events` só quando mudou.
- Uma clínica falhando não derruba as outras. Falha do modelo não impede a
  regra. Resumo no retorno: por clínica, contagem por estágio, chamadas ao
  modelo, descartes, erros.
- IAM: leitura no MessageEvents e nas sessões, RDS via env como as demais.

---

## 8. API

### 8.1 `GET /clinics/{clinicId}/leads` (existente, estendido)

- Novos query params: `stage=A,B,C` (múltiplos), `source=landing-page,whatsapp`
  (múltiplos). Convivem com `startDate`, `endDate`, `booked`, `excludeSource`,
  `limit`, `offset`.
- Resposta ganha `totals.por_estagio: {STAGE: n}` sobre o filtro de origem e
  período (não sobre o de estágio), para os chips.
- Cada lead devolve `stage`, `stage_reason`, `stage_source`,
  `stage_updated_at`, `dias_parado` (inteiro, desde a última mensagem) e
  `ultima_mensagem_de` (`LEAD` | `NOS` | null). Esses dois últimos vêm do
  cálculo já feito pela listagem, não de coluna.
- A página `/leads` não muda de comportamento.

### 8.2 `PATCH /clinics/{clinicId}/leads/{leadId}/stage` (novo)

- Body `{ "stage": "...", "reason": "..." }`. Papéis STAFF e ADMIN (entrar em
  `PERMISSOES_DO_STAFF`).
- Aceita só estágios de julgamento ou conversa: `NAO_AGENDOU`, `NAO_E_LEAD`,
  `EM_ANDAMENTO`, `SUMIU`, `AGUARDANDO_NOS`, `SEM_CONVERSA`,
  `INICIADA_SEM_RESPOSTA`. Recusa 400 com mensagem para `AGENDOU`, `CANCELOU`,
  `FALTOU` ("vem da agenda").
- Grava `stage_source = MANUAL`, evento com `usuario_id`. Devolve o lead.

### 8.3 Disparo em lote (revisado em 21/11)

- Não existe endpoint de lote: o painel faz um `POST /send` por destinatário
  com `phone` e `campanha`. O modal passa a aceitar qualquer destinatário com
  `id`, `name`, `phone`; os resultados são indexados por `id`. Nada muda no
  backend para isso.
- **Regra posterior que vence (PRD 039):** `POST /send` com `campanha` passa a
  recusar contato silenciado (409, `motivo: silenciado`), como já fazem o
  lembrete e a fila de saída. Vale para pacientes e leads, porque é a mesma
  rota. As recusas de hoje (bot pausado, janela de silêncio; humano e cooldown
  destravam) continuam.
- `POST /send` segue exigindo ADMIN. STAFF não dispara.

---

## 9. Painel: página `/crm`

- Rota `/crm`, item "CRM" no grupo WhatsApp da sidebar, para STAFF e ADMIN.
  STAFF vê, filtra e corrige; o botão de disparo só aparece para ADMIN, porque
  `POST /send` é ADMIN (2.4).
- **Topo**: chips de estágio na ordem da seção 5.1, cada um com contagem;
  "mais" abre `NAO_E_LEAD` e `HISTORICO`. Filtro de origem (multi) e período.
- **Lista**: nome, telefone, origem, estágio (badge) com motivo e ícone da
  fonte (robô MODELO, lápis MANUAL, relógio HISTORICO, nada para REGRA), última
  mensagem (quando e de quem), dias parado, agendamento quando houver.
  Ordenação padrão por `dias_parado` decrescente. Paginação como `/leads`.
- **Corrigir**: clicar no badge abre popover com os estágios editáveis e campo
  de motivo; salva via PATCH; invalida a query.
- **Selecionar e disparar**: checkbox por linha, "selecionar todos do filtro",
  botão "Disparar mensagem" reaproveitando `BatchMessageModal` com uma
  variante que recebe leads.
- 4 estados em toda busca. Named exports. TanStack Query para tudo. Design
  conforme `frontend/CLAUDE.md`.

---

## 10. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/scripts/setup_database.py` | modificar | colunas em `leads` e `clinics`, tabela `lead_stage_events`, CHECKs, índices na lista `SQL_STATEMENTS`; `CREATE TABLE` em sincronia |
| `scheduler/src/services/estagio_do_lead.py` | criar | regras puras da seção 5 |
| `scheduler/src/services/classificador_de_lead.py` | criar | triagem e desfecho, cliente injetável, teto |
| `scheduler/src/services/transcricao.py` | criar | leitura do MessageEvents (última mensagem, existe INBOUND, últimas 40) |
| `scheduler/src/functions/lead/classifica_estagios.py` | criar | Lambda do job com dryRun |
| `scheduler/src/functions/lead/list.py` + `lead_service.py` | modificar | filtros, totais por estágio, campos novos |
| `scheduler/src/functions/lead/atualiza_estagio.py` | criar | PATCH |
| `scheduler/src/functions/send/handler.py` | modificar | recusa `silenciado` quando há `campanha` (PRD 039) |
| `scheduler/src/utils/acesso.py` | modificar | permissão nova |
| `scheduler/sls/functions/lead/interface.yml` | modificar | `ClassificaLeads`, `AtualizaEstagioDoLead` |
| `scheduler/tests/unit/test_estagio_do_lead.py` etc. | criar | ver seção 12 |
| `frontend/src/types/index.ts` | modificar | `LeadStage`, campos novos |
| `frontend/src/services/leads.service.ts` | modificar | params, `patchStage` |
| `frontend/src/hooks/` | modificar | hooks de lista por estágio e de correção |
| `frontend/src/pages/crm/` | criar | `CrmPage.tsx`, componentes, testes |
| `frontend/src/layouts/AppLayout.tsx`, `App.tsx` | modificar | rota e menu |
| `tests/integration/057-crm-de-leads.md`, `tests/postman/...` | criar | pós-implementação |

---

## 11. Dependências e riscos

- **Dependências**: Anthropic API (chave já no SSM), MessageEvents e sessões
  (DynamoDB), espelho `whatsapp_chats`, agenda.
- **Risco: TTL 60 dias**. Lead antigo não tem transcrição; vira HISTORICO.
  Aceito pelo André em 24/10.
- **Risco: custo de modelo**. Mitigado pelo teto por execução e por classificar
  cada lead uma vez por tarefa.
- **Risco: variantes de telefone**. Reusar `variantes_do_numero`; a listagem já
  passou por isso.
- **Risco: duas fontes de "estado da conversa"**. A listagem calcula
  `conversation_status` na hora; o estágio é gravado. São coisas diferentes
  (quem conduz agora vs. em que pé a conversa está) e a tela mostra as duas sem
  misturar. Documentar no código.
- **Deploy**: migration em prod antes do deploy do `scheduler`; backfill em
  dryRun antes do real. Frontend via Vercel ao mergear.

---

## 12. Testes

- **Regras**: um caso por linha da seção 5.1; precedência (agendou vence
  manual; manual vence regra; mensagem nova derruba NAO_AGENDOU do modelo);
  fallback do espelho; HISTORICO por data; N dias vindo da clínica.
- **Classificador**: parse de JSON, enum inválido descartado, truncamento do
  motivo, teto, lead de site não passa na triagem, desfecho exige INBOUND.
- **Job**: dryRun não escreve; evento só quando muda; clínica com erro não
  bloqueia a próxima; resumo correto.
- **API**: `stage` múltiplo, `source` múltiplo, totais por estágio ignoram o
  filtro de estágio, PATCH recusa fato da agenda, PATCH exige papel.
- **Frontend (Vitest)**: chips com contagem e seleção, popover de correção
  chama o service e invalida, seleção em lote abre o modal com os leads, 4
  estados.
- **E2E em dev**: migration, job em dryRun, job real, conferir distribuição,
  corrigir um lead à mão, disparar para um grupo de 2 leads de teste.

---

## 13. Critérios de aceite

- [ ] Todo lead da Essência tem `stage` após o backfill; a soma dos estágios da
      vista padrão mais NAO_E_LEAD e HISTORICO é igual ao total.
- [ ] `/crm` filtra por qualquer combinação de estágio, origem e período.
- [ ] Corrigir um estágio à mão sobrevive ao job da noite seguinte.
- [ ] Um lead que agenda depois de corrigido à mão vira AGENDOU.
- [ ] Lead de WhatsApp que é fornecedor sai da vista padrão sem ação humana.
- [ ] Disparo para um grupo filtrado chega aos telefones certos e respeita as
      recusas existentes.
- [ ] Nenhuma mudança visível em `/leads`.
- [ ] `lead_stage_events` tem uma linha por mudança, inclusive as manuais.

---

## 14. Referências

- `CLAUDE.md`, `frontend/CLAUDE.md`
- PRD 016 (NO_SHOW), PRD 017 (conversão de agendamento), PRD 019 (pausa do bot)
- `scheduler/src/services/status_da_conversa.py` (por que o estado da conversa
  não é denormalizado, e por que o estágio é outra coisa)

---

## Status

- [x] Discovery concluído em 24/10/2026
- [x] Revisado sobre a main em 21/11/2026 (seção 2.4)
- [x] Spec gerada: `docs/work/spec/057-crm-de-leads.md` (revisada em 21/11)
- [x] Implementado em dev: 21/11/2026 (PR #243; migração aplicada, scheduler dev layer 207; smoke 16/16 pelo roteiro + browser 13/13); revisão da classificação em 22/11 (layer 209; Premium AGUARDANDO_NOS 22 → 11, NAO_AGENDOU 3 → 14)
- [x] Implementado em prod: 22/11/2026 (migração, scheduler prod layers 164 e 165, dryRun por clínica conferido pelo log, rodada real: 1.041 leads classificados, 540 chamadas ao modelo, 0 descartes; retenção de 90 d nos dois log groups)
- [x] Registrado em `TASKS_LOG.md`
