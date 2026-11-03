# Spec - 035 Reagendamento não é cancelamento

> Gerada na fase **Spec** em 01/11/2026. Use como input para a fase Code.

- **PRD de origem:** `prd/035-reagendamento-nao-e-cancelamento.md`

---

## 1. Resumo

Uma coluna `rescheduled_to_id` em `appointments`, gravada no registro antigo, é
a única fonte da distinção: reagendado é `CANCELLED` com vínculo, cancelado é
`CANCELLED` sem vínculo, falta é `NO_SHOW`. O vínculo nasce em **um lugar só**,
dentro de `create_appointment`: ao criar para um paciente que teve um
cancelamento nos últimos 30 minutos na mesma clínica, o antigo é ligado ao
novo e a conversão do Google Ads muda de registro em vez de duplicar. Isso
cobre painel, site e bot sem que nenhum chamador precise saber da regra. O
site ganha "Remarcar" (endpoint público + UI) para que o caso comum nem gere
registro novo: usa o `reschedule_appointment` em lugar. Painel, dashboard,
relatórios, agenda por data e resumo de conversões passam a ler a regra por
um helper SQL único. Um backfill com dry-run aplica a mesma janela aos 37
pares já existentes em prod.

Achados da pesquisa que mudam o plano do PRD:

- **Não há transação entre métodos do service.** Cada `execute_write` abre,
  commita e devolve a conexão ao pool; `db.transaction()` existe, mas
  `cancel_appointment` e `create_appointment` não aceitam conexão. A operação
  "substituir" do PRD vira: **criar primeiro, vincular depois**. Se a criação
  falha (conflito, serviço inativo), nada foi cancelado. Se o vínculo falha
  depois de criado, o novo fica como agendamento solto e o antigo cancelado,
  que é o estado de hoje; o log registra e o backfill corrige. Não há estado
  pior que o atual em nenhum ponto da sequência.
- **A conversão deve ser movida, não re-datada.** `record_conversion` é
  idempotente por `UNIQUE(appointment_id)`, e o uploader do `infra/` sobe o
  evento de agendamento **sem filtro de status** e retrata compra quando o
  agendamento vira `CANCELLED`. Se o novo registro ganhar conversão própria, o
  Google recebe dois agendamentos e uma retratação para uma pessoa que só
  remarcou. Mover a linha de `lead_conversions` para o id novo resolve os três
  casos (compra, agendamento, retratação) sem tocar no uploader.
- **O site já tem seletor de dia e horário reutilizáveis** (`DayList`,
  `TimeSlotGrid`) e a disponibilidade pública recebe o carrinho
  (`serviceIds`, `serviceAreaPairs`, `totalDuration`). Para remarcar, a lista
  de "Meus agendamentos" precisa devolver esses três campos por agendamento,
  e a disponibilidade precisa ignorar o próprio agendamento
  (`excludeAppointmentId`), senão mover 10:00 para 10:30 no mesmo dia colide
  consigo mesmo.
- **Stack do CloudFormation em 435/500.** A rota nova (`/reschedule`) adiciona
  Resource + Method + OPTIONS. Cabe, mas é o último tipo de mudança a fazer
  sem pensar; conferir `aws cloudformation describe-stack-resources | wc -l`
  no deploy de dev.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---|---|
