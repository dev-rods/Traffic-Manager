# PRD - 027 Lembrete de sessão: agenda do dia, bot que encaminha ao autoatendimento e confirmação

> Gerado na fase **Research** em 27/10/2026, a partir de um discovery com o André.
> Vale como PRD e como spec de desenho: as decisões abaixo já foram tomadas.
> A fase Spec detalha arquivo por arquivo.

---

## 1. Objetivo

Lembrar, pelo WhatsApp, todo paciente com sessão marcada em **um dia da agenda**,
primeiro por um botão no painel ("Lembrar agenda do dia") e depois por um gatilho
automático de antecedência, ligado por clínica. A mensagem é um **lembrete**, não
um pedido de confirmação, e **não menciona cancelar nem remarcar**: quem quer
sair da agenda planta a ideia sozinho. Se a pessoa pedir para cancelar ou
remarcar, o bot **não executa**: manda o link de "Meus agendamentos" do site da
clínica para ela resolver por conta própria. Quem responde positivamente fica
**Confirmado** na agenda; quem não responde fica **Pendente**, e a recepção vê
quem ligar na véspera.

---

## 2. Contexto

### 2.1 O que existe

- **Lembrete 24h latente.** `src/services/reminder_service.py` (tabela DynamoDB
  `scheduled-reminders`), `src/functions/reminder/processor.py` (cron de 15 min)
  e o template `REMINDER_24H` ("Responda OK para confirmar") existem, foram
  corrigidos em 06/10/2026 (fuso, cancelado, janela de silêncio), mas **nunca
  foram ligados**: a tabela de prod está vazia, `AppointmentService.completo()`
  não injeta `reminder_service`, nenhuma clínica tem o template. Memória:
  `project_lembrete_24h_nunca_ligado`.
