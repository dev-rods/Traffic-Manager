# Spec — 008 Soft-Delete de Pacientes

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/008-patient-soft-delete.md`

---

## 1. Resumo

Adicionar coluna `deleted_at TIMESTAMPTZ NULL` em `scheduler.patients` e novo endpoint `DELETE /clinics/{clinicId}/patients/{patientId}` que seta o timestamp. Todas as leituras que tratam paciente como entidade ativa (lista, dashboard, reports, lookups por telefone do bot, painel de atendentes) passam a filtrar `deleted_at IS NULL`. JOINs históricos em `appointments` mantêm o nome do paciente deletado. `_get_or_create_patient` (WhatsApp) e `POST /patients` (REST) implementam **restore on recreate**: se o telefone existir soft-deletado, `UPDATE` zera `deleted_at` e atualiza dados. Frontend ganha botão de excluir + modal de confirmação + mutation TanStack Query.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/functions/patient/delete.py` | Handler `DELETE /clinics/{clinicId}/patients/{patientId}` — soft-delete idempotente |
| `frontend/src/pages/pacientes/components/DeletePatientConfirmModal.tsx` | Modal de confirmação destrutiva (nome + telefone, botão "Excluir paciente") |
| `scheduler/tests/mocks/patient/delete_patient.json` | Mock de evento DELETE para invocação local |
| `scheduler/tests/integration/patient-soft-delete.md` | Documentação dos casos de teste manuais via curl |
| `scheduler/tests/postman/patient-soft-delete.postman_requests.json` | Postman requests do fluxo completo |

---

## 3. Arquivos a modificar