| `scheduler/src/services/reagendamento.py` | Regra única: `JANELA_DE_VINCULO_MIN = 30`, fragmentos SQL `E_REAGENDADO`, `E_CANCELADO_DE_VERDADE`, e `vincula_antecessor(db, novo)` usado por `create_appointment` e pelo backfill |
| `scheduler/src/functions/public_booking/reschedule_appointment.py` | `POST /public/clinics/{clinicId}/appointments/{appointmentId}/reschedule`; mesmo guard do `cancel_appointment.py` |
| `scheduler/src/scripts/backfill_reagendamentos.py` | Dry-run por padrão; `--aplicar` grava; mesma função `vincula_antecessor` |
| `scheduler/tests/unit/test_reagendamento_vincula_antecessor.py` | Vínculo automático: dentro da janela liga; fora não; paciente diferente não; já vinculado não religa; escolhe o cancelamento mais recente; conversão move e `record_conversion` não roda |
| `scheduler/tests/unit/test_reagendamento_nos_relatorios.py` | `dashboard`, `reports`, `agenda_summary`: reagendado sai de cancelados e de `perdido_cents`, entra em `rescheduled`; cadeia de 3 conta 2 reagendamentos e 1 desfecho |
| `scheduler/tests/unit/test_remarcar_pelo_site.py` | Endpoint: token inválido 401; agendamento de outro telefone 404; sucesso mantém `id` e muda data; conflito 409; `my-appointments` devolve `service_ids`, `service_area_pairs`, `total_duration_minutes` |
| `scheduler/tests/unit/test_backfill_reagendamentos.py` | Dry-run não escreve; `--aplicar` escreve uma vez; segunda execução é no-op; pares de importação (cancelado em 08 e 09/09 com data anterior a 09/2026) ficam de fora |
| `scheduler/tests/integration/035-reagendamento.md` | Casos de teste manuais via curl |
| `scheduler/tests/postman/035-reagendamento.postman_requests.json` | Requests do endpoint público e dos relatórios |
| `booking-site/src/components/RescheduleInline.tsx` | Bloco inline dentro do card de "Meus agendamentos": `DayList` + `TimeSlotGrid` + confirmar |
| `booking-site/src/components/RescheduleInline.test.tsx` | Carrega dias com o carrinho do agendamento; seleciona dia e hora; chama o hook; erro 409 mostra mensagem e recarrega a grade |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---|---|
| `scheduler/src/scripts/setup_database.py` | `ADD COLUMN IF NOT EXISTS rescheduled_to_id UUID REFERENCES scheduler.appointments(id)`; índice parcial `idx_appointments_rescheduled_to ON appointments(rescheduled_to_id) WHERE rescheduled_to_id IS NOT NULL`; coluna no `CREATE TABLE`; comentário ao lado do `appointments_status_check` explicando por que não há `RESCHEDULED` |
| `scheduler/src/services/appointment_service.py` | `create_appointment`: entre o insert das junções e o passo 9, chama `vincula_antecessor`; se vinculou e a conversão foi movida, **não** chama `record_conversion`. `cancel_appointment`: inalterado. `reschedule_appointment`: inalterado. `get_active_appointments_by_phone`: devolve `service_ids`, `service_area_pairs`, `total_duration_minutes` |
| `scheduler/src/services/lead_service.py` | Novo `move_conversion(old_appointment_id, new_appointment_id, conversion_date) -> bool`; `resumo_de_conversoes`: `canceladas` usa `E_CANCELADO_DE_VERDADE` |
| `scheduler/src/functions/public_booking/router.py` | Rota `("POST", "public/clinics/{clinicId}/appointments/{appointmentId}/reschedule")` |
| `scheduler/sls/functions/public_booking/interface.yml` | Evento http da rota nova, `cors: true` |
| `scheduler/src/functions/public_booking/availability.py` | Query param opcional `excludeAppointmentId`, repassado à engine |
| `scheduler/src/services/availability_engine.py` | `get_days_status(..., exclude_appointment_id=None)` e `get_available_slots_multi(..., exclude_appointment_id=None)`: o agendamento excluído não ocupa janela |
| `scheduler/src/functions/clinic/dashboard.py` | `cancelled_appointments` com `E_CANCELADO_DE_VERDADE`; novo `rescheduled_appointments`; `cancellation_rate` sobre o novo cancelados; lista do dia expõe `rescheduled_to_id` e `rescheduled_to_date` |
| `scheduler/src/functions/clinic/reports.py` | Idem no summary e no período anterior; novo `rescheduled_appointments` |
| `scheduler/src/functions/clinic/agenda_summary.py` | `cancelados` e `perdido_cents` com `E_CANCELADO_DE_VERDADE`; novo `reagendados` por dia e no total (`rescheduled`) |
| `scheduler/src/functions/appointment/list.py` | SELECT ganha `a.rescheduled_to_id` e LATERAL `rescheduled_to_date` (data do novo) |
| `scheduler/src/functions/appointment/update.py` | Resposta do cancel (`status = CANCELLED`) inalterada; nada a fazer aqui, o vínculo nasce no create |
| `scheduler/src/services/lembrete.py` | Bloco de prompt: "Se ela quiser REMARCAR ou CANCELAR, envie o link ... ela remarca ou cancela em um minuto por lá" |
| `booking-site/src/types/index.ts` | `Appointment` ganha `service_ids: string[]`, `service_area_pairs: {serviceId, areaId}[]`, `total_duration_minutes`; `RescheduleAppointmentPayload` |
| `booking-site/src/services/booking.service.ts` | `rescheduleAppointment(clinicId, appointmentId, {phone, token, date, time})`; `availability` aceita `excludeAppointmentId` |
| `booking-site/src/hooks/useBooking.ts` | `useRescheduleAppointment(clinicId)`: invalida `myAppointments` e `availabilityAll`; `useAvailability` aceita `excludeAppointmentId` na queryKey |
| `booking-site/src/components/MyAppointmentsModal.tsx` | Botão "Remarcar" ao lado de "Cancelar agendamento"; estado `reschedulingId`; renderiza `RescheduleInline`; um só card aberto por vez |
| `booking-site/src/components/MyAppointmentsModal.test.tsx` | Caso: clicar Remarcar abre o bloco e fecha o de cancelar |
| `frontend/src/types/index.ts` | `Appointment.rescheduled_to_id: string \| null`, `rescheduled_to_date: string \| null`; `ReportSummary.rescheduled_appointments`; `AgendaPorData` dia e total ganham `rescheduled` |
| `frontend/src/services/reports.service.ts` | Tipos acima |
| `frontend/src/pages/agenda/components/CancelAppointmentModal.tsx` | Pergunta "A pessoa vai remarcar?" com botão secundário "Remarcar em vez de cancelar" que fecha este modal e abre o `EditAppointmentModal` (callback `onReschedule(appointment)`) |
| `frontend/src/pages/agenda/AgendaPage.tsx` | Passa `onReschedule` ao modal de cancelar: `setCancelling(null); setEditing(a)` |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | Quando `rescheduled_to_id`: cabeçalho "Remarcado para dd/mm" em vez de "Cancelado"; link "ver novo" que navega para a data nova |
| `frontend/src/pages/dashboard/components/KpiCards.tsx` | Card "Cancelamentos" mostra só cancelados de verdade; `detail` vira `"N reagendados"` quando N > 0, senão a taxa |
| `frontend/src/pages/dashboard/components/AgendaPorData.tsx` | Nova coluna "Remarc." entre "Cancelam." e a perda; total "Reagendamentos" |
| `frontend/src/pages/dashboard/components/AgendaPorData.test.tsx`, `KpiCards` testes | Casos com `rescheduled` |
| `docs/work/prd/035-reagendamento-nao-e-cancelamento.md` | Status: Spec gerada |

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação

