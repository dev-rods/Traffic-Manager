# PRD - 060 Revisão do 056: "remarcar ou marcar mais uma?" para qualquer sessão futura, e link direto para "Meus agendamentos"

> Gerado na fase **Research** em 23/11/2026. Use como input para a fase Spec.
> Revisa o PRD 056 (uma sessão por mês). Nasce de três casos reais da Essência em 23/11/2026.

---

## 1. Objetivo

Dois ajustes no autoatendimento, nas três portas (site, bot, painel):

1. **Quem já tem sessão futura e marca outra data é perguntado se quer remarcar
   ou marcar mais uma**, mesmo quando a nova data cai em **outro mês**. Hoje a
   pergunta só existe no mesmo mês (PRD 056); em outro mês o sistema cria a
   segunda em silêncio, e a paciente que queria remarcar fica com duas sessões
   até a recepção perceber.
2. **O site ganha um link que abre direto "Meus agendamentos"** (remarcar e
   cancelar). O bot e a recepção passam a mandar esse link quando a pessoa
   quer mexer numa sessão, em vez da raiz do site, que abre no fluxo de marcar.

A regra do mês do PRD 056 não muda: no mesmo mês continua sendo sempre
remarcação, sem opção de "mais uma". O que muda é que **outro mês deixa de
passar em silêncio**: passa com uma pergunta.

---

## 2. Contexto

### 2.1 Os casos de 23/11/2026 (Essência)

Três relatos da clínica no mesmo dia. Dados conferidos em prod, só leitura
(banco + CloudWatch); telefones e nomes ficam fora deste documento.

| Caso | O que a paciente queria | O que aconteceu | Causa |
|---|---|---|---|
| 1 | Remarcar | Remarcou 3 vezes pelo site em 17 min, cada uma cancelando a anterior (correto). A recepção, achando que havia duplicata, cancelou pelo painel a única sessão válida. A paciente ficou sem sessão. | Nenhum defeito no backend. Hipótese: tela da agenda sem recarregar (o painel só refaz a busca quando a própria atendente mexe em algo). |
| 2 | Remarcar 25/11 para dezembro | Escreveu "vou precisar remarcar"; a recepção mandou o link raiz do site; ela **criou um agendamento novo** em 09/12. Como dezembro é outro mês, o site não avisou nem substituiu. O 25/11 ficou vivo, o lembrete saiu, ela respondeu "remarquei pro dia 9" e a recepção cancelou à mão. | Regra do PRD 056: outro mês passa em silêncio. |
| 3 | Cancelar | Respondeu ao lembrete "não vou poder comparecer". O bot (código anterior ao PRD 059) mandou o link raiz. Ela: "não consigo desmarcar pelo link". O site não registrou nenhum pedido de código para esse número nesse intervalo: ela não achou "Meus agendamentos". Dois minutos depois o PRD 059 entrou em prod e o bot cancelou direto. | "Meus agendamentos" é um botão no cabeçalho; o link raiz abre o fluxo de marcar. |

### 2.2 Medição em prod (60 dias até 23/11/2026, só leitura)

Agendamentos criados (sem vínculo de remarcação) enquanto o mesmo paciente já
tinha outra sessão CONFIRMED futura **em outro mês**, na mesma clínica:

| Clínica | Casos | Antiga continua confirmada | Antiga cancelada à mão em até 3 dias |
|---|---|---|---|
| Essência | 8 | 5 | 2 (os casos 2 e 3 acima, no mesmo dia do relato) |
| Nobre | 1 | 0 | 0 (a antiga virou remarcação por outro caminho) |

Leitura: o volume é pequeno, mas a consequência de cada erro é alta (lembrete
indevido, horário bloqueado, retrabalho da recepção, e no caso 1 uma paciente
sem sessão). As 5 que "continuam confirmadas" podem ser antecipação legítima
ou duplicatas ainda não percebidas; a pergunta resolve os dois lados.

### 2.3 O que o sistema faz hoje

