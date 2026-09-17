# Spec — 011 Duração manual do agendamento

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/011-duracao-manual-do-agendamento.md`

---

## 1. Resumo

Uma coluna nova (`manual_duration_minutes`) registra a duração que uma pessoa
fixou para **um** agendamento. Um módulo novo (`duracao_manual.py`) é a única
autoridade sobre a faixa válida e sobre qual duração vale — manual ou calculada.
`appointment_service.py` passa a consultar esse módulo em todos os três caminhos
de escrita (criar, remarcar, trocar áreas), e o `reschedule` para de reaplicar a
regra por cima de decisão humana. A API ganha `manualDurationMinutes` na criação
e na edição, e o painel ganha um campo compartilhado pelos dois modais.

`scheduler.duration_rules` não é lida para gravar o override e não é escrita em
lugar nenhum desta task.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/services/duracao_manual.py` | Faixa válida, validação e a decisão "manual ou calculada" |
| `scheduler/tests/unit/test_duracao_manual.py` | A regra: faixa, efetiva, recusas |
| `scheduler/tests/unit/test_duracao_manual_sobrevive.py` | Fiação: sobrevive ao remarcar, morre ao trocar áreas |
| `frontend/src/pages/agenda/components/DuracaoField.tsx` | O campo, usado pelos dois modais |
| `tests/integration/duracao-manual.md` | Casos de teste via curl |
| `tests/postman/duracao-manual.postman_requests.json` | Requests, padrão de `tests/postman/CLAUDE.md` |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/scripts/setup_database.py` | Migration idempotente + `CREATE TABLE` de `appointments` em sincronia |
| `scheduler/src/services/appointment_service.py` | `create_appointment` aceita o manual; novo `set_manual_duration`; `reschedule_appointment` para de reaplicar a regra e passa a gravar a duração; `update_appointment_services` descarta o override |
| `scheduler/src/functions/appointment/create.py` | Ler `manualDurationMinutes` |
| `scheduler/src/functions/appointment/update.py` | Ler `manualDurationMinutes` (inclusive `null`); nova etapa **antes** do reschedule |
| `scheduler/src/functions/appointment/list.py` | Devolver `manual_duration_minutes` |
| `scheduler/src/functions/clinic/dashboard.py` | Devolver `manual_duration_minutes` |
| `frontend/src/types/index.ts` | `manual_duration_minutes` em `Appointment`; `manualDurationMinutes` nos dois payloads |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx` | Usar `DuracaoField`; descartar override ao mudar áreas |
| `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx` | Usar `DuracaoField` |
| `frontend/src/lib/duracao.test.ts` | Casos com override |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

A ordem existe para que cada passo seja testável sozinho e para que nada chegue
ao painel antes de o backend aceitar.

1. **Migration** (`setup_database.py`) — a coluna nasce, tudo segue igual.
2. **`duracao_manual.py` + `test_duracao_manual.py`** — a regra pura, sem I/O.
3. **`appointment_service.py`** — os três caminhos de escrita, nesta ordem:
   `create` → `set_manual_duration` (novo) → `reschedule` → `update_services`.
4. **`test_duracao_manual_sobrevive.py`** — a fiação, antes de expor pela API.
5. **Handlers** (`create.py`, `update.py`, `list.py`, `dashboard.py`).
6. **Deploy do backend em prod** e migration rodada. *Obrigatoriamente antes do
   passo 7*: a Vercel publica o frontend sozinha, e um painel que manda um campo
   que a API ignora perde a decisão da atendente em silêncio.
7. **Frontend** (`types` → `DuracaoField` → os dois modais → testes).
8. **Docs de teste** (`tests/integration`, `tests/postman`).

---

## 6. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py`

- **Modificar**
- Em `MIGRATIONS`, junto das outras de `appointments`:
  ```python
  # A duracao que uma PESSOA fixou para este agendamento. NULL = sem override,
  # que e o comportamento de sempre. Separada de total_duration_minutes de
  # proposito: uma guarda o que a regra calcula, a outra o que alguem decidiu,
  # e poder comparar as duas e o que permite voltar atras.
  "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS manual_duration_minutes INTEGER",
  ```