1. `setup_database.py` (migration) e `reagendamento.py` com os fragmentos SQL. Rodar o setup em dev.
2. `lead_service.move_conversion` + `vincula_antecessor` + chamada em `create_appointment` + teste. A partir daqui, qualquer cancela-e-cria em até 30 min já fica vinculado, por qualquer canal.
3. Relatórios do backend (`dashboard`, `reports`, `agenda_summary`, `list.py`, `resumo_de_conversoes`) + teste. Deploy em dev e conferir os números com um par criado à mão.
4. Backfill + teste. Dry-run em prod para o André conferir a lista contra os 37 pares medidos; `--aplicar` é dele.
5. Endpoint público de remarcar, `excludeAppointmentId` na disponibilidade, campos novos em `my-appointments`, rota no yml + teste. Deploy em dev. Conferir a contagem de resources do stack.
6. Booking-site: tipos, service, hook, `RescheduleInline`, modal + testes. `npm run build` antes do push.
7. Frontend do painel: tipos, modal de cancelar, popover, KPI, agenda por data + testes. `npm run build` antes do push.
8. `lembrete.py` texto + teste existente ajustado.
9. Integração manual (curl) e Postman. Deploy prod do scheduler; Vercel sobe os fronts no merge.

Passos 2 e 3 já entregam o relato da clínica corrigido para frente. Passo 4 corrige para trás. Passos 5 a 7 atacam a causa para que o vínculo seja exceção, não rotina.

