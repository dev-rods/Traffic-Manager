# Spec - 054 Regras de cancelamento, falta e remarcação, e o que os relatórios contam

> Gerada em 20/11/2026 a partir de `prd/054-regras-de-cancelamento-falta-e-remarcacao.md`. Decisões da §4 confirmadas pelo André em 20/11 (1: abertura da agenda; 2: painel sobrepõe com motivo; 4: manual, sem lembrete; 5: `NOT IN (CANCELLED, NO_SHOW)`; 6: bot e site em silêncio).
> Fluxo: código → PR → migration dev → deploy dev → roteiro → prod com o André. **Sem Lambda nova** (stack em 494/500).

---

## 1. O que muda, em quatro frases

Cancelar passa a ter desfecho pela antecedência: 24 h ou mais antes da **abertura da agenda do dia da sessão** é `CANCELLED`; menos é `NO_SHOW`; a função que decide mora em `desfecho.py` e todas as portas passam por `cancel_appointment`. Remarcar para **outra data** deixa de mover o registro: o antigo recebe o desfecho da antecedência e `rescheduled_to_id`, nasce um novo com `rescheduled_from_id`, e pagamento, link de documentos, lembrete e conversão acompanham (`AppointmentService.remarca`). Mesma data continua edição in-place. Relatórios e dashboard somam dinheiro e contam agendamentos só com `status NOT IN ('CANCELLED', 'NO_SHOW')`, com `no_show_appointments` e `attendance_rate` novos.

---

## 2. Arquivos

| Arquivo | O que acontece |
|---|---|
| `scheduler/src/services/desfecho.py` (+`tests/unit/test_desfecho.py`) | **novo**: `abertura_da_agenda`, `classifica`, `LIMITE` |
| `scheduler/src/services/appointment_service.py` | `cancel_appointment(desfecho=None, motivo=None, autor=None)`; **novo** `remarca(...)`; `reschedule_appointment` recusa outra data; docstring de `marca_no_show` |
| `scheduler/src/services/reagendamento.py` | fragmentos e `vincula_antecessor` passam a aceitar `NO_SHOW` com vínculo |
| `scheduler/src/scripts/setup_database.py` | `rescheduled_from_id UUID`, `outcome_overridden_by VARCHAR(100)`, `outcome_reason VARCHAR(200)` |
| `scheduler/src/functions/appointment/update.py` | `status: CANCELLED` com `outcome`/`outcomeReason` (painel); `date` ≠ atual → `remarca` |
| `scheduler/src/functions/appointment/list.py` | expõe `rescheduled_from_id`, `outcome_reason` |
| `scheduler/src/functions/public_booking/cancel_appointment.py`, `reschedule_appointment.py` | cancel sem opinião; reschedule → `remarca` quando a data muda |
| `scheduler/src/services/ai_tools.py` | `alterar_agendamento` com data nova → `remarca`; devolve o `appointment_id` **novo** |
| `scheduler/src/functions/clinic/reports.py`, `dashboard.py` | filtros; `no_show_appointments`, `attendance_rate` |
| `scheduler/tests/unit/test_relatorio_nao_conta_falta.py` | **novo** guarda |
| `scheduler/tests/unit/test_remarcacao.py` | **novo** |
| `scheduler/tests/unit/test_falta_do_paciente.py`, `test_remarcar_pelo_site.py`, `test_reagendamento_nos_relatorios.py`, `test_reagendamento_vincula_antecessor.py`, `test_reagendar_limpa_confirmacao.py` | ajustes (ver §6) |
| `scheduler/tests/integration/054-desfecho.md` | **novo** roteiro |
| `frontend/src/lib/desfecho.ts` (+test) | **novo**: a mesma conta das 24 h para o texto |
| `frontend/src/pages/agenda/components/CancelAppointmentModal.tsx` (+test) | desfecho automático, seletor e motivo |
| `frontend/src/pages/agenda/components/EditAppointmentModal.tsx`, `lib/alteracaoDeAgendamento.ts` (+tests) | mudar data = remarcar: linha e avisos no resumo |
| `frontend/src/pages/agenda/components/AppointmentPopover.tsx` | `remarcado` inclui `NO_SHOW` com vínculo; "Remarcado de"; motivo da sobreposição |
| `frontend/src/pages/dashboard/components/KpiCards.tsx`, `pages/relatorios/RelatoriosPage.tsx` | cards "Faltas" e "Presença" |
| `frontend/src/services/appointments.service.ts`, `hooks/useAppointments.ts`, `types/index.ts` | `cancel(id, {outcome, outcomeReason})`; tipos |

---

## 3. Backend

