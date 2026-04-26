# Spec — 009 Multi-unit architecture

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/009-multi-unit-architecture.md`

---

## 1. Resumo

Refatorar o Scheduler para suportar **múltiplas unidades por clínica** em 4 fases idempotentes (Schema → Backfill → Dual-read → Cutover). A `clinic` segue como tenant raiz (auth, billing, patients, leads, discount_rules); unit vira a fronteira operacional (agenda, profissionais, appointments, preços) e a fronteira de override de catálogo (services, areas, faq, templates) via padrão `unit_id IS NULL = clinic-default + unit_id != NULL = override`. Implementação cobre: **schema/migrations** em `setup_database.py`, **services novos** (`UnitService`, `CatalogResolver`, `TemplateResolver`), **CRUD de units e endpoints by-unit** em `serverless.yml`, **estado `ASK_UNIT`** no `conversation_engine` com lookup de unit por `instance_id` (suporta cenário híbrido: número clinic-wide hoje, per-unit no futuro, sem refator), **backfill script** com tratamento especial Nobre Laser (2 units), **`UnitContext` no painel React** com dropdown obrigatório na topbar, página `Configurações > Unidades`, refator de hooks/queries por `unitId`, refator do `Configurações > Catálogo` com badges Padrão/Customizado e toggle de override. Endpoints antigos `/clinics/{c}/...` continuam funcionando durante a transição (Fase 2 dual-read), retornam 400 para clinics multi-unit operacionais na Fase 3 (cutover).

---

## 2. Arquivos a criar

### Backend — Schema/Scripts

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/scripts/backfill_multi_unit.py` | Script one-shot idempotente. Cria 1 unit default por clinic + backfill `unit_id` em operacionais. Override hardcoded para `nobre-laser-sp-*` cria 2 units (Jardins + Tatuapé) e atribui histórico a Jardins (com log) |
| `scheduler/src/scripts/seed_clinic_units.py` | Helper para devs: cria unit a partir de payload JSON (utilitário, não usado em prod) |

### Backend — Services

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/services/unit_service.py` | `UnitService` com `create_unit`, `get_unit`, `list_units(clinic_id, active_only)`, `update_unit`, `soft_delete_unit`. Validações: clinic exists, slug único `(clinic_id, slug)`, FK consistente |
| `scheduler/src/services/catalog_resolver.py` | `CatalogResolver` com `list_services(clinic_id, unit_id)`, `list_areas(clinic_id, unit_id)`, `list_service_areas(clinic_id, unit_id, service_id)`. Algoritmo: união `(unit_id=U) ∪ (unit_id=NULL AND chave NOT IN unit-rows)` |
| `scheduler/src/services/template_resolver.py` | `TemplateResolver` com `list_faq_items(clinic_id, unit_id)`, `list_message_templates(clinic_id, unit_id)`. Mesmo algoritmo |

### Backend — Functions (handlers)

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/src/functions/unit/create.py` | `POST /clinics/{clinicId}/units` |
| `scheduler/src/functions/unit/get.py` | `GET /clinics/{clinicId}/units/{unitId}` |
| `scheduler/src/functions/unit/list.py` | `GET /clinics/{clinicId}/units` |
| `scheduler/src/functions/unit/update.py` | `PUT /clinics/{clinicId}/units/{unitId}` |
| `scheduler/src/functions/unit/delete.py` | `DELETE /clinics/{clinicId}/units/{unitId}` (soft: `active=false`) |
| `scheduler/src/functions/availability/list_rules_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/availability-rules` |
| `scheduler/src/functions/availability/create_rule_by_unit.py` | `POST /clinics/{clinicId}/units/{unitId}/availability-rules` |
| `scheduler/src/functions/availability/list_exceptions_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/availability-exceptions` |
| `scheduler/src/functions/availability/create_exception_by_unit.py` | `POST /clinics/{clinicId}/units/{unitId}/availability-exceptions` |
| `scheduler/src/functions/availability/get_slots_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/available-slots?date=&serviceId=` |
| `scheduler/src/functions/appointment/create_by_unit.py` | `POST /clinics/{clinicId}/units/{unitId}/appointments` |
| `scheduler/src/functions/appointment/list_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/appointments` |
| `scheduler/src/functions/service/list_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/services` (resolvido) |
| `scheduler/src/functions/service/list_areas_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/services/{serviceId}/areas` (resolvido) |
| `scheduler/src/functions/professional/list_by_unit.py` | `GET /clinics/{clinicId}/units/{unitId}/professionals` |
| `scheduler/src/functions/professional/create_by_unit.py` | `POST /clinics/{clinicId}/units/{unitId}/professionals` (cria + vincula M2M) |

