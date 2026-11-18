# PRD - 049 Edição pelo painel tolera até 15 min de sobreposição

> Gerado na fase **Research** em 17/11/2026. Pedido do André: "o fluxo de
> editar agendamento às vezes acrescenta áreas de paciente já agendada e é
> bloqueado por conflito de horário na sequência. Somente no fluxo de edição
> pelo painel (manual), permitir sobreposição com o horário anterior ou
> posterior de no máximo 15 minutos." Fluxo completo autorizado: PRD, spec,
> PR, merge, deploy dev (alinhando dev com prod antes), validação, deploy prod.

---

## 1. Objetivo

Quando a recepção edita uma sessão já marcada pelo painel (trocar áreas,
fixar duração, mudar horário) e a sessão passa a invadir a vizinha em **até
15 minutos**, o servidor aceita. Acima disso, recusa como hoje. Bot, site
público e criação de sessão nova continuam sem tolerância nenhuma.

---

## 2. Contexto

### 2.1 Como o conflito é conferido hoje

Toda edição passa por três métodos de `AppointmentService`
(`update_appointment_services`, `set_manual_duration`,
`reschedule_appointment`), e cada um repete inline o mesmo SQL: há conflito
se existe sessão `CONFIRMED` no mesmo dia e clínica com
`start_time < novo_fim AND end_time > novo_inicio` (encostar é permitido). A
criação (`create_appointment`) repete uma quarta cópia. Não há buffer, não há
profissional, não há tolerância. `ConflictError` vira 409 no handler.

### 2.2 Quem chama os mesmos métodos

| Caminho | Entrada | Chama |
|---|---|---|
| Painel, editar | `PUT appointments/{id}` → `functions/appointment/update.py` | os três métodos, na ordem áreas → duração → remarcação |
| Bot, `alterar_agendamento` | `services/ai_tools.py` ~1262 | `update_appointment_services` + `reschedule_appointment` **direto**, sem passar pelo handler |
| Site, remarcar | `public_booking/reschedule_appointment.py` | `reschedule_appointment` |
| Painel, criar | `functions/appointment/create.py` | `create_appointment` |
| Site e bot, criar | `public_booking/create_appointment.py`, `ai_tools.book_appointment` | `create_appointment` |

Chegar em `update.py` já significa painel (ou a chave mestra). Por isso a
regra entra como **parâmetro** dos métodos, com padrão zero, e só o handler
do painel passa 15.

### 2.3 Por que 15 minutos pelo painel e zero nos outros

A grade de horários que o site e o bot oferecem já é mais estrita que a
gravação (usa `buffer_minutes` da clínica). Quem edita pelo painel é a
própria recepção, olhando a agenda do dia, e sabe que uma virilha de 10 min
cabe num encaixe. A paciente, pelo site ou pelo bot, não tem esse contexto.

### 2.4 O caso que motivou

Sessão A termina 12:40; a seguinte começa 12:40. A recepção acrescenta uma
área a A, que passa a terminar 12:45. Hoje: 409 "Conflito de horário com
nova duração". Com este PRD: aceita (5 min de sobreposição). Se A passasse a
terminar 13:00 (20 min), continua 409.

---

## 3. Proposta

1. **Um helper só** em `AppointmentService`: `_conflitos(clinic_id, data,
   inicio, fim, excluir_id=None, tolerancia_minutos=0)`, no lugar das quatro
   cópias. Conflito = sessão vizinha cuja **sobreposição com a janela nova é
   maior que a tolerância**, medida por vizinho:
   `LEAST(end_time, fim) - GREATEST(start_time, inicio) > tolerância`.
   Com tolerância 0 é exatamente a regra atual (encostar não conflita).
2. **Parâmetro `tolerancia_minutos=0`** nos três métodos de edição. Bot e
   site não passam nada: comportamento idêntico ao de hoje.
3. **`update.py` passa `tolerancia_minutos=TOLERANCIA_DO_PAINEL_MIN` (15)**
   nas três chamadas. A regra "só confere contra a data final" (PRD 011) fica
   como está.
4. **Mensagem do 409** no painel passa a dizer o que foi tolerado: "Conflito
   de horário: a sessão invadiria a vizinha em mais de 15 minutos
   ({data} {inicio}-{fim})". Bot e site mantêm as mensagens atuais.