| Porta | Mesmo mês | Outro mês | Mexer numa sessão existente |
|---|---|---|---|
| Site | 409 `SAME_MONTH_APPOINTMENT` com a sessão existente; diálogo "será substituída, confirmar?"; `substituir: true` faz o `remarca` (PRD 056). | Cria a segunda sem avisar. | Só pelo botão **Meus agendamentos** no cabeçalho (`BookingChrome.tsx`), que abre o modal `MyAppointmentsModal` (código por WhatsApp, depois remarcar inline ou cancelar). Não há URL que abra isso. |
| Bot | `book_appointment` recusa e manda o modelo avisar e usar `alterar_agendamento` (`_recusa_segunda_sessao`, PRD 056 C). | Cria e devolve ao modelo "diga que a anterior continua marcada". Skill `paciente_com_horario` item 3 repete isso. | Remarcar na janela do lembrete vai pelo **link raiz** (`lembrete.bloco_de_prompt`, PRD 059). Cancelar o bot faz direto (PRD 059). |
| Painel | 409 com a sessão existente; modal `ConflitoDoMes` com Confirmar / Voltar / Manter as duas (só ADMIN, com motivo). | Cria a segunda sem avisar. | A recepção manda o link raiz do site à mão quando a paciente quer remarcar. |

Em código, a fonte única da regra é `AppointmentService.sessao_no_mesmo_mes`
(PRD 056 A), filtrada por `date_trunc('month', ...)`.

### 2.4 Decisões anteriores que este PRD toca

- **PRD 056, decisão 2**: "mês diferente nunca bloqueia (antecipar reserva é
  legítimo)". Mantida: antecipar continua possível. Só deixa de ser silencioso.
- **PRD 056, decisão 5**: o bot nunca cria duas no mesmo mês. Mantida.
- **PRD 059**: na janela do lembrete, remarcar vai pelo link. Mantida; o link
  passa a ser o de "Meus agendamentos".
- **PRD 035**: cancelar e marcar de novo é remarcação (vínculo). Mantida; é o
  que o caso 3 acabou produzindo pelo caminho certo.

---

## 3. Escopo

### Dentro do escopo

**A. Backend: a pergunta para qualquer sessão futura (fonte única)**

- `AppointmentService` passa a distinguir dois conflitos ao **criar**:
  - `SessaoNoMesmoMes` (existe): sessão CONFIRMED futura no mesmo ano-mês da
    data alvo. Comportamento do PRD 056, sem mudança.
  - **`OutraSessaoFutura`** (novo): nenhuma no mesmo mês, mas existe sessão
    CONFIRMED futura em **outro mês**. Carrega a mesma carga do primeiro (id,
    data, hora, áreas da existente, a mais próxima).
- A criação com `OutraSessaoFutura` só acontece com uma escolha explícita no
  pedido: **`remarcar_a_existente: true`** (vira o `remarca` da 054 com o
  carrinho novo, exatamente como `substituir_mesmo_mes` faz hoje) ou
  **`mais_uma: true`** (cria a segunda, como hoje). Sem nenhuma das duas, a
  resposta é o conflito. Fuso da clínica, variantes do número, mesma clínica,
  como no 056.
- `remarca` (mover a data) para outro mês continua passando sem pergunta: já é
  uma remarcação, a antiga é a que está sendo movida.
- "Mais uma" não pede ADMIN nem motivo: não quebra a regra do mês, é só a
  confirmação de que a pessoa quer antecipar. Legado com mais de uma futura em
  outros meses: a carga traz a mais próxima; com `mais_uma` cria; com
  `remarcar_a_existente` remarca a mais próxima.
- Guarda de teste: a consulta de "sessão futura em outro mês" vive só no
  serviço; site, bot e painel não reimplementam.

**B. Site**

- `POST public/.../appointments` devolve 409 com código novo
  **`OTHER_MONTH_APPOINTMENT`** e `existing` (mesmo formato do
  `SAME_MONTH_APPOINTMENT`). Aceita `remarcarExistente: true` ou `maisUma:
  true` no corpo.