- No `CREATE TABLE` de `appointments` em `TABLES`, adicionar
  `manual_duration_minutes INTEGER` (convenção do `CLAUDE.md`: os dois em sincronia).
- **Sem `CHECK` no banco.** A faixa vive em `duracao_manual.py`; duplicá-la no
  schema criaria duas fontes que divergem quando uma muda.

### `scheduler/src/services/duracao_manual.py`

- **Criar**
- Docstring de cabeçalho no estilo do módulo vizinho, registrando a decisão:
  por que o override existe, por que ele **não** passa por piso/teto/passo, e que
  ele nunca toca a regra da clínica.
- Constantes e funções:

  ```python
  MINIMO, MAXIMO = 5, 480

  def valida(valor):
      """O inteiro de minutos, ou None quando não há override.

      Levanta ValueError com mensagem para a atendente quando está fora da
      faixa. Aceita None e "" como "sem override" - o campo vazio da tela e o
      null explícito do payload são a mesma intenção.
      """

  def efetiva(calculada, manual):
      """A duração que vale: a manual quando existe, a calculada quando não.

      Única resposta para essa pergunta em todo o sistema. Se algum caminho de
      escrita decidir sozinho, volta a existir mais de uma verdade sobre quanto
      tempo a sala fica ocupada - que é o defeito que duration_rules resolveu.
      """
  ```

- `efetiva` trata `0` como ausência de override (coerente com `MINIMO = 5`), para
  um `0` vindo de payload malformado não zerar a agenda.
- **Não** importa `duration_rules`: o manual não passa por piso, teto nem passo.
  Essa independência é o ponto, e um import criaria a tentação de "só clampar um
  pouquinho".

### `scheduler/src/services/appointment_service.py`

- **Modificar**

**`create_appointment`**
- Novo parâmetro `manual_duration_minutes: Optional[int] = None`.
- Depois do bloco que calcula `duration_minutes` (linha ~86), aplicar:
  ```python
  manual = valida_duracao_manual(manual_duration_minutes)
  duration_minutes = duracao_efetiva(duration_minutes, manual)
  ```
- O log de "ignorando total_duration_minutes" (linha ~94) **fica como está**. Ele
  guarda outro princípio: `total_duration_minutes` vindo do chamador continua sem
  valor nenhum. Quem informa duração agora é `manual_duration_minutes`, e só ele.
- Gravar `manual_duration_minutes` no `INSERT` (linha ~180).

**`set_manual_duration(appointment_id, minutos, verificar_conflito=True)`** — novo
- Lê o agendamento com `version` (mesmo padrão de lock dos outros métodos).
- `minutos is None` → limpa o override e **recalcula** a duração a partir das
  áreas gravadas em `appointment_service_areas`, passando por
  `duracao_da_sessao`. Voltar ao cálculo tem de voltar ao cálculo de verdade,
  não ao último valor gravado.
- `minutos` válido → é a duração efetiva, sem piso/teto/passo.
- Recalcula `end_time` a partir de `start_time` + duração efetiva.
- Confere conflito com o mesmo `SELECT` dos outros métodos, **exceto** quando
  `verificar_conflito=False` (ver `update.py`: um reschedule vindo logo em seguida
  conferiria contra a data errada).
- `UPDATE` grava `manual_duration_minutes`, `total_duration_minutes`, `end_time`,
  `version + 1`, `updated_at`. Lock otimista: 0 linhas → `OptimisticLockError`.

**`reschedule_appointment`** — a correção central
- Hoje (linha ~360):
  ```python
  duration_minutes = duracao_da_sessao(
      duration_minutes, get_duration_rules(self.db, clinic_id))
  ```
  Passa a rodar **só quando não há override**:
  ```python
  # A normalizacao existe para agendamento criado sob a regra antiga, e isso
  # continua valendo. Mas duracao que uma PESSOA fixou nao e regra velha: ate
  # 16/09/2026 um override de 75min virava 50 no teto assim que alguem
  # remarcasse, e o end_time mudava sem a coluna mudar. Ver duracao_manual.
  manual = appointment.get("manual_duration_minutes")
  if manual:
      duration_minutes = duracao_efetiva(duration_minutes, manual)
  else:
      duration_minutes = duracao_da_sessao(
          duration_minutes, get_duration_rules(self.db, clinic_id))
  ```
