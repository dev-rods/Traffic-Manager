# PRD — 011 Duração manual do agendamento

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Permitir que a recepção fixe, pelo painel, uma duração diferente da que o cálculo
produz para **um agendamento específico**, sem alterar a regra da clínica
(`scheduler.duration_rules`) nem a duração cadastrada das áreas.

O caso real é o que o cálculo não sabe: a paciente que sempre demora mais, a
sessão que vai acumular duas coisas, o dia em que a sala precisa de folga. Hoje
não há como registrar isso — a agenda mostra um fim de sessão que a clínica sabe
que está errado, e a próxima paciente é marcada por cima.

---

## 2. Contexto

### O princípio que está em vigor hoje

`duration_rules.py` é explícito: a duração é **derivada, nunca informada**. O
`create_appointment` recebe `total_duration_minutes` na assinatura e o **ignora**,
logando que ignorou (`appointment_service.py:94-98`). Isso foi decidido em
02/09/2026, depois de o agente pedir horários para uma sessão de 4 minutos.

Este PRD **reverte esse princípio num ponto só e de propósito**: quando quem
informa é uma pessoa da recepção, num agendamento específico, com registro de que
foi decisão humana. Continua valendo para todo o resto — o bot nunca informa
duração, a criação pelo chat continua 100% derivada.

Essa distinção é a linha inteira do desenho: **o override é sobre um
agendamento, nunca sobre a regra.**

### Duas armadilhas que a pesquisa encontrou

Sem tratá-las, o override some sozinho e ninguém percebe.

**1. `reschedule_appointment` reaplica a regra sobre o valor gravado**
(`appointment_service.py:360-361`):

```python
duration_minutes = duracao_da_sessao(
    duration_minutes, get_duration_rules(self.db, clinic_id))
```

Uma duração manual de 75 min, com teto 50, vira **50** assim que alguém remarcar.
Pior: o reschedule atualiza `end_time` mas **não reescreve
`total_duration_minutes`** — a coluna fica 75 e a agenda passa a mostrar 50. É a
divergência silenciosa de sempre.

O comentário que justifica essa linha diz que ela existe para normalizar
agendamento criado sob a regra antiga. A razão é boa; ela só não pode valer para
duração que uma pessoa fixou de propósito.

**2. `update_appointment_services` recalcula a duração ao editar áreas**
(`appointment_service.py:487`), por decisão do PR #32. Colide de frente com o
override.

### O que já está certo e não precisa mudar

Disponibilidade e bot bloqueiam sala por `start_time`/`end_time`
(`availability_engine.py:124` e `:205`), sem recalcular nada. Se o `end_time`
refletir a duração manual, **o bot já enxerga a sala ocupada corretamente** — zero
mudança em `ai_tools.py`, `conversation_agent.py` ou no motor de disponibilidade.

### Decisões do André (16/09/2026)

| Pergunta | Decisão |
|---|---|
| Editar as áreas de um agendamento com duração manual | **Descarta o override** e volta ao cálculo, avisando na tela |
| A duração manual respeita piso/teto/passo | **Não.** Livre, com sanidade só: inteiro, 5 a 480 min |
| Onde entra o campo | **Edição e criação** pelo painel |

---

## 3. Escopo

### Dentro do escopo

- Coluna nova em `scheduler.appointments` para registrar a duração manual,
  separada da calculada.
- Uma função única que decide a duração efetiva (manual ou calculada), usada por
  todo caminho de escrita.
- `reschedule_appointment` deixa de reaplicar a regra quando há duração manual, e
  passa a manter `total_duration_minutes` coerente com o `end_time` em **todos**
  os casos (corrige a divergência que já existe hoje).
- `update_appointment_services` descarta o override e informa isso na resposta.
- API: `POST /appointments` e `PUT /appointments/{id}` aceitam
  `manualDurationMinutes` (e `null` para voltar ao cálculo).
- Painel: campo de duração no `CreateAppointmentModal` e no
  `EditAppointmentModal`, mostrando o valor da regra e permitindo sobrescrever.
- Validação de conflito com a duração efetiva (já acontece; garantir que continua).

### Fora do escopo

- **Qualquer alteração em `scheduler.duration_rules`** ou na duração cadastrada de
  serviços/áreas. O override não toca em nenhuma das duas.
- Dar ao bot acesso ao override. O chat continua derivando a duração, sempre.
- Override de **preço** — o preço segue a soma das áreas e o desconto atual.
- Histórico/auditoria de quem mudou a duração (não existe para nenhum outro campo
  do agendamento hoje; abrir isso só aqui seria inconsistente).

---

