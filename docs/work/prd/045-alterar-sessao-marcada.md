# PRD - 045 Alterar uma sessão marcada é editar, nunca marcar outra

> Gerado na fase **Research** em 09/11/2026. Use como input para a fase Spec.
> Pedido do André, a partir de uma conversa da Essência: "a cliente já tinha
> agendamento, entrou em contato para alterar, e o bot não editou: criou um
> novo, mudando data e horário, sem oferecer o mesmo horário. Bug grave."
>
> Nomes e telefones ficam fora deste documento; o rastro está nos logs e no
> `message-events`, e as conversas estão identificadas por clínica, data e hora.

---

## 1. Objetivo

Quando uma paciente com sessão marcada pede uma mudança - áreas, dia ou hora -,
o bot **edita a sessão que existe**, mantém o horário dela sempre que couber, e
nunca cria uma segunda linha na agenda. Hoje ele faz o contrário nas três
camadas: a agenda dele considera o horário dela ocupado (por ela mesma), não
existe ferramenta que altere áreas, e o prompt não tem esse caminho.

---

## 2. Os casos

### Essência, 09/11/2026

Paciente com sessão em **18/11 às 14:50**, marcada em 05/11.

| Hora (UTC) | Quem | O quê |
|---|---|---|
| 12:17 | recepção | "Bom dia 😊" / "Quais seriam as áreas?" |
| 20:27 | sistema | disparo em massa com campanha (aviso sobre faltas) |
| 20:34 | ela | lista cinco áreas - responde à pergunta **da recepção**, 8 h depois |
| 20:35 | bot | pergunta as variantes (meia perna, perianal) |
| 20:52 | bot | **"o horário de 14:50 não encaixa mais. O horário disponível nesse dia (18/11) é 20:35"** e oferece 19, 25, 26/11 e 08/12 |
| 20:53-20:58 | ela / bot | "Dia 19" → lista de 13 horários → "8" → **"Confirmando: 19/11 às 15:25. Confirmo?"** |
| 21:38-21:44 | recepção | desfaz à mão, mantém 18/11 às 14:50, pede desculpas pela "assistente virtual" |

Log do turno das 20:52:

```
[Slots] <telefone>: pediu 14:50 em 2026-11-18 -> nao cabe
```

O bot **sabia** da sessão dela (citou o 14:50) e tentou manter o dia. O engine
respondeu que 14:50 não cabia - porque o bloco 14:50-15:20 estava ocupado **por
ela**. Reproduzido contra o banco de produção, com a agenda real de 18/11:

```
duração 30 min       cabe em 14:50?    grade do dia
  sem excluir a dela     False            []
  excluindo a dela       True             ['14:40']
```

Mesmo resultado com 31 e 35 min. A recepção tinha razão: cabia.

O "Confirmo?" das 20:58 iria para `book_appointment`, que **insere uma linha
nova** e não sabe que já existe uma CONFIRMED da mesma paciente. A recepção
interrompeu antes; por isso hoje não há duplicata no banco - a linha original
está em `version 2`, editada por humano às 21:38.

### Nobre Laser, 05/11/2026

Paciente com sessão em **06/11 às 13:50** (axilas + 1/2 perna). Responde ao
lembrete de 24 h:

| Hora (UTC) | Quem | O quê |
|---|---|---|
| 14:42 | ela | "eu gostaria de remarcar para fazer somente a axila" |
| 14:58 | bot | confirma: mesmo dia e horário, só axila - "é isso?" |
| 14:59 | ela | "Isso" |
| 15:01 | bot | **"o horário das 13:50 não encaixa só com a axila nessa agenda. Os mais próximos são 13:20 ou 14:05"** |
| 15:02 | recepção | **"Bot viajou, vou reagendar aqui."** |

Log: `[Slots] <telefone>: pediu 13:50 em 2026-11-06 -> nao cabe`. **Tirar** uma
área fez a sessão "não caber" no horário que ela já ocupava. Mesma causa.

### Medição

Nos últimos 30 dias em produção, o bot respondeu "não cabe" a um horário
pedido 11 vezes. **Em 2 delas o horário era o da própria pessoa** - os dois
casos acima, nas duas clínicas, ambos terminando com a recepção assumindo e se
desculpando pelo bot. Não há duplicata gravada hoje: nas duas vezes uma pessoa
interrompeu a tempo.

---

## 3. Por que acontece - três camadas, e nenhuma segura a outra

### 3.1 A agenda do bot conta o agendamento da própria paciente como ocupado