### Backend — Serverless interface

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/sls/functions/unit/interface.yml` | Interface das 5 functions de unit (Create/Get/List/Update/Delete) |
| `scheduler/sls/functions/availability/by-unit-interface.yml` | Interface das 5 functions de availability per-unit |
| `scheduler/sls/functions/appointment/by-unit-interface.yml` | Interface das 2 functions de appointment per-unit |
| `scheduler/sls/functions/service/by-unit-interface.yml` | Interface das 2 functions de service/area per-unit |
| `scheduler/sls/functions/professional/by-unit-interface.yml` | Interface das 2 functions de professional per-unit |

### Backend — Tests

| Arquivo | Descrição |
|---------|-----------|
| `scheduler/tests/mocks/unit/create_unit.json` | Payload de criação |
| `scheduler/tests/mocks/unit/list_units.json` | Path/query params |
| `scheduler/tests/mocks/unit/update_unit.json` | Payload de update |
| `scheduler/tests/mocks/availability/create_rule_by_unit.json` | Payload de regra |
| `scheduler/tests/mocks/availability/get_slots_by_unit.json` | Path com `unitId` |
| `scheduler/tests/mocks/appointment/create_appointment_by_unit.json` | Payload com `unitId` |
| `scheduler/tests/mocks/service/list_services_by_unit.json` | Path com `unitId` |
| `scheduler/tests/mocks/multi_unit/catalog_resolution_with_overrides.json` | Cenário: clinic com 2 services default + 1 override em uma unit |
| `scheduler/tests/mocks/multi_unit/ask_unit_state.json` | Webhook payload simulando lead chegando na clinic com 2+ units |
| `scheduler/tests/integration/multi-unit.md` | Casos de teste manuais (Fase 0, 1, 2, 3) com curl |
| `scheduler/tests/postman/multi-unit.postman_requests.json` | Coleção Postman: CRUD units, catalog resolution, appointment by unit, conflict scenarios |
| `scheduler/tests/unit/test_catalog_resolver.py` | Testes do algoritmo de resolução (4 cenários) |
| `scheduler/tests/unit/test_no_cross_unit_leak.py` | Itera handlers per-unit; valida que retornam apenas dados da unit pedida |

### Frontend — Tipos / contexto / serviços / hooks

| Arquivo | Descrição |
|---------|-----------|
| `frontend/src/types/unit.ts` | Tipos `Unit`, `CreateUnitRequest`, `UpdateUnitRequest` |
| `frontend/src/store/UnitContext.tsx` | Provider com `currentUnit`, `setCurrentUnit`, `unitsList`, `isLoadingUnits`. Persiste `tm_current_unit_id` em localStorage. Auto-seleciona primeira unit no boot |
| `frontend/src/hooks/useUnit.ts` | Hook `useUnit()` para consumir `UnitContext` |
| `frontend/src/services/unit.service.ts` | HTTP client: `list`, `get`, `create`, `update`, `delete` |
| `frontend/src/hooks/useUnits.ts` | Query hook que carrega `unitsList` |

### Frontend — Componentes / Páginas

| Arquivo | Descrição |
|---------|-----------|
| `frontend/src/components/UnitSelector.tsx` | Dropdown na topbar; readonly badge se 1 unit; vazio → CTA criar primeira unit |
| `frontend/src/pages/configuracoes/unidades/UnidadesPage.tsx` | Lista de cards + botão "Nova unidade" |
| `frontend/src/pages/configuracoes/unidades/UnitFormModal.tsx` | Modal de criação/edição (nome, slug, address, timezone, business_hours, buffer_minutes, zapi_instance_id) |
| `frontend/src/pages/configuracoes/unidades/components/UnitCard.tsx` | Card de unit (nome, address, status, ações) |
| `frontend/src/pages/configuracoes/unidades/components/UnitDeleteConfirmModal.tsx` | Modal de soft-delete (com aviso sobre dados associados) |
| `frontend/src/pages/configuracoes/catalogo/components/OverrideToggle.tsx` | Componente reutilizável: toggle "Aplicar a: [Toda a clínica] / [Apenas esta unidade]" |
| `frontend/src/pages/configuracoes/catalogo/components/ScopeBadge.tsx` | Badge `[Padrão]` / `[Customizado nesta unidade]` |

---

## 3. Arquivos a modificar

### Backend — Schema

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/scripts/setup_database.py` | (a) Adicionar `units` e `professionals_units` em `TABLES`; (b) Em `MIGRATIONS`: blocos para `ADD COLUMN IF NOT EXISTS unit_id` em 8 tabelas, partial unique indexes para override, índices novos por unit_id, `professionals_units` table; (c) Atualizar `CREATE TABLE` de `services`, `areas`, `service_areas`, `faq_items`, `message_templates`, `appointments`, `availability_rules`, `availability_exceptions`, `clinic_users` em `TABLES` para incluir `unit_id`. Schema completo em `prd/009-...md` §5 |

