# PRD — 024 Booking-site: "Meus agendamentos", desconto progressivo à vista, aviso de agendamento repetido e nome de quem agenda

> Gerado na fase **Research**. Use como input para a fase Spec.
> Origem: teste do André no site em produção (18/10/2026), logo depois do
> deploy da task 023.

---

## 1. Objetivo

Quatro ajustes no fluxo público de agendamento:

1. **"Meus agendamentos" encontra o que foi agendado.** O André agendou pelo
   site, recebeu a confirmação no WhatsApp e viu o agendamento no painel. Em
   "Meus agendamentos" o site respondeu "Nenhum agendamento encontrado".
2. **Desconto progressivo à vista na escolha das áreas.** Com o preço exposto,
   quem escolhe várias áreas vê um valor alto. A pessoa precisa saber, ANTES de
   escolher, que o desconto cresce com o número de áreas, e quanto falta para a
   próxima faixa.
3. **Aviso de agendamento repetido.** Se o número já tem um agendamento futuro
   confirmado, o site pergunta antes de criar outro. O site não bloqueia, só
   pede que a pessoa confirme que quer manter os dois.
4. **Nome de quem agenda.** Duas pessoas podem usar o mesmo telefone (mãe e
   filha, por exemplo). "Meus agendamentos" e as mensagens sobre o agendamento
   mostram o nome que foi digitado naquele agendamento.

---

## 2. Contexto

### 2.1 Causa do "Nenhum agendamento encontrado"

`list_appointments.py` repassa o telefone **como veio na query** para
`AppointmentService.get_active_appointments_by_phone`, que compara com
`patients.phone` por igualdade exata. O site manda o telefone do jeito que o
campo mostra, `(11) 99999-0000`, e o paciente é gravado normalizado,
`5511999990000`. A comparação nunca casa.

O token passa porque `verify_token` normaliza antes de comparar. O
cancelamento passa porque `cancel_appointment.py` normaliza. Só a listagem
não normalizava.

Há um segundo caso, menor: o paciente criado pelo bot guarda o número como o
WhatsApp entrega. Fora dos DDDs 11 a 28 o WhatsApp entrega muito número
**sem** o nono dígito (`554797053940`). Quem agendou pelo bot e digita o
número com o 9 no site também não se encontraria. `phone.variantes_do_numero`
já resolve essa comparação no resto do sistema (leads).

### 2.2 Desconto progressivo

A política (`politica_de_desconto.decide`) já aplica a faixa por quantidade
de áreas no carrinho: a cotação de prod mostrou R$ 330 → R$ 297. O que falta
é **anunciar** a regra. Hoje a pessoa só descobre o desconto depois de marcar
a segunda área. As faixas vêm de `scheduler.discount_rules` (`tier_2_*`,
`tier_3_*`), uma linha ativa por clínica.

A primeira sessão e o desconto personalizado ficam fora do anúncio porque
dependem de quem é a pessoa. Eles continuam aparecendo na cotação quando ela
digita o telefone.

### 2.3 Agendamento repetido

A criação pelo site não exige código de verificação (decisão da task 015). Por
isso o aviso não pode listar os agendamentos existentes: qualquer pessoa que
digitasse o número de outra veria a agenda dela. O aviso diz **quantos**
agendamentos futuros o número tem, sem data, serviço ou nome, e aponta para
"Meus agendamentos", que exige o código, para quem quiser conferir.

### 2.4 Nome por agendamento

`scheduler.patients` tem um registro por (clínica, telefone). O nome digitado
em cada agendamento fica em `appointments.full_name`, que já é gravado desde a
task 015. Falta usá-lo:

- a lista de "Meus agendamentos" não mostra nome;
- o template `BOOKED`, a confirmação que o site manda, não tem nome. Conferido
  em 18/10/2026: nenhuma clínica de prod personalizou `BOOKED`,
  `REMINDER_24H`, `CANCELLED` ou `RESCHEDULED`, então todas usam o padrão;
- o lembrete de 24h (latente, não ligado, ver `reminder_service.py`) grava
  `patientName` a partir de um campo que o agendamento não tem.

---

## 3. Escopo

### Dentro

- Listagem e cancelamento públicos comparam o telefone normalizado e tolerante
  ao nono dígito.
- A resposta da listagem inclui `full_name`, e o site mostra o nome em cada
  cartão.
- `bootstrap` devolve as faixas de desconto ativas. A etapa de áreas mostra as
  faixas e quanto falta para a próxima.
- A criação devolve 409 `HAS_FUTURE_APPOINTMENT` (com a contagem) quando o
  número já tem agendamento futuro e o corpo não traz `confirmDuplicate: true`.
  O site mostra o aviso e reenvia com a confirmação.
- O `BOOKED` padrão traz o nome. O site passa `full_name`. O lembrete usa
  `full_name` do agendamento.

### Fora

- Unificar pacientes duplicados por causa do nono dígito (`_get_or_create_patient`
  continua exato). Isso é limpeza de dados, com PRD próprio.
- Exigir verificação por código antes de agendar.
- Aviso de repetição no bot. O agente já lista os agendamentos do número antes
  de remarcar ou cancelar.

---

## 4. Critérios de aceite

1. Agendar pelo site com `(11) 9xxxx-xxxx` e abrir "Meus agendamentos" com o
   mesmo número mostra o agendamento, com o nome de quem agendou.
2. Paciente gravado como `554797053940` aparece para quem digita
   `(47) 99705-3940`.
3. Na etapa de áreas de uma clínica com faixas, o site mostra "2 a 3 áreas:
   10% off · 4 ou mais: 20% off" e, com 1 área marcada, "Falta 1 área para
   10% de desconto".
4. Clínica sem `discount_rules` ativa não mostra nada.
5. Número com agendamento futuro: o "Confirmar agendamento" abre o aviso. Em
   "Manter os dois", o agendamento é criado. Em "Voltar", nada é criado.
6. Número sem agendamento futuro: agenda direto, sem aviso.
7. A confirmação no WhatsApp começa com "Agendamento confirmado para *Nome*!".

---

## 5. Status

- [x] Spec gerada (`spec/024-booking-site-meus-agendamentos-aviso-nome.md`)
- [x] Implementado (2026-10-18)
- [x] Deploy dev (2026-10-18, testado com curl e no site; ver `scheduler/tests/integration/024-...md`)
- [x] Deploy prod (2026-10-18, PR #137; scheduler prod sem rota nova, sem create-deployment; booking-site pelo deploy do merge. Smoke: faixas no bootstrap, "Meus agendamentos" com telefone formatado achando o agendamento com nome, nota de faixas em agendar.draclaradourado.com.br)