- Diálogo novo (irmão do `ConflitoDoMes` do site), texto curto no tom do 056:
  "Você já tem uma sessão em **{data} às {hora}**. O que você quer fazer?"
  Botões: **Remarcar essa sessão para {nova data}** (chama com
  `remarcarExistente`), **Marcar mais uma** (chama com `maisUma`), Voltar.
  Link "Falar no WhatsApp" como no 056. Sucesso: "Agendamento remarcado!" ou
  "Agendamento confirmado!" conforme a escolha.
- **Link direto para "Meus agendamentos"**: `BookingChrome` lê a query string
  e abre o modal quando a URL vier com **`?meus=1`** (nome definitivo na
  spec). Fechar o modal limpa o parâmetro. Vale nas duas árvores (domínio
  próprio e `/:clinicId`). Ex.: `https://{custom_domain}/?meus=1`.

**C. Bot**

- `book_appointment` com sessão futura em outro mês deixa de criar direto:
  devolve ao modelo a sessão existente e a instrução "pergunte se ela quer
  remarcar a sessão de {data} para {nova data} ou marcar mais uma; só chame de
  novo com a escolha". A tool ganha o parâmetro **`mais_uma`** (bool), que o
  modelo só manda depois da resposta explícita da pessoa. Remarcar é
  `alterar_agendamento`, como sempre. Mesmo mês: sem mudança (PRD 056 C).
- Skill `paciente_com_horario` item 3: "Em outro mês pode marcar outra:
  pergunte e confirme as áreas como sempre, e diga que a anterior continua
  marcada" passa a "Em outro mês, pergunte primeiro se é remarcação da sessão
  de {data} ou mais uma sessão; remarcação é alterar_agendamento, mais uma é
  book_appointment com mais_uma=true". Conferir o prompt da clínica no banco
  (não é o default do código).
- `autoatendimento` ganha **`link_de_meus_agendamentos(clinic)`** =
  `link_de_autoatendimento(clinic) + "?meus=1"`. `lembrete.bloco_de_prompt`
  (PRD 059) e qualquer outro ponto que mande a paciente remarcar pelo site
  passam a usar esse link. O link de **marcar** (`bloco_do_site`, PRD 046)
  continua sendo a raiz.

**D. Painel**

- Criar para outro mês com sessão futura devolve 409 `OTHER_MONTH_APPOINTMENT`
  com a existente. O `CreateAppointmentModal` reaproveita o `ConflitoDoMes`
  com título e botões próprios: "{nome} já tem sessão em {data} às {hora}."
  **Remarcar essa sessão** / **Marcar mais uma** / Voltar. Sem exigir ADMIN
  nem motivo para "mais uma" (ver A). O `EditAppointmentModal` ao mover data
  não muda (é remarcação).
- `AppointmentPopover`: botão **Copiar link de remarcação** que copia o link
  de "Meus agendamentos" da clínica (só aparece com `custom_domain`). É o que
  a recepção manda quando a paciente pede para remarcar pelo WhatsApp.

**E. Docs e testes**

- Roteiro `scheduler/tests/integration/060-...md` (site, bot, painel; nos
  casos que passam pelo envio, só com número combinado com o André, ver PRD
  059 §Status). Postman do `create` público com os dois corpos novos. Unit
  tests: outro mês sem flag = conflito; com `mais_uma` cria; com
  `remarcar_a_existente` remarca e vincula; mesmo mês continua
  `SessaoNoMesmoMes`; `remarca` para outro mês passa; link `?meus=1` abre o
  modal e fechar limpa a URL.