### Backend — Services existentes

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/services/availability_engine.py` | (a) Adicionar `unit_id: str` como param obrigatório em `get_available_slots` (linha 15), `get_available_days` (linha 89), `get_available_slots_multi` (linha 113), `get_available_days_multi` (linha 178); (b) Filtrar appointments + availability_rules + availability_exceptions por `unit_id` em todas as queries; (c) Wrapper deprecated `get_available_slots_legacy(clinic_id, ...)` que resolve unit default (loga warning); (d) Buffer e business_hours lidos da `units`, não mais da `clinics` |
| `scheduler/src/services/appointment_service.py` | (a) `create_appointment` (linha 29) ganha `unit_id: str` obrigatório; (b) Conflict check muda de `(clinic_id, appointment_date, ...)` para `(unit_id, appointment_date, ...)`; (c) INSERT inclui `unit_id` em `appointments`; (d) `mark_as_booked` no lead permanece clinic-wide; (e) Wrapper legacy resolve unit default da clinic |
| `scheduler/src/services/conversation_engine.py` | (a) Novo estado `ASK_UNIT` em `ConversationState` enum + STATE_CONFIG; (b) Em `_on_enter_welcome`: após resolver clinic, chamar `resolve_unit_or_clinic(instance_id)` (helper novo); se 0 unit, transitar para `ASK_UNIT`; se 1, gravar em session.context e seguir; (c) `_on_enter_ask_unit`: lista units ativas da clinic e envia mensagem; (d) `_handle_ask_unit_response`: usa `intent_classifier.classify_unit(message, units)` e grava em session.context.unit_id; (e) Todas as transições downstream que usam `clinic_id` para queries operacionais (slots, appointments) passam a usar `unit_id` da session |
| `scheduler/src/services/intent_classifier.py` | Novo método `classify_unit(message: str, units: list[Unit]) -> Optional[str]` — fuzzy match por nome (Levenshtein) com fallback OpenAI quando ambíguo; padrão idêntico ao `classify_service` existente |
| `scheduler/src/services/lead_service.py` | Sem mudança (lead permanece clinic-wide). Confirmar que `upsert_lead` e `mark_as_booked` não exigem `unit_id` |
| `scheduler/src/services/template_service.py` | Refatorar para usar `TemplateResolver`: passa a aceitar `unit_id` opcional; resolve template default ou override |

### Backend — Handlers existentes (backward-compat ajustes Fase 2)

| Arquivo | Alterações |
|---------|------------|
| `scheduler/src/functions/webhook/handler.py` | Após receber evento z-api: chamar `resolve_unit_or_clinic(event.instance_id)` (helper novo em `webhook/handler.py` ou em `services/unit_service.py`); injetar `unit_id` resolvido no contexto que vai pro `conversation_engine`. Tratamento de fallback documentado em §6 |
| `scheduler/src/functions/availability/list_rules.py` | Continua funcionando; em Fase 2 retorna apenas regras com `unit_id = clinic.default_unit_id` (resolvido internamente) com header `X-Multi-Unit: true` se clinic tem 2+ units; em Fase 3 retorna 400 + `X-Migration-Required: true` quando clinic é multi-unit |
| `scheduler/src/functions/availability/get_slots.py` | Idem |
| `scheduler/src/functions/appointment/create.py` | Idem (Fase 2 default unit; Fase 3 reject) |
| `scheduler/src/functions/appointment/list.py` | Aceita `?unitId=<u>` opcional; sem o filtro retorna agregado de todas as units da clinic (sem 400) |
| `scheduler/src/functions/service/list.py` | Em Fase 2: retorna apenas linhas `unit_id IS NULL` (clinic-defaults); header `X-Multi-Unit: true` quando aplicável |
| `scheduler/src/functions/clinic/get.py` | Adicionar `units_count` no response para o painel saber se mostra dropdown ou badge |

### Backend — Serverless config

| Arquivo | Alterações |
|---------|------------|
| `scheduler/serverless.yml` | (a) Adicionar `${file(./sls/functions/unit/interface.yml)}` e os outros 4 novos arquivos `by-unit-interface.yml` em `functions:`; (b) Sem novos secrets/SSM neste PRD (z-api instance lookup é DB) |

### Frontend — Refatorações sistêmicas

| Arquivo | Alterações |
|---------|------------|
| `frontend/src/App.tsx` | Wrap `<AuthProvider>` com `<UnitProvider>` (UnitProvider lê `clinic_id` do AuthContext) |
| `frontend/src/router.tsx` | Nova rota `/configuracoes/unidades` (carrega `UnidadesPage`) |
| `frontend/src/layouts/AppLayout.tsx` | Topbar: incluir `<UnitSelector />` à esquerda do nome do usuário |
| `frontend/src/store/AuthContext.tsx` | Sem mudança estrutural; expor `clinic.units_count` se backend incluir |
| `frontend/src/services/api.ts` | Sem mudança (axios mantém `x-api-key`); todos novos services ganham métodos com `unitId` |

### Frontend — Hooks de query (impacto sistêmico)

| Arquivo | Alterações |
|---------|------------|
| `frontend/src/hooks/useAvailableSlots.ts` | (a) Aceitar `unitId` no param; (b) Query key: `['available-slots', clinicId, unitId, date, serviceId]`; (c) URL: `/clinics/{c}/units/{u}/available-slots`; (d) `enabled: !!unitId` |
| `frontend/src/hooks/useAppointments.ts` | (a) Aceitar `unitId`; (b) Query key inclui `unitId`; (c) URL muda para per-unit; (d) `refetchInterval: 10_000` permanece |
| `frontend/src/hooks/useServices.ts` | (a) Aceitar `unitId`; (b) URL: `/clinics/{c}/units/{u}/services`; (c) Resposta agora pode incluir `is_override: boolean` por linha |
| `frontend/src/hooks/useAreas.ts` | Idem |
| `frontend/src/hooks/useProfessionals.ts` | (a) Aceitar `unitId`; (b) URL per-unit; (c) Resposta lista profissionais ativos na unit |
| `frontend/src/hooks/useAvailabilityRules.ts` | Idem |

### Frontend — Páginas

| Arquivo | Alterações |
|---------|------------|
| `frontend/src/pages/agenda/Agenda.tsx` | Passar `currentUnit.id` para todos os hooks. Mensagem "Selecione uma unidade" se `currentUnit === null`. Coluna/badge da unit aparece apenas quando admin tem visão multi-unit (default: ocultar pq já filtra) |
| `frontend/src/pages/dashboard/Dashboard.tsx` | KPIs filtrados por `currentUnit.id` (appointments, ocupação). Lead/Patient KPIs continuam clinic-wide (deixar claro com legenda "Clínica toda") |
| `frontend/src/pages/configuracoes/servicos/ServicosPage.tsx` | (a) Header indica unit ativa; (b) Badge `[Padrão]`/`[Customizado]` em cada serviço; (c) Toggle de modo de visualização (Resolvido / Apenas overrides / Apenas defaults); (d) Modal de edição usa `OverrideToggle` |
| `frontend/src/pages/configuracoes/areas/AreasPage.tsx` | Idem |
| `frontend/src/pages/configuracoes/precos/PrecosPage.tsx` | Idem (preços = `service_areas`) |
| `frontend/src/pages/configuracoes/disponibilidade/DisponibilidadePage.tsx` | Filtra por `currentUnit.id`. Sem badges de override (availability é sempre per-unit) |
| `frontend/src/pages/configuracoes/profissionais/ProfissionaisPage.tsx` | Filtra por `currentUnit.id`. Modal de criação/edição inclui multi-select "Atende em quais unidades" (M2M) |
| `frontend/src/pages/pacientes/PacientesPage.tsx` | Permanece clinic-wide; coluna nova "Última unidade" no histórico de appointments |
| `frontend/src/pages/relatorios/RelatoriosPage.tsx` | Toggle no topo "Esta unidade / Clínica toda"; default "Esta unidade" |
| `frontend/src/components/Sidebar.tsx` | Adicionar item "Unidades" sob Configurações |

### Tests / docs

| Arquivo | Alterações |
|---------|------------|
| `scheduler/tests/postman/CLAUDE.md` | Documentar a nova coleção `multi-unit.postman_requests.json` no índice |
| `scheduler/CLAUDE.md` | Adicionar parágrafo sobre o modelo multi-unit (clinic = tenant raiz, unit = operacional) |
| `Traffic-Manager/CLAUDE.md` | Atualizar seção "Data Stores" para refletir `units`, `professionals_units`, `unit_id` em tabelas operacionais e de catálogo |
| `Traffic-Manager/frontend/CLAUDE.md` | Documentar `UnitContext` e o padrão de hooks com `unitId` |
| `Traffic-Manager/KANBAN.md` | Mover card 009 de Backlog → In Progress → Done conforme andamento |
| `Traffic-Manager/TASKS_LOG.md` | Registrar conclusão da task 009 com data |

---

## 4. Arquivos a remover

Nenhum nesta fase. **Fase 3 (cutover)** marca handlers operacionais antigos como deprecated mas **não remove** — eles continuam servindo clinics single-unit (que são maioria por enquanto). Remoção final é decisão futura.

---

## 5. Ordem de implementação sugerida

A implementação segue as 4 fases do PRD. Cada fase é deployable e testável independentemente; fim de fase = ponto de checkpoint para validação antes da próxima.

### Fase 0 — Schema (deploy 1)

1. **Schema migrations** — `scheduler/src/scripts/setup_database.py`
   - Adicionar `units` table em `TABLES`
   - Adicionar `professionals_units` table em `TABLES`
   - `MIGRATIONS` ganha 8 blocos `ADD COLUMN IF NOT EXISTS unit_id` em tabelas alvo
   - `MIGRATIONS` ganha drops dos UNIQUE antigos + partial unique indexes novos (services, areas, service_areas, faq_items, message_templates)
   - `MIGRATIONS` ganha índices novos (operacionais por unit_id)
   - Atualizar `CREATE TABLE` de tabelas afetadas em `TABLES` para refletir `unit_id`
2. **Validação local** — rodar `setup_database.py` 2× contra DB local; verificar idempotência
3. **Deploy dev** — deploy do scheduler em `dev`; rodar `setup_database.py` no RDS dev
4. **Validação** — `psql` para ver schema; criar 1 unit manual via SQL para sanity

### Fase 1 — Backfill (one-shot)

5. **Backfill script** — `scheduler/src/scripts/backfill_multi_unit.py`
   - Função `create_default_unit(clinic)` UPSERT por `(clinic_id, slug='default')`
   - Função `backfill_operational_rows(clinic, unit)` — UPDATE em `appointments`, `availability_rules`, `availability_exceptions` setando `unit_id` da unit default. Apenas linhas com `unit_id IS NULL` (idempotente)
   - Função `backfill_professionals(clinic, unit)` — INSERT em `professionals_units` para cada professional ativo, ON CONFLICT DO NOTHING
   - **Override Nobre Laser**: detecta clinic_id começando com `nobre-laser-sp-`, cria 2 units (Jardins, Tatuapé), atribui appointments existentes a Jardins (com log linha por linha)
   - Modo `--dry-run` que apenas conta o que seria feito
6. **Rodar em dev** — `python -m scheduler.src.scripts.backfill_multi_unit --stage dev --dry-run`, depois sem `--dry-run`
7. **Validação** — query `SELECT COUNT(*) FROM scheduler.appointments WHERE unit_id IS NULL` deve retornar 0
8. **Rodar em prod** — depois de revisão manual dos logs do dev

### Fase 2 — Dual-read + new endpoints (deploy 2)

9. **Services novos** — criar `unit_service.py`, `catalog_resolver.py`, `template_resolver.py`
   - `UnitService.create_unit/get_unit/list_units/update_unit/soft_delete_unit`
   - `CatalogResolver.list_services/list_areas/list_service_areas` (algoritmo §6.2)
   - `TemplateResolver.list_faq_items/list_message_templates` (mesmo algoritmo)
10. **Refator services existentes** — `availability_engine.py`, `appointment_service.py`, `intent_classifier.py`, `template_service.py`
    - Assinaturas com `unit_id` obrigatório
    - Wrappers legacy (que resolvem unit default da clinic) com `logger.warning("[deprecated]...")`
11. **Conversation engine** — `conversation_engine.py`
    - Adicionar `ConversationState.ASK_UNIT`
    - `STATE_CONFIG[ASK_UNIT]` com transitions, template_keys, fallbacks
    - Helper `resolve_unit_or_clinic(instance_id)` — primeiro `units.zapi_instance_id`, fallback `clinics.zapi_instance_id`
    - Em `_on_enter_welcome`: roteia para `ASK_UNIT` se necessário
    - `_on_enter_ask_unit` + `_handle_ask_unit_response`
    - Persiste `session.context.unit_id` em DynamoDB
12. **Handlers novos** — criar 16 handlers Lambda (CRUD units, by-unit availability/appointment/service/professional)
    - Cada handler: parse path params, chamar service, retornar JSON com `corsHeaders()`
    - Padrão idêntico aos handlers existentes (logger com `[traceId]`, validation, error handling)
13. **Serverless interfaces** — criar 5 arquivos `*-interface.yml` e importar em `serverless.yml`
14. **Deploy dev** — `cd scheduler && serverless deploy --stage dev`
15. **Smoke test** — bateria de curl manuais (criar unit, criar regra, criar appointment, listar slots) usando `tests/integration/multi-unit.md`
16. **Frontend** — começar refator do painel **em paralelo a 9–14** (não bloqueia)
    - `UnitContext` + `useUnit` + `unit.service.ts` + `useUnits`
    - `UnitSelector` na topbar
    - Página `Configurações > Unidades` (CRUD)
    - Refator dos hooks (`useAvailableSlots`, `useAppointments`, `useServices`, `useAreas`, `useProfessionals`, `useAvailabilityRules`)
    - Refator das páginas (Agenda, Dashboard, Serviços, Áreas, Preços, Disponibilidade, Profissionais)
    - Adicionar `Unidades` ao Sidebar
17. **Build/typecheck/lint frontend** — `npm run build && npm run lint`
18. **Smoke test painel** — bateria manual: trocar unit, validar refetch, criar override de serviço, validar isolamento

### Fase 3 — Cutover (deploy 3)

19. **NOT NULL constraints** — adicionar em `MIGRATIONS`:
    ```sql
    ALTER TABLE scheduler.appointments ALTER COLUMN unit_id SET NOT NULL;
    ALTER TABLE scheduler.availability_rules ALTER COLUMN unit_id SET NOT NULL;
    ALTER TABLE scheduler.availability_exceptions ALTER COLUMN unit_id SET NOT NULL;
    ```
20. **Reject em handlers antigos** — em `appointment/create.py`, `availability/get_slots.py`, etc., quando `clinic.units_count > 1`: retornar 400 com `{"error": "MIGRATION_REQUIRED", "message": "Use /clinics/{c}/units/{u}/...", "deprecated_endpoint": true}` e header `X-Migration-Required: true`
21. **Deploy prod** — após smoke test em dev e em prod single-unit clinics (verificar zero impacto)
22. **Documentação final** — atualizar CLAUDE.md, KANBAN.md, TASKS_LOG.md

### Pós-Fase 3 (validação contínua)

23. **Tests automatizados** — escrever `test_catalog_resolver.py` e `test_no_cross_unit_leak.py`
24. **Postman collection** — criar `tests/postman/multi-unit.postman_requests.json`
25. **Doc de integração** — finalizar `tests/integration/multi-unit.md`

---

## 6. Detalhes por arquivo

### 6.1. `scheduler/src/scripts/setup_database.py`

**Modificar** — Adicionar nas listas `TABLES` e `MIGRATIONS`.

#### `TABLES` — novas tabelas (no fim da lista, antes de `# Indexes`)