### 3.1 `desfecho.py` (novo)

```python
LIMITE = timedelta(hours=24)
CANCELADO, FALTA = "CANCELLED", "NO_SHOW"

def abertura_da_agenda(db, clinic_id, dia: date, start_time_da_sessao: time) -> time:
    """O start_time mais cedo das availability_rules ativas do dia (rule_date
    vence day_of_week); SPECIAL_HOURS da exceção vence tudo. Sem regra (ou
    BLOCKED), vale o horário da sessão."""

def classifica(abertura: datetime, agora: datetime) -> str:
    """CANCELLED se agora <= abertura - LIMITE; senão NO_SHOW (inclui passado)."""

def desfecho_do_agendamento(db, appointment: dict, agora: Optional[datetime] = None) -> str:
    """Junta as duas: lê timezone da clínica (relogio.agora_na_clinica), a
    abertura do dia e classifica."""
```

- A consulta das regras copia a de `AvailabilityEngine._regras_do_dia` (recorrente + fixa + exceções); não importa a engine para não arrastar duração/buffer. `day_of_week = dt.isoweekday() % 7`, como lá.
- `agora` injetável para teste.

### 3.2 `appointment_service.cancel_appointment`

```python
def cancel_appointment(self, appointment_id, desfecho=None, motivo=None, autor=None):
```

- Lê o agendamento (`SELECT * ... status = 'CONFIRMED'`); 404 se não há.
- `automatico = desfecho_do_agendamento(self.db, appointment)`.
- Se `desfecho` veio e difere de `automatico`: exige `motivo` (senão `DesfechoInvalido` → 400) e grava `outcome_overridden_by = autor`, `outcome_reason = motivo`. Se veio igual ao automático, grava sem sobreposição. Se não veio, `desfecho = automatico`.
- `UPDATE ... SET status = %s, outcome_overridden_by, outcome_reason, updated_at, version+1 WHERE id AND status = 'CONFIRMED' RETURNING *`.
- Mantém `passa_a_marca_adiante` e `cancel_reminder` para os dois desfechos (falta por cancelamento tardio também solta a estreia e o lembrete; `marca_no_show` manual continua **não** chamando `passa_a_marca_adiante`, como o teste atual exige, porque ali a sessão já passou).
- Resultado ganha `result["outcome"] = desfecho`.
- `marca_no_show`: docstring passa a dizer que a regra das 24 h existe desde 20/11/2026 (PRD 054) para o **cancelamento**, e que este método segue sendo o "não veio" descoberto depois.

### 3.3 `appointment_service.remarca` (novo)

```python
def remarca(self, appointment_id, nova_data, nova_hora, tolerancia_minutos=0,
            desfecho=None, motivo=None, autor=None) -> Dict[str, Any]:
    """Outra data: o antigo recebe o desfecho da antecedência (ou a sobreposição
    do painel) e aponta para o novo; o novo nasce igual ao antigo. Devolve
    {"antigo": ..., "novo": ...}."""
```

Passos, nesta ordem:

1. Lê o antigo (`CONFIRMED`), suas áreas (`appointment_service_areas` → pares), telefone da paciente.
2. Se `nova_data == appointment_date`: delega a `reschedule_appointment` (mesma data é edição) e devolve `{"antigo": None, "novo": linha}`.
3. **Conflito antes de encerrar**: calcula a duração como `reschedule_appointment` faz hoje (manual vence; senão normaliza) e chama `_conflitos(clinic, nova_data, nova_hora, fim, excluir_id=antigo, tolerancia)`; `ConflictError` sem tocar em nada.
4. `antigo = self.cancel_appointment(appointment_id, desfecho, motivo, autor)`.
5. `novo = self.create_appointment(clinic_id, phone, service_id, nova_data, nova_hora, professional_id=antigo.professional_id, service_area_pairs=pares, full_name=antigo.full_name, notes=antigo.notes, discount_pct=antigo.discount_pct, discount_cents=antigo.discount_cents, discount_reason=antigo.discount_reason, manual_duration_minutes=antigo.manual_duration_minutes, is_first_visit=antigo.is_first_visit)`.
   - `vincula_antecessor` dentro do create acha o antigo (ver 3.4) e já grava `rescheduled_to_id` e move a conversão, sem registrar outra.
   - Desconto vai **como está gravado** (opinião explícita): remarcar não re-decide a política; o PRD 053 cobre a edição de áreas.
