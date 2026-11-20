# PRD - 054 Regras de cancelamento, falta e remarcação, e o que os relatórios contam

> Gerado na fase **Research** em 20/11/2026. Use como input para a fase Spec.
> Fluxo: PRD → spec → PR → deploy **dev** → validação → deploy prod.

---

## 1. Objetivo

Uma regra só, aplicada nas três portas (painel, bot e site), para o desfecho de
um agendamento que não acontece como marcado:

| Situação | Desfecho |
|---|---|
| Cancelar com 24 h ou mais de antecedência | **Cancelamento** |
| Cancelar com menos de 24 h | **Falta** |
| Não comparecer, com ou sem aviso | **Falta** |
| Remarcar para outra data com 24 h ou mais | **Cancelamento** + agendamento novo, vinculados |
| Remarcar para outra data com menos de 24 h | **Falta** + agendamento novo, vinculados |
| Mudar áreas, horário, desconto ou valor **na mesma data** | edição do agendamento, sem desfecho, mesmo com menos de 24 h |

E a consequência que motiva tudo: **falta e cancelamento não entram em
relatório financeiro nem de presença.** Hoje a falta entra na receita.

---

## 2. Contexto

### 2.1 O que o sistema faz hoje

Os três status existem (`CONFIRMED`, `CANCELLED`, `NO_SHOW`), e remarcação é
`CANCELLED` com `rescheduled_to_id` apontando para o novo (PRD 035). Mas a
classificação é inteiramente manual e a remarcação quase nunca gera esse par:

| Porta | Cancelar | Remarcar data | Falta |
|---|---|---|---|
| Painel | modal → `CANCELLED`, qualquer antecedência | "Editar" muda a data **no mesmo registro** (`reschedule_appointment`); o cancelar oferece "Remarcar em vez de cancelar", que leva ao editar | botão "Marcar falta", manual |
| Bot | tool `cancel_appointment` → `CANCELLED` | tool `alterar_agendamento` → mesmo registro | não existe |
| Site "Meus agendamentos" | `CANCELLED` | `reschedule` → mesmo registro (PRD 035) | não existe |

Nenhuma porta olha a antecedência. O vínculo `rescheduled_to_id` só nasce
quando alguém cancela e cria outro em até 30 min (`reagendamento.vincula_antecessor`),
que era o caminho antigo; desde 01/10, **1** agendamento em prod tem esse
vínculo. As remarcações de verdade passam pela edição in-place e **somem da
história**: o dia original não guarda que houve uma sessão ali que não
aconteceu.

