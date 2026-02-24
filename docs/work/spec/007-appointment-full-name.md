# Spec — 007 Coleta de Nome Completo no Agendamento

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/007-appointment-full-name.md`

---

## 1. Resumo

Adicionar um novo estado `ASK_FULL_NAME` no fluxo de conversa WhatsApp, entre `SELECT_TIME` e `CONFIRM_BOOKING`, para coletar o nome completo do cliente. O nome será salvo na coluna `full_name` da tabela `scheduler.appointments` via `appointment_service.create_appointment()`. Os 3 pontos de entrada (WhatsApp, API REST, Google Sheets) serão atualizados para aceitar e propagar esse campo.

---

## 2. Arquivos a criar

Nenhum arquivo novo necessário.

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/scripts/setup_database.py` | Migration: `ADD COLUMN full_name VARCHAR(255)` na tabela appointments; atualizar CREATE TABLE |
| `scheduler/src/services/conversation_engine.py` | Novo estado `ASK_FULL_NAME` no enum; alterar transição `SELECT_TIME` → `ASK_FULL_NAME`; handler `_on_enter_ask_full_name`; captura de texto livre → `session["full_name"]`; exibir nome no `CONFIRM_BOOKING`; passar `full_name` no `_on_enter_booked` |
| `scheduler/src/services/template_service.py` | Novo template `ASK_FULL_NAME`; atualizar template `CONFIRM_BOOKING` para incluir `{{full_name}}` |
| `scheduler/src/services/appointment_service.py` | Novo parâmetro `full_name` em `create_appointment()`; incluir no INSERT SQL |
| `scheduler/src/functions/appointment/create.py` | Ler `fullName` do body e passar para `create_appointment()` |
| `scheduler/src/functions/sheets/webhook.py` | Ler `full_name` do body/row e passar para `create_appointment()` |
| `scheduler/src/services/sheets_sync.py` | Adicionar `full_name` ao `SHEET_HEADERS` e ao `row_values` em `sync_appointment()` |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. **Migration** — `setup_database.py`: adicionar coluna `full_name`
2. **Appointment Service** — `appointment_service.py`: aceitar e gravar `full_name`
3. **Templates** — `template_service.py`: novo template `ASK_FULL_NAME` + atualizar `CONFIRM_BOOKING`
4. **Conversation Engine** — `conversation_engine.py`: novo estado, transições e handlers
5. **API REST** — `appointment/create.py`: aceitar `fullName` no body
6. **Sheets Webhook** — `sheets/webhook.py`: aceitar `full_name`
7. **Sheets Sync** — `sheets_sync.py`: exportar `full_name`

---

## 6. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py`

- **Modificar** — Adicionar migration idempotente ao final da lista `MIGRATIONS`:

```sql
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);
```

- **Modificar** — Atualizar o `CREATE TABLE scheduler.appointments` para incluir:

```sql
full_name VARCHAR(255),
```

Adicionar logo após a linha `notes TEXT,` (antes de `created_at`).

---

### `scheduler/src/services/appointment_service.py`

- **Modificar** — Adicionar parâmetro `full_name: Optional[str] = None` na assinatura de `create_appointment()` (linha 29), após `final_price_cents`:

```python
def create_appointment(
    self,
    clinic_id: str,
    phone: str,
    service_id: str,
    date: str,
    time: str,
    professional_id: Optional[str] = None,
    service_ids: Optional[List[str]] = None,
    total_duration_minutes: Optional[int] = None,
    service_area_pairs: Optional[List[Dict[str, str]]] = None,
    discount_pct: int = 0,
    discount_reason: Optional[str] = None,
    original_price_cents: Optional[int] = None,
    final_price_cents: Optional[int] = None,
    full_name: Optional[str] = None,
) -> Dict[str, Any]:
```

- **Modificar** — Atualizar o INSERT SQL (linha 123) para incluir `full_name`:

```sql
INSERT INTO scheduler.appointments (
    clinic_id, patient_id, professional_id, service_id,
    appointment_date, start_time, end_time,
    total_duration_minutes,
    discount_pct, discount_reason, original_price_cents, final_price_cents,
    full_name,
    status, created_at, updated_at, version
) VALUES (
    %s, %s::uuid, %s::uuid, %s::uuid,
    %s, %s::time, %s::time,
    %s,
    %s, %s, %s, %s,
    %s,
    'CONFIRMED', NOW(), NOW(), 1
)
RETURNING *
```

- **Modificar** — Adicionar `full_name` na tupla de parâmetros (linha 138):

```python
(clinic_id, patient_id, prof_id_param, primary_service_id,
 date, time, end_time,
 duration_minutes,
 discount_pct, discount_reason, original_price_cents, final_price_cents,
 full_name),
```

---

### `scheduler/src/services/template_service.py`

- **Modificar** — Adicionar novo template ao `DEFAULT_TEMPLATES` (linha ~21):

```python
"ASK_FULL_NAME": "Ótimo! Para finalizar, por favor me informe seu *nome completo*:",
```

- **Modificar** — Atualizar template `CONFIRM_BOOKING` para incluir `{{full_name}}`:

```python
"CONFIRM_BOOKING": "Confirme seu agendamento:\n*{{full_name}}*\n{{date}} às {{time}}\n{{service}}\nÁreas: {{areas}}\nDuração prevista: {{duration}}\n*Valor: {{price}}*\n{{clinic_name}} - {{address}}",
```

---

### `scheduler/src/services/conversation_engine.py`