### Backend (scheduler/)

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/scripts/setup_database.py` | Migration `ADD COLUMN IF NOT EXISTS deleted_at` + índice `idx_patients_deleted`; atualizar `CREATE TABLE` de `patients` em `TABLES` |
| `scheduler/sls/functions/patient/interface.yml` | Adicionar bloco `DeletePatient` (rota DELETE) seguindo o padrão dos outros 3 handlers |
| `scheduler/src/functions/patient/list.py` | Adicionar `AND p.deleted_at IS NULL` na cláusula WHERE da count query e da query principal (linhas ~88, ~112) |
| `scheduler/src/functions/patient/update.py` | Adicionar `AND deleted_at IS NULL` no SELECT de existência (linha 54) e no UPDATE final (linha 90) |
| `scheduler/src/functions/patient/create.py` | Substituir check de duplicidade simples (linhas 77-85) por lógica de **restore**: se existir registro soft-deletado, `UPDATE` zerando `deleted_at` e atualizando dados; se ativo, retornar 409 |
| `scheduler/src/functions/clinic/dashboard.py` | Adicionar `AND deleted_at IS NULL` em queries que contam pacientes ativos (manter join LEFT em appointments sem filtro) |
| `scheduler/src/functions/clinic/reports.py` | Adicionar `AND deleted_at IS NULL` no COUNT de novos pacientes (linhas 103-107, 124-128) |
| `scheduler/src/functions/attendant/conversations.py` | Adicionar `AND deleted_at IS NULL` no IN-clause de phones (linhas 92-95) |
| `scheduler/src/functions/attendant/list_active.py` | Adicionar `AND deleted_at IS NULL` (linha 80) |
| `scheduler/src/functions/send/handler.py` | Adicionar `AND deleted_at IS NULL` no UPDATE de `last_message_at` (linhas 145-150) |
| `scheduler/src/services/appointment_service.py` | (a) `_get_or_create_patient`: lógica de restore quando match com `deleted_at IS NOT NULL`; (b) `get_active_appointment_by_phone` e `get_active_appointments_by_phone`: adicionar `AND deleted_at IS NULL` no SELECT de patients |
| `scheduler/src/services/conversation_engine.py` | `_on_enter_welcome`: adicionar `AND deleted_at IS NULL` no SELECT direto (linhas 936-939). **Não tocar** no JOIN lateral da linha 1167 (preserva histórico) |
| `scheduler/src/services/ai_tools.py` | Verificar lookup ~linha 669: se for SELECT direto na tabela `patients` (não JOIN com appointments), adicionar `AND deleted_at IS NULL`. Se for JOIN para enriquecer appointment, manter |

### Frontend (frontend/)

| Arquivo | Alterações |
|---------|------------|
| `frontend/src/types/index.ts` | Adicionar `deleted_at?: string \| null` em `Patient`; criar tipo `CreatePatientResponse` com `status: 'created' \| 'restored'` e `patient: Patient` |
| `frontend/src/services/patients.service.ts` | (a) `delete(clinicId, patientId)` retornando `void`; (b) `create` retornar o objeto completo `CreatePatientResponse` (status + patient) em vez de só o patient |
| `frontend/src/hooks/usePatients.ts` | (a) `useDeletePatient` mutation que invalida `patientKeys.lists()`; (b) `useCreatePatient` retorna `CreatePatientResponse` para o componente saber se foi restore |
| `frontend/src/pages/pacientes/components/PatientsTable.tsx` | Nova prop `onDelete: (patient: PatientWithStats) => void`; botão "Excluir" na coluna de ações ao lado dos existentes (ícone lixeira, cor red-600) |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | (a) Estado `patientToDelete: PatientWithStats \| null`; (b) Wire-up do `DeletePatientConfirmModal`; (c) Passar `onDelete={setPatientToDelete}` para a `PatientsTable`; (d) Tratar resposta de `useCreatePatient` para toast distinto em restore |
| `frontend/src/pages/pacientes/components/CreatePatientModal.tsx` | Repassar resultado de `useCreatePatient` (com `status`) ao `onSuccess` para `PacientesPage` decidir o toast |

---

## 4. Arquivos a remover

Nenhum.

---

## 5. Ordem de implementação sugerida

1. **Migration** — `setup_database.py`: coluna `deleted_at` + índice, atualizar CREATE TABLE
2. **Handler DELETE** — criar `patient/delete.py` e adicionar entrada em `interface.yml`
3. **Filtros nos handlers REST** — `list.py`, `update.py`, `create.py` (com restore), `clinic/dashboard.py`, `clinic/reports.py`
4. **Filtros nos handlers de atendente** — `attendant/conversations.py`, `attendant/list_active.py`
5. **Filtro no send handler** — `send/handler.py`
6. **Filtros + restore nos services** — `appointment_service.py` (lookups + `_get_or_create_patient`), `conversation_engine.py`, `ai_tools.py`
7. **Mocks + integração + Postman** — criar `tests/mocks/patient/delete_patient.json`, doc de integração e Postman
8. **Frontend types + service + hook** — `types/index.ts`, `patients.service.ts`, `usePatients.ts`
9. **Frontend UI** — `DeletePatientConfirmModal.tsx`, `PatientsTable.tsx`, `PacientesPage.tsx`, `CreatePatientModal.tsx`
10. **Validação E2E** — `npm run lint`, `npm run build`, deploy dev e bateria de testes manuais (criar → deletar → mensagem WhatsApp do mesmo número → verificar restore)

---

## 6. Detalhes por arquivo

### `scheduler/src/scripts/setup_database.py`

- **Modificar** — Atualizar `CREATE TABLE scheduler.patients` em `TABLES` (linhas 102-114) adicionando a coluna **antes** de `created_at`:

```sql
CREATE TABLE IF NOT EXISTS scheduler.patients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) REFERENCES scheduler.clinics(clinic_id),
    phone VARCHAR(20) NOT NULL,
    name VARCHAR(255),
    gender VARCHAR(1) CHECK (gender IN ('M', 'F')),
    last_message_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clinic_id, phone)
)
```

- **Modificar** — Adicionar ao final da lista `MIGRATIONS` (após linha 476):

```python
# Soft-delete column on patients
"ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ",
"CREATE INDEX IF NOT EXISTS idx_patients_deleted ON scheduler.patients(clinic_id, deleted_at)",
```

> Manter `UNIQUE(clinic_id, phone)` como está — restore é responsável por evitar conflito.

---

### `scheduler/sls/functions/patient/interface.yml`

- **Modificar** — Adicionar ao final do arquivo, seguindo o mesmo padrão dos outros handlers:

```yaml
DeletePatient:
  handler: src.functions.patient.delete.handler
  memorySize: 512
  timeout: 30
  iamRoleStatementsName: ${self:service}-${self:custom.stage}-DeletePatient-lambdaRole
  iamRoleStatements:
    - Effect: Allow
      Action:
        - ssm:GetParameter
      Resource:
        - "arn:aws:ssm:${self:provider.region}:*:parameter/${self:custom.stage}/*"
    - Effect: Allow
      Action:
        - logs:CreateLogGroup
        - logs:CreateLogStream
        - logs:PutLogEvents
      Resource: "arn:aws:logs:*:*:*"
  events:
    - http:
        path: clinics/{clinicId}/patients/{patientId}
        method: delete
        cors: true