```python
"""
CREATE TABLE IF NOT EXISTS scheduler.units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    address TEXT,
    timezone VARCHAR(50) NOT NULL DEFAULT 'America/Sao_Paulo',
    business_hours JSONB DEFAULT '{}',
    buffer_minutes INTEGER DEFAULT 0,
    zapi_instance_id VARCHAR(100),
    max_future_dates INTEGER DEFAULT 5,
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clinic_id, slug)
)
""",

"""
CREATE TABLE IF NOT EXISTS scheduler.professionals_units (
    professional_id UUID NOT NULL REFERENCES scheduler.professionals(id) ON DELETE CASCADE,
    unit_id UUID NOT NULL REFERENCES scheduler.units(id) ON DELETE CASCADE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (professional_id, unit_id)
)
""",
```

#### `TABLES` — atualizar tabelas existentes incluindo `unit_id`

Adicionar `unit_id UUID REFERENCES scheduler.units(id)` em:
- `appointments` — após `clinic_id`, antes de `patient_id`
- `availability_rules` — após `clinic_id`
- `availability_exceptions` — após `clinic_id`
- `services` — após `clinic_id` (nullable)
- `areas` — após `clinic_id` (nullable)
- `service_areas` — após `service_id` (nullable)
- `faq_items` — após `clinic_id` (nullable)
- `message_templates` — após `clinic_id` (nullable)
- `clinic_users` — após `clinic_id` (nullable)

