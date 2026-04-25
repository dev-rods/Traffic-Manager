# PRD — 008 Soft-Delete de Pacientes

> Gerado na fase **Research**. Use como input para a fase Spec.

---

## 1. Objetivo

Permitir ao proprietário da clínica excluir um paciente pelo painel web, usando soft-delete via coluna `deleted_at TIMESTAMPTZ` na tabela `scheduler.patients`. Todo o sistema (API REST, fluxo WhatsApp, dashboard, relatórios, painel de atendentes) deve passar a ignorar pacientes soft-deletados nas operações de leitura/criação que usam o paciente como entidade ativa, preservando histórico em joins de appointments.

---

## 2. Contexto

Hoje a tabela `patients` não tem mecanismo de exclusão. Pacientes cadastrados por engano, duplicados, ou que pediram desligamento permanecem visíveis na lista da página `/pacientes` e continuam sendo encontrados pelo bot de WhatsApp. Hard-delete não é viável porque há FK em `appointments` (sem CASCADE) e perderíamos histórico financeiro/operacional.

Soft-delete via `deleted_at` resolve os dois problemas: o paciente some das listas e dos lookups ativos, mas o histórico de appointments continua intacto, com nome do paciente exibido normalmente nas telas de agenda e relatório.

A coluna `deleted_at TIMESTAMPTZ NULL` foi escolhida em vez de `active BOOLEAN` (padrão do resto do schema) porque carrega timestamp de auditoria útil para suporte e para a lógica de "restore on recreate" descrita abaixo.

---

## 3. Escopo

### Dentro do escopo

1. **Migration idempotente** em `setup_database.py`:
   - `ALTER TABLE scheduler.patients ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ`
   - Índice: `CREATE INDEX IF NOT EXISTS idx_patients_deleted ON scheduler.patients(clinic_id, deleted_at)`
   - Atualizar o `CREATE TABLE` correspondente em `TABLES` para manter consistência.

2. **Novo endpoint** `DELETE /clinics/{clinicId}/patients/{patientId}`:
   - Handler `scheduler/src/functions/patient/delete.py` que seta `deleted_at = NOW()` (idempotente: se já deletado, retorna 200 sem alterar timestamp).
   - Entrada nova em `scheduler/sls/functions/patient/interface.yml`.
   - Mesmo padrão de auth/CORS/timeout dos demais handlers de patient.

3. **Filtro `deleted_at IS NULL` em todas as leituras de paciente como entidade ativa**:
   - Handlers REST: `patient/list.py`, `patient/update.py`, `patient/create.py` (check de duplicidade), `clinic/dashboard.py` (KPIs de pacientes), `clinic/reports.py` (count de novos pacientes), `attendant/conversations.py`, `attendant/list_active.py`, `send/handler.py` (UPDATE de `last_message_at`).
   - Services: `appointment_service._get_or_create_patient`, `appointment_service.get_active_appointment_by_phone`, `appointment_service.get_active_appointments_by_phone`, `conversation_engine._on_enter_welcome`, `ai_tools.py` (lookup linha 669).

4. **Joins de appointments preservam histórico**:
   - Em `appointment/list.py`, `clinic/dashboard.py`, `report/daily.py`, `conversation_engine.py` (linha 1167) e qualquer LEFT JOIN `patients` para enriquecer dados de appointment, **NÃO** filtrar `deleted_at`. Nome do paciente continua aparecendo na agenda histórica.

5. **Restore on recreate** — comportamento idempotente em duas frentes:
   - **WhatsApp** (`appointment_service._get_or_create_patient`): se houver match por `(clinic_id, phone)` com `deleted_at IS NOT NULL`, fazer `UPDATE patients SET deleted_at = NULL, updated_at = NOW() WHERE id = ...` e retornar o paciente restaurado em vez de criar novo. Isso evita violar o `UNIQUE(clinic_id, phone)`.
   - **API REST** (`POST /clinics/{clinicId}/patients`): se o phone normalizado já existe soft-deletado, restaurar o paciente atualizando `name`, `gender` e zerando `deleted_at`. Resposta indica restore (`status: "restored"`) para o frontend.

6. **Appointments futuros NÃO são tocados** ao deletar paciente. Continuam com `status` original e seguem aparecendo na agenda. (Decisão consciente: paciente deletado pode ser legítimo no contexto de "limpar lista" sem cancelar agendamento já marcado.)