```

---

### `scheduler/src/functions/patient/delete.py` (criar)

- **Criar** — Handler novo seguindo o mesmo skeleton de `update.py`:

```python
import logging

from src.utils.http import http_response, require_api_key, extract_path_param
from src.services.db.postgres import PostgresService

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event, context):
    """
    DELETE /clinics/{clinicId}/patients/{patientId}
    Soft-delete: seta deleted_at = NOW() se ainda nao deletado.
    Idempotente: paciente ja deletado retorna 200 sem rescrever.
    """
    try:
        logger.info("Delete patient request received")

        api_key, error_response = require_api_key(event)
        if error_response:
            return error_response

        clinic_id = extract_path_param(event, "clinicId")
        patient_id = extract_path_param(event, "patientId")
        if not clinic_id or not patient_id:
            return http_response(400, {
                "status": "ERROR",
                "message": "clinicId e patientId sao obrigatorios"
            })

        db = PostgresService()

        existing = db.execute_query(
            "SELECT id, deleted_at FROM scheduler.patients WHERE id = %s::uuid AND clinic_id = %s",
            (patient_id, clinic_id),
        )
        if not existing:
            return http_response(404, {
                "status": "ERROR",
                "message": "Paciente nao encontrado"
            })

        if existing[0].get("deleted_at"):
            logger.info(f"Patient {patient_id} already soft-deleted, returning 200")
            return http_response(200, {
                "status": "SUCCESS",
                "message": "Paciente ja estava excluido"
            })

        db.execute_write_returning(
            "UPDATE scheduler.patients SET deleted_at = NOW(), updated_at = NOW() "
            "WHERE id = %s::uuid AND clinic_id = %s RETURNING id",
            (patient_id, clinic_id),
        )

        logger.info(f"Patient soft-deleted: {patient_id}")
        return http_response(200, {
            "status": "SUCCESS",
            "message": "Paciente excluido"
        })

    except Exception as e:
        error_msg = str(e)
        logger.error(f"Error deleting patient: {error_msg}")
        return http_response(500, {
            "status": "ERROR",
            "message": "Erro interno do servidor",
            "error": error_msg,
        })
```

---

### `scheduler/src/functions/patient/list.py`

- **Modificar** — Adicionar filtro `AND p.deleted_at IS NULL` à variável `where` (linha 52):

```python
where = "WHERE p.clinic_id = %s AND p.deleted_at IS NULL"
```

> O JOIN com `appointments` continua sem filtro de `deleted_at` (irrelevante aqui pois pacientes deletados nem aparecem na query). Nada mais muda.

---

### `scheduler/src/functions/patient/update.py`

- **Modificar** — Linha 54: `SELECT id FROM scheduler.patients WHERE id = %s::uuid AND clinic_id = %s AND deleted_at IS NULL`
- **Modificar** — Linha 90: WHERE final do UPDATE: `WHERE id = %s::uuid AND clinic_id = %s AND deleted_at IS NULL`

> Update em paciente deletado retorna 404 — coerente com o resto da API.

---

### `scheduler/src/functions/patient/create.py`

- **Modificar** — Substituir o bloco de check de duplicidade (linhas 76-85) pela lógica de restore:

```python
db = PostgresService()

# Check if phone already exists for this clinic (active or soft-deleted)
existing = db.execute_query(
    "SELECT id, deleted_at FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
    (clinic_id, phone),
)

if existing:
    row = existing[0]
    if row.get("deleted_at") is None:
        return http_response(409, {
            "status": "ERROR",
            "message": "Ja existe um paciente com esse telefone"
        })

    # Soft-deleted patient with same phone — restore and update fields
    result = db.execute_write_returning("""
        UPDATE scheduler.patients
        SET name = %s, gender = %s, deleted_at = NULL, updated_at = NOW()
        WHERE id = %s::uuid
        RETURNING *
    """, (name, gender, str(row["id"])))

    if not result:
        return http_response(500, {
            "status": "ERROR",
            "message": "Falha ao restaurar paciente"
        })

    patient = _serialize_row(result)
    logger.info(f"Patient restored: {patient['id']} for clinic {clinic_id}")
    return http_response(200, {
        "status": "RESTORED",
        "patient": patient,
    })

# Brand new patient
result = db.execute_write_returning("""
    INSERT INTO scheduler.patients (clinic_id, name, phone, gender, created_at, updated_at)
    VALUES (%s, %s, %s, %s, NOW(), NOW())
    RETURNING *
""", (clinic_id, name, phone, gender))