#### `MIGRATIONS` — blocos novos (concatenados)

```python
# units / professionals_units (CREATE TABLE IF NOT EXISTS já em TABLES; aqui apenas índices)
"CREATE INDEX IF NOT EXISTS idx_units_clinic ON scheduler.units(clinic_id) WHERE active = TRUE",
"CREATE INDEX IF NOT EXISTS idx_units_zapi ON scheduler.units(zapi_instance_id) WHERE zapi_instance_id IS NOT NULL",
"CREATE INDEX IF NOT EXISTS idx_prof_units_unit ON scheduler.professionals_units(unit_id) WHERE active = TRUE",

# unit_id columns (idempotente)
"ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.availability_rules ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.availability_exceptions ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.services ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.areas ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.faq_items ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.message_templates ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",
"ALTER TABLE scheduler.clinic_users ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id)",

# Índices operacionais por unit
"CREATE INDEX IF NOT EXISTS idx_appointments_unit_date ON scheduler.appointments(unit_id, appointment_date)",
"CREATE INDEX IF NOT EXISTS idx_availability_rules_unit ON scheduler.availability_rules(unit_id)",
"CREATE INDEX IF NOT EXISTS idx_availability_exceptions_unit ON scheduler.availability_exceptions(unit_id, exception_date)",

# Drops dos UNIQUE antigos (se existirem) + partial unique indexes para override pattern
# services
"ALTER TABLE scheduler.services DROP CONSTRAINT IF EXISTS services_clinic_id_name_key",
"CREATE UNIQUE INDEX IF NOT EXISTS uniq_services_clinic_default ON scheduler.services(clinic_id, name) WHERE unit_id IS NULL",
"CREATE UNIQUE INDEX IF NOT EXISTS uniq_services_clinic_unit ON scheduler.services(clinic_id, unit_id, name) WHERE unit_id IS NOT NULL",
# areas
"ALTER TABLE scheduler.areas DROP CONSTRAINT IF EXISTS areas_clinic_id_name_key",
"CREATE UNIQUE INDEX IF NOT EXISTS uniq_areas_clinic_default ON scheduler.areas(clinic_id, name) WHERE unit_id IS NULL",
"CREATE UNIQUE INDEX IF NOT EXISTS uniq_areas_clinic_unit ON scheduler.areas(clinic_id, unit_id, name) WHERE unit_id IS NOT NULL",
# service_areas
"ALTER TABLE scheduler.service_areas DROP CONSTRAINT IF EXISTS service_areas_service_id_area_id_key",
"CREATE UNIQUE INDEX IF NOT EXISTS uniq_svcareas_default ON scheduler.service_areas(service_id, area_id) WHERE unit_id IS NULL",
"CREATE UNIQUE INDEX IF NOT EXISTS uniq_svcareas_unit ON scheduler.service_areas(service_id, area_id, unit_id) WHERE unit_id IS NOT NULL",
# faq_items / message_templates: idem (chaves a confirmar conforme schema atual)
```

> **Nota:** os nomes exatos das constraints UNIQUE antigas precisam ser confirmados via `psql \d scheduler.services` etc. antes do drop. Se a constraint não existir com o nome esperado, o `DROP CONSTRAINT IF EXISTS` é no-op (idempotente). Adicionar comentário explicando isso no script.

### 6.2. `scheduler/src/services/catalog_resolver.py` (criar)

```python
"""
Resolução clinic-default + unit-override para catálogo (services, areas, service_areas).
Algoritmo: prefere row da unit; cai pra row default da clinic se chave não tem override.
"""
from typing import Optional
from src.services.db.connection import get_connection
import logging
logger = logging.getLogger(__name__)


class CatalogResolver:
    def list_services(self, clinic_id: str, unit_id: str) -> list[dict]:
        """Retorna services resolvidos: overrides da unit + defaults da clinic não overridadas."""
        sql = """
        WITH unit_services AS (
            SELECT *, TRUE AS is_override FROM scheduler.services
            WHERE clinic_id = %s AND unit_id = %s AND active = TRUE
        ),
        clinic_defaults AS (
            SELECT *, FALSE AS is_override FROM scheduler.services
            WHERE clinic_id = %s AND unit_id IS NULL AND active = TRUE
              AND name NOT IN (SELECT name FROM unit_services)
        )
        SELECT * FROM unit_services
        UNION ALL
        SELECT * FROM clinic_defaults
        ORDER BY name;
        """
        with get_connection() as conn, conn.cursor() as cur:
            cur.execute(sql, (clinic_id, unit_id, clinic_id))
            return [dict(row) for row in cur.fetchall()]

    def list_areas(self, clinic_id: str, unit_id: str) -> list[dict]:
        # Mesmo padrão; chave funcional `name`.
        ...

    def list_service_areas(self, clinic_id: str, unit_id: str, service_id: str) -> list[dict]:
        # Chave funcional `(service_id, area_id)`.
        sql = """
        WITH unit_sa AS (
            SELECT *, TRUE AS is_override FROM scheduler.service_areas
            WHERE service_id = %s AND unit_id = %s AND active = TRUE
        ),
        clinic_defaults AS (
            SELECT *, FALSE AS is_override FROM scheduler.service_areas
            WHERE service_id = %s AND unit_id IS NULL AND active = TRUE
              AND area_id NOT IN (SELECT area_id FROM unit_sa)
        )
        SELECT * FROM unit_sa
        UNION ALL
        SELECT * FROM clinic_defaults;
        """
        ...
```