#### 6.1 Novo estado no enum (linha 33, após `SELECT_TIME`)

```python
class ConversationState(str, Enum):
    ...
    SELECT_TIME = "SELECT_TIME"
    ASK_FULL_NAME = "ASK_FULL_NAME"      # ← NOVO
    CONFIRM_BOOKING = "CONFIRM_BOOKING"
    ...
```

#### 6.2 Alterar transição em `_on_enter_select_time` (linha 1336)

Mudar o destino dos botões de horário de `CONFIRM_BOOKING` para `ASK_FULL_NAME`:

```python
# ANTES:
dynamic_transitions[btn_id] = ConversationState.CONFIRM_BOOKING.value
# DEPOIS:
dynamic_transitions[btn_id] = ConversationState.ASK_FULL_NAME.value
```

#### 6.3 Novo handler `_on_enter_ask_full_name`

Criar método que renderiza o template `ASK_FULL_NAME`. Este estado recebe **input de texto livre** (sem botões dinâmicos):

```python
def _on_enter_ask_full_name(self, clinic_id: str, session: dict) -> dict:
    return {}
```

O template `ASK_FULL_NAME` será renderizado automaticamente pelo engine (sem variáveis).

#### 6.4 Captura do nome e transição para CONFIRM_BOOKING

No método `process_message` (ou na lógica de transição de estados), quando o estado atual é `ASK_FULL_NAME`:

- Aceitar **qualquer texto** como nome completo (input livre)
- Salvar em `session["full_name"]` com `.strip()`
- Transicionar para `CONFIRM_BOOKING`

Isso deve ser tratado na seção onde o engine processa inputs de texto livre (similar a como trata outros estados de input livre). Adicionar ao mapa de transições estáticas:

```python
# Na configuração de estados, ASK_FULL_NAME aceita texto livre
# e transiciona para CONFIRM_BOOKING
```

**Lógica de captura:** No processamento de `ASK_FULL_NAME`, interceptar o input do usuário antes das validações de botão:

```python
if current_state == ConversationState.ASK_FULL_NAME.value:
    session["full_name"] = user_input.strip()
    next_state = ConversationState.CONFIRM_BOOKING.value
```

#### 6.5 Exibir nome no CONFIRM_BOOKING (linha 1382)

Adicionar `full_name` ao dicionário `variables` em `_on_enter_confirm_booking`:

```python
variables = {
    "full_name": session.get("full_name", ""),
    "date": self._format_date_br(session.get("selected_date", "")),
    "time": session.get("selected_time", ""),
    ...
}
```

#### 6.6 Passar nome em `_on_enter_booked` (linha 1407)

Adicionar `full_name` na chamada a `create_appointment`:

```python
result = self.appointment_service.create_appointment(
    clinic_id=clinic_id,
    phone=phone,
    ...
    final_price_cents=session.get("discounted_price_cents"),
    full_name=session.get("full_name"),
)
```

---

### `scheduler/src/functions/appointment/create.py`

- **Modificar** — Ler `fullName` do body (linha ~92):

```python
result = service.create_appointment(
    clinic_id=clinic_id,
    phone=phone,
    service_id=service_id,
    date=appt_date,
    time=appt_time,
    professional_id=body.get("professionalId"),
    service_ids=service_ids,
    service_area_pairs=service_area_pairs if service_area_pairs else None,
    full_name=body.get("fullName"),
)
```

---

### `scheduler/src/functions/sheets/webhook.py`

- **Modificar** — Ler `full_name` do body/row e passar na chamada (linha ~307):

```python
result = appt_service.create_appointment(
    clinic_id=clinic_id,
    phone=phone,
    service_id=service_id,
    date=appt_date,
    time=appt_time,
    service_area_pairs=service_area_pairs,
    full_name=body.get("full_name") or body.get("patient_name"),
)
```

---

### `scheduler/src/services/sheets_sync.py`

- **Modificar** — Atualizar `SHEET_HEADERS` (linha 16) para incluir `Nome Completo`:

```python
SHEET_HEADERS = [
    "Data", "Horário", "Nome Completo", "Paciente", "Telefone", "Serviço",
    "Áreas", "Desconto", "Valor Original", "Valor Final",
    "Status", "Observações", "AppointmentId", "UltimaAtualização"
]
```

- **Modificar** — Atualizar `row_values` em `sync_appointment()` (linha 264) para incluir `full_name`:

```python
row_values = [
    str(appointment.get("appointment_date", "")),
    str(appointment.get("start_time", "")),
    appointment.get("full_name", ""),          # ← NOVO
    patient_name,
    patient_phone,
    service_name,
    areas_display,
    discount_str,
    original_str,
    final_str,
    appointment.get("status", ""),
    appointment.get("notes", ""),
    appointment_id,
    datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
]
```

**Nota:** Adicionar o header antes de "Paciente" exigirá que planilhas existentes sejam atualizadas manualmente ou que novas abas criadas já recebam o novo header. Abas existentes ficarão com colunas desalinhadas se não forem ajustadas.

---

## 7. Convenções a respeitar

- Logging: `[ConversationEngine]` prefix nos logs do conversation engine
- Naming: `full_name` (snake_case) no banco e Python; `fullName` (camelCase) na API REST
- Migrations: idempotentes com `ADD COLUMN IF NOT EXISTS`
- Input: aplicar `.strip()` no nome para remover espaços extras
- Coluna nullable: appointments existentes e criações sem nome continuam funcionando