6. `UPDATE appointments SET rescheduled_from_id = antigo WHERE id = novo`; se `vincula_antecessor` não ligou (janela), `UPDATE antigo SET rescheduled_to_id = novo` explícito.
7. Move o que é por agendamento: `UPDATE appointment_payments SET appointment_id = novo WHERE appointment_id = antigo AND status IN ('PENDING','AWAITING_CASH','PAID')`; `UPDATE appointments SET consent_link_sent_at = antigo.consent_link_sent_at WHERE id = novo` (quando não nulo). Lembrete: `cancel_reminder(antigo)` já saiu no passo 4; o novo entra pelo lote do dia.
8. Log `[Remarcacao] antigo -> novo (desfecho=X)`; devolve `{"antigo": ..., "novo": ...}` com `outcome` no antigo.

### 3.4 `reagendamento.py`

- `E_REAGENDADO = "({a}.status IN ('CANCELLED','NO_SHOW') AND {a}.rescheduled_to_id IS NOT NULL)"`? **Não.** Decisão do PRD: remarcação com menos de 24 h **é falta**. Então:
  - `E_REAGENDADO` fica `CANCELLED + vínculo` (remarcação com antecedência: não é perda).
  - `E_CANCELADO_DE_VERDADE` fica `CANCELLED` sem vínculo.
  - Falta é `status = 'NO_SHOW'`, com ou sem vínculo (fragmento novo `E_FALTA`).
- `_VINCULA` e `_CANDIDATO`: `c.status IN ('CANCELLED', 'NO_SHOW')` para a remarcação tardia também ligar e mover a conversão.
- Teste `test_fragmentos_sao_complementares` ganha o terceiro fragmento.

### 3.5 `reschedule_appointment`

- Primeira linha útil: se `new_date != str(appointment["appointment_date"])` → `raise ValueError("Mudança de data é remarcação: use remarca()")` (classe nova `MudancaDeData(ValueError)` para o handler mapear em 400). Mesma data segue como hoje (limpa `confirmado_em`, teste `test_reagendar_limpa_confirmacao` continua valendo).

### 3.6 `functions/appointment/update.py`

- `status == "CANCELLED"`: lê `outcome` (`"CANCELLED" | "NO_SHOW"`, opcional) e `outcomeReason`; chama `service.cancel_appointment(id, desfecho=outcome, motivo=outcomeReason, autor=identidade.rotulo_ou_email)`; `DesfechoInvalido` → 400 "Para trocar o desfecho, informe o motivo". Mensagem: "Agendamento cancelado" ou "Falta registrada (menos de 24 h)".
- Etapa 3 (data/horário): se `new_date` veio e difere da atual → `resultado = service.remarca(id, new_date, new_time or hora_atual, tolerancia=TOLERANCIA_DO_PAINEL_MIN, desfecho=body.get("outcome"), motivo=body.get("outcomeReason"), autor=...)`; a resposta passa a ser `{"appointment": novo, "previous": antigo, "outcome": antigo.outcome}`. As etapas 1 e 2 (áreas/duração) rodam **depois**, sobre o novo id (reordenar: quando há remarcação, aplicar áreas/duração ao `novo`; na prática o painel manda só a data no "Remarcar", mas combinar não pode quebrar). Só horário → `reschedule_appointment` como hoje.
- Docstring com `outcome`, `outcomeReason` e o retorno `previous`.

### 3.7 Público e bot

- `public_booking/cancel_appointment.py`: nada muda na chamada; a resposta ganha `outcome` (o site não o mostra: decisão 6).
- `public_booking/reschedule_appointment.py`: `service.remarca(...)`; resposta `appointment` = **novo** (o site recarrega "Meus agendamentos"); `MudancaDeData` não ocorre porque chama `remarca` direto.
- `ai_tools._tool_alterar_agendamento`: se `moveu` e `data_final != data_atual` → `remarca`; `appointment_id` devolvido é o **novo**; se só a hora mudou → `reschedule_appointment`. Áreas novas (`pares`) com data nova: aplicar `update_appointment_services` **no novo** depois de remarcar. Texto ao paciente igual ao de hoje. `_tool_cancel_appointment`: igual; devolve `outcome` no dict para o log, o modelo não o lê (não entra em `o_que_fazer`).

### 3.8 Relatórios