`AvailabilityEngine` sabe excluir um agendamento ao calcular janelas livres:
`ignorar_agendamento` existe desde o PRD 035 (`availability_engine.py:262`).
Mas só a rota do site o usa (`public_booking/availability.py:75`,
`excludeAppointmentId`). O bot constrói o engine sem ele (`agent_runner.py:31`,
`webhook/handler.py:712`), e as três consultas da conversa -
`get_available_days_multi`, `get_available_slots_multi`, `cabe_no_horario` -
veem a vaga dela como de outra pessoa.

O dado para excluir **já está na mão do bot a cada turno**:
`identificar_paciente` devolve `agendamento_futuro = {id, data, hora}` e isso
vai no `ctx["paciente"]` de toda tool (`conversation_agent.py:544`). Ninguém
o passa para o engine.

Consequência direta: para quem tem sessão marcada, o bot **nunca** consegue
oferecer o próprio horário. É determinístico.

### 3.2 Não existe tool que altere as áreas de uma sessão

`reschedule_appointment` recebe só `appointment_id`, `new_date`, `new_time`
(`ai_tools.py:381`). Para gravar áreas diferentes, o único caminho do modelo é
`book_appointment` → `create_appointment`, que insere uma linha nova
(`ai_tools.py:1045`) e deixa a antiga CONFIRMED. O resultado seria **duas
sessões na agenda para a mesma pessoa**, uma delas num horário que ela não
vai usar.

O painel já faz a edição certa: `appointment/update.py` chama
`update_appointment_services(appointment_id, service_id, pairs, ...)`, que
recalcula duração e preço, confere conflito **excluindo o próprio id**
(`appointment_service.py:649`) e grava com optimistic lock; se a data muda,
`reschedule_appointment` vem em seguida. A capacidade existe - só não está
exposta ao bot.

### 3.3 O prompt e a skill não têm o caminho "alterar"

No `AI_SYSTEM_PROMPT` da Essência em produção: zero ocorrências de "remarcar",
"alterar", `reschedule_appointment` ou `cancel_appointment`. `lookup_appointments`
aparece uma vez, só no galho "DÚVIDA", e `COMO CONDUZIR A CONVERSA` tem sete
etapas, todas de **marcação**: primeiro contato → dúvida → áreas → data e
horário → confirmação → cadastro → após agendar.

A skill `PACIENTE_COM_HORARIO` (`skills/__init__.py:79`) chega perto: "quem já
tem sessão marcada raramente quer marcar outra: confirme se não é remarcar,
cancelar ou tirar uma dúvida". Mas:

- `lookup_appointments` devolve id, data, hora e serviço - **não devolve as
  áreas**, embora a query já traga `areas_display`
  (`appointment_service.py:1041`). O modelo não sabe o que ela tem marcado e
  não consegue ler "só a axila" como "tirar a 1/2 perna".
- O bloco `QUEM É` diz "Próximo horário marcado: 2026-11-18 às 14:50" e, logo
  abaixo, para `ACTIVE_CUSTOMER`: "As áreas desta sessão você pergunta e
  confirma com ela, como sempre" (`estado_comercial.py:93`). Para quem tem
  horário futuro, isso empurra o modelo para o roteiro de marcar.
- O roteador pré-carrega `lookup_appointments` só quando o texto casa com
  "remarcar|reagendar|cancelar|meu agendamento" (`roteador.py:32`). "Buço,
  mento, linha alba, perna, virilha completa" não casa com nada.

Nos dois casos o modelo fez o melhor que o ambiente permitia: entendeu que era
alteração, tentou manter o horário, o engine disse não, e ele seguiu o único
roteiro que tinha.

### 3.4 Como a conversa foi parar com o bot (Essência)

A recepção tinha uma pergunta em aberto desde 12:17, o que pausa o bot por 24 h.
O disparo em massa das 20:27 foi enviado **com campanha**, e campanha destrava
`atendimento_humano` e `cooldown` por decisão de desenho (PR #144,
`porta_do_disparo.py:20`). Log: `[Send] Conversa de <telefone> destravada
(atendimento_humano) pelo disparo com bot`. Quando ela respondeu à recepção, o
bot já estava com a conversa.

Isto não é bug - é a regra funcionando como foi decidida. Mas aqui a regra
entregou ao bot uma conversa que uma pessoa estava conduzindo. Fica como
**achado para decisão** (§7.4), fora da correção principal.

---

## 4. Proposta - a mesma regra em três camadas