- Cada método retorna list de dicts incluindo `is_override: bool` para o front renderizar badges.
- Não fazer caching nesta versão; deixar para v2 se virar gargalo.
- Logging: `[traceId: {trace_id}] CatalogResolver.list_services clinic=X unit=Y → N rows (M overrides)`.

### 6.3. `scheduler/src/services/unit_service.py` (criar)

Padrão CRUD igual aos outros services do projeto. Validações:
- `create_unit`: clinic existe e está ativa; slug único `(clinic_id, slug)`; auto-gerar slug a partir do `name` se não informado (kebab-case sem acentos).
- `update_unit`: bloquear mudança de `clinic_id` (FK imutável após criação); `slug` editável mas valida unicidade.
- `soft_delete_unit`: validar que não há appointments futuros ativos (`appointment_date >= today AND status='CONFIRMED'`); se houver, retornar 409 com payload claro.
- `list_units(clinic_id, active_only=True)`: ORDER BY `name ASC`.

### 6.4. `scheduler/src/services/availability_engine.py`

**Modificar** — assinatura nova:

```python
class AvailabilityEngine:
    def get_available_slots(
        self, unit_id: str, target_date: str, service_id: str
    ) -> List[str]:
        ...
```

- Buscar `business_hours`, `buffer_minutes`, `timezone` de `units WHERE id = unit_id` (não mais de clinics).
- Filtrar `availability_rules WHERE unit_id = %s` (não `clinic_id`).
- Filtrar `availability_exceptions WHERE unit_id = %s`.
- Filtrar `appointments WHERE unit_id = %s AND appointment_date = %s AND status = 'CONFIRMED'`.
- Wrapper legacy (Fase 2):
  ```python
  def get_available_slots_legacy(self, clinic_id, target_date, service_id):
      logger.warning("[deprecated] resolving default unit for clinic_id=%s", clinic_id)
      unit = UnitService().get_default_unit(clinic_id)
      return self.get_available_slots(unit.id, target_date, service_id)
  ```
  - `get_default_unit` retorna a primeira unit ativa por `name ASC` (definição arbitrária para single-unit clinics; multi-unit clinics não devem chamar legacy).

### 6.5. `scheduler/src/services/appointment_service.py`

**Modificar** — `create_appointment`:

```python
def create_appointment(
    self,
    unit_id: str,           # NOVO obrigatório
    clinic_id: str,         # mantém para validação cross-FK e para LeadService
    phone: str,
    service_ids: list[str],
    appointment_date: str,
    start_time: str,
    full_name: str,
    service_area_pairs: list[dict] = None,
    metadata: dict = None,    # mantém da spec do PRD 010 (será usado lá depois)
) -> dict:
    ...
```

- Validar `unit_id` pertence à `clinic_id` (SELECT em `units` antes de prosseguir; 400 se não).
- Conflict check: `SELECT ... FROM appointments WHERE unit_id = %s AND appointment_date = %s AND status = 'CONFIRMED' AND ...` (mesmo overlap check existente, só troca `clinic_id` por `unit_id`).
- INSERT inclui `unit_id`.
- `metadata` (JSONB do PRD 010) continua suportado mas não obrigatório.

### 6.6. `scheduler/src/services/conversation_engine.py`

**Modificar** — adicionar `ASK_UNIT`:

```python
class ConversationState(Enum):
    ...
    ASK_UNIT = "ASK_UNIT"  # entre WELCOME e MAIN_MENU
    ...

STATE_CONFIG[ConversationState.ASK_UNIT] = {
    "template_keys": ["ask_unit_message"],
    "transitions": {
        "select_unit": ConversationState.MAIN_MENU,
        "fallback": ConversationState.ASK_UNIT,
    },
    "input_type": "free_text",
    "max_attempts": 3,
}
```

**Helper novo** (em `webhook/handler.py` ou em `unit_service.py`):

```python
def resolve_unit_or_clinic(instance_id: str) -> tuple[Optional[str], Optional[str]]:
    """Retorna (clinic_id, unit_id). unit_id pode ser None se ainda não determinada."""
    # 1. Tenta unit-level
    unit = db.fetch_one(
        "SELECT id, clinic_id FROM scheduler.units WHERE zapi_instance_id = %s AND active",
        (instance_id,)
    )
    if unit:
        return unit["clinic_id"], unit["id"]

    # 2. Fallback clinic-level
    clinic = db.fetch_one(
        "SELECT clinic_id FROM scheduler.clinics WHERE zapi_instance_id = %s AND active",
        (instance_id,)
    )
    if clinic:
        # Se clinic tem 1 única unit ativa, auto-resolve
        units = UnitService().list_units(clinic["clinic_id"], active_only=True)
        if len(units) == 1:
            return clinic["clinic_id"], units[0]["id"]
        # Senão, deixa unit_id None → conversation_engine vai pro ASK_UNIT
        return clinic["clinic_id"], None

    return None, None
```

**Em `_on_enter_welcome`** (linhas atuais ~936-980):
- Após resolver clinic, se `unit_id is None` e `clinic.units_count > 1` → transitar para `ASK_UNIT`
- Senão, gravar `unit_id` em `session.context.unit_id` e seguir para `MAIN_MENU` normalmente

**Novos handlers** em `conversation_engine.py`:

```python
def _on_enter_ask_unit(self, session: Session) -> str:
    units = UnitService().list_units(session.clinic_id, active_only=True)
    options = "\n".join(f"{i+1}️⃣ {u['name']} — {u.get('address', '')}" for i, u in enumerate(units))
    template = TemplateResolver().get_template(
        clinic_id=session.clinic_id,
        unit_id=None,  # ASK_UNIT é antes de unit estar definida
        key="ask_unit_message",
    )
    return template.format(clinic_name=session.clinic_name, options=options)

def _handle_ask_unit_response(self, session: Session, message: str) -> ConversationState:
    units = UnitService().list_units(session.clinic_id, active_only=True)
    selected = IntentClassifier().classify_unit(message, units)
    if selected:
        session.context["unit_id"] = selected["id"]
        DynamoDB.save_session(session)
        return ConversationState.MAIN_MENU
    # Re-prompt
    return ConversationState.ASK_UNIT
```