- O `UPDATE` (linha ~389) passa a gravar também
  `total_duration_minutes = %s`. **Vale para os dois casos, com e sem override** —
  hoje o reschedule muda `end_time` e deixa a coluna velha, e isso já é um bug em
  produção.

**`update_appointment_services`**
- Depois de `calcula_duracao` (linha ~487), zerar o override:
  ```python
  # O override foi decidido para OUTRO conjunto de areas. Mudou a area, mudou
  # a premissa - manter seria carregar 50min escolhidos para quatro areas numa
  # sessao que agora tem uma. Decisao do Andre em 16/09/2026.
  ```
- O `UPDATE` (linha ~526) passa a incluir `manual_duration_minutes = NULL`.
- O retorno ganha `manual_duration_descartada: bool`, para o handler informar a
  tela. Sem isso o valor some e a atendente não sabe por quê.

### `scheduler/src/functions/appointment/create.py`

- **Modificar**
- Ler `body.get("manualDurationMinutes")` e repassar a `create_appointment`.
- Envolver a chamada de forma que `ValueError` de `duracao_manual` vire
  **400** com a mensagem do módulo, não 500.
- Atualizar a docstring do handler com o campo novo.

### `scheduler/src/functions/appointment/update.py`

- **Modificar**
- Ler `manual_duration = body.get("manualDurationMinutes")`, distinguindo
  **ausente** (não mexe) de **`null`** (limpa o override). Usar
  `"manualDurationMinutes" in body` — `body.get()` devolve `None` nos dois casos,
  e tratá-los igual impediria limpar o campo.
- **A ordem das etapas muda.** Hoje é: (1) serviço/áreas → (2) reschedule →
  (3) campos simples. A duração manual **não pode** entrar em (3): o `end_time`
  já teria sido calculado em (2) com a duração antiga. Nova ordem:

  | # | Etapa | Observação |
  |---|---|---|
  | 1 | serviço/áreas | descarta o override; se o corpo também traz `manualDurationMinutes`, o novo valor vence e é aplicado em 2 |
  | 2 | **duração manual** | `verificar_conflito=False` quando 3 vai rodar |
  | 3 | reschedule | usa a duração efetiva, já correta |
  | 4 | campos simples | notes, status, desconto, primeira visita |

- Quando a etapa 1 descartar um override e o corpo **não** trouxer um valor novo,
  acrescentar a `messages` algo como
  `"duração manual descartada (as áreas mudaram)"`, para a resposta contar o que
  aconteceu.
- `ValueError` → 400.

### `scheduler/src/functions/appointment/list.py` e `clinic/dashboard.py`

- **Modificar**
- Acrescentar `a.manual_duration_minutes` ao `SELECT`. `duration_minutes`
  (que é `total_duration_minutes`) continua sendo a duração efetiva — a tela usa
  ele para desenhar o bloco, e `manual_duration_minutes` só para saber se mostra
  a marca de "fixada".

### `frontend/src/types/index.ts`

- **Modificar**
- `Appointment`: `manual_duration_minutes: number | null`.
- `UpdateAppointmentPayload` e o payload de criação:
  `manualDurationMinutes?: number | null`.

### `frontend/src/pages/agenda/components/DuracaoField.tsx`

- **Criar**
- Props: `{ calculada?: number; manual: number | null; onChange: (v: number | null) => void; disabled?: boolean }`.
- Estado visual, dois casos:
  - **sem override:** `Duração: 30 min` + nota `calculada pelas áreas` + botão
    `Ajustar`.
  - **com override:** input numérico + `a regra calcula 30 min` + botão
    `Voltar ao cálculo` (chama `onChange(null)`).
- Validação local espelhando `MINIMO`/`MAXIMO` (5..480, inteiro), com a mesma
  mensagem do backend. É preview: quem decide é o servidor.
- O texto deixa explícito que vale **só para este agendamento**. É a defesa contra
  o mal-entendido de achar que mudou a regra da clínica.