## 4. Áreas / arquivos impactados

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | Migration idempotente: `ADD COLUMN IF NOT EXISTS manual_duration_minutes INTEGER`; atualizar o `CREATE TABLE` de `appointments` junto |
| `scheduler/src/services/duracao_manual.py` | **criar** | Autoridade sobre "esta duração é manual ou derivada". Valida faixa, decide a efetiva, explica a recusa |
| `scheduler/src/services/appointment_service.py` | modificar | `create_appointment` passa a aceitar o manual; `reschedule_appointment` para de reaplicar a regra sobre manual e passa a gravar `total_duration_minutes`; `update_appointment_services` descarta o override |
| `scheduler/src/functions/appointment/create.py` | modificar | Ler `manualDurationMinutes` do corpo |
| `scheduler/src/functions/appointment/update.py` | modificar | Ler `manualDurationMinutes`, incluindo `null` explícito para limpar |
| `scheduler/src/functions/appointment/list.py` | modificar | Devolver `manual_duration_minutes` para a tela saber que está fixada |
| `scheduler/src/functions/clinic/dashboard.py` | modificar | Idem, para a agenda do dashboard |
| `frontend/src/types/index.ts` | modificar | `manual_duration_minutes` em `Appointment`; `manualDurationMinutes` nos payloads |
| `frontend/src/pages/agenda/components/DuracaoField.tsx` | **criar** | O campo, compartilhado pelos dois modais |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | modificar | Usar o campo; descartar o override quando as áreas mudarem, avisando |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | modificar | Usar o campo |
| `scheduler/tests/unit/test_duracao_manual.py` | **criar** | A regra da duração efetiva e da faixa |
| `scheduler/tests/unit/test_duracao_manual_sobrevive.py` | **criar** | Fiação: o override sobrevive ao remarcar e morre ao trocar áreas |
| `frontend/src/lib/duracao.test.ts` | modificar | Preview com override |
| `tests/integration/duracao-manual.md` | **criar** | Casos de teste via curl |
| `tests/postman/duracao-manual.postman_requests.json` | **criar** | Requests, padrão de `tests/postman/CLAUDE.md` |

---

## 5. Dependências e riscos

**Dependências**

- Migration roda por `python src/scripts/setup_database.py` contra o Supabase de
  prod (e dev). Idempotente, `ADD COLUMN IF NOT EXISTS`.
- Deploy do backend é manual (`serverless deploy --stage prod`); frontend sai
  automático pela Vercel. **O frontend não pode subir antes do backend**, senão o
  painel manda um campo que a API ignora em silêncio.

**Riscos**

| Risco | Mitigação |
|---|---|
| O override some ao remarcar (armadilha 1) | É o item central do escopo; teste de fiação dedicado, não só de unidade |
| Duração manual longa gera conflito com a próxima paciente | A checagem de conflito já roda com a duração efetiva; teste cobrindo o caso |
| `total_duration_minutes` divergir do `end_time` | O reschedule passa a gravar as duas coisas juntas — isso **corrige** um bug que já existe hoje |
| Alguém usar o override achando que muda a regra da clínica | O campo diz o valor da regra ao lado, e a tela deixa explícito que vale só para aquele agendamento |
| Agendamentos antigos | `manual_duration_minutes` nasce `NULL` = "não tem override". Comportamento idêntico ao de hoje |

---

## 6. Critérios de aceite

- [ ] Fixar 75 min num agendamento cuja regra dá 30 grava 75, e o `end_time`
      reflete 75.
- [ ] Remarcar esse agendamento para outro dia/hora **mantém** 75 — não vira 50
      pelo teto, não vira 30 pela regra.
- [ ] Depois de remarcar, `total_duration_minutes` e `end_time` concordam.
- [ ] Trocar as áreas descarta o override, volta ao calculado e a tela avisa.
- [ ] Limpar o campo (mandar `null`) volta ao calculado.
- [ ] Valores fora de 5..480, ou não inteiros, são recusados com mensagem clara.
- [ ] Um agendamento com duração manual bloqueia a agenda pela duração manual —
      conferido pelo `GetAvailableSlots` e pelo bot.
- [ ] `scheduler.duration_rules` fica **inalterada** em todos os casos acima.
- [ ] O bot continua derivando a duração: nenhuma tool aceita duração informada.
- [ ] Agendamento sem override se comporta exatamente como antes desta task.
- [ ] `npm run build`, `npm run lint` e `pytest tests/unit` verdes.

---

## 7. Referências

- `CLAUDE.md` — padrões do projeto e convenções do scheduler
- `scheduler/src/services/duration_rules.py` — o princípio "derivada, nunca informada"
- `scheduler/src/services/appointment_service.py:360` — a reaplicação da regra no reschedule
- `scheduler/src/services/availability_engine.py:124` — sala ocupada por `end_time`
- PR #32 (`92358da`) — editar áreas recalcula a duração
- `frontend/src/lib/duracao.ts` — o espelho da regra no frontend

---

## Status (preencher após conclusão)

- [ ] Pendente
- [x] Spec gerada: `spec/011-duracao-manual-do-agendamento.md` (16/09/2026)
- [x] Implementado em: 16/09/2026
- [x] Registrado em `TASKS_LOG.md`