---

## 6. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py` (modificar)

```sql
ALTER TABLE scheduler.appointments
  ADD COLUMN IF NOT EXISTS rescheduled_to_id UUID REFERENCES scheduler.appointments(id);
CREATE INDEX IF NOT EXISTS idx_appointments_rescheduled_to
  ON scheduler.appointments(rescheduled_to_id) WHERE rescheduled_to_id IS NOT NULL;
```

- Mesma coluna no `CREATE TABLE` da lista `TABLES`.
- Comentário junto do `appointments_status_check`: "Reagendado NÃO é status. É `CANCELLED` + `rescheduled_to_id`. Motor de horários, lembretes e uploader continuam lendo só `status`; quem precisa distinguir usa `src/services/reagendamento.py`."
- Sem `ON DELETE`: agendamento não é apagado fisicamente.

### `scheduler/src/services/reagendamento.py` (criar)

```python
JANELA_DE_VINCULO_MIN = 30

# Fragmentos para FILTER (...) e WHERE. Alias da tabela entra por format.
E_REAGENDADO = "{a}.status = 'CANCELLED' AND {a}.rescheduled_to_id IS NOT NULL"
E_CANCELADO_DE_VERDADE = "{a}.status = 'CANCELLED' AND {a}.rescheduled_to_id IS NULL"

def vincula_antecessor(db, novo: dict, janela_min=JANELA_DE_VINCULO_MIN) -> Optional[str]:
    """Liga ao `novo` o cancelamento mais recente do mesmo paciente na mesma
    clínica dentro da janela. Devolve o id do antecessor ou None.

    Um UPDATE só, com subselect ORDER BY updated_at DESC LIMIT 1 e
    `rescheduled_to_id IS NULL` no WHERE: idempotente e sem corrida."""
```

- SQL do UPDATE:

```sql
UPDATE scheduler.appointments a
   SET rescheduled_to_id = %(novo)s::uuid, updated_at = NOW()
 WHERE a.id = (
   SELECT c.id FROM scheduler.appointments c
    WHERE c.clinic_id = %(clinic)s AND c.patient_id = %(patient)s::uuid
      AND c.status = 'CANCELLED' AND c.rescheduled_to_id IS NULL
      AND c.id <> %(novo)s::uuid
      AND c.updated_at >= %(criado_em)s - make_interval(mins => %(janela)s)
      AND c.updated_at <= %(criado_em)s + INTERVAL '10 minutes'
    ORDER BY c.updated_at DESC LIMIT 1)
RETURNING a.id
```

- `criado_em` é o `created_at` do novo (não `NOW()`), para o backfill reusar a função com registros antigos. Os 10 minutos depois cobrem quem cria primeiro e cancela em seguida (pares com delta -1 a -7 na medição).
- `patient_id` igual é obrigatório. Dois pacientes no mesmo telefone não se vinculam (risco do PRD).
- Log: `[Reagendamento] antecessor={id} novo={id} clinic={clinic}`.

### `scheduler/src/services/appointment_service.py` (modificar)

- Em `create_appointment`, depois do passo 7 (junções) e antes do passo 9:

```python
antecessor = vincula_antecessor(self.db, result)
conversao_movida = False
if antecessor and self.lead_service:
    try:
        conversao_movida = self.lead_service.move_conversion(
            antecessor, appointment_id, f"{date} {time}-03:00")
    except Exception as e:
        logger.error(f"[AppointmentService] Erro ao mover conversao: {e}")
```

- No passo 9, `record_conversion` só roda se `not conversao_movida`. `mark_as_booked` continua rodando (o lead continua agendado).
- `result["rescheduled_from_id"] = antecessor` na resposta, para o painel poder avisar "vinculado ao cancelamento das 14:02" se quiser (não obrigatório nesta entrega).
- `get_active_appointments_by_phone`: acrescentar ao SELECT

```sql
COALESCE(svc.ids, ARRAY[a.service_id::text]) AS service_ids,
COALESCE(pares.lista, '[]'::json)            AS service_area_pairs
```

  com LATERALs sobre `appointment_services` (array de `service_id::text`) e `appointment_service_areas` (`json_agg(json_build_object('serviceId', service_id, 'areaId', area_id))`). `a.*` já traz `total_duration_minutes`.

### `scheduler/src/services/lead_service.py` (modificar)

```python
def move_conversion(self, old_appointment_id, new_appointment_id, conversion_date) -> bool:
    """Reagendamento com registro novo: a conversão acompanha a pessoa, não o
    id. Compra ainda não enviada passa a esperar a sessão nova; evento de
    agendamento já enviado não sobe de novo; retratação não dispara, porque o
    id apontado está CONFIRMED. Devolve True se havia conversão para mover."""
```

- SQL:

```sql
UPDATE scheduler.lead_conversions
   SET appointment_id = %s::uuid,
       conversion_date = CASE WHEN uploaded_at IS NULL
                              THEN GREATEST(%s::timestamptz, click_date + INTERVAL '1 minute')
                              ELSE conversion_date END
 WHERE appointment_id = %s::uuid
RETURNING id
```

- Compra já enviada (`uploaded_at` preenchido) mantém a data: é a chave no Google (ver docstring da retratação no uploader).
- `resumo_de_conversoes`: `COUNT(*) FILTER (WHERE a.status = 'CANCELLED' AND a.rescheduled_to_id IS NULL) AS canceladas`. Como a conversão foi movida, na prática esse filtro só pega cancelamento de verdade; o fragmento fica pela regra única.

### `scheduler/src/functions/public_booking/reschedule_appointment.py` (criar)

- Copiar a estrutura de `cancel_appointment.py` inteira: api key de intake, path params, `phone` + `token`, `verify_token`, query de posse com `variantes_do_numero` e `status = 'CONFIRMED'`.
- Body: `{ "phone", "token", "date": "YYYY-MM-DD", "time": "HH:MM" }`. Validar formato com `datetime.strptime`; 400 se inválido ou data no passado (fuso da clínica, `business_hours.fuso`).
- `AppointmentService.completo(db).reschedule_appointment(appointment_id, date, time)`.
- `ConflictError` → 409 `{"status": "ERROR", "message": "Esse horário acabou de ser ocupado. Escolha outro."}`; `NotFoundError` → 404; `OptimisticLockError` → 409.
- 200: `{"status": "SUCCESS", "message": "Agendamento remarcado com sucesso", "appointment": _serialize_row(...)}`.

### `scheduler/src/functions/public_booking/availability.py` e `availability_engine.py` (modificar)

- `excludeAppointmentId` (query) → `exclude_appointment_id` nas duas funções usadas pelo site (`get_days_status`, `get_available_slots_multi`).
- Na engine, onde os agendamentos do dia são carregados para montar as janelas ocupadas (`janelas_livres` / `_janelas_das_regras`), acrescentar `AND id <> %s::uuid` quando informado. Um parâmetro, propagado; sem duplicar a query.
- Sem o parâmetro, comportamento idêntico ao atual (teste de regressão: mesma saída para `None`).

### `scheduler/src/functions/clinic/dashboard.py`, `reports.py`, `agenda_summary.py` (modificar)