- `reports.py` e `dashboard.py`: trocar todo `status != 'CANCELLED'` por `status NOT IN ('CANCELLED', 'NO_SHOW')` nas somas e no `total_appointments` (summary, prev, série por dia, top services, discount breakdown). Constante `ATIVOS = "status NOT IN ('CANCELLED', 'NO_SHOW')"` em `reagendamento.py` (é a casa dos fragmentos) e uso por f-string, como os outros.
- Campos novos no summary de ambos: `no_show_appointments = COUNT(*) FILTER (WHERE status = 'NO_SHOW')`; `attendance_rate` calculado em Python: `realizadas = COUNT(*) FILTER (WHERE status NOT IN (...) AND appointment_date < hoje_na_clinica)`; `attendance_rate = round(100 * realizadas / (realizadas + no_show), 1)` ou `None` sem base.
- Guarda `test_relatorio_nao_conta_falta.py`: lê `reports.py` e `dashboard.py` e falha se encontrar `SUM(` ou `COUNT(*) FILTER` na mesma linha de `!= 'CANCELLED'`; prova positiva: `caixa.py` ou um trecho sintético casa com o regex.

### 3.9 `setup_database.py`

```sql
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS rescheduled_from_id UUID REFERENCES scheduler.appointments(id);
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS outcome_overridden_by VARCHAR(100);
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS outcome_reason VARCHAR(200);
```
+ as três no `CREATE TABLE`. `list.py` expõe as três.

---

## 4. Frontend

### 4.1 `lib/desfecho.ts`

```ts
export function aberturaDoDia(regras: AvailabilityRule[] | undefined, dia: string, horaDaSessao: string): string
export function desfechoAutomatico(agora: Date, dia: string, abertura: string): 'CANCELLED' | 'NO_SHOW'
export function textoDoDesfecho(d, automatico): string  // "Vai contar como falta: faltam menos de 24 h para a agenda do dia." / "Vai contar como cancelamento."
```
- `regras` vêm de `useAvailabilityRules()` (já carregadas na agenda); `rule_date` vence `day_of_week`; sem regra → `horaDaSessao`. O fuso: a tela já vive no horário da clínica (o painel é usado na clínica); o backend é quem decide, a tela só antecipa.

### 4.2 `CancelAppointmentModal.tsx`

- Mostra o texto do desfecho automático. Abaixo, "Registrar como:" com dois `aria-pressed` (Falta / Cancelamento), pré-marcado no automático. Ao escolher o outro, aparece `Input` "Motivo" obrigatório (até 200). "Confirmar" desabilitado sem motivo quando diverge.
- `useCancelAppointment` passa a aceitar `{ appointmentId, outcome?, outcomeReason? }`; `appointmentsService.cancel(id, extra)` manda `{ status: 'CANCELLED', ...extra }`.
- Mantém "Remarcar em vez de cancelar" e o aviso de pago.
- Toast depois: "Falta registrada" ou "Agendamento cancelado".

### 4.3 `EditAppointmentModal.tsx` e `alteracaoDeAgendamento.ts`

- `dateChanged` vira **remarcação**: `alteracao.data` continua, e `avisosDaAlteracao` ganha, quando `a.data`: "O agendamento de {dia antigo} fica registrado como **{falta|cancelamento}** ({motivo da regra}) e nasce um novo em {dia novo}." + "Pagamento, documentos e lembrete passam para o novo." O modal recebe `regras` para `desfechoAutomatico`.
- Payload: igual (`date`, `time`); a resposta traz `appointment` novo. Se o desfecho automático é falta, o resumo oferece "Registrar como cancelamento, com motivo" (mesmo seletor do cancelar) → `outcome`/`outcomeReason` no payload.
- Título do botão de confirmar: "Confirmar remarcação" quando `a.data`.

### 4.4 Popover, dashboard, relatórios

- `remarcado = (isCancelled || faltou) && !!a.rescheduled_to_id`; rótulo "Remarcado para …" nos dois; `faltou && remarcado` mostra "Falta (remarcado para …)". Mostra `outcome_reason` quando houver: "Desfecho ajustado: {motivo}".
- `rescheduled_from_id`: "Remarcado de {dia}" (precisa da data: `list.py` já faz `LEFT JOIN rt` para o destino; adicionar `rf` para a origem → `rescheduled_from_date`).
- `KpiCards` (dashboard): card "Faltas" (`no_show_appointments`) no lugar do detalhe de taxa; `RelatoriosPage`: cards "Faltas" e "Presença" (`attendance_rate`%).
- Tipos: `ReportSummary.no_show_appointments`, `attendance_rate: number | null`; `Appointment.rescheduled_from_id`, `rescheduled_from_date`, `outcome_reason`.

---

## 5. Testes

**Backend**