O desenho segue o do PRD 044: o prompt diz o que fazer, e o código garante que
o contrário não acontece.

### 4.1 Código: a agenda do bot exclui a sessão da paciente

O executor de tools passa `ctx["paciente"]["agendamento_futuro"]["id"]` ao
engine nas três consultas. O engine é compartilhado entre turnos (nasce com o
agente), então a exclusão vai **por chamada**, não no construtor - o
`ignorar_agendamento` do construtor continua para o site.

Efeito: 14:50 passa a caber para quem já está nas 14:50; a grade do dia mostra
a vaga dela; "não cabe" volta a significar só "outra pessoa está lá".

### 4.2 Código: uma tool para alterar a sessão que existe

`alterar_agendamento(appointment_id, service_area_pairs?, new_date?, new_time?)`
- edita a linha existente reutilizando o que o painel já usa:
`update_appointment_services` para áreas (duração e preço recalculados,
conflito conferido sem contar a própria sessão) e `reschedule_appointment`
quando data ou hora mudam (que já zera `confirmado_em`, PRD 043). Devolve a
sessão resultante - data, hora, áreas, duração, valor - para a confirmação ser
escrita com dado consultado.

`reschedule_appointment` vira o caso particular "só data e hora" da mesma tool
(§7.2).

### 4.3 Código: `book_appointment` não cria uma segunda sessão em silêncio

Quando `ctx["paciente"]` tem `agendamento_futuro`, `book_appointment` recusa
com `o_que_fazer`: "esta pessoa já tem sessão em <data> às <hora>; se ela quer
mudar essa sessão, chame `alterar_agendamento`; se ela quer de fato uma
SEGUNDA sessão, pergunte isso a ela com todas as letras e chame de novo com
`segunda_sessao=true`". É o mesmo padrão de `full_name_obrigatorio`: a tool
explica e o modelo refaz. O argumento `segunda_sessao` é o registro, no rastro
da tool, de que a duplicidade foi intencional.

### 4.4 Código: o modelo passa a saber o que ela tem marcado

- `lookup_appointments` devolve `areas` (de `areas_display`), `duration_minutes`
  e `final_price_cents`, além do que já devolve.
- `agendamento_futuro` ganha `areas`, e o bloco `QUEM É` mostra
  "Próximo horário marcado: 18/11 às 14:50 - Axilas, Buço, Linha alba (30 min)".
- Para `ACTIVE_CUSTOMER` **com horário futuro**, a linha "as áreas desta sessão
  você pergunta e confirma" sai do bloco `QUEM É`; quem manda nesse caso é a
  skill (abaixo). Para `NO_NEXT_BOOKING` ela continua.
- O roteador pré-carrega `lookup_appointments` para qualquer mensagem de quem
  tem `agendamento_futuro`, independentemente do texto - a condição é o estado
  da pessoa, não a frase.

### 4.5 Prompt: o galho que falta

No `AI_SYSTEM_PROMPT` das duas clínicas (banco, via script idempotente, como
nos PRDs 037 e 044), em `COMO CONDUZIR A CONVERSA`, antes de "3. ÁREAS":

```
2b. SESSÃO JÁ MARCADA
   Se o bloco QUEM É mostra um próximo horário, você está falando com alguém
   que já tem sessão. Qualquer pedido de mudança - trocar, tirar ou incluir
   área, mudar o dia ou a hora - é ALTERAÇÃO dessa sessão, nunca marcação de
   outra.
   1. Leia as áreas que ela tem marcadas (QUEM É ou lookup_appointments) e
      confirme em uma frase o que muda: "Então fica só axilas, no mesmo dia
      18/11 às 14:50 - é isso?"
   2. O horário dela é dela. Mantenha data e hora por padrão. Só proponha
      outro horário se ela pedir ou se get_time_slots disser que as áreas
      novas não cabem no horário atual - e aí ofereça primeiro o mais
      próximo no MESMO dia.
   3. Confirmada a mudança, chame alterar_agendamento. Nunca book_appointment:
      ele cria uma segunda sessão e deixa a primeira ocupando a agenda.
   4. Só se ela disser, com todas as letras, que quer OUTRA sessão além da que
      tem, siga para marcação - e diga a ela que a primeira continua marcada.
```

E na skill `PACIENTE_COM_HORARIO`, o item 2 passa a apontar para esse galho e
para `alterar_agendamento` pelo nome; o item 3 ("se for marcar outra sessão")
ganha a condição "só depois de ela confirmar que é uma segunda sessão".