- Trocar `COUNT(*) FILTER (WHERE status = 'CANCELLED')` por `FILTER (WHERE {E_CANCELADO_DE_VERDADE})` e adicionar `FILTER (WHERE {E_REAGENDADO}) AS rescheduled_appointments` (ou `reagendados` no agenda_summary, exposto como `rescheduled`).
- `perdido_cents` em `agenda_summary`: `FILTER (WHERE {E_CANCELADO_DE_VERDADE})`. A perda de um reagendamento é zero.
- `total_appointments` em `reports.py` é `status != 'CANCELLED'`: continua, porque o novo registro já está contado. Não mudar.
- `cancellation_rate` usa o novo `cancelled`.
- Lista do dia no dashboard e `appointment/list.py`: `a.rescheduled_to_id`, e

```sql
LEFT JOIN LATERAL (SELECT n.appointment_date AS rescheduled_to_date
                   FROM scheduler.appointments n WHERE n.id = a.rescheduled_to_id) rt ON TRUE
```

- Cadeia: o relatório conta por registro, e cada elo intermediário é `CANCELLED` com vínculo, logo "reagendado"; o último elo é `CONFIRMED` ou `NO_SHOW`. Nenhuma CTE recursiva é necessária para as contagens desta entrega. "Compareceu depois de remarcar?" é pergunta do prontuário, fora do escopo; a coluna já permite responder no futuro.

### `scheduler/src/scripts/backfill_reagendamentos.py` (criar)

```
python -m src.scripts.backfill_reagendamentos <clinic_id> [--aplicar] [--desde 2026-09-01]
```

- Seleciona `CONFIRMED | NO_SHOW | CANCELLED` criados desde `--desde`, em ordem de `created_at`, e chama `vincula_antecessor(db, novo)` para cada um. Em dry-run, substitui o UPDATE por SELECT equivalente e imprime `antecessor, data antiga, novo, data nova, delta_min, status do novo`.
- Exclui importação: antecessor com `appointment_date < '2026-09-01'`.
- Idempotente pelo `rescheduled_to_id IS NULL` do UPDATE. Imprime total vinculado ao final.
- Não move conversões no backfill: as conversões dos pares antigos já foram ou não enviadas, e mexer nelas agora é assunto do PRD 016/017. Dizer isso no docstring.

### `scheduler/src/services/lembrete.py` (modificar)

- Texto quando há link: `"Se ela quiser REMARCAR ou CANCELAR, NÃO execute nada: envie o link {link} e diga que por lá ela remarca ou cancela em um minuto, com o mesmo número de WhatsApp. ..."`. Ajustar o teste que casa com a frase atual.

### `booking-site/src/components/RescheduleInline.tsx` (criar)

- Props: `clinicId`, `appointment: Appointment`, `phone`, `token`, `onDone()`, `onBack()`.
- Monta `cart` a partir de `appointment.service_ids` e `service_area_pairs`; chama `useAvailability(clinicId, cart, true, { excludeAppointmentId: appointment.id })`; `DayList` com `days`; ao escolher o dia, slots do dia (mesmo hook usado em `Booking.tsx` para a grade de horários); `TimeSlotGrid`.
- Botão "Confirmar remarcação" desabilitado até dia e hora; chama `useRescheduleAppointment`. Sucesso: `onDone()`; o modal mostra o card já com a data nova (query invalidada). Erro 409: mensagem inline e `refetch` da grade. Outros erros: `ErrorState` com retry.
- Quatro estados: loading (Spinner), erro (ErrorState), vazio (nenhum dia disponível: texto + telefone da clínica, igual ao `DayList`), sucesso.
- Mobile first: ocupa a largura do card; `DayList` e `TimeSlotGrid` já são responsivos.

### `booking-site/src/components/MyAppointmentsModal.tsx` (modificar)

- Estado `reschedulingId`; abrir um fecha o outro (`setCancelingId(null)`).
- Dois botões de texto no rodapé do card: "Remarcar" (cor `brand`) e "Cancelar agendamento" (cor `danger`), separados por `·`. Hierarquia: remarcar à esquerda, é a ação que queremos.
- `handleClose` também zera `reschedulingId`.

