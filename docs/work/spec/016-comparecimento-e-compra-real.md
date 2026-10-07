# Spec — 016 Comparecimento, para a conversão PURCHASE ser verdade

> Gerado na fase **Spec**, a partir de `docs/work/prd/016-comparecimento-e-compra-real.md`.

---

## 1. O que a exploração do código, e a revisão do André, mudaram no plano

Cinco coisas - as quatro primeiras que o PRD não podia saber, e a 1.4 que
corrige um erro desta própria Spec:

### 1.1 Não precisa de rota nova — e isso economiza o CloudFormation

Já existe `UpdateAppointment` (`PUT /appointments/{appointmentId}`), que aceita
`status` no corpo. Estender esse handler custa **zero recursos** de
CloudFormation. Uma rota nova custaria ~6-7, e o `scheduler` está em 452/500.

### 1.2 Não existe CHECK em `appointments.status`

A coluna é `VARCHAR(20)`, nullable, default `'CONFIRMED'`, e **sem constraint
nenhuma** (conferido em prod: só as 5 chaves estrangeira/primária). O banco já
aceitaria `'NO_SHOW'` hoje.

Mas o handler escreve o status **cru**:

```python
if new_status:
    updates.append("status = %s")
    params.append(new_status)
```

Então `"NOSHOW"`, `"no_show"` ou qualquer typo é gravado em silêncio, e o
agendamento sai das duas queries do uploader — não é elegível (`= 'CONFIRMED'`)
nem tem o valor zerado (`= 'CANCELLED'`). A conversão fica órfã, viva no Google
e invisível aqui. **Validar o status entra no escopo**, porque a feature nova é
precisamente a que introduz um terceiro valor para alguém errar.

### 1.3 `NO_SHOW` deve mexer SÓ no status

`cancel_appointment` faz três coisas além do status: incrementa `version`, chama
`passa_a_marca_adiante` e cancela o lembrete.

`passa_a_marca_adiante` move `is_first_visit` para a próxima sessão confirmada e
**não tem inverso**. Como marcar falta é reversível (existe o desmarcar),
espelhá-lo tornaria o desmarcar lossy: a marca de estreia não voltaria.

Lembrete fica de fora por outra razão: ele é sobre a sessão existir na agenda,
e a falta registra que o horário foi perdido - não que a sessão deixou de estar
marcada. Cancelá-lo aqui mudaria o que a paciente recebe por causa de uma
anotação administrativa.

**Consequência aceita e registrada:** quem falta na estreia continua com
`is_first_visit = TRUE` na linha da falta, então a próxima sessão — a primeira
em que a pessoa de fato pisa na clínica — aparece como veterana. É o mesmo
defeito que a decisão de 09/09/2026 resolveu para cancelamento. Fica como
pendência própria, porque consertar aqui exigiria um inverso de
`passa_a_marca_adiante` que não existe, e inventá-lo nesta fatia trocaria um
defeito de exibição estreito por risco de corromper a marca.

### 1.4 Não há guard de data — revisão do André em 04/10/2026

A primeira versão desta Spec exigia `appointment_date < hoje` para marcar falta.
**Estava errado**, e o André apontou o cenário que a derruba: a cliente não
aparece às 10h de hoje, outra se interessa pelo horário às 10h30. Com o guard, a
recepcionista não pode marcar a falta — teria de **cancelar** para liberar o
horário, perdendo exatamente a informação que o status existe para capturar.

E o raciocínio é mais amplo: **avisar no dia é falta, não cancelamento** — o
horário já não dá para preencher. Quem distingue os dois é quem está no balcão,
com contexto que o código não tem (a razão da cliente, a chance de reocupar).
Encodar uma política do tipo "menos de 24h é falta" seria inventar regra que
ninguém pediu.

O que separa `NO_SHOW` de `CANCELLED`, então, não é o momento: é a **contagem**.
As duas liberam o horário; só `NO_SHOW` registra que ele foi perdido.

**Efeito colateral bom:** sem o predicado de data em `marca_no_show`, a exceção
que esta Spec havia aberto no `test_elegibilidade_tem_um_dono` deixou de ser
necessária. Aquele guard voltou sem brecha.

**Preço aceito:** "Marcar falta" aparece em qualquer agendamento confirmado,
inclusive de sessão distante. Um clique errado ali registra falta do que não
aconteceu — e o desfazer está no toast e na linha de faltas ocultas.