7. **Frontend**:
   - `patients.service.ts` ganha `delete(clinicId, patientId)`.
   - `usePatients.ts` ganha mutation `useDeletePatient` que invalida `patientKeys.lists()`.
   - `PatientsTable` ganha botão de excluir na coluna de ações.
   - Novo componente `DeletePatientConfirmModal` mostrando nome + telefone do paciente, exigindo confirmação antes de chamar a API.
   - `useCreatePatient` deve lidar com resposta de restore (toast/feedback distinto: "Paciente restaurado" vs "Paciente cadastrado").

### Fora do escopo

- UI de "ver pacientes deletados" / restaurar via painel (restore só ocorre automaticamente no recreate).
- Cancelamento automático de appointments futuros ao deletar paciente.
- Hard-delete administrativo.
- Soft-delete em outras tabelas (`appointments`, `leads`, `services`, etc.).
- Migração de dados existentes (todos os pacientes atuais ficam com `deleted_at = NULL`).
- Auditoria de quem deletou (sem `deleted_by`).

---

## 4. Áreas / arquivos impactados

### Backend (scheduler/)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | Migration idempotente + atualizar CREATE TABLE de `patients` |
| `scheduler/src/functions/patient/delete.py` | criar | Handler DELETE — soft-delete idempotente |
| `scheduler/sls/functions/patient/interface.yml` | modificar | Adicionar `DeletePatient` Lambda + rota DELETE |
| `scheduler/src/functions/patient/list.py` | modificar | Filtro `WHERE deleted_at IS NULL` na query principal |
| `scheduler/src/functions/patient/update.py` | modificar | Filtro `deleted_at IS NULL` no SELECT de existência |
| `scheduler/src/functions/patient/create.py` | modificar | Lógica de restore quando phone existe soft-deletado |
| `scheduler/src/functions/clinic/dashboard.py` | modificar | Filtro `deleted_at IS NULL` no count de pacientes ativos (manter join LEFT em appointments) |
| `scheduler/src/functions/clinic/reports.py` | modificar | Filtro `deleted_at IS NULL` no COUNT de novos pacientes |
| `scheduler/src/functions/attendant/conversations.py` | modificar | Filtro `deleted_at IS NULL` no IN-clause de phones |
| `scheduler/src/functions/attendant/list_active.py` | modificar | Filtro `deleted_at IS NULL` |
| `scheduler/src/functions/send/handler.py` | modificar | Filtro `deleted_at IS NULL` no UPDATE de `last_message_at` |
| `scheduler/src/services/appointment_service.py` | modificar | Filtros + lógica de restore em `_get_or_create_patient` e nos lookups por phone |
| `scheduler/src/services/conversation_engine.py` | modificar | Filtro `deleted_at IS NULL` em `_on_enter_welcome` (lookup direto). Linha 1167 (join lateral em appointments) **não** filtra |
| `scheduler/src/services/ai_tools.py` | modificar | Verificar lookup linha ~669 e adicionar filtro se for lookup direto de patient |
| `scheduler/src/functions/appointment/list.py` | manter | Join com patients **não** filtra `deleted_at` (preserva histórico) |
| `scheduler/src/functions/report/daily.py` | manter | Join com patients **não** filtra `deleted_at` (preserva histórico) |

### Frontend (frontend/)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `frontend/src/services/patients.service.ts` | modificar | Método `delete(clinicId, patientId)` + tipo de retorno do `create` com flag de restore |
| `frontend/src/hooks/usePatients.ts` | modificar | `useDeletePatient` mutation; ajustar `useCreatePatient` se necessário |
| `frontend/src/types/index.ts` | modificar | Adicionar `deleted_at?: string \| null` em `Patient`; tipo de resposta do create com `status` |
| `frontend/src/pages/pacientes/components/PatientsTable.tsx` | modificar | Botão de excluir na coluna de ações |
| `frontend/src/pages/pacientes/components/DeletePatientConfirmModal.tsx` | criar | Modal de confirmação destrutiva (nome + telefone, botão "Excluir paciente") |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | modificar | Wire-up do modal + estado de paciente sendo deletado |
| `frontend/src/pages/pacientes/components/CreatePatientModal.tsx` | modificar | Tratar resposta de restore (toast/feedback distinto, opcional) |