**State recovery** — toda função que usa `session.context["unit_id"]` valida que existe; se faltar, `return ConversationState.ASK_UNIT` (não erro).

### 6.7. `scheduler/src/services/intent_classifier.py`

**Adicionar método**:

```python
def classify_unit(self, message: str, units: list[dict]) -> Optional[dict]:
    """Fuzzy match por nome. Retorna a unit selecionada ou None se ambíguo."""
    # 1. Match exato (case-insensitive)
    msg_lower = message.lower().strip()
    for unit in units:
        if msg_lower == unit["name"].lower():
            return unit
    # 2. Match numérico (1, 2, 3...)
    if msg_lower.isdigit():
        idx = int(msg_lower) - 1
        if 0 <= idx < len(units):
            return units[idx]
    # 3. Levenshtein fuzzy (mesmo padrão de classify_service)
    best_match, best_score = self._fuzzy_match(msg_lower, [u["name"] for u in units])
    if best_score >= 0.75:
        return next(u for u in units if u["name"] == best_match)
    # 4. Fallback OpenAI (mesmo padrão dos outros classifiers)
    return self._openai_classify_unit(message, units)
```

### 6.8. `scheduler/src/scripts/backfill_multi_unit.py` (criar)

```python
"""
Backfill script (Fase 1 da migração 009).
Idempotente: pode rodar 2x sem efeitos colaterais.

Uso:
    python -m scheduler.src.scripts.backfill_multi_unit --stage dev --dry-run
    python -m scheduler.src.scripts.backfill_multi_unit --stage dev
    python -m scheduler.src.scripts.backfill_multi_unit --stage prod
"""
import argparse, logging, sys
from src.services.db.connection import get_connection

NOBRE_LASER_PREFIX = "nobre-laser-sp-"

def backfill(dry_run: bool = False):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT clinic_id, name, address, timezone, business_hours, buffer_minutes, max_future_dates FROM scheduler.clinics WHERE active = TRUE")
        clinics = cur.fetchall()

        for clinic in clinics:
            if clinic["clinic_id"].startswith(NOBRE_LASER_PREFIX):
                _backfill_nobre_laser(cur, clinic, dry_run)
            else:
                _backfill_default_clinic(cur, clinic, dry_run)

        if not dry_run:
            conn.commit()

def _backfill_default_clinic(cur, clinic, dry_run):
    """Cria 1 unit 'default' e backfill operacional."""
    # UPSERT unit default
    cur.execute("""
        INSERT INTO scheduler.units (clinic_id, name, slug, address, timezone, business_hours, buffer_minutes, max_future_dates, active)
        VALUES (%(clinic_id)s, %(name)s, 'default', %(address)s, %(timezone)s, %(business_hours)s, %(buffer_minutes)s, %(max_future_dates)s, TRUE)
        ON CONFLICT (clinic_id, slug) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW()
        RETURNING id
    """, dict(clinic))
    unit_id = cur.fetchone()["id"]

    # Backfill apenas linhas com unit_id IS NULL (idempotente)
    cur.execute("UPDATE scheduler.appointments SET unit_id = %s WHERE clinic_id = %s AND unit_id IS NULL", (unit_id, clinic["clinic_id"]))
    cur.execute("UPDATE scheduler.availability_rules SET unit_id = %s WHERE clinic_id = %s AND unit_id IS NULL", (unit_id, clinic["clinic_id"]))
    cur.execute("UPDATE scheduler.availability_exceptions SET unit_id = %s WHERE clinic_id = %s AND unit_id IS NULL", (unit_id, clinic["clinic_id"]))

    # M2M professionals
    cur.execute("""
        INSERT INTO scheduler.professionals_units (professional_id, unit_id)
        SELECT id, %s FROM scheduler.professionals WHERE clinic_id = %s AND active = TRUE
        ON CONFLICT DO NOTHING
    """, (unit_id, clinic["clinic_id"]))

    logger.info("[backfill] %s → 1 unit (default), %d appointments updated", clinic["clinic_id"], cur.rowcount)

def _backfill_nobre_laser(cur, clinic, dry_run):
    """Override: cria 2 units (Jardins, Tatuapé). Histórico vai pra Jardins."""
    units_payload = [
        {"name": "Nobre Laser - Jardins", "slug": "jardins", "address": "Jardins, São Paulo - SP"},
        {"name": "Nobre Laser - Tatuapé", "slug": "tatuape", "address": "Tatuapé, São Paulo - SP"},
    ]
    unit_ids = {}
    for u in units_payload:
        cur.execute("""
            INSERT INTO scheduler.units (clinic_id, name, slug, address, timezone, business_hours, buffer_minutes, max_future_dates, active)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, TRUE)
            ON CONFLICT (clinic_id, slug) DO UPDATE SET name = EXCLUDED.name, updated_at = NOW()
            RETURNING id
        """, (clinic["clinic_id"], u["name"], u["slug"], u["address"], clinic["timezone"], clinic["business_hours"], clinic["buffer_minutes"], clinic["max_future_dates"]))
        unit_ids[u["slug"]] = cur.fetchone()["id"]

    jardins_id = unit_ids["jardins"]

    # Histórico de appointments → Jardins (com log linha por linha)
    cur.execute("SELECT id, appointment_date FROM scheduler.appointments WHERE clinic_id = %s AND unit_id IS NULL", (clinic["clinic_id"],))
    rows = cur.fetchall()
    for row in rows:
        logger.info("[backfill][nobre] appointment %s (date=%s) → Jardins", row["id"], row["appointment_date"])
    cur.execute("UPDATE scheduler.appointments SET unit_id = %s WHERE clinic_id = %s AND unit_id IS NULL", (jardins_id, clinic["clinic_id"]))

    # Availability rules/exceptions → ambas as units (não dá pra heurística; replica)
    cur.execute("""
        INSERT INTO scheduler.availability_rules (clinic_id, unit_id, professional_id, day_of_week, rule_date, start_time, end_time, active)
        SELECT clinic_id, %s, professional_id, day_of_week, rule_date, start_time, end_time, active
        FROM scheduler.availability_rules WHERE clinic_id = %s AND unit_id IS NULL
    """, (unit_ids["tatuape"], clinic["clinic_id"]))
    cur.execute("UPDATE scheduler.availability_rules SET unit_id = %s WHERE clinic_id = %s AND unit_id IS NULL", (jardins_id, clinic["clinic_id"]))

    # Idem para exceptions, professionals_units (todos os profs em ambas as units)
    ...

    logger.info("[backfill][nobre] %s → 2 units (Jardins, Tatuapé). Histórico em Jardins.", clinic["clinic_id"])

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", default="dev", choices=["dev", "prod"])
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    backfill(dry_run=args.dry_run)
```