# ... resto do bloco de criação fica igual, mas a resposta de sucesso muda:
return http_response(201, {
    "status": "CREATED",
    "patient": patient,
})
```

> Mudança no contrato de resposta: `status` agora é `"CREATED"` (201) ou `"RESTORED"` (200) em vez de `"SUCCESS"`. Frontend será atualizado para tratar ambos. Erros continuam `"ERROR"`.

---

### `scheduler/src/functions/clinic/dashboard.py`

- **Modificar** — Em queries que contam ou listam pacientes diretamente (sem JOIN com appointments), adicionar `AND deleted_at IS NULL`. Manter LEFT JOINs sem filtro para preservar histórico.

> Identificar cada query no arquivo durante implementação. Heurística: se a query é "quantos pacientes ativos eu tenho" → filtra; se é "appointment X tem qual nome de paciente" → não filtra.

---

### `scheduler/src/functions/clinic/reports.py`

- **Modificar** — Linhas 103-107 e 124-128 (COUNT de novos pacientes): adicionar `AND deleted_at IS NULL` ao WHERE.

---

### `scheduler/src/functions/attendant/conversations.py`

- **Modificar** — Linhas 92-95: adicionar `AND deleted_at IS NULL` ao WHERE com IN-clause de phones.

---

### `scheduler/src/functions/attendant/list_active.py`

- **Modificar** — Linha 80: adicionar `AND deleted_at IS NULL`.

---

### `scheduler/src/functions/send/handler.py`

- **Modificar** — Linhas 145-150 (UPDATE `last_message_at`): adicionar `AND deleted_at IS NULL` no WHERE para não tocar paciente deletado.

---

### `scheduler/src/services/appointment_service.py`

- **Modificar** — `get_active_appointment_by_phone` (linhas 531-534): adicionar `AND deleted_at IS NULL`:

```python
patients = self.db.execute_query(
    "SELECT id FROM scheduler.patients WHERE clinic_id = %s AND phone = %s AND deleted_at IS NULL",
    (clinic_id, phone),
)
```

- **Modificar** — `get_active_appointments_by_phone` (linhas 565-568): mesma alteração.

- **Modificar** — `_get_or_create_patient` (linhas 595-616): substituir pela versão com restore:

```python
def _get_or_create_patient(self, clinic_id: str, phone: str) -> Dict[str, Any]:
    from src.utils.phone import normalize_phone
    phone = normalize_phone(phone)

    patients = self.db.execute_query(
        "SELECT * FROM scheduler.patients WHERE clinic_id = %s AND phone = %s",
        (clinic_id, phone),
    )

    if patients:
        existing = patients[0]
        if existing.get("deleted_at") is None:
            return existing

        # Soft-deleted patient came back — restore in place
        restored = self.db.execute_write_returning(
            """
            UPDATE scheduler.patients
            SET deleted_at = NULL, updated_at = NOW()
            WHERE id = %s::uuid
            RETURNING *
            """,
            (str(existing["id"]),),
        )
        logger.info(
            f"[AppointmentService] Patient restored from soft-delete: id={existing['id']} phone={phone}"
        )
        return restored

    result = self.db.execute_write_returning(
        """
        INSERT INTO scheduler.patients (clinic_id, phone, created_at, updated_at)
        VALUES (%s, %s, NOW(), NOW())
        RETURNING *
        """,
        (clinic_id, phone),
    )
    return result