### 4.6 O que a correção NÃO faz

- Não avisa a paciente quando a **clínica** altera (débito D1, PRD futuro).
- Não muda a regra do disparo com campanha (§3.4 → §7.4).
- Não toca na pausa de 24 h do atendimento humano.

---

## 5. Achado fora do escopo

A mensagem de 12:17 da recepção ("Quais seriam as áreas?") não tem resposta
registrada do lado da clínica até 21:39: a pergunta ficou 8 h em aberto, e foi
um disparo em massa que a entregou ao bot. Com a regra atual, qualquer
campanha enviada para uma conversa que a recepção está conduzindo faz o mesmo.
Ver §7.4.

---

## 6. Escopo

### Dentro

- Exclusão da sessão da paciente nas três consultas de agenda do bot (§4.1).
- Tool `alterar_agendamento` sobre `update_appointment_services` +
  `reschedule_appointment` (§4.2).
- Recusa de `book_appointment` para quem tem sessão futura, com
  `segunda_sessao` explícito (§4.3).
- Áreas no `lookup_appointments`, no `agendamento_futuro` e no bloco `QUEM É`;
  pré-carga de `lookup_appointments` por estado (§4.4).
- Galho "SESSÃO JÁ MARCADA" no prompt das duas clínicas e ajuste da skill
  `PACIENTE_COM_HORARIO` (§4.5).
- Testes: o engine com e sem exclusão sobre a mesma agenda; a tool nova em
  cada combinação (só áreas, só data, os dois, não cabe); `book_appointment`
  recusando e aceitando com `segunda_sessao`; o laço do agente nos dois casos
  reais, dublados: o horário é mantido e a linha é editada.
- Logs: `[Alteracao] <phone>: sessão <id> áreas X→Y, horário mantido|movido
  para ...` e `[Alteracao] <phone>: book_appointment recusado, sessão futura
  <id>` - para contar por clínica no CloudWatch.

### Fora

- Alteração feita pelo painel (já funciona) e pelo site (PRD 035).
- Lembrete de 24 h: com site de autoatendimento, remarcar e cancelar continuam
  saindo do bot enquanto o lembrete está vivo (`lembrete.ferramentas_a_remover`).
  Decidir se `alterar_agendamento` entra na mesma lista está em §7.3.
- A política do disparo com campanha (§7.4).

---

## 7. Decisões para o André

### 7.1 Ao alterar áreas, o que o bot faz com o horário?

- **A (recomendada).** Mantém data e hora. Só propõe outro horário se ela
  pedir ou se as áreas novas não couberem no horário atual, e aí o mais
  próximo no mesmo dia. É o que a recepção fez à mão nos dois casos.
- **B.** Sempre pergunta se quer manter ou mudar. Custa uma mensagem a mais a
  quem, nas duas vezes, só queria ajustar as áreas.

### 7.2 Uma tool ou duas?

- **A (recomendada).** `alterar_agendamento` substitui `reschedule_appointment`
  (data/hora viram argumentos opcionais). Uma só decisão de "o que é alterar
  uma sessão", um só lugar para o lembrete remover, um só rastro no log.
- **B.** `alterar_agendamento` só para áreas, `reschedule_appointment` segue
  como está. Dois caminhos para a mesma pergunta divergem em silêncio.

### 7.3 Durante o lembrete, com site de autoatendimento

Hoje remarcar e cancelar saem do bot e a pessoa recebe o link. O caso da
Nobre foi exatamente uma resposta ao lembrete pedindo para tirar uma área.

- **A (recomendada).** `alterar_agendamento` fica disponível no lembrete
  mesmo com site: trocar áreas é uma frase, e o site não faz isso. Remarcar
  e cancelar continuam pelo link.
- **B.** Sai junto com as outras: tudo que mexe na sessão vai pelo link.

### 7.4 Disparo com campanha para conversa que a recepção está conduzindo

- **A.** Mantém: o operador decidiu na tela que o bot assume (PR #144).
- **B.** Quando a última mensagem da conversa é humana e ainda não houve
  resposta da pessoa, o disparo sai mas **não destrava**: a recepção continua
  com a conversa. É uma mudança em `porta_do_disparo`, pequena e separada
  deste PRD - aqui só se decide se vira PRD.

---

## 8. Status

- [ ] Decisões §7 registradas
- [ ] Spec gerada
- [ ] Implementado em dev
- [ ] Prompt corrigido no banco (dev e prod)
- [ ] Em prod
- [ ] Registrado no TASKS_LOG