> **Importante:** rodar sempre `--dry-run` primeiro em prod e revisar logs. Histórico da Nobre vai todo para Jardins por convenção; se for crítico marcar appointments antigos manualmente, registrar na issue de followup.

### 6.9. Frontend — `frontend/src/store/UnitContext.tsx` (criar)

```tsx
import { createContext, useState, useEffect, useCallback, ReactNode } from "react";
import { useAuth } from "@/hooks/useAuth";
import { unitService } from "@/services/unit.service";
import type { Unit } from "@/types/unit";

type UnitContextValue = {
  currentUnit: Unit | null;
  setCurrentUnit: (unit: Unit) => void;
  unitsList: Unit[];
  isLoadingUnits: boolean;
  refetchUnits: () => Promise<void>;
};

export const UnitContext = createContext<UnitContextValue | null>(null);
const STORAGE_KEY = "tm_current_unit_id";

export function UnitProvider({ children }: { children: ReactNode }) {
  const { clinic } = useAuth();
  const [unitsList, setUnitsList] = useState<Unit[]>([]);
  const [currentUnit, setCurrentUnitState] = useState<Unit | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const setCurrentUnit = useCallback((unit: Unit) => {
    setCurrentUnitState(unit);
    localStorage.setItem(STORAGE_KEY, unit.id);
  }, []);

  const refetchUnits = useCallback(async () => {
    if (!clinic) return;
    setIsLoading(true);
    const list = await unitService.list(clinic.clinic_id);
    setUnitsList(list);
    const stored = localStorage.getItem(STORAGE_KEY);
    const found = list.find((u) => u.id === stored) ?? list[0] ?? null;
    setCurrentUnitState(found);
    if (found) localStorage.setItem(STORAGE_KEY, found.id);
    setIsLoading(false);
  }, [clinic]);

  useEffect(() => { refetchUnits(); }, [refetchUnits]);

  return (
    <UnitContext.Provider value={{ currentUnit, setCurrentUnit, unitsList, isLoadingUnits: isLoading, refetchUnits }}>
      {children}
    </UnitContext.Provider>
  );
}
```

### 6.10. Frontend — `frontend/src/components/UnitSelector.tsx` (criar)

- Se `unitsList.length === 0`: render CTA "Criar primeira unidade" → `/configuracoes/unidades?onboarding=true`.
- Se `unitsList.length === 1`: badge readonly `Unidade: {currentUnit.name}`.
- Senão: dropdown shadcn-style com lista; `onSelect` chama `setCurrentUnit(u)` + `queryClient.invalidateQueries()`.
- Padrão visual: respeitar Impeccable design (ver `frontend/CLAUDE.md` "Design Principles").

### 6.11. Frontend — refator de hook (exemplo `useAvailableSlots.ts`)

```ts
export function useAvailableSlots(params: { date: string; serviceId: string }) {
  const { clinic } = useAuth();
  const { currentUnit } = useUnit();
  return useQuery({
    queryKey: ["available-slots", clinic?.clinic_id, currentUnit?.id, params.date, params.serviceId],
    queryFn: () => availabilityService.getSlots({
      clinicId: clinic!.clinic_id,
      unitId: currentUnit!.id,
      date: params.date,
      serviceId: params.serviceId,
    }),
    enabled: !!clinic && !!currentUnit && !!params.date && !!params.serviceId,
    refetchInterval: 10_000,
  });
}
```

Padrão idêntico para `useAppointments`, `useServices`, `useAreas`, `useProfessionals`, `useAvailabilityRules`.

---

## 7. Convenções a respeitar

- **Logging**: `[traceId: {trace_id}] [unit_id: {unit_id}] ...` em todo handler/service que opere por unit. Sem unit_id (ASK_UNIT antes da seleção): só `[traceId]`.
- **Naming**:
  - Tabelas: `scheduler.units`, `scheduler.professionals_units`
  - Lambdas: `CreateUnit`, `GetUnit`, `ListUnits`, `UpdateUnit`, `DeleteUnit`, `CreateAppointmentByUnit`, etc. (PascalCase em interface.yml)
  - Handlers: `src.functions.unit.create.handler`, `src.functions.appointment.create_by_unit.handler`
  - Slug de unit: kebab-case, ASCII (`jardins`, `tatuape`, `default`)
  - Query keys TanStack: sempre incluem `unitId` quando aplicável: `['available-slots', clinicId, unitId, date, serviceId]`
- **Migrations**: `IF NOT EXISTS` / `IF EXISTS`; `DROP CONSTRAINT IF EXISTS` antes de novos índices; `ON CONFLICT DO NOTHING` em backfills.
- **Secrets**: nenhum novo neste PRD. `units.zapi_instance_id` é VARCHAR direto na tabela (mesmo padrão de `clinics`).
- **Auth**: `x-api-key` continua único path; `clinic_users.unit_id` nullable, mas Fase 0/1/2 não exigem unit-scoped roles (ver futuro).
- **Backward compat (Fase 2)**: handlers antigos retornam dados da unit default + header `X-Multi-Unit: true` quando `clinic.units_count > 1`. Header documenta a deprecação.
- **Cutover (Fase 3)**: handlers antigos retornam HTTP 400 + `{"error":"MIGRATION_REQUIRED"}` para clinics multi-unit operacionais; aliases agregados (leads, patients, discount_rules) continuam funcionando sem header.
- **Cross-unit leak prevention**: todo SQL em service novo passa `unit_id` no WHERE; PR review obrigatório quando tocar em `*_service.py` checa explicitamente esse ponto. `test_no_cross_unit_leak.py` valida automaticamente.
- **Frontend states**: 4 estados (loading/error/empty/success) em todos os componentes que carregam dados, conforme `frontend/CLAUDE.md`.