A `marca_no_show` tem, na docstring, a decisão de 04/10/2026 de **não** ter
regra de antecedência ("encodar uma política de 24 h seria inventar regra que
ninguém pediu"). Agora foi pedida; este PRD a reverte, registrando o porquê.

### 2.2 O bug dos relatórios

`clinic/reports.py` e `clinic/dashboard.py` somam receita e contam
agendamentos com `status != 'CANCELLED'`. Falta não é cancelado, então
**NO_SHOW entra em receita bruta, receita líquida, descontos concedidos, top
serviços e total de agendamentos.** Medido em prod (01/10 a 20/11/2026):

| Clínica | CONFIRMED | NO_SHOW (contadas como receita) | CANCELLED |
|---|---|---|---|
| Essência | 149 (R$ 40.850) | **48 (R$ 9.809)** | 67 |
| Nobre | 20 (R$ 2.564) | **2 (R$ 484)** | 10 |

A Essência tem quase 20% da "receita" do período vinda de gente que não veio.
`agenda_summary.py` e `caixa.py` já contam só `CONFIRMED`; `estado_comercial`
e o uploader de conversões também. É o relatório e o dashboard que estão fora.

### 2.3 O que não dá para inferir

Falta "sem aviso" hoje depende de alguém clicar. O check-in do iPad não serve
como prova de presença: desde 01/10 há **141** agendamentos `CONFIRMED` com
data passada e sem check-in, quase o total, porque a Nobre não usa o iPad e a
Essência nem sempre. Marcar falta automaticamente por ausência de check-in
marcaria falta em quem veio.

### 2.4 Decisões anteriores que este PRD toca

- **PRD 035** (reagendamento não é cancelamento): o espírito fica, o mecanismo
  muda. Remarcar continua **não** contando como cancelamento "puro" nos
  relatórios, mas passa a deixar o registro antigo com o desfecho da
  antecedência (cancelamento ou falta) e o vínculo para o novo, em vez de
  mover o mesmo registro.
- **PRD 027/053**: falta e confirmado pedem confirmação inline; nada muda.
- **Conversão offline**: `move_conversion` já acompanha a pessoa ao novo
  registro quando há vínculo; passa a ser o caminho padrão da remarcação.

---

## 3. Escopo

### Dentro do escopo

**A. Classificação pela antecedência (backend, uma função)**

- `desfecho.py` (novo): `classifica(inicio_da_sessao, agora_na_clinica) -> 'CANCELLED' | 'NO_SHOW'`,
  com a linha em **24 h antes do horário de início**, no fuso da clínica
  (`relogio.agora_na_clinica`). Sessão já passada também é `NO_SHOW`.
- `AppointmentService.cancel_appointment(appointment_id)` passa a aplicar a
  classificação: grava `CANCELLED` ou `NO_SHOW` conforme a antecedência. Quem
  chama (painel, bot, site) não decide; recebe o desfecho na resposta
  (`outcome`) para mostrar à pessoa.
- `marca_no_show` continua existindo para o "não veio" descoberto depois
  (manual, pelo painel). `desmarca_no_show` idem.

**B. Remarcação de data = desfecho + agendamento novo, vinculados**

- `AppointmentService.remarca(appointment_id, nova_data, nova_hora, ...)`
  (novo): cria o agendamento novo copiando áreas, desconto, duração fixada,
  observação e primeira visita do antigo; aplica `cancel_appointment` ao
  antigo (que classifica pela antecedência); grava `rescheduled_to_id` no
  antigo e `rescheduled_from_id` no novo (coluna nova, hoje só existe no
  retorno); move a conversão (`move_conversion`), o lembrete pendente, o
  pagamento vinculado (`payments.appointment_id`) e o link dos documentos
  (`consent_link_sent_at`) para o novo. Devolve os dois.
- `reschedule_appointment` (mesmo registro) **fica só para a mesma data**:
  mudar o horário dentro do dia. Mudar a data por ela passa a ser recusado
  (400 com mensagem), para nenhuma porta contornar a regra.
- Painel: no "Editar", mudar a data vira "Remarcar": o resumo do PRD 043 diz
  o desfecho do dia antigo ("fica registrado como **falta**, porque faltam
  menos de 24 h" ou "como cancelamento") e que nasce um agendamento novo. O
  modal de cancelar mantém "Remarcar em vez de cancelar" e passa a dizer, com
  o relógio, qual será o desfecho do cancelamento.
- Bot (`alterar_agendamento` com `new_date`) e site (`reschedule`) chamam
  `remarca`. As respostas ao paciente passam a dizer o desfecho quando é
  falta ("como faltam menos de 24 h, a sessão de hoje fica registrada como
  falta; a nova está marcada para…").
- `vincula_antecessor` (cancelar + criar em 30 min) continua como rede de
  segurança para quem ainda cancela e recria à mão.
- Horário original liberado: já acontece (motor de horários lê só
  `CONFIRMED`); teste que prova.

**C. Mesma data: edição, nunca desfecho**

- Horário, áreas, desconto, duração, observação e primeira visita na mesma
  data seguem pelo `PUT` de hoje, sem gerar `CANCELLED`/`NO_SHOW`, com
  qualquer antecedência. Teste que prova para < 24 h.

**D. Relatórios e dashboard contam só o que aconteceu ou vai acontecer**

- `reports.py`, `dashboard.py`: receita bruta, líquida, descontos, top
  serviços, série por dia e `total_appointments` passam a filtrar
  `status = 'CONFIRMED'`. `CANCELLED` e `NO_SHOW` saem de toda soma
  financeira.
- Novos campos no resumo (período e dia): `no_show_appointments`,
  `attendance_rate` = sessões realizadas (`CONFIRMED` com data passada) ÷
  (realizadas + `NO_SHOW`), e `cancelled`/`rescheduled` como já existem.
  Painel: card "Faltas" e "Presença" em Relatórios; "Hoje" no dashboard
  mostra faltas do dia.
- `caixa.py`, `agenda_summary.py`, `estado_comercial`, uploader: já corretos;
  teste de guarda que varre os handlers de relatório procurando
  `status != 'CANCELLED'` em soma de dinheiro (o padrão que deixou a falta
  entrar), no estilo de `test_prontuario_nao_toca_o_comercial`.

**E. Textos e documentação**

- Mensagens do bot e do site para cancelar/remarcar com menos de 24 h.
- Docstring de `marca_no_show`: a decisão de 04/10 foi revertida em 20/11
  pelo André, e por quê.

### Fora do escopo

- Falta automática por ausência de check-in (não é prova de presença, §2.3).
- Cobrar a falta, multa ou política comercial de no-show.
- Backfill: remarcações passadas feitas in-place não têm o registro antigo
  para reconstruir; faltas antigas já saem da receita com o filtro novo.
- Mudar o `status` para um quarto valor ("RESCHEDULED"): PRD 035 decidiu que
  não, e a razão (motor de horários, lembretes e uploader leem o valor puro)
  continua valendo.
- Avisar a paciente quando a recepção remarca (PRD futuro, desde o 043).

---

## 4. Decisões (para o André confirmar ou derrubar no spec)

1. **A linha das 24 h é contada até o horário de início da sessão, no fuso da
   clínica.** Alternativa: até a meia-noite do dia. Início é o que a paciente
   combinou; "até meia-noite" daria 23 h de antecedência para uma sessão às
   23h59 e 0 h para uma às 00h01.
   *Proposta: horário de início.*
2. **O painel segue a mesma regra automática, sem sobrepor.** Cancelar com 20 h
   no painel vira falta, igual ao bot e ao site. Alternativa: deixar a
   recepção trocar o desfecho com motivo ("desmarcou por doença"). Ela ainda
   pode corrigir depois: "Desmarcar falta" existe, e cancelar em seguida vira
   cancelamento só se ainda houver 24 h, então na prática a correção seria
   "desmarcar falta" e deixar como CONFIRMED até marcar de novo.
   *Proposta: sem sobreposição; a recepção vê o desfecho antes de confirmar.*
3. **Remarcar cria um agendamento novo e encerra o antigo**, revertendo o
   mecanismo in-place do PRD 035. Custo: pagamento, link dos documentos,
   lembrete e conversão têm de ser movidos para o novo (lista em §3.B). Ganho:
   o dia original guarda a sessão que não aconteceu, com o desfecho certo e o
   vínculo. O relatório continua **não** contando a remarcação como
   cancelamento puro (os fragmentos de `reagendamento.py` já separam).
   *Proposta: registro novo + vínculo nos dois sentidos.*
4. **Falta "sem aviso" continua manual**, pelo botão do painel, até existir
   uma prova de presença que a Nobre também tenha. Para não esquecer, o
   dashboard ganha "sessões de ontem sem desfecho" (CONFIRMED passado, sem
   check-in nem registro de sessão) como lembrete à recepção.
   *Proposta: manual, com lembrete no dashboard.*
5. **Receita e presença contam só `CONFIRMED`.** Receita futura (sessões
   marcadas ainda por vir) continua entrando no período, como hoje; o que sai
   é falta e cancelamento. Alternativa: separar "realizado" de "previsto".
   *Proposta: só CONFIRMED, com "Faltas" e "Presença" como cards novos; a
   separação realizado/previsto fica para um PRD de relatórios.*
6. **Site e bot avisam o desfecho quando é falta.** Quem cancela às 10 h para
   uma sessão às 15 h ouve que fica registrado como falta. Alternativa: aplicar
   em silêncio.
   *Proposta: avisar, em uma frase, sem tom de cobrança.*
7. **Mesma data com menos de 24 h: edição livre**, como o André escreveu.
   Inclui mudar o horário para mais tarde no mesmo dia.
   *Proposta: sim.*

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/desfecho.py` (+test) | criar | `classifica(inicio, agora)`; `LIMITE = 24h` |
| `scheduler/src/services/appointment_service.py` | modificar | `cancel_appointment` classifica e devolve `outcome`; **novo** `remarca(...)`; `reschedule_appointment` recusa mudança de data; `marca_no_show` docstring |
| `scheduler/src/scripts/setup_database.py` | modificar | `appointments.rescheduled_from_id UUID` (migration idempotente + CREATE TABLE) |
| `scheduler/src/functions/appointment/update.py` | modificar | `status: CANCELLED` devolve o desfecho; `date` diferente → `remarca` e devolve os dois registros |
| `scheduler/src/functions/appointment/list.py` | modificar | expõe `rescheduled_from_id` |
| `scheduler/src/functions/public_booking/cancel_appointment.py`, `reschedule_appointment.py` | modificar | chamam o serviço novo; resposta com `outcome` e texto |
| `scheduler/src/services/ai_tools.py` | modificar | `cancel_appointment` e `alterar_agendamento` (com `new_date`) devolvem `outcome`; texto da resposta |
| `scheduler/src/services/lead_service.py` | verificar | `move_conversion` chamado pela remarcação |
| `scheduler/src/services/checkin.py` / pagamento | modificar | mover `payments.appointment_id` na remarcação |
| `scheduler/src/functions/clinic/reports.py`, `dashboard.py` | modificar | filtros `= 'CONFIRMED'` em dinheiro e contagem; `no_show_appointments`, `attendance_rate`, "sem desfecho ontem" |
| `scheduler/tests/unit/test_relatorio_nao_conta_falta.py` | criar | guarda por regex sobre os handlers de relatório + casos positivos |
| `scheduler/tests/unit/test_desfecho.py`, `test_remarcacao.py`, ajustes em `test_reagendamento*.py`, `test_falta*.py` | criar/modificar | |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx`, `ResumoDaAlteracao`, `lib/alteracaoDeAgendamento.ts` | modificar | mudar data = remarcar: aviso do desfecho e do registro novo |
| `frontend/src/pages/agenda/components/CancelAppointmentModal.tsx` | modificar | diz o desfecho ("vai contar como falta: menos de 24 h") |
| `frontend/src/lib/desfecho.ts` (+test) | criar | a mesma conta das 24 h para o texto, com o fuso da clínica |
| `frontend/src/pages/relatorios/RelatoriosPage.tsx`, `pages/dashboard/*` | modificar | cards "Faltas", "Presença", "Sem desfecho ontem" |
| `frontend/src/types/index.ts` | modificar | `rescheduled_from_id`, campos novos do resumo, `outcome` nas respostas |
| site público (`booking-site`, se aplicável) | modificar | texto do desfecho ao cancelar/remarcar |
| `scheduler/tests/integration/054-desfecho.md` | criar | roteiro |

Deploy: backend primeiro. Migration pequena (`rescheduled_from_id`).
**Sem Lambda nova** (stack em 494/500).

---

## 6. Dependências e riscos

- **Fuso da clínica**: a conta das 24 h usa `clinics.timezone`; sem ele,
  `America/Sao_Paulo`, como o lembrete.
- **Mover vínculos na remarcação** é a parte com mais superfície: pagamento
  (um pago no antigo tem de aparecer no novo, senão o Caixa mostra "estorno
  pendente" para uma sessão que vai acontecer), lembrete (cancelar o antigo,
  o novo entra pelo lote do dia), conversão (`move_conversion` já existe),
  documentos (`consent_link_sent_at` é por agendamento). Cada um com teste.
- **Registro de sessão** (`patient_session_records.appointment_id`): o
  registro técnico fica no agendamento em que a sessão de fato aconteceu;
  remarcar antes da sessão não tem registro a mover. Conferir na spec se
  algum registro aponta para agendamento `CANCELLED`/`NO_SHOW` (não deveria:
  `patient_record/create.py` recusa).
- **Bot**: a tool `alterar_agendamento` hoje devolve um `appointment_id` só;
  passar a devolver o novo exige ajustar a sessão de atendimento que guarda o
  id do agendamento em curso.
- **Relatórios mudam de número**: a receita da Essência no mês cai o valor
  das faltas. É o objetivo, mas avisar antes de ligar em prod.
- **Decisão 2 pode incomodar a recepção** em casos legítimos (doença). O
  caminho de correção existe (desmarcar falta); documentar no roteiro.
- **PRD 035** e `test_reagendamento*`: parte dos testes assume o in-place para
  data; serão reescritos, não apagados.

---

## 7. Critérios de aceite

- [ ] Cancelar pelo painel, bot e site com 24 h ou mais grava `CANCELLED`;
      com menos, `NO_SHOW`; a resposta diz qual.
- [ ] Remarcar para outra data pelas três portas: antigo com o desfecho da
      antecedência e `rescheduled_to_id`; novo `CONFIRMED` com
      `rescheduled_from_id`, mesmas áreas/desconto/duração; conversão,
      pagamento, documentos e lembrete movidos; horário antigo livre.
- [ ] Mudar horário, áreas, desconto ou valor na mesma data, com menos de
      24 h, não gera `CANCELLED` nem `NO_SHOW` nem registro novo.
- [ ] `reschedule_appointment` com data diferente é recusado.
- [ ] Relatórios e dashboard: nenhuma soma de dinheiro inclui `NO_SHOW` ou
      `CANCELLED`; teste de guarda falha se `status != 'CANCELLED'` voltar a
      uma soma.
- [ ] Resumo traz faltas e taxa de presença; o painel mostra.
- [ ] Remarcação não conta como cancelamento puro (fragmentos de
      `reagendamento.py`).
- [ ] Textos do bot e do site dizem o desfecho quando é falta.
- [ ] pytest, vitest, build e lint verdes; roteiro em dev e prod.

---

## 8. Referências

- PRD 035 (reagendamento não é cancelamento), PRD 027 (falta/confirmado),
  PRD 043 (resumo da alteração), PRD 053 (confirmação inline).
- `scheduler/src/services/reagendamento.py` (fragmentos de contagem),
  `appointment_service.marca_no_show` (docstring com a decisão de 04/10/2026).
- `infra/src/functions/conversions/uploader.py` (por que falta importa para a
  conversão).

---

## Status (preencher após conclusão)

- [ ] Pendente
- [ ] Spec gerada: `spec/054-regras-de-cancelamento-falta-e-remarcacao.md`
- [ ] Implementado em dev: (data)
- [ ] Implementado em prod: (data)
- [ ] Registrado em `TASKS_LOG.md`