### Tests / Mocks / Postman

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/tests/mocks/patient/delete_patient.json` | criar | Mock de evento DELETE |
| `scheduler/tests/integration/patient-soft-delete.md` | criar | Casos de teste manuais via curl |
| `scheduler/tests/postman/patient-soft-delete.postman_requests.json` | criar | Postman requests do fluxo (create, delete, recreate-restore, list) |

---

## 5. Dependências e riscos

### Dependências

- Migration roda via `setup_database.py` (já existente no fluxo de deploy).
- Frontend depende do endpoint DELETE estar publicado antes do merge.
- Nenhuma dependência externa (sem mudança em z-api, OpenAI ou Google Sheets).

### Riscos

- **Lookup de WhatsApp não filtrar `deleted_at` em algum ponto** → paciente "deletado" continua sendo reconhecido pelo bot. Mitigação: enumerar todos os pontos no escopo e adicionar testes E2E manuais (mensagem de paciente deletado deve cair como paciente novo).
- **UNIQUE(clinic_id, phone)** continua aplicado mesmo a registros soft-deletados → se a lógica de restore falhar, recreate dará erro 409. Mitigação: a lógica de restore é a primeira coisa testada em `_get_or_create_patient` e em `POST /patients`.
- **Migration sem default** — linha existente fica com `deleted_at = NULL`, comportamento default é "ativo". Sem breaking change.
- **Frontend confundindo restore com create** — UX deve diferenciar para o usuário não pensar que cadastrou duplicado.
- **Joins históricos** — atenção redobrada para não adicionar filtro `deleted_at` em join de appointments por descuido (regrediria histórico). Code review obrigatório nesse ponto.

---

## 6. Critérios de aceite

### Backend

- [ ] Migration idempotente aplicada (rerun seguro): `deleted_at TIMESTAMPTZ NULL` + índice `idx_patients_deleted`.
- [ ] CREATE TABLE de `patients` em `TABLES` reflete a coluna nova.
- [ ] Endpoint `DELETE /clinics/{clinicId}/patients/{patientId}` retorna 200 e seta `deleted_at = NOW()`.
- [ ] DELETE em paciente já deletado é idempotente (não regrava timestamp, retorna 200).
- [ ] DELETE em paciente inexistente retorna 404.
- [ ] `GET /clinics/{clinicId}/patients` não retorna pacientes deletados.
- [ ] `PATCH /clinics/{clinicId}/patients/{patientId}` em paciente deletado retorna 404.
- [ ] `POST /clinics/{clinicId}/patients` com phone de paciente soft-deletado **restaura** o registro (status="restored") e atualiza name/gender.
- [ ] WhatsApp recebido de paciente deletado → `_on_enter_welcome` trata como novo paciente; `_get_or_create_patient` restaura o registro existente (sem criar duplicado).
- [ ] Dashboard, relatórios e painel de atendentes não contam/listam pacientes deletados.
- [ ] Agenda (`appointment/list.py`, `report/daily.py`) continua exibindo nome de paciente deletado em appointments existentes.

### Frontend

- [ ] Botão de excluir aparece em cada linha da tabela de pacientes.
- [ ] Click no botão abre modal de confirmação com nome + telefone.
- [ ] Confirmação chama DELETE e invalida a query `patientKeys.lists()`.
- [ ] Erro na chamada exibe mensagem inline e mantém o modal aberto.
- [ ] Após sucesso, paciente some da lista sem reload manual.
- [ ] Cadastrar paciente com phone de outro deletado mostra feedback de restore (toast/mensagem distinta).
- [ ] Tipo `Patient` inclui `deleted_at` opcional; build TS sem erros.

### QA geral

- [ ] `npm run lint` no frontend passa sem warnings.
- [ ] `npm run build` no frontend compila sem erros.
- [ ] Postman collection executa o fluxo completo (create → delete → recreate-restore → list-empty).
- [ ] Documentação `tests/integration/patient-soft-delete.md` cobre os casos acima.

---

## 7. Referências

- `Traffic-Manager/CLAUDE.md` (padrões backend e frontend)
- `Traffic-Manager/frontend/CLAUDE.md` (padrões React/TanStack Query)
- `scheduler/src/scripts/setup_database.py` (schema e migrations)
- `scheduler/sls/functions/patient/interface.yml` (rotas Lambda)
- `scheduler/src/services/appointment_service.py` (lookup por phone — caminho crítico do bot)
- `scheduler/src/services/conversation_engine.py` (state machine WhatsApp)
- `frontend/src/pages/pacientes/PacientesPage.tsx` (UI atual)

---

## Status (preencher após conclusão)

- [x] Pendente
- [x] Spec gerada: `spec/008-patient-soft-delete.md`
- [x] Implementado em: 2026-04-25
- [x] Registrado em `TASKS_LOG.md`