- **Disparo em lote** (Pacientes > WhatsApp em lote): `POST /send` por telefone,
  com `campanha` que faz o bot assumir. Desde 19/10 destrava atendimento humano e
  cooldown; só bot pausado e janela de silêncio recusam (PRs #132 e #144).
- **Sobreposição de campanha** (`src/services/campanha.py`): modo gravado na
  sessão no ato do disparo, nunca inferido pelo modelo, com validade. É o molde
  da sobreposição de lembrete.
- **Site de agendamento** (`booking-site/`, repo neste monorepo): rotas `/`
  (Home, com "Meus agendamentos" via OTP por WhatsApp) e `/agendar`. Com domínio
  próprio da clínica (`clinics.custom_domain`, PRD 021) a raiz é a clínica; no
  domínio padrão é `/:clinicId`. Cancelamento próprio em
  `public/clinics/{id}/appointments/{appointmentId}/cancel` (PRD 024).
- **Bot cancela e remarca sozinho** quando há sessão marcada:
  `cancel_appointment`, `reschedule_appointment` em `ai_tools.py`, filtradas por
  skill via `TOOLS_DE_SESSAO_MARCADA` em `skills/__init__.py`.
- **Agenda do painel**: `AgendaPage`, `AgendaHeader`, `AgendaDoDia`,
  `AppointmentPopover` (com falta/NO_SHOW do PRD 016).
- `appointments.status` é `CONFIRMED | CANCELLED | NO_SHOW` e governa motor de
  horários, conversão offline e agenda. Não ganha quarto valor.

### 2.2 Decisões do discovery (27/10/2026)

| Decisão | Escolha |
|---|---|
| Unidade | **Um dia** da agenda de uma clínica. Todos os `CONFIRMED` do dia. |
| Quem atende depois | **O bot assume**, com regra nova: cancelar/remarcar vira link, não ferramenta. Dúvidas respondidas pelo FAQ como sempre. |
| Texto | Sem link e **sem citar cancelar ou remarcar** (gatilho). Reforça compromisso e pede um preparo pequeno (raspar, evitar sol). |
| Repetição | **Um lembrete por agendamento, nunca repetido.** Duas sessões no dia = duas mensagens. |
| Fora da janela | **Enfileirar** até o fim do silêncio. Bot pausado recusa com motivo. |
| Automático | Configuração por clínica **agora, desligada**: `lembrete_automatico`, `lembrete_antecedencia_horas` (24). |
| Antecedência | Relativa ao **início da agenda do dia** (primeiro agendamento confirmado), **lote único** para o dia. Sem cron de 15 min. |
| Sem link de autoatendimento | Clínica sem `custom_domain`: a sobreposição **não esconde** as ferramentas; o bot cancela e remarca como hoje. |
| Confirmação | Coluna nova `confirmado_em`, **não** mudança de `status`. Resposta positiva marca via ferramenta `confirm_attendance`; recepção marca/desmarca no popover. Antes do lembrete nada aparece. |

---

## 3. Escopo

### Dentro do escopo

1. Colunas em `appointments` (`lembrete_enviado_em`, `lembrete_status`,
   `lembrete_erro`, `confirmado_em`, `confirmado_por`) e em `clinics`
   (`lembrete_automatico`, `lembrete_antecedencia_horas`). Migrations
   idempotentes.
2. Template `LEMBRETE_SESSAO` (default + editável no painel). Remoção do
   `REMINDER_24H`.
3. Rotina `lembra_agenda(clinic, dia, send_at)` que seleciona e enfileira o
   lote na tabela `scheduled-reminders`.
4. Endpoint manual `POST /clinics/{clinicId}/agenda/{dia}/lembretes` (com
   `?simular=true` para a prévia de contagens) que acorda o processador.
5. Lambda horária `LembretesAutomaticos` para clínicas com
   `lembrete_automatico`.
6. `ReminderProcessor` passa a: ser acordado por invocação, rodar também por
   cron horário, gravar `lembrete_*` no agendamento e abrir a sobreposição de
   lembrete na sessão.
7. Sobreposição de lembrete no bot (`src/services/lembrete.py`): filtro de
   ferramentas, bloco de prompt com o link, ferramenta `confirm_attendance`.
8. `link_de_autoatendimento(clinic) -> Optional[str]`.
9. Painel: botão com prévia na agenda do dia, badge Pendente/Confirmado, estado
   do lembrete e ações de confirmar no popover, seção de configuração.
10. Testes unitários (backend e frontend) e E2E em dev.

### Fora do escopo

- Relatório de taxa de confirmação e de falta por lembrete (dados ficam
  gravados).
- Segunda mensagem de "não respondeu" na véspera.
- Lembrete por profissional ou por intervalo de dias.
- Confirmação por botão interativo do WhatsApp (o z-api cai em fallback
  numerado; texto livre basta).
- Link no domínio Vercel padrão. Só `custom_domain` conta como site disponível.
  Se quiser habilitar o padrão depois, é uma env var em
  `link_de_autoatendimento`.

---

## 4. Modelo de dados

### 4.1 `scheduler.appointments`

| Coluna | Tipo | Significado |
|---|---|---|
| `lembrete_enviado_em` | TIMESTAMPTZ NULL | quando a mensagem saiu (idempotência) |
| `lembrete_status` | VARCHAR(16) NULL | `ENFILEIRADO`, `ADIADO`, `ENVIADO`, `FALHOU` |
| `lembrete_erro` | VARCHAR(120) NULL | motivo legível quando `FALHOU` (ex.: "bot pausado") |
| `confirmado_em` | TIMESTAMPTZ NULL | paciente ou equipe confirmou presença |
| `confirmado_por` | VARCHAR(16) NULL | `PACIENTE`, `EQUIPE` |

CHECKs em `lembrete_status` e `confirmado_por` via `DO $$ IF NOT EXISTS`.
Índice parcial `(clinic_id, appointment_date) WHERE lembrete_enviado_at IS NULL`
para a seleção do lote. **Pendente** e **Confirmado** são derivados: lembrete
enviado e `confirmado_em` nulo = Pendente; `confirmado_em` preenchido =
Confirmado; sem lembrete = nada.

### 4.2 `scheduler.clinics`

`lembrete_automatico BOOLEAN NOT NULL DEFAULT FALSE`,
`lembrete_antecedencia_horas INTEGER NOT NULL DEFAULT 24`.

### 4.3 `scheduled-reminders` (DynamoDB, existente)

Um item por agendamento do lote, com `send_at` do lote, `appointment_id`,
`clinic_id`, `phone`, `tipo = LEMBRETE_SESSAO`. Cancelar o agendamento continua
cancelando o item pendente (`cancel_reminder`, já existe).

### 4.4 Template `LEMBRETE_SESSAO`

Default em `template_service.DEFAULT_TEMPLATES` (substitui `REMINDER_24H`):

> Oi {nome}! Sua sessão de {areas} na {clinica} está confirmada para {dia} às {hora}. Já estamos preparando tudo para você. Lembre de raspar a área no dia e evitar sol até lá. Até breve! 😊

Variáveis: `{nome}` (primeiro nome do `full_name` do agendamento, senão do
paciente), `{areas}` (nomes das áreas do agendamento, "e" antes da última),
`{clinica}` (`display_name` ou `name`), `{dia}` ("quinta, 06/11"), `{hora}`
("09:00"). Editável por clínica em `message_templates`, como
`POST_BOOKING_INSTRUCTIONS`. Teste literal garante que o default não contém
"cancel" nem "remarc".

---

## 5. Seleção e disparo do lote

### 5.1 `lembra_agenda(db, reminder_service, clinic, dia, send_at, simular=False)`

Em `src/services/lembrete_da_agenda.py`:

1. Seleciona `appointments` da clínica com `appointment_date = dia`,
   `status = 'CONFIRMED'`, `lembrete_enviado_em IS NULL` e
   `lembrete_status IS DISTINCT FROM 'ENFILEIRADO'` (não enfileira duas vezes),
   com telefone do paciente.
2. Separa: `enfileiraveis`, `ja_lembrados` (tem `lembrete_enviado_em`),
   `sem_telefone`.
3. Se `simular`, devolve só as contagens.
4. Senão, para cada enfileirável: `reminder_service.schedule_reminder(...)` com
   `send_at` e marca `lembrete_status = 'ENFILEIRADO'`. Devolve
   `{enfileirados, ja_lembrados, sem_telefone, send_at}`.

`send_at` já vem ajustado pelo chamador para o fim do silêncio quando cai dentro
dela (`business_hours.fim_do_silencio(clinic, quando)`), e a resposta carrega
`adiados_para` nesse caso.

### 5.2 Manual: `POST /clinics/{clinicId}/agenda/{dia}/lembretes`

- `require_acesso(event, "agenda.escrever")`. `dia` em `YYYY-MM-DD`, não pode
  ser passado.
- `?simular=true` devolve as contagens para a prévia do botão.
- Sem `simular`: `send_at = agora` (ou fim do silêncio), chama `lembra_agenda`,
  e **invoca o `ReminderProcessor`** (`lambda:InvokeFunction`, como
  `IniciarConversaPeloBot` já faz com o `OutboundProcessor`) para a entrega sair
  na hora.
- Resposta 200 com `{enfileirados, ja_lembrados, sem_telefone, adiados_para}`.

### 5.3 Automático: Lambda `LembretesAutomaticos`

- `schedule: rate(60 minutes)`. Para cada clínica com `lembrete_automatico`:
  para `dia` em hoje+1 .. hoje+3 (fuso da clínica): `inicio` = menor
  `start_time` dos `CONFIRMED` do dia; `send_at = inicio - antecedencia_horas`;
  se `agora >= send_at` e nenhum agendamento do dia foi lembrado ou enfileirado,
  chama `lembra_agenda(..., send_at=max(send_at, fim_do_silencio(agora)))`.
- Dia sem agendamento confirmado não gera nada. Agendamento criado depois do
  lote (ex.: encaixe de última hora) é pego na próxima hora se `send_at` já
  passou, porque a seleção é por agendamento sem lembrete, não por dia.
- Ligar e desligar é só a coluna; sem deploy.

### 5.4 `ReminderProcessor` (existente, ajustado)

- Gatilhos: invocação direta (manual) e `rate(60 minutes)` (lotes automáticos).
  O cron de 15 min sai.
- Para cada item vencido: recarrega o agendamento; se não é mais `CONFIRMED`,
  marca o item cancelado e `lembrete_status = NULL`; se bot pausado, `FALHOU`
  com "bot pausado"; se em silêncio, `adia` para o fim e `ADIADO`; senão renderiza
  `LEMBRETE_SESSAO`, envia, marca `ENVIADO` + `lembrete_enviado_em`, e abre a
  **sobreposição de lembrete** na sessão (6.1). Atendimento humano e cooldown
  não barram: a sobreposição libera o bot como o disparo em lote faz
  (`MOTIVOS_QUE_O_DISPARO_DESTRAVA`).
- Falha de envio: `FALHOU` com o erro do provider truncado.

---

## 6. A conversa depois do lembrete

### 6.1 Sobreposição (`src/services/lembrete.py`)

Molde de `campanha.py`: gravada na sessão no ato da entrega, nunca inferida.

```
session["lembrete"] = {"appointment_id", "dia", "hora", "areas", "expira_em"}
```

- `expira_em` = fim do dia da sessão, no fuso da clínica.
- `esta_vivo(session, agora) -> bool`.
- `ferramentas_a_remover(session, clinic, agora) -> frozenset`: devolve
  `{"reschedule_appointment", "cancel_appointment"}` quando a sobreposição está
  viva **e** `link_de_autoatendimento(clinic)` não é `None`; senão vazio. O
  filtro entra no mesmo ponto em que `skill.filtra` já poda as ferramentas por
  skill. Não é só prompt: a ferramenta não existe para o modelo.
- `bloco_de_prompt(session, clinic) -> str`, injetado quando viva:

  > Esta pessoa recebeu lembrete da sessão de {dia} às {hora} ({areas}). Se ela
  > responder confirmando que vai (ok, confirmado, estarei lá, joinha), use
  > `confirm_attendance` e agradeça em uma linha. Se quiser cancelar ou remarcar,
  > NÃO execute nada: envie o link {link} e diga que ela resolve em um minuto por
  > lá, com o mesmo número de WhatsApp. Se disser que não vai poder ir sem pedir
  > nada, pergunte se prefere remarcar ou cancelar e então envie o link. Dúvidas
  > sobre a sessão, preparo e endereço, responda normalmente.

  Sem link, a última frase sobre o link sai e o bloco diz que ela pode remarcar
  ou cancelar por aqui mesmo (ferramentas disponíveis).

### 6.2 Ferramenta `confirm_attendance`

Em `ai_tools.py`, disponível **só** com a sobreposição viva (entra pelo mesmo
filtro, ao contrário das outras duas). Grava `confirmado_em = NOW()`,
`confirmado_por = 'PACIENTE'` no `appointment_id` da sobreposição. Idempotente.

### 6.3 `link_de_autoatendimento(clinic) -> Optional[str]`

Em `src/services/autoatendimento.py`: `https://{custom_domain}/` quando
`clinics.custom_domain` está preenchido; senão `None`. Um lugar só, usado pelo
prompt e exposto ao painel na resposta do endpoint manual (para a prévia dizer
"o bot vai encaminhar ao site" ou "esta clínica não tem site; o bot cancela e
remarca pela conversa").

---

## 7. Painel

### 7.1 Agenda do dia

- Botão **"Lembrar agenda do dia"** em `AgendaHeader`, só com `agenda.escrever`,
  desabilitado para dia passado. Clique chama `?simular=true` e abre confirmação
  inline: "12 confirmados, 3 já lembrados, 1 sem telefone. Enviar para 8?" com
  a linha sobre o link (6.3). Confirmar chama o endpoint e mostra o resultado,
  inclusive "fora do horário: saem às 08:00".
- `AgendaDoDia` e `WeekGrid`: badge **Pendente** (âmbar) ou **Confirmado**
  (verde) só quando `lembrete_enviado_em` existe. Nada antes.
- `AppointmentPopover`: linha de estado do lembrete ("enviado às 09:12",
  "adiado para 08:00", "falhou: bot pausado", "não enviado"); ações "Marcar
  como confirmado" / "Desfazer confirmação" (grava `confirmado_por = 'EQUIPE'`),
  via `PATCH /clinics/{clinicId}/appointments/{id}` com `confirmado: true|false`.

### 7.2 Configurações

Seção **Lembrete de sessão** em `ConfiguracoesPage`: interruptor "Enviar
automaticamente", campo "Antecedência (horas) em relação ao primeiro horário do
dia" (padrão 24, mínimo 1, máximo 72), template `LEMBRETE_SESSAO` editável com
as variáveis listadas e pré-visualização com dados de exemplo. Aviso em uma
linha: "o texto não menciona cancelamento de propósito; o bot envia o link só
se a pessoa pedir".

---

## 8. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/scripts/setup_database.py` | modificar | colunas em `appointments` e `clinics`; `CREATE TABLE` em sincronia |
| `scheduler/src/services/template_service.py` | modificar | `LEMBRETE_SESSAO` no lugar de `REMINDER_24H`; renderização das variáveis |
| `scheduler/src/services/lembrete_da_agenda.py` | criar | seleção e enfileiramento do lote |
| `scheduler/src/services/lembrete.py` | criar | sobreposição: viva, ferramentas a remover, bloco de prompt |
| `scheduler/src/services/autoatendimento.py` | criar | `link_de_autoatendimento` |
| `scheduler/src/services/reminder_service.py` | modificar | item carrega `appointment_id`, `tipo`; `schedule_reminder` aceita `send_at` |
| `scheduler/src/functions/reminder/processor.py` | modificar | gatilho por invocação, grava `lembrete_*`, abre sobreposição, destrava como o disparo |
| `scheduler/src/functions/reminder/automaticos.py` | criar | Lambda horária |
| `scheduler/src/functions/appointment/lembretes_do_dia.py` | criar | endpoint manual com `simular` |
| `scheduler/src/functions/appointment/update.py` | modificar | `confirmado` no PATCH |
| `scheduler/src/services/ai_tools.py`, `skills/__init__.py`, `conversation_agent.py` | modificar | `confirm_attendance`, filtro da sobreposição, bloco de prompt |
| `scheduler/sls/functions/reminder/interface.yml`, `appointment/interface.yml` | modificar | crons, invoke, rota nova |
| `scheduler/tests/unit/test_lembrete_*.py` | criar | ver seção 10 |
| `frontend/src/types/index.ts`, `services/appointments.service.ts`, `hooks/useAppointments.ts` | modificar | campos e endpoint |
| `frontend/src/pages/agenda/components/AgendaHeader.tsx`, `AgendaDoDia.tsx`, `WeekGrid.tsx`, `AppointmentPopover.tsx` | modificar | botão, badges, ações |
| `frontend/src/pages/agenda/components/LembrarAgendaDoDia.tsx` | criar | prévia + confirmação inline |
| `frontend/src/pages/configuracoes/ConfiguracoesPage.tsx` | modificar | seção de lembrete |
| `tests/integration/027-lembrete-de-sessao.md`, `tests/postman/...` | criar | pós-implementação |

---

## 9. Dependências e riscos

- **Dependências**: z-api (envio), `scheduled-reminders` (DynamoDB), sessões,
  `business_hours`, template da clínica aprovado pela clínica antes de ligar.
- **Risco: tom do texto.** O default foi pensado para reforçar o compromisso.
  A clínica pode editar e reintroduzir "se precisar cancelar". O aviso na tela
  mitiga; não há trava.
- **Risco: bot cancelando quando não devia.** Mitigado por remover a ferramenta
  da chamada, não só por instruir. Teste trava isso.
- **Risco: duas sessões no dia** geram duas mensagens, por decisão. Se virar
  incômodo, agrupar por paciente é mudança só em `lembra_agenda`.
- **Risco: fuso.** `send_at` e `expira_em` calculados no fuso da clínica
  (`clinics.timezone`), como `hoje_na_clinica` já faz. Lambda roda em UTC.
- **Risco: Nobre sem WhatsApp integrado.** O envio funciona (z-api da clínica)
  mas não há bot: a sobreposição fica gravada e inerte. Sem efeito colateral.
- **Deploy**: migration em prod antes do deploy do `scheduler`; `REMINDER_24H`
  não tem linha em prod, remover é seguro. Ligar `lembrete_automatico` é
  decisão de produto por clínica.

---

## 10. Testes

- **Seleção do lote**: só `CONFIRMED` do dia; pula `lembrete_enviado_em` e
  `ENFILEIRADO`; separa sem telefone; `simular` não escreve; dois agendamentos
  do mesmo paciente = dois itens.
- **Automático**: `send_at = inicio - antecedencia`; dia sem confirmado não
  gera; já lembrado não repete; `send_at` dentro do silêncio vai para o fim; fuso
  da clínica.
- **Processador**: cancelado entre enfileirar e enviar é pulado; bot pausado =
  `FALHOU` com motivo; silêncio = `ADIADO`; sucesso grava `ENVIADO`,
  `lembrete_enviado_em` e abre a sobreposição com `expira_em` no fim do dia.
- **Sobreposição**: com link, `ferramentas_a_remover` tem as duas e o bloco tem
  o link; sem link, vazio e o bloco diz que resolve por aqui; expirada, nada;
  `confirm_attendance` só aparece viva e grava `confirmado_em`/`PACIENTE`.
- **Template**: variáveis renderizadas; default sem "cancel" e "remarc"
  (literal, de propósito); `{areas}` com "e" antes da última.
- **API**: endpoint exige `agenda.escrever`; dia passado recusa; segundo clique
  devolve `enfileirados = 0` e `ja_lembrados = N`; PATCH `confirmado` grava
  `EQUIPE` e desfaz.
- **Frontend (Vitest)**: botão abre prévia com as contagens; badge só após
  lembrete; popover marca e desfaz; configurações salvam.
- **E2E em dev**: 3 agendamentos para amanhã com números de teste; clicar;
  receber; responder "preciso remarcar" em um e ver o link; responder "ok" em
  outro e ver Confirmado na agenda; segundo clique não reenvia.

---

## 11. Critérios de aceite

- [ ] O botão envia um lembrete por agendamento confirmado do dia e nunca
      repete.
- [ ] O texto padrão não contém "cancelar" nem "remarcar" nem link.
- [ ] Paciente que pede para cancelar ou remarcar recebe o link e **nenhum**
      agendamento muda pelo bot, em clínica com `custom_domain`.
- [ ] Em clínica sem `custom_domain`, o bot cancela e remarca como hoje.
- [ ] Resposta positiva vira **Confirmado** na agenda; sem resposta fica
      **Pendente**; antes do lembrete, nada.
- [ ] Clique fora da janela enfileira e a tela diz a hora de saída.
- [ ] Com `lembrete_automatico` ligado, o lote do dia sai `antecedencia` horas
      antes do primeiro horário, de uma vez.
- [ ] Cancelar o agendamento cancela o lembrete pendente.

---

## 12. Referências

- `CLAUDE.md`, `frontend/CLAUDE.md`
- PRD 016 (NO_SHOW), PRD 019 (pausa do bot), PRD 021 (domínio customizado),
  PRD 024 ("Meus agendamentos"), PRD 026 (CRM; o estado Confirmado/Pendente é
  insumo futuro do estágio FALTOU)
- `scheduler/src/services/campanha.py` (molde da sobreposição)
- Memórias `project_lembrete_24h_nunca_ligado`, `project_disparo_segue_o_operador`

---

## Status

- [x] Discovery concluído em 27/10/2026
- [ ] Spec gerada: `spec/027-lembrete-de-sessao.md`
- [ ] Implementado em:
- [ ] Registrado em `TASKS_LOG.md`