### `booking-site/src/services/booking.service.ts`, `hooks/useBooking.ts`, `types/index.ts` (modificar)

```ts
rescheduleAppointment: (clinicId, appointmentId, body: { phone; token; date; time }) =>
  api.post<{ appointment: Appointment }>(`/public/clinics/${clinicId}/appointments/${appointmentId}/reschedule`, body)
     .then((r) => r.data.appointment)
```

- `bookingKeys.availability(clinicId, cart, excludeAppointmentId?)`: o id entra na key para não reaproveitar a grade do fluxo normal.
- `useRescheduleAppointment`: `onSuccess` invalida `myAppointments(clinicId, phone)`; `onSettled` invalida `availabilityAll(clinicId)`.

### `frontend/src/pages/agenda/components/CancelAppointmentModal.tsx` (modificar)

- Nova prop `onReschedule: (a: Appointment) => void`.
- Acima dos botões, bloco neutro: "A pessoa vai remarcar? Então não cancele: edite a data e o agendamento continua o mesmo." com botão `variant="secondary"` "Remarcar em vez de cancelar" → `onReschedule(appointment)`.
- Botões finais inalterados ("Voltar", "Confirmar cancelamento").

### `frontend/src/pages/agenda/AgendaPage.tsx` (modificar)

- `onReschedule={(a) => { setCancelling(null); setEditing(a) }}` (usar o nome real do estado que abre o `EditAppointmentModal`).

### `frontend/src/pages/agenda/components/AppointmentPopover.tsx` (modificar)

- `const remarcado = isCancelled && a.rescheduled_to_id`. Quando `remarcado`: rótulo "Remarcado para {dd/mm}" no lugar de "Cancelado", cor neutra (`gray`) em vez de vermelha; botão de texto "Ver novo" que chama `onNavigateToDate(a.rescheduled_to_date)` (prop nova, ligada ao seletor de data da agenda).
- `AgendaDoDia` e `WeekGrid` já filtram `CANCELLED`; não mudam.

### `frontend/src/pages/dashboard/components/KpiCards.tsx` e `AgendaPorData.tsx` (modificar)

- KPI "Cancelamentos": `value = cancelled_appointments`; `detail = rescheduled_appointments > 0 ? \`${n} reagendado(s)\` : \`${rate}% taxa\``. Mantém grid de 4.
- `AgendaPorData`: coluna "Remarc." (`d.rescheduled`), célula `—` quando zero (mesmo tratamento da coluna de cancelamentos); linha de totais "Reagendamentos".

### `scheduler/tests/integration/035-reagendamento.md` e Postman (criar)

Casos: remarcar pelo site (200, mesmo id), token inválido (401), agendamento de outro telefone (404), conflito (409), `my-appointments` com os campos novos, painel cria em até 30 min após cancelar e `GET /appointments` mostra `rescheduled_to_id`, dashboard e `agenda-summary` com `rescheduled`.

---

## 7. Convenções a respeitar

- Migrations idempotentes; coluna também no `CREATE TABLE` (CLAUDE.md).
- Regra num lugar só (`reagendamento.py`); nenhum handler escreve `rescheduled_to_id` por conta própria. Antes do PR: `grep -rn "CANCELLED" scheduler/src frontend/src booking-site/src` e justificar cada ocorrência que não usa o fragmento (motor de horários, lembretes e uploader ficam com `status` puro, de propósito).
- Testes de comportamento com `MagicMock` do db como em `test_agenda_summary.py`; nada de `assertIn` no fonte.
- Frontend e booking-site: 4 estados, named exports, zero `any`, `npm run build` e `npm run lint` antes do push.
- Logging `[Reagendamento] ...` e `[AppointmentService] ...` como o restante do service.
- Deploys de dev e prod nunca em paralelo; conferir estado real após o deploy, não o exit code.