- `test_desfecho.py`: 24 h antes da abertura (9h → limite 9h do dia anterior): 8h59 do dia anterior = CANCELLED, 9h01 = NO_SHOW; sem regra usa a hora da sessão; `rule_date` vence `day_of_week`; SPECIAL_HOURS vence; sessão passada = NO_SHOW.
- `test_remarcacao.py`: ordem (conflito antes de cancelar; conflito não toca nada); antigo com desfecho e `rescheduled_to_id`; novo com `rescheduled_from_id`, mesmas áreas/desconto/duração/notas/estreia; pagamento e `consent_link_sent_at` movidos; conversão movida uma vez (dublê de `lead_service`); mesma data delega ao `reschedule_appointment`; sobreposição com motivo grava `outcome_*`; sem motivo → `DesfechoInvalido`.
- `test_falta_do_paciente.py`: `test_cancelar_CONTINUA_chamando` segue; novo caso "cancelar com menos de 24 h grava NO_SHOW e também chama `passa_a_marca_adiante` e `cancel_reminder`"; `test_NAO_ha_guard_de_data` e `test_a_razao_esta_escrita_no_codigo` atualizados para a docstring nova.
- `test_remarcar_pelo_site.py`: `test_sucesso_mantem_o_id...` vira "data nova devolve o id novo e o antigo com desfecho"; horário no mesmo dia mantém o id.
- `test_reagendamento_nos_relatorios.py`: faltas fora da receita; `no_show_appointments`; cadeia com NO_SHOW + vínculo conta como falta, não como reagendado.
- `test_reagendamento_vincula_antecessor.py`: candidato `NO_SHOW` também liga.
- `test_relatorio_nao_conta_falta.py` (guarda).
- Handler `update.py`: `outcome` divergente sem motivo → 400; `date` diferente → `remarca` chamado e `previous` na resposta; só `time` → `reschedule_appointment`.

**Frontend**

- `desfecho.test.ts`: abertura por regra do dia/fixa/sem regra; 24 h; textos.
- `CancelAppointmentModal.test.tsx`: desfecho automático exibido; trocar exige motivo; payload com `outcome`/`outcomeReason`.
- `EditAppointmentModal.test.tsx`: mudar data mostra o aviso do desfecho e "Confirmar remarcação"; horário só não.
- `alteracaoDeAgendamento.test.ts`: avisos novos.
- `AppointmentPopover`/`FaltaDoPaciente`: `NO_SHOW` com vínculo mostra "Remarcado para".
- `KpiCards`/`RelatoriosPage`: cards novos.

---

## 6. Ordem

1. `desfecho.py` + teste → `reagendamento.py` → `appointment_service` (`cancel_appointment`, `remarca`, `reschedule_appointment`) → `setup_database` → handlers (`update`, `list`, público, `ai_tools`) → relatórios + guarda → ajustes de testes. `pytest` verde.
2. Migration dev + deploy dev; roteiro §7 casos de API.
3. Frontend: `lib/desfecho` → service/hook/types → `CancelAppointmentModal` → `Edit` + `alteracao` → popover → cards → testes. build/lint/test verdes.
4. PR único; merge sobe o painel.
5. Prod com o André: migration + deploy; relatórios mudam de número (avisar).

---

## 7. Roteiro (dev) - esqueleto

Pré-requisitos como no 053. Agenda de dev abre às 09:00 (conferir em `availability_rules`).

| # | Chamada | Esperado |
|---|---|---|
| 1 | `PUT {A}` `{status: CANCELLED}` com A daqui a 3 dias | `status CANCELLED`, `outcome CANCELLED` |
| 2 | idem com A amanhã às 15h, agora depois das 09:00 de hoje | `NO_SHOW`, `outcome NO_SHOW` |
| 3 | caso 2 + `outcome: CANCELLED` sem motivo → 400; com `outcomeReason` → `CANCELLED`, `outcome_reason` gravado |
| 4 | `PUT {A}` `{date: +5 dias, time}` | resposta `appointment` novo com `rescheduled_from_id = A`; `previous` = A `CANCELLED` + `rescheduled_to_id`; áreas/desconto iguais; horário antigo livre em `slots` |
| 5 | idem com A amanhã (< 24 h) | `previous` `NO_SHOW` + vínculo |
| 6 | `PUT {A}` `{time}` mesma data, amanhã | mesmo id, `CONFIRMED`, sem registro novo |
| 7 | `PUT {A}` `{serviceAreaPairs}` mesma data, < 24 h | sem desfecho |
| 8 | `GET reports?period=current_month` e `dashboard` | receita exclui `NO_SHOW`; `no_show_appointments`, `attendance_rate` presentes |
| 9 | público: `reschedule` com data nova | id novo; `cancel` < 24 h → `NO_SHOW` |
| 10 | Painel: cancelar mostra o desfecho; trocar exige motivo; editar data mostra "Confirmar remarcação"; popover "Remarcado para/de"; cards Faltas/Presença |