### 1.5 Marcar falta não leva modal

`CancelAppointmentModal` existe porque cancelar é irreversível ("Essa acao nao
pode ser desfeita"). Marcar falta **é** reversível, então a confirmação não se
paga: vira ação direta no popover, alternando entre marcar e desmarcar. Cerimônia
que não compra nada treina a clicar sem ler.

---

## 2. Arquivos, em ordem de implementação

A ordem importa: o banco aceita antes de alguém escrever; o backend recusa o
inválido antes de o frontend oferecer; o uploader entende antes de a falta
existir.

### 2.1 `scheduler/src/scripts/setup_database.py` — migration

Duas instruções no fim da lista, no padrão idempotente que o arquivo já usa
(`DROP CONSTRAINT IF EXISTS` + `DO $$ IF NOT EXISTS`):

```sql
ALTER TABLE scheduler.appointments
  DROP CONSTRAINT IF EXISTS appointments_status_check;

DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint
                 WHERE conname = 'appointments_status_check') THEN
    ALTER TABLE scheduler.appointments
      ADD CONSTRAINT appointments_status_check
      CHECK (status IS NULL OR status IN ('CONFIRMED','CANCELLED','NO_SHOW'));
  END IF;
END $$;
```

`status IS NULL OR` acompanha o padrão de `patients_skin_type_check`: a coluna é
nullable, e uma CHECK que proíba NULL reprovaria linha que o default nunca
preencheu.

Também atualizar o `CREATE TABLE` de `appointments` na lista `TABLES`, conforme a
convenção do `CLAUDE.md` — o `IF NOT EXISTS` não reexecuta, mas os dois
divergirem engana quem lê.

### 2.2 `scheduler/src/services/appointment_service.py`

```python
NO_SHOW = "NO_SHOW"

def marca_no_show(self, appointment_id) -> Dict[str, Any]
def desmarca_no_show(self, appointment_id) -> Dict[str, Any]
```

`marca_no_show`: `WHERE id = %s AND status = 'CONFIRMED'`. O filtro no WHERE,
não em `if` no Python — quem consulta primeiro e escreve depois deixa janela
entre as duas: a recepção marca falta no mesmo instante em que a paciente
cancela pelo bot, e o segundo UPDATE sobrescreve o primeiro sem ninguém notar.
Sem linha → `NotFoundError`.

Sem predicado de data, por 1.4.

`desmarca_no_show`: `WHERE id = %s AND status = 'NO_SHOW'`.

Ambos `version = version + 1` e `updated_at = NOW()`. Nenhum dos dois chama
`passa_a_marca_adiante` nem toca lembrete (ver 1.3).

### 2.3 `scheduler/src/functions/appointment/update.py`

- `STATUS_VALIDOS = {"CONFIRMED", "CANCELLED", "NO_SHOW"}`; status fora disso →
  400 nomeando os aceitos. **Antes** de qualquer escrita.
- `NO_SHOW` é exclusivo, como `CANCELLED`: chama `marca_no_show` e retorna.
- `CONFIRMED` sobre um agendamento `NO_SHOW` é o desmarcar: chama
  `desmarca_no_show`. Precisa ler o status atual para decidir, porque hoje
  `status='CONFIRMED'` cairia no UPDATE genérico e pularia o guard.
- `CONFIRMED` sobre `CONFIRMED` segue pelo caminho genérico (no-op de status).

### 2.4 `infra/src/functions/conversions/uploader.py`

- `_get_pending_retractions`: `a.status = 'CANCELLED'` →
  `a.status IN ('CANCELLED', 'NO_SHOW')`. Falta descoberta depois do upload tem
  o valor zerado, igual a cancelamento.
- `_get_pending_conversions` **não muda**: já exige `= 'CONFIRMED'`, então
  `NO_SHOW` sai sozinho.
- Docstrings: registrar que o mecanismo passou a existir, **sem** remover o aviso
  de que o guard não prova presença — ele continua verdadeiro enquanto a
  cobertura de `NO_SHOW` não se provar. `test_o_limite_do_guard_esta_escrito`
  segue valendo.

### 2.5 Frontend

| Arquivo | Mudança |
|---|---|
| `src/types/index.ts` | `AppointmentStatus` ganha `'NO_SHOW'` |
| `src/services/appointments.service.ts` | `marcarFalta` e `desmarcarFalta` |
| `src/hooks/useAppointments.ts` | `useMarcarFalta`, `useDesmarcarFalta`, invalidando as mesmas três chaves |
| `src/pages/agenda/components/AppointmentPopover.tsx` | ação "Marcar falta" (qualquer CONFIRMED) e "Desmarcar falta" (NO_SHOW) |
| `src/pages/agenda/components/AgendaDoDia.tsx` | falta visualmente distinta (esmaecida, riscada, marcador `FALTOU`) |
| `src/pages/agenda/components/WeekGrid.tsx` | idem |
| `src/lib/faltasNaAgenda.ts` | `semFaltas` e `contaFaltas`, com teste próprio |

### A falta sai da agenda por padrão

Decisão do André em 04/10/2026. O motivo é de espaço: `NO_SHOW` libera o horário
(as queries de conflito e de horários livres usam `= 'CONFIRMED'`, verificado),
então o slot é reaproveitado — e aí os dois agendamentos se sobrepõem e
`distribuiEmColunas` dá **metade da largura a cada um**. O agendamento que
importa encolhe por causa de um registro histórico.

**Mas não desaparece em silêncio.** Não existe nenhuma outra tela onde um
agendamento em falta seja alcançável (não há histórico de agendamentos do
paciente — verificado), então filtrar sem dizer nada esconderia a informação e
tiraria o único caminho para "Desmarcar falta" depois que o toast passa.

A solução é uma linha que aparece **só quando há falta na faixa visível**:

```
2 faltas ocultas · mostrar
```

Controle permanente para algo que quase sempre está ausente é ruído, e a
contagem já é a informação que se perderia. A lógica mora em `lib/` e não dentro
da página, porque é regra que decide o que a agenda mostra.

---

## 3. Testes

| Teste | Onde | O que trava |
|---|---|---|
| `NO_SHOW` aceito pela constraint | `scheduler/tests/unit` | a migration existe e lista os três valores |
| status inválido → 400 | `scheduler/tests/unit` | o typo para de ser gravado em silêncio |
| `marca_no_show` exige CONFIRMED | `scheduler/tests/unit` | o filtro está no WHERE, não em `if` |
| **não** há guard de data | `scheduler/tests/unit` | a revisão de 04/10 não é desfeita por engano |
| `marca_no_show` não chama `passa_a_marca_adiante` | `scheduler/tests/unit` | a decisão de 1.3 não é desfeita por engano |
| `desmarca_no_show` só age sobre NO_SHOW | `scheduler/tests/unit` | não ressuscita cancelado |
| falta sai da elegibilidade | `infra/tests/unit` | `= 'CONFIRMED'` continua exato |
| falta entra no zeramento | `infra/tests/unit` | `IN ('CANCELLED','NO_SHOW')` |
| aviso do guard continua escrito | `infra/tests/unit` | já existe; tem de seguir verde |
| popover oferece marcar em hoje E no futuro | `frontend` | o guard não volta pela porta da tela |
| `semFaltas` / `contaFaltas` | `frontend` | o filtro e a contagem, isolados e sem mutar o cache |
| popover oferece desmarcar em NO_SHOW | `frontend` | o caminho de volta existe |
| falta distinta de cancelado na agenda | `frontend` | os dois estados não se confundem |

---

## 4. Fora do escopo

- Backfill das 604 sessões passadas — vale daqui para frente.
- Inverso de `passa_a_marca_adiante` (ver 1.3).
- Promover `PURCHASE` a biddable — depende de a cobertura de `NO_SHOW` se provar.
- Rebaixar `PURCHASE` no nível da conta — é painel, não código, e é pendência
  própria.

---

## 5. Risco que a Spec não remove

**Adoção.** Se a recepção não marcar falta, nada muda: o evento continua
afirmando compras não verificadas, exatamente como hoje. A diferença é que o
sistema passa a ter onde registrar, e os 26% de cancelamento que chegam 7+ dias
depois da sessão sugerem que a prática já existe — hoje conflada com
cancelamento.

**Medir antes de confiar:** contar `NO_SHOW` em 60 dias. Cobertura baixa
significa que o número do Google continua sendo agendamento, não compra, e
promover a ação a biddable seria prematuro.