- Sem `default export` (convenção do `frontend/CLAUDE.md`).

### `frontend/src/pages/agenda/components/EditAppointmentModal.tsx`

- **Modificar**
- `const [manualDuration, setManualDuration] = useState(appointment?.manual_duration_minutes ?? null)`.
- `const duracaoEfetiva = manualDuration ?? totalDuration` — e **`useAvailableSlots`
  passa a receber `duracaoEfetiva`**, não `totalDuration`. Sem isso a tela oferece
  horários que não cabem na sessão.
- `areasChanged === true` → limpar `manualDuration` pelo padrão de derived state
  já usado no arquivo (o `prevSlotKey`), mostrando o aviso combinado.
- `manualChanged` entra em `hasChanges`; `payload.manualDurationMinutes` é enviado
  quando mudou, inclusive como `null`.

### `frontend/src/pages/agenda/components/CreateAppointmentModal.tsx`

- **Modificar**
- Mesmo padrão: estado, `duracaoEfetiva` alimentando os slots, campo no formulário,
  `manualDurationMinutes` no payload quando preenchido.
- Trocar áreas **limpa** o campo, como na edição — mesma razão.

### `scheduler/tests/unit/test_duracao_manual.py`

- **Criar** — a regra pura:
  - `efetiva(30, 75) == 75`; `efetiva(30, None) == 30`; `efetiva(30, 0) == 30`.
  - `valida` aceita `5`, `480`, `"37"`; recusa `0`, `4`, `481`, `-10`, `"abc"`, `3.5`.
  - `valida(None) is None` e `valida("") is None`.
  - **O manual ignora piso, teto e passo**: com a regra da Essência
    (10/50/5), `efetiva` devolve `75` e `7` intactos. É o caso que justifica a
    task inteira.

### `scheduler/tests/unit/test_duracao_manual_sobrevive.py`

- **Criar** — a fiação, no espírito de `test_trava_de_areas_ligada`. A regra pode
  estar certa e o override sumir mesmo assim; é o que acontece hoje.
  - Remarcar um agendamento com override de 75 e teto 50 **mantém 75**, e o
    `end_time` gravado bate com 75.
  - Depois de remarcar, `total_duration_minutes == 75` (a divergência de hoje).
  - Remarcar **sem** override continua normalizando pela regra — a correção não
    pode desligar a normalização de agendamento antigo.
  - Trocar áreas zera `manual_duration_minutes` e devolve
    `manual_duration_descartada=True`.
  - `set_manual_duration(None)` recalcula pelas áreas, não devolve o último valor.
  - Duração manual longa que invade a próxima paciente levanta `ConflictError`.
  - Em nenhum caso há `UPDATE`/`INSERT` em `scheduler.duration_rules`.

---

## 7. Convenções a respeitar

- **Migrations idempotentes** (`ADD COLUMN IF NOT EXISTS`) e `CREATE TABLE` em
  sincronia — `CLAUDE.md`, seção Database Migrations.
- **Fonte única**: a faixa e a decisão "manual ou calculada" existem em
  `duracao_manual.py` e em nenhum outro lugar do backend. O frontend espelha, com
  comentário dizendo que espelha — como `duracao.ts` já faz com a regra.
- Naming: handlers `src.functions.{domain}.{module}.handler`; RDS
  `scheduler.{table}`; nada de `default export` no frontend.
- Logging com `[Duracao]`, seguindo o prefixo já usado em `appointment_service.py`.
- Frontend: TanStack Query para estado de servidor, zero `any`, os 4 estados nas
  views que buscam dados.
- **Ordem de deploy**: backend + migration antes do frontend (passo 6 antes do 7).

---

## 8. O que esta spec deliberadamente não faz

- Não toca em `duration_rules.py`, `ai_tools.py`, `conversation_agent.py` nem
  `availability_engine.py`. O bot continua derivando a duração, e a sala continua
  sendo bloqueada por `end_time` — que passa a refletir o override sem que o
  motor de disponibilidade saiba que ele existe.
- Não cria auditoria de quem mudou a duração. Nenhum outro campo do agendamento
  tem isso hoje; abrir só aqui seria inconsistente.
- Não permite override de preço.