```

> SELECT inicial não filtra `deleted_at` porque a função precisa decidir entre criar novo, retornar ativo ou restaurar. A decisão é feita em Python.

---

### `scheduler/src/services/conversation_engine.py`

- **Modificar** — `_on_enter_welcome` (linhas 936-939): adicionar `AND deleted_at IS NULL`:

```python
patients = self.db.execute_query(
    "SELECT name, gender FROM scheduler.patients WHERE clinic_id = %s AND phone = %s AND deleted_at IS NULL",
    (clinic_id, phone),
)
```

- **NÃO MODIFICAR** — Linha 1167 (JOIN lateral em appointments). Esse JOIN é parte de uma query que enriquece appointment com nome do paciente; preserva histórico.

---

### `scheduler/src/services/ai_tools.py`

- **Verificar e modificar** — Linha ~669: ler o contexto da query.
  - Se for `FROM scheduler.patients ... WHERE phone = ...` (lookup direto) → adicionar `AND deleted_at IS NULL`.
  - Se for `... LEFT JOIN scheduler.patients ON ...` (enriquecimento de appointment) → não tocar.

> Decisão durante implementação após Read do arquivo.

---

### `scheduler/tests/mocks/patient/delete_patient.json` (criar)

```json
{
  "httpMethod": "DELETE",
  "path": "/clinics/clinic-test/patients/00000000-0000-0000-0000-000000000001",
  "pathParameters": {
    "clinicId": "clinic-test",
    "patientId": "00000000-0000-0000-0000-000000000001"
  },
  "headers": {
    "x-api-key": "REPLACE_WITH_ENV_KEY"
  },
  "body": null
}
```

---

### `frontend/src/types/index.ts`

- **Modificar** — Adicionar campo na interface `Patient`:

```typescript
export interface Patient {
  id: string
  clinic_id: string
  phone: string
  name: string
  gender: 'M' | 'F'
  deleted_at?: string | null
  created_at: string
  updated_at: string
}
```

- **Modificar** — Substituir o tipo de retorno do create por uma interface dedicada:

```typescript
export interface CreatePatientResponse {
  status: 'CREATED' | 'RESTORED'
  patient: Patient
}
```

---

### `frontend/src/services/patients.service.ts`

- **Modificar** — `create` retorna o objeto completo:

```typescript
create(clinicId: string, payload: CreatePatientPayload) {
  return api
    .post<CreatePatientResponse>(`/clinics/${clinicId}/patients`, payload)
    .then((r) => r.data)
},
```

- **Adicionar** — Método `delete`:

```typescript
delete(clinicId: string, patientId: string) {
  return api
    .delete<{ status: string; message: string }>(`/clinics/${clinicId}/patients/${patientId}`)
    .then((r) => r.data)
},
```

---

### `frontend/src/hooks/usePatients.ts`

- **Modificar** — `useCreatePatient` agora resolve com `CreatePatientResponse`:

```typescript
export function useCreatePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation<CreatePatientResponse, Error, CreatePatientPayload>({
    mutationFn: (payload) => patientsService.create(clinicId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}
```

- **Adicionar** — `useDeletePatient`:

```typescript
export function useDeletePatient() {
  const { clinicId } = useAuth()
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (patientId: string) => patientsService.delete(clinicId!, patientId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: patientKeys.lists() })
    },
  })
}
```

---

### `frontend/src/pages/pacientes/components/DeletePatientConfirmModal.tsx` (criar)

- **Criar** — Modal de confirmação destrutiva. Estrutura:

```typescript
import { Modal } from '@/components/ui/Modal'
import { Button } from '@/components/ui/Button'
import { useDeletePatient } from '@/hooks/usePatients'
import { formatPhone } from '@/utils/formatPhone'
import type { PatientWithStats } from '@/types'

interface DeletePatientConfirmModalProps {
  patient: PatientWithStats | null
  onClose: () => void
  onSuccess: (patientName: string) => void
}

export function DeletePatientConfirmModal({ patient, onClose, onSuccess }: DeletePatientConfirmModalProps) {
  const mutation = useDeletePatient()

  if (!patient) return null

  async function handleDelete() {
    if (!patient) return
    try {
      await mutation.mutateAsync(patient.id)
      onSuccess(patient.name ?? 'Paciente')
      onClose()
    } catch {
      // erro renderizado inline via mutation.isError
    }
  }

  return (
    <Modal isOpen onClose={onClose} title="Excluir paciente">
      <div className="space-y-4">
        <p className="text-gray-700">
          Tem certeza que deseja excluir <strong>{patient.name ?? 'este paciente'}</strong> ({formatPhone(patient.phone)})?
        </p>
        <p className="text-sm text-gray-500">
          O paciente sai da lista, mas o histórico de agendamentos é preservado. Se ele voltar a entrar em contato pelo WhatsApp ou for cadastrado novamente, será restaurado automaticamente.
        </p>
        {mutation.isError && (
          <p className="text-sm text-red-600">Falha ao excluir. Tente novamente.</p>
        )}
        <div className="flex justify-end gap-2 pt-2">
          <Button variant="secondary" onClick={onClose} disabled={mutation.isPending}>
            Cancelar
          </Button>
          <Button variant="danger" onClick={handleDelete} loading={mutation.isPending}>
            Excluir paciente
          </Button>
        </div>
      </div>
    </Modal>
  )
}
```

> Reutilizar `Modal` e `Button` do `components/ui/`. Variant `danger` já existe (red-600). Conferir copy do CLAUDE.md frontend antes de finalizar.

---

### `frontend/src/pages/pacientes/components/PatientsTable.tsx`

- **Modificar** — Adicionar prop `onDelete: (patient: PatientWithStats) => void` na interface `PatientsTableProps`.
- **Modificar** — Adicionar botão na coluna de ações (após o botão Pause), com `onClick` que chama `e.stopPropagation()` + `onDelete(p)`:

```tsx
<button
  onClick={(e) => { e.stopPropagation(); onDelete(p) }}
  className="px-2.5 py-1.5 rounded-lg text-xs font-medium text-red-700 bg-red-50 hover:bg-red-100 transition-colors cursor-pointer"
  title="Excluir paciente"