5. **Painel**: o aviso fixo do modal de edição, "Conflitos de horário serão
   verificados automaticamente", passa a explicar a regra: "Até 15 minutos
   de sobreposição com a sessão vizinha são aceitos; acima disso o servidor
   recusa." Nenhum campo novo; nenhuma mudança na grade de horários.

### Fora

- Criação de sessão (painel, site, bot): tolerância zero.
- Grade de horários (`availability_engine`): continua com o buffer da
  clínica; horários que só cabem com tolerância não aparecem como sugestão,
  mas podem ser digitados (o `TimeField` já permite).
- Tolerância configurável por clínica: constante no código por ora.
- Sobreposição com mais de uma vizinha ao mesmo tempo: cada vizinha é
  medida sozinha; invadir duas em 10 min cada passa. Aceito: é o caso de
  uma sessão curta espremida entre duas, e a recepção vê a agenda.

---

## 4. Decisões (17/11/2026, tomadas pelo agente com o André ausente)

| # | Pergunta | Decisão | Motivo |
|---|---|---|---|
| 1 | Onde mora a tolerância | Parâmetro dos métodos, padrão 0; `update.py` passa 15 | O bot reusa os métodos; o handler é o único ponto que é "painel" |
| 2 | Como medir | Por vizinho, `LEAST - GREATEST > T`, no SQL | Encolher a janela em 15 deixaria passar vizinha curta inteira e não é "no máximo 15" |
| 3 | Helper único | Sim, substitui as 4 cópias | Mesma regra, um lugar; a 3ª cláusula do SQL atual era redundante |
| 4 | Criação pelo painel | Sem tolerância | O pedido foi "somente edição" |
| 5 | Mensagem | Cita os 15 min só no painel | Quem recebe o 409 precisa saber que o encaixe tem limite |
| 6 | Grade de slots | Não muda | Fora do pedido; o campo aceita horário digitado |

---

## 5. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---|---|---|
| `scheduler/src/services/appointment_service.py` | modificar | `_conflitos` helper; `tolerancia_minutos` em `reschedule_appointment`, `update_appointment_services`, `set_manual_duration`; `create_appointment` usa o helper com 0 |
| `scheduler/src/functions/appointment/update.py` | modificar | `TOLERANCIA_DO_PAINEL_MIN = 15` nas três chamadas |
| `scheduler/tests/unit/test_tolerancia_de_sobreposicao.py` | criar | helper (0 e 15, por vizinho, encostar, vizinha curta), handler passa 15, bot e site passam 0 |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` (+ test) | modificar | texto do aviso |
| `scheduler/tests/integration/049-tolerancia-de-sobreposicao.md` | criar | roteiro curl em dev |

Sem migration. Sem rota nova.

---

## 6. Dependências e riscos

- **Fakes de teste** detectam o SQL por `SELECT id FROM` e leem `params[3]`
  como o fim novo. O helper mantém a ordem dos primeiros parâmetros
  (`clinic, data, [id], fim, inicio`) e acrescenta os da tolerância no fim.
- **Dev atrasado em relação a prod** (048 e fuso subiram direto): antes
  desta feature, dev recebe a `main` atual e a migration do 048.
- **Deploys nunca em paralelo** (dev e prod compartilham o Docker/estado da
  CLI).
- **Chave mestra** também passa por `update.py` e ganha a tolerância. É o
  mesmo operador humano do painel; aceito.

---

## 7. Critérios de aceite

- [ ] Editar pelo painel uma sessão que passa a invadir a vizinha em até 15 min → 200.
- [ ] A mesma edição invadindo em 16 min ou mais → 409 com a mensagem citando 15 minutos.
- [ ] Encostar (fim == início da vizinha) continua 200 em todos os caminhos.
- [ ] Bot `alterar_agendamento` e site remarcar com 5 min de invasão → recusa como hoje.
- [ ] Criar sessão pelo painel com 5 min de invasão → 409 como hoje.
- [ ] Modal de edição mostra o texto novo.
- [ ] pytest, Vitest, build e lint verdes; validação por curl em dev antes de prod.

---

## Status

- [x] Pendente
- [x] Spec gerada: `spec/049-edicao-pelo-painel-tolera-15-min-de-sobreposicao.md` (17/11/2026)
- [x] Implementado em dev: 18/11/2026 (PR #211; dev alinhado com prod antes, layer 197 → 198; roteiro curl verde)
- [x] Implementado em prod: 18/11/2026 (layer 156; painel pela Vercel no merge)
- [x] Registrado em `TASKS_LOG.md`