- Atualizar `booking-site/CLAUDE.md`, o PRD 056 (ponteiro "Revisto pelo PRD
  060") e o PRD 059 (link do lembrete).

### Fora do escopo

- **Recarga automática da agenda do painel** quando algo muda pelo site ou
  pelo bot (hipótese do caso 1). Problema real, PRD próprio: envolve
  polling/foco e toca todas as telas, não só a agenda.
- Limitar sessões por serviço ou por intervalo em dias (fora no 056, continua
  fora).
- Trocar o modal de "Meus agendamentos" por uma página própria.
- Parte C do PRD 059 (pedido de saída em conversa humana vira tarefa).

---

## 4. Decisões (confirmadas pelo André em 23/11/2026: as cinco propostas)

1. **Outro mês passa a perguntar, nas três portas**, sem exigir ADMIN para
   "mais uma". *Proposto: sim. É pergunta, não bloqueio; a decisão 2 do 056
   (antecipar é legítimo) fica de pé.*
2. **O bot pergunta antes de criar em outro mês** e só cria com a resposta
   explícita (`mais_uma`). *Proposto: sim. Custa um turno a mais só para quem
   já tem sessão futura.*
3. **Nome e forma do link direto**: query `?meus=1` na raiz, em vez de rota
   `/meus-agendamentos`. *Proposto: query. A rota exigiria duplicar a Home e
   o modal já existe no cabeçalho de todas as telas.*
4. **Texto da pergunta no site**: "Você já tem uma sessão em {data} às
   {hora}. O que você quer fazer?" com dois botões de ação. *Proposto: esse,
   na versão curta como o 056.*
5. **Botão "Copiar link de remarcação" no popover do painel**: entra neste
   PRD ou fica para a recepção usar o link à mão? *Proposto: entra. É pequeno
   e é o que a recepção faz hoje de cabeça (caso 2).*

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/appointment_service.py` | modificar | `OutraSessaoFutura`, consulta de sessão futura em outro mês, `create_appointment(remarcar_a_existente=, mais_uma=)` |
| `scheduler/src/functions/public_booking/create_appointment.py` | modificar | 409 `OTHER_MONTH_APPOINTMENT`; corpo `remarcarExistente` / `maisUma` |
| `scheduler/src/functions/appointment/create.py` | modificar | mesmo 409 e corpo para o painel |
| `scheduler/src/services/ai_tools.py` | modificar | `book_appointment` em outro mês devolve a pergunta; parâmetro `mais_uma` |
| `scheduler/src/services/skills/__init__.py` | modificar | item 3 de `paciente_com_horario` |
| `scheduler/src/services/autoatendimento.py` | modificar | `link_de_meus_agendamentos` |
| `scheduler/src/services/lembrete.py` | modificar | bloco do lembrete usa o link de "Meus agendamentos" |
| `booking-site/src/layouts/BookingChrome.tsx` | modificar | abre o modal pela query `?meus=1` e limpa ao fechar |
| `booking-site/src/pages/Booking.tsx` + componente novo | modificar/criar | diálogo "remarcar ou mais uma?" |
| `booking-site/src/services/booking.service.ts`, `types/index.ts` | modificar | código e corpo novos |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx`, `ConflitoDoMes.tsx` | modificar | variante "outro mês" com os três botões |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | modificar | "Copiar link de remarcação" |
| `scheduler/tests/unit/...`, `booking-site/src/**/*.test.tsx`, `frontend/src/**/*.test.tsx` | criar/modificar | casos do §3 E |
| `scheduler/tests/integration/060-...md`, `scheduler/tests/postman/...` | criar | roteiro e Postman |
| `booking-site/CLAUDE.md`, `docs/work/prd/056-...md`, `docs/work/prd/059-...md` | modificar | ponteiros e regra atual |

---

## 6. Dependências e riscos

- **Dependências:** PRD 056 (código sempre no site, `remarca` com carrinho
  novo, `ConflitoDoMes`), PRD 054 (`remarca`, desfecho), PRD 059 (bloco do
  lembrete), PRD 046 (`bloco_do_site`).
- **Riscos:**
  - Front do site em cache: um `create` sem as flags novas recebe 409 que o
    front antigo não conhece e mostra erro genérico. Mitigação: o front antigo
    já trata 409 com `message`; a mensagem do 409 novo diz o que fazer ("Você
    já tem uma sessão em {data}. Abra Meus agendamentos para remarcar, ou
    recarregue a página").
  - Bot: o modelo pode mandar `mais_uma=true` sem perguntar. Mitigação: a tool
    só aceita `mais_uma` quando a resposta anterior da própria tool foi a
    pergunta (mesmo padrão de `alterar_agendamento` com confirmação, PRD 043);
    teste cobre.
  - Mais um turno no bot e mais um clique no site para quem já tem sessão
    futura. Aceito: é exatamente o público que hoje gera duplicata.
  - Deploy: scheduler (prod perto do limite do CloudFormation, nenhuma função
    nova aqui), booking-site e frontend pela Vercel.

---

## 7. Critérios de aceite

- [ ] Site: número com sessão futura em outro mês recebe o diálogo com
      "Remarcar essa sessão" / "Marcar mais uma" / Voltar; cada botão produz
      o resultado certo e o vínculo de remarcação quando for o caso.
- [ ] Site: mesmo mês continua exatamente como no 056.
- [ ] Site: `https://{dominio}/?meus=1` abre "Meus agendamentos" direto, nas
      duas árvores; fechar limpa a URL.
- [ ] Bot: paciente com sessão futura que pede outra data em outro mês é
      perguntada antes de qualquer criação; "remarcar" vira
      `alterar_agendamento`; "mais uma" cria com `mais_uma=true`; sem resposta
      explícita a tool não cria.
- [ ] Bot: o link que o lembrete manda para remarcar abre "Meus agendamentos".
- [ ] Painel: criar em outro mês com sessão futura mostra o modal com os três
      botões; STAFF consegue "Marcar mais uma" sem motivo.
- [ ] Painel: popover copia o link de remarcação quando há domínio próprio.
- [ ] Regra em um lugar só (guarda de teste); pytest, vitest dos dois fronts
      e lint passando.
- [ ] Roteiro em dev sem número inventado; prod conferido pelo primeiro caso
      real.

---

## 8. Referências

- `docs/work/prd/056-uma-sessao-por-mes-e-codigo-no-site.md` (regra do mês,
  diálogo, `remarca` com carrinho)
- `docs/work/prd/059-cancelamento-pela-conversa.md` (bloco do lembrete, link
  para remarcar, lição dos telefones)
- `docs/work/prd/054-regras-de-cancelamento-falta-e-remarcacao.md`
- `docs/work/prd/035-reagendamento-nao-e-cancelamento.md` (cancelar e marcar de novo é remarcação)
- `docs/work/prd/046-link-e-o-primeiro-caminho.md` (`bloco_do_site`)
- `booking-site/src/layouts/BookingChrome.tsx`,
  `booking-site/src/components/MyAppointmentsModal.tsx`
- Medição: `mede_outro_mes_prod.py` (scratchpad da sessão, só leitura)

---

## Status (preencher após conclusão)

- [x] Decisões do §4 confirmadas em 23/11/2026 (as cinco propostas)
- [x] Spec gerada: `docs/work/spec/060-sessao-futura-e-link-meus-agendamentos.md` (23/11/2026)
- [x] Implementado em dev: 23/11/2026 (PR #249; scheduler layer 212; smoke 8/8
  pelo painel, sem nenhum envio de WhatsApp; pytest, vitest do site e do painel,
  lint e build limpos). Roteiro:
  `scheduler/tests/integration/060-sessao-futura-e-link-meus-agendamentos.md`.
- [ ] Implementado em prod (scheduler por deploy manual; site e painel pela
  Vercel no merge)
- [x] Registrado em `TASKS_LOG.md`
- Guarda do bot: `mais_uma=true` só vale depois de a tool ter devolvido a
  pergunta na mesma conversa (`pergunta_mais_uma` gravado na sessão). O modelo
  não decide por ela.
- O link pós-cancelamento do PRD 059 continua sendo a raiz (ali a pessoa marca
  uma sessão nova); só o link para REMARCAR do lembrete virou `?meus=1`.