>
  🗑 Excluir
</button>
```

---

### `frontend/src/pages/pacientes/PacientesPage.tsx`

- **Modificar**:
  - Adicionar estado `const [patientToDelete, setPatientToDelete] = useState<PatientWithStats | null>(null)`.
  - Importar `DeletePatientConfirmModal`.
  - Passar `onDelete={setPatientToDelete}` para `<PatientsTable />`.
  - Renderizar `<DeletePatientConfirmModal patient={patientToDelete} onClose={() => setPatientToDelete(null)} onSuccess={(name) => toast.success(\`Paciente ${name} excluído\`)} />` (ou padrão de toast já em uso na página).
  - No `onSuccess` do `useCreatePatient` (via `CreatePatientModal`), diferenciar resposta `RESTORED` vs `CREATED` para mostrar toast distinto: `"Paciente restaurado"` vs `"Paciente cadastrado"`.

---

### `frontend/src/pages/pacientes/components/CreatePatientModal.tsx`

- **Modificar** — A prop `onSuccess` (ou callback equivalente) passa a receber o objeto `CreatePatientResponse` em vez de só o `Patient`, para a `PacientesPage` decidir o toast. Se a UX atual já usa um único toast genérico, basta passar o `status` adiante.

---

## 7. Convenções a respeitar

- **Logging**: handlers Lambda usam `logger.info/error` no padrão dos outros handlers de patient.
- **Idempotência das migrations**: `IF NOT EXISTS` em ADD COLUMN e CREATE INDEX (já é o padrão do `setup_database.py`).
- **Tipagem frontend**: zero `any`. Tipos vivos em `types/index.ts`. `mutateAsync` para await + try/catch no handler de delete.
- **Estados obrigatórios** no modal de delete: loading (botão `loading={mutation.isPending}`), erro (mensagem inline), sucesso (modal fecha + toast).
- **Auth**: handler novo herda `require_api_key`. Frontend usa interceptor Axios já existente.
- **Naming**: arquivos backend kebab/snake conforme patterns de `patient/`. Componentes frontend em PascalCase.
- **Design Impeccable**: botão de excluir usa cor red-700/red-50 (não vermelho puro), espaçamento alinhado com os outros botões da linha (`gap-1.5`). Modal sem aninhar cards. Confirmação destrutiva com hierarquia clara (botão danger destacado, secondary discreto).
- **Histórico preservado**: nunca filtrar `deleted_at` em JOINs cuja origem é `appointments`. Esses pontos estão **intencionalmente** sem o filtro.

---

## 8. Validação pós-implementação

1. **Migration**: rodar `setup_database.py` em ambiente dev e verificar `\d scheduler.patients` (coluna + índice presentes).
2. **Endpoints REST** via curl (com `API_KEY` do `.env`):
   - Criar paciente novo → 201 status `CREATED`
   - Listar → aparece
   - Deletar → 200 status `SUCCESS`
   - Listar → não aparece
   - Deletar mesmo ID de novo → 200 (idempotente)
   - Criar com mesmo phone → 200 status `RESTORED`
   - Listar → aparece
3. **Fluxo WhatsApp**:
   - Deletar paciente via API
   - Enviar mensagem do mesmo número via z-api dev
   - Verificar logs: `Patient restored from soft-delete`
   - Confirmar via SQL: `deleted_at IS NULL` + `name` original preservado
4. **Frontend**:
   - `npm run lint` zero warnings
   - `npm run build` compila
   - Testar manualmente no Vite: criar, deletar, recriar (toast restore), conferir invalidação automática da lista
5. **Documentação**: criar `tests/integration/patient-soft-delete.md` com os comandos curl e Postman collection.
