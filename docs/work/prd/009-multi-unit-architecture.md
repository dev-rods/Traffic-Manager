# PRD — 009 Multi-unit architecture

> Gerado na fase **Research**. Use como input para a fase Spec.
>
> **Bloqueia:** PRD 010 — Lovable integration.

---

## 1. Objetivo

Refatorar o Scheduler para suportar **clínica multi-unidade**, onde uma `clinic` (tenant raiz, ownership/auth/billing) tem **N `units`** (estabelecimentos físicos) e cada unit pode ter sua própria agenda, lista de profissionais, preços e — opcionalmente — número de WhatsApp/instância z-api. Catálogo (services/areas) e templates (faq/messages) seguem padrão **clinic-default + unit-override**: a clínica define o padrão e cada unit pode sobrescrever entradas individuais. Patients e leads continuam clinic-wide.

A solução deve ser implementada de forma **faseada e idempotente**, sem downtime, com backward-compat dos endpoints existentes durante a transição. Ao final, todo dado operacional (appointments, availability_*, etc) é particionado por `unit_id`.

---

## 2. Contexto

- Hoje o sistema modela `1 clinica = 1 unidade física`. Toda entidade operacional (`appointments`, `availability_rules`, `services`, `areas`, `service_areas`, `professionals`, `faq_items`, `message_templates`) é qualificada apenas por `clinic_id`. WhatsApp/z-api é 1 instância por clínica (`clinics.zapi_instance_id`).
- A Nobre Laser tem **2 unidades reais** (Jardins + Tatuapé) operando hoje sob 1 único `clinic_id`. A diferenciação aparece informalmente no formulário do site Lovable mas não chega como FK ao banco.
- O PO definiu que a unidade é a fronteira natural de operação:
  - Cada unidade tem agenda própria (espaço físico, equipamentos, profissionais).
  - Cada unidade pode ter preços diferentes (custo de aluguel/operação varia por bairro).
  - **Hoje** Nobre Laser usa 1 número WhatsApp para as 2 unidades; **no futuro** pode separar. A arquitetura precisa estar pronta para os dois cenários sem refator.
  - Catálogo (services/areas) costuma ser igual entre unidades, mas precisa permitir override pontual (ex: unidade Jardins oferece um serviço extra que Tatuapé não tem).
- Outras entidades (patients, leads, discount_rules) permanecem clinic-wide — paciente ou lead são da marca, não da unidade.

---

## 3. Escopo

### Dentro do escopo

**Modelo de dados (schema PostgreSQL)**
- Nova tabela `scheduler.units` (id UUID, clinic_id FK, name, slug, address, timezone, business_hours JSONB, buffer_minutes, zapi_instance_id NULL, max_future_dates, active, created_at, updated_at).
- Coluna `unit_id` (nullable durante migração, NOT NULL após cleanup) em:
  - `appointments` ✅ obrigatório por unit
  - `availability_rules` ✅ obrigatório por unit
  - `availability_exceptions` ✅ obrigatório por unit
- Coluna `unit_id` **nullable** (NULL = clinic-default) em:
  - `services` (clinic-default + unit-override)
  - `areas` (clinic-default + unit-override)
  - `service_areas` (price_cents per unit override)
  - `faq_items` (clinic-default + unit-override)
  - `message_templates` (clinic-default + unit-override)
- Nova tabela junction `scheduler.professionals_units` (professional_id, unit_id, active) — profissional pode atuar em N unidades (M2M).
- `clinic_users.unit_id` (nullable) — futuro role "operadora unit-scoped"; quando NULL = acesso clinic-wide.
- `discount_rules` permanece clinic-wide (sem mudança).
- `patients`, `leads` permanecem clinic-wide (sem mudança).
- Índices novos: ver seção 4.
- Constraints de unicidade ajustadas para suportar override: ver seção 5.

**Resolução de catálogo/templates (clinic-default + unit-override)**
- Lookup por unit retorna **união** de:
  - Linhas `unit_id = <u>` (override da unit), **OR**
  - Linhas `unit_id IS NULL` (default da clinic) **cuja chave funcional não tem override** na unit.
- Chave funcional por entidade:
  - `services`: `(clinic_id, name)`
  - `areas`: `(clinic_id, name)`
  - `service_areas`: `(service_id, area_id)` — override de preço/duração
  - `faq_items`: `(clinic_id, intent_key)` ou `(clinic_id, question)` se não houver intent
  - `message_templates`: `(clinic_id, template_key)`
- Resolução implementada em **service layer** (não em SQL view) para clareza e testabilidade. View materializada pode entrar v2 se virar gargalo.

**API surface**
- Novos endpoints (path-based):
  - `POST /clinics/{clinicId}/units` — criar unit
  - `GET /clinics/{clinicId}/units` — listar units da clinic
  - `GET /clinics/{clinicId}/units/{unitId}` — obter unit
  - `PUT /clinics/{clinicId}/units/{unitId}` — atualizar
  - `DELETE /clinics/{clinicId}/units/{unitId}` — soft delete (`active=false`)
  - `GET /clinics/{clinicId}/units/{unitId}/services` — catálogo resolvido (clinic + unit overrides)
  - `GET /clinics/{clinicId}/units/{unitId}/services/{serviceId}/areas`
  - `POST /clinics/{clinicId}/units/{unitId}/availability-rules`
  - `GET /clinics/{clinicId}/units/{unitId}/availability-rules`
  - `POST /clinics/{clinicId}/units/{unitId}/availability-exceptions`
  - `GET /clinics/{clinicId}/units/{unitId}/available-slots?date=&serviceId=`
  - `POST /clinics/{clinicId}/units/{unitId}/appointments`
  - `GET /clinics/{clinicId}/units/{unitId}/appointments`
  - `PUT /appointments/{appointmentId}` — continua via path simples (id global; unit_id imutável após criação)
  - `POST /clinics/{clinicId}/units/{unitId}/professionals` (e GET/PUT/DELETE)
- Endpoints clinic-level mantidos para **leitura agregada e backward compat**:
  - `GET /clinics/{clinicId}/services` — retorna **somente clinic-default rows** (sem overrides) com header `X-Multi-Unit: true` quando a clinic tem 2+ units.
  - `GET /clinics/{clinicId}/leads` — sem mudança (lead é clinic-wide).
  - `GET /clinics/{clinicId}/patients` — sem mudança.
  - `GET /clinics/{clinicId}/discount-rules` — sem mudança.
  - `GET /clinics/{clinicId}/appointments` — passa a aceitar `?unitId=<u>` (sem o filtro retorna agregado de todas as units).
  - Demais endpoints operacionais antigos (availability-rules, available-slots, appointment create/update no path antigo) ganham resposta `400` com `X-Migration-Required` quando chamados em clinic multi-unit, **a partir da fase 3** (após cutover).

**Conversação WhatsApp / z-api routing (cenário híbrido)**
- Webhook handler determina a unit ao receber mensagem:
  1. Lookup `units WHERE zapi_instance_id = <event.instance_id>`. Se única → `unit_id` da sessão definido.
  2. Senão, lookup `clinics WHERE zapi_instance_id = <event.instance_id>` → `clinic_id` da sessão. **Unit ainda indefinida.**
- Novo estado na máquina de conversação: `ASK_UNIT` (entre `WELCOME` e `MAIN_MENU`).
  - Disparado quando `clinic_id` está definido mas `unit_id` está vazio na sessão **e** a clinic tem 2+ units ativas.
  - Bot lista as units (com `name` + `address` curto) e pede seleção via fuzzy match (intent_classifier).
  - Resposta é gravada em `ConversationSessions.context.unit_id` e persiste pela conversa.
  - Skipped se a clinic tem 1 unit ativa (auto-seleciona).
- Todas as etapas downstream (`SELECT_SERVICES`, `AVAILABLE_DAYS`, `SELECT_DATE`) passam `unit_id` da sessão para o `AvailabilityEngine` e `AppointmentService`.
- Se z-api instance é **per unit** (cenário A futuro), `ASK_UNIT` nunca é disparada (passo 1 já resolveu).

**Availability engine + Appointment service**
- `AvailabilityEngine.get_available_slots(unit_id, date, service_id)` — assinatura nova requer unit_id.
- Wrapper deprecated `AvailabilityEngine.get_available_slots_legacy(clinic_id, ...)` resolve para a unit default da clinic (durante transição).
- `AppointmentService.create_appointment(unit_id, ...)` — exige unit_id. Conflict check passa a ser por `(unit_id, appointment_date)` em vez de `(clinic_id, appointment_date)`.
- `LeadService.upsert_lead(clinic_id, ...)` — sem mudança (lead é clinic-wide). `LeadService.mark_as_booked(lead_id, appointment_id)` — sem mudança.

**Painel React (`Traffic-Manager/frontend`)**
- Novo `UnitContext` (similar ao `AuthContext`): `{ currentUnit, setCurrentUnit, unitsList }`. Persiste em `localStorage` (`tm_current_unit_id`).
- Topbar do `AppLayout`: dropdown de seleção de unit. Sempre visível, sempre obrigatório (não há "todas as unidades" — uma única unit ativa por vez).
- No primeiro login após migração, auto-seleciona a unit default da clinic. Se a clinic tem 1 unit ativa, dropdown vira badge readonly.
- Todas as queries TanStack passam a usar `currentUnit.id`. Mudança de unit invalida cache (`queryClient.invalidateQueries()`).
- Páginas afetadas: Agenda, Pacientes, Relatórios, Configurações > Serviços, Configurações > Áreas, Configurações > Disponibilidade, Configurações > Profissionais.
- Nova página `Configurações > Unidades` — CRUD de units.
- Nova página `Configurações > Catálogo` (refator de Serviços) — toggle "Visualizar: clinic-default | Override desta unidade". Quando overrides existem, badge "Customizado" no item.

**Migração (4 fases idempotentes)**

**Fase 0 — Schema only (no behavior change)**
- Migrations criam tabelas/colunas; tudo nullable; nenhum código novo lê/escreve nas colunas novas.
- Pode rodar em produção sem risco.

**Fase 1 — Backfill data (one-time, idempotent)**
- Script `scheduler/src/scripts/backfill_multi_unit.py`:
  - Para cada clinic existente, cria 1 unit `default` com `name = clinic.name`, `slug = 'default'`, `address = clinic.address` (se houver), `timezone = clinic.timezone`, `business_hours = clinic.business_hours`, `zapi_instance_id = NULL` (clinic mantém o instance_id por enquanto, fallback no webhook).
  - Backfill de `unit_id` em `appointments`, `availability_rules`, `availability_exceptions` apontando para a unit default. **`services`, `areas`, `service_areas`, `faq_items`, `message_templates` ficam com `unit_id = NULL`** (são "clinic-default", o modelo previsto).
  - Backfill de `professionals_units` (linha por professional ↔ unit default).
- **Caso especial Nobre Laser**: o script tem um override para criar 2 units (Jardins, Tatuapé) em vez de 1 default, e atualiza `appointments` existentes (se houver) baseado em algum critério de heurística (ou todos para Jardins se não houver dado). Detalhes dessa heurística na SPEC.
- Idempotência: usar UPSERT por `(clinic_id, slug)`. Re-execuções não duplicam.

**Fase 2 — New endpoints + dual-read (parallel paths)**
- Novos endpoints `/clinics/{c}/units/{u}/...` ativos.
- Endpoints antigos `/clinics/{c}/...` continuam, resolvem internamente para a unit default.
- Painel migra para usar novos endpoints (lê `currentUnit.id`).
- Webhook z-api passa a resolver unit (por instance_id ou ASK_UNIT).
- Lovable site (PRD 010) pode começar a desenvolver, sem impacto em prod.

**Fase 3 — Cutover + cleanup**
- `unit_id` vira `NOT NULL` em `appointments`, `availability_rules`, `availability_exceptions` (já está populado, é só constraint).
- Endpoints antigos operacionais retornam `400 X-Migration-Required` para clinics multi-unit.
- Endpoints de leitura agregada continuam funcionando.
- Documentação atualizada.

### Fora do escopo (futuro)

- Per-unit billing/cobrança.
- Per-unit Google Ads (campaigns no `infra/` continuam clinic-wide).
- Transferência de pacientes entre units (paciente é clinic-wide, não há transferência).
- Cross-unit calendar view ("ver agenda de todas as units sobreposta") no painel — v2.
- Cross-clinic users (usuário de uma corporate ver várias clinics) — v3.
- Per-unit GCLID tracking (lead continua clinic-wide).
- Migração reversa (de multi-unit volta para single-unit) — não suportada.

---

## 4. Áreas / arquivos impactados

### Backend (`scheduler/`)

**Schema/Migrations**

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/scripts/setup_database.py` | modificar | Adicionar `units` table + `professionals_units` junction + `unit_id` columns + índices + constraints. Atualizar `TABLES` list e `MIGRATIONS` list (todas idempotentes) |
| `scheduler/src/scripts/backfill_multi_unit.py` | criar | Script one-time para criar default units + backfill `unit_id`. Caso especial Nobre Laser hardcoded |

**Services**

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/services/unit_service.py` | criar | CRUD de units (create/get/list/update/soft-delete), validações (clinic exists, slug unique within clinic) |
| `scheduler/src/services/availability_engine.py` | modificar | Assinatura nova (`unit_id` required); legacy wrapper para clinic-default |
| `scheduler/src/services/appointment_service.py` | modificar | `create_appointment(unit_id, ...)` requer unit_id; conflict check por unit; `metadata` continua suportado |
| `scheduler/src/services/conversation_engine.py` | modificar | Novo estado `ASK_UNIT`; lookup de unit por instance_id; persistir `unit_id` em session.context |
| `scheduler/src/services/intent_classifier.py` | modificar | Novo intent `select_unit` (fuzzy match dos nomes das units) |
| `scheduler/src/services/catalog_resolver.py` | criar | Resolução clinic-default + unit-override para services/areas/service_areas |
| `scheduler/src/services/template_resolver.py` | criar | Resolução clinic-default + unit-override para faq/templates |
| `scheduler/src/services/professional_service.py` | modificar | M2M com units via `professionals_units`; CRUD com lista de unit_ids |

**Functions (Lambda handlers)**

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/src/functions/unit/create.py` | criar | `POST /clinics/{c}/units` |
| `scheduler/src/functions/unit/get.py` | criar | `GET /clinics/{c}/units/{u}` |
| `scheduler/src/functions/unit/list.py` | criar | `GET /clinics/{c}/units` |
| `scheduler/src/functions/unit/update.py` | criar | `PUT /clinics/{c}/units/{u}` |
| `scheduler/src/functions/unit/delete.py` | criar | `DELETE /clinics/{c}/units/{u}` (soft) |
| `scheduler/src/functions/availability/list_rules_by_unit.py` | criar | `GET /clinics/{c}/units/{u}/availability-rules` |
| `scheduler/src/functions/availability/create_rule_by_unit.py` | criar | `POST /clinics/{c}/units/{u}/availability-rules` |
| `scheduler/src/functions/availability/get_slots_by_unit.py` | criar | `GET /clinics/{c}/units/{u}/available-slots` |
| `scheduler/src/functions/appointment/create_by_unit.py` | criar | `POST /clinics/{c}/units/{u}/appointments` |
| `scheduler/src/functions/appointment/list_by_unit.py` | criar | `GET /clinics/{c}/units/{u}/appointments` |
| `scheduler/src/functions/service/list_by_unit.py` | criar | `GET /clinics/{c}/units/{u}/services` (resolvido) |
| `scheduler/src/functions/service/list_areas_by_unit.py` | criar | `GET /clinics/{c}/units/{u}/services/{s}/areas` (resolvido) |
| `scheduler/src/functions/professional/*_by_unit.py` | criar | CRUD professionals com unit M2M |
| `scheduler/src/functions/webhook/handler.py` | modificar | Resolver unit por instance_id; flow `ASK_UNIT` quando ambíguo |
| Demais handlers operacionais antigos | modificar | Adicionar warning header `X-Multi-Unit: true` quando aplicável; em fase 3, reject para clinics multi-unit com 400 + `X-Migration-Required` |

**Serverless interface**

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/sls/functions/units.yml` | criar | Interface das 5 functions de unit |
| `scheduler/sls/functions/availability-by-unit.yml` | criar | Interface das functions per-unit de availability |
| `scheduler/sls/functions/appointments-by-unit.yml` | criar | Idem para appointments |
| `scheduler/sls/functions/services-by-unit.yml` | criar | Idem para services |
| `scheduler/sls/functions/professionals-by-unit.yml` | criar | Idem para professionals |
| `scheduler/serverless.yml` | modificar | Importar novos arquivos em `functions:` |

### Frontend painel (`Traffic-Manager/frontend/`)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `frontend/src/store/UnitContext.tsx` | criar | Provider com `currentUnit`, `setCurrentUnit`, `unitsList`. Persiste em localStorage |
| `frontend/src/hooks/useUnit.ts` | criar | Hook para consumir o context |
| `frontend/src/services/unit.ts` | criar | HTTP layer para CRUD de units |
| `frontend/src/components/UnitSelector.tsx` | criar | Dropdown na topbar; readonly badge se 1 unit |
| `frontend/src/layouts/AppLayout.tsx` | modificar | Inclui `UnitSelector` na topbar |
| `frontend/src/types/unit.ts` | criar | Tipos TypeScript |
| `frontend/src/hooks/useAvailableSlots.ts` | modificar | Aceita `unitId`, query key inclui unitId |
| `frontend/src/hooks/useAppointments.ts` | modificar | Idem |
| `frontend/src/hooks/useServices.ts` | modificar | Idem; lê de endpoint per-unit (resolvido) |
| `frontend/src/pages/configuracoes/Unidades.tsx` | criar | Página CRUD de units |
| `frontend/src/pages/configuracoes/Catalogo.tsx` | modificar | Toggle "clinic-default vs unit-override"; badges "Customizado" |
| `frontend/src/pages/agenda/Agenda.tsx` | modificar | Filtra por currentUnit |
| `frontend/src/pages/pacientes/*.tsx` | modificar (pequeno) | Adicionar coluna "Unidade" no histórico de appointments do paciente |
| `frontend/src/App.tsx` | modificar | Wrap com `UnitProvider` |
| `frontend/src/router.tsx` | modificar | Rota nova `/configuracoes/unidades` |

### Tests / docs

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/tests/mocks/units/*.json` | criar | Payloads CRUD |
| `scheduler/tests/mocks/multi_unit_*.json` | criar | Cenários multi-unit (catálogo resolvido, ASK_UNIT no webhook) |
| `scheduler/tests/integration/multi-unit.md` | criar | Casos de teste integrados |
| `scheduler/tests/postman/multi-unit.postman_requests.json` | criar | Coleção Postman |

---

## 5. Schema detalhado (referência)

### `scheduler.units`

```sql
CREATE TABLE scheduler.units (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) NOT NULL,
    address TEXT,
    timezone VARCHAR(50) NOT NULL DEFAULT 'America/Sao_Paulo',
    business_hours JSONB DEFAULT '{}',
    buffer_minutes INTEGER DEFAULT 0,
    zapi_instance_id VARCHAR(100),  -- NULL = usa o da clinic
    max_future_dates INTEGER DEFAULT 5,
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(clinic_id, slug)
);

CREATE INDEX idx_units_clinic ON scheduler.units(clinic_id) WHERE active = TRUE;
CREATE INDEX idx_units_zapi ON scheduler.units(zapi_instance_id) WHERE zapi_instance_id IS NOT NULL;
```

### `scheduler.professionals_units`

```sql
CREATE TABLE scheduler.professionals_units (
    professional_id UUID NOT NULL REFERENCES scheduler.professionals(id) ON DELETE CASCADE,
    unit_id UUID NOT NULL REFERENCES scheduler.units(id) ON DELETE CASCADE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (professional_id, unit_id)
);

CREATE INDEX idx_prof_units_unit ON scheduler.professionals_units(unit_id) WHERE active = TRUE;
```

### Colunas `unit_id` adicionadas

```sql
-- Operacionais (NOT NULL após Fase 3)
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
ALTER TABLE scheduler.availability_rules ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
ALTER TABLE scheduler.availability_exceptions ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);

-- Catálogo / templates (sempre nullable; NULL = clinic-default)
ALTER TABLE scheduler.services ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
ALTER TABLE scheduler.areas ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
ALTER TABLE scheduler.service_areas ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
ALTER TABLE scheduler.faq_items ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
ALTER TABLE scheduler.message_templates ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);

-- Auth
ALTER TABLE scheduler.clinic_users ADD COLUMN IF NOT EXISTS unit_id UUID REFERENCES scheduler.units(id);
```

### Constraints de unicidade ajustadas (override pattern)

`services` antes: `UNIQUE(clinic_id, name)` → conflita com override.

**Solução** (partial unique indexes):
```sql
-- Drop antigo se existir
ALTER TABLE scheduler.services DROP CONSTRAINT IF EXISTS services_clinic_id_name_key;

-- Default da clinic (1 row sem unit_id por nome)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_services_clinic_default
    ON scheduler.services(clinic_id, name) WHERE unit_id IS NULL;

-- Overrides por unit (1 row por unit por nome)
CREATE UNIQUE INDEX IF NOT EXISTS uniq_services_clinic_unit
    ON scheduler.services(clinic_id, unit_id, name) WHERE unit_id IS NOT NULL;
```

Padrão idêntico para `areas` (chave `name`), `service_areas` (chave `service_id, area_id`), `faq_items` (chave a definir), `message_templates` (chave `template_key`).

### Índices novos para queries por unit

```sql
CREATE INDEX IF NOT EXISTS idx_appointments_unit_date ON scheduler.appointments(unit_id, appointment_date);
CREATE INDEX IF NOT EXISTS idx_availability_rules_unit ON scheduler.availability_rules(unit_id);
CREATE INDEX IF NOT EXISTS idx_availability_exceptions_unit ON scheduler.availability_exceptions(unit_id, exception_date);
```

---

## 6. Resolução de catálogo (clinic-default + unit-override)

### Algoritmo

Para listar serviços resolvidos da unit `U` da clinic `C`:

```sql
WITH unit_services AS (
    SELECT * FROM scheduler.services
    WHERE clinic_id = :C AND unit_id = :U AND active = TRUE
),
clinic_defaults AS (
    SELECT * FROM scheduler.services
    WHERE clinic_id = :C AND unit_id IS NULL AND active = TRUE
      AND name NOT IN (SELECT name FROM unit_services)
)
SELECT * FROM unit_services
UNION ALL
SELECT * FROM clinic_defaults
ORDER BY name;
```

**Encapsulado em `CatalogResolver.list_services(clinic_id, unit_id)`** — não expor SQL para os handlers.

Padrão idêntico para `list_areas`, `list_service_areas`, `list_faq_items`, `list_message_templates`.

### Sobreescrita explícita (admin)

Pelo painel, ao editar um serviço/área:
- Toggle "Esta configuração se aplica a:"
  - "Toda a clínica (padrão)" → INSERT/UPDATE com `unit_id = NULL`
  - "Apenas esta unidade" → INSERT/UPDATE com `unit_id = <currentUnit.id>`
- Se editar um clinic-default a partir do contexto de uma unit: o painel pergunta "Aplicar mudança à clínica toda ou criar override só para esta unidade?".

### Preços (caso especial `service_areas`)

`service_areas` tem `price_cents` e `duration_minutes`. Override por unit pode ser parcial:

- Se `unit_id IS NULL`: default da clinic (`(service_id, area_id)`).
- Se `unit_id = U`: override (mesma `(service_id, area_id, U)`).

Resolução: prefere row da unit; se não houver, usa default. Implementado no `CatalogResolver`.

---

## 7. Conversação WhatsApp / z-api routing

### State machine — novo estado `ASK_UNIT`

```
            ┌──────────────┐
            │   WELCOME    │
            └──────┬───────┘
                   │
                   ▼
         ┌──────────────────┐
         │ Resolve unit by  │
         │   instance_id    │
         └──────┬───────────┘
                │
        ┌───────┴────────┐
        │                │
   1 unit found      0 units found
   (unit set)            │
        │                ▼
        │          ┌──────────────┐
        │          │   ASK_UNIT   │◄──────┐
        │          └──────┬───────┘       │
        │                 │ (intent: select_unit)
        │                 ▼               │
        │          ┌──────────────┐       │
        │          │ unit detected│───────┘ (re-prompt if fuzzy)
        │          └──────┬───────┘
        │                 │
        └────────┬────────┘
                 ▼
          ┌─────────────┐
          │  MAIN_MENU  │
          └─────────────┘
```

### Lookup de unit no webhook handler

```python
# Pseudo-code
def resolve_unit_or_clinic(instance_id: str) -> tuple[Optional[str], Optional[str]]:
    # 1. Try unit-level instance
    unit = db.query("SELECT id, clinic_id FROM scheduler.units WHERE zapi_instance_id = %s AND active", instance_id)
    if unit:
        return unit.clinic_id, unit.id

    # 2. Fallback to clinic-level instance
    clinic = db.query("SELECT clinic_id FROM scheduler.clinics WHERE zapi_instance_id = %s AND active", instance_id)
    if clinic:
        return clinic.clinic_id, None  # unit will be asked

    return None, None  # invalid instance
```

### `ASK_UNIT` flow

- Bot envia: `"Olá! 😊 A {clinic.name} atende em mais de uma unidade. Em qual delas você gostaria de agendar?\n\n1️⃣ {unit_1.name} — {unit_1.address}\n2️⃣ {unit_2.name} — {unit_2.address}"`
- User responde com número, nome, ou texto livre.
- `intent_classifier.classify_unit(message, units)` → fuzzy match.
- Se single match → grava `session.context.unit_id` e transita para `MAIN_MENU`.
- Se ambíguo → re-prompt com clarificação.
- Skip: se `clinic.units_count == 1`, auto-seleciona e pula para `MAIN_MENU`.

### Persistência

`ConversationSessions.context` (DynamoDB) ganha campo `unit_id` (string UUID). Vive 30 min (TTL existente). Re-perguntar caso sessão expire.

---

## 8. Painel React — UX detalhada

### Topbar

```
┌─────────────────────────────────────────────────────────────────┐
│  Logo  │   [Unidade ▼: Jardins]   │  Notif  Avatar  Logout      │
└─────────────────────────────────────────────────────────────────┘
                  ▲
                  │ Click → dropdown:
                  │   ✓ Jardins (Av. Paulista, 1234)
                  │     Tatuapé (R. Tuiuti, 567)
                  │     ─────────────────
                  │     + Adicionar unidade  →  /configuracoes/unidades
```

- Persiste em `localStorage`. Sobrevive a reload.
- Mudança dispara `queryClient.invalidateQueries()` → refetch de tudo na nova unit.
- Se 1 única unit → vira badge readonly: `[Unidade: Jardins]` (sem dropdown).
- Se 0 units (clinic recém-criada) → vai pra wizard de criação obrigatório (`/configuracoes/unidades?onboarding=true`).

### Página `Configurações > Unidades`

Lista de units (cards): nome, endereço, status (ativa/inativa), ações (editar, desativar).
Form de criação/edição: nome, slug (auto-gerado, editável), address, timezone, business_hours, buffer_minutes, zapi_instance_id (opcional).

### Página `Configurações > Catálogo` (refator)

Tabs: Serviços | Áreas | Preços
- Cabeçalho: "Visualizando catálogo da unidade **Jardins**"
- Toggle: `[● Resolvido (clinic + override)]  [Apenas overrides desta unidade]  [Apenas clinic-default]`
- Cada item tem badge: `[Padrão]` (vem da clinic) ou `[Customizado nesta unidade]`
- Ação "Editar" abre modal:
  - Campos
  - Toggle "Aplicar a:" `[● Toda a clínica]  [Apenas esta unidade]`
  - Se editar item `[Padrão]` mas marcar "Apenas esta unidade" → cria override sem alterar o default.
  - Se editar item `[Customizado]` mas marcar "Toda a clínica" → cria/atualiza default e remove override (com confirmação).

---

## 9. Migração — sequência de execução

```
┌─────────────────────────────────────────────────────────────┐
│                    FASE 0 — SCHEMA                          │
│  • setup_database.py com novas tabelas/colunas              │
│  • Deploy scheduler                                         │
│  • Validar via SELECT 1 (zero impacto runtime)              │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    FASE 1 — BACKFILL                        │
│  • Run backfill_multi_unit.py (one-shot, idempotente)       │
│  • Override Nobre Laser: cria 2 units (Jardins, Tatuapé)    │
│  • Validar: SELECT COUNT(*) WHERE unit_id IS NULL = 0       │
│             nas tabelas operacionais (apenas catálogo NULL) │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                FASE 2 — DUAL-READ + NEW PATHS               │
│  • Deploy novos endpoints /units/...                        │
│  • Deploy webhook handler com ASK_UNIT                      │
│  • Deploy painel com UnitSelector                           │
│  • Endpoints antigos continuam funcionando                  │
│  • Smoke test ambos caminhos em paralelo                    │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                  FASE 3 — CUTOVER + CLEANUP                 │
│  • ALTER ... SET NOT NULL nas FKs operacionais              │
│  • Endpoints antigos retornam 400 para clinics multi-unit   │
│  • Aliases agregados continuam pra leituras clinic-wide     │
│  • Documentação atualizada; KANBAN.md, TASKS_LOG.md         │
└─────────────────────────────────────────────────────────────┘
```

Cada fase é deploy independente; rollback é possível antes da Fase 3 (depois fica difícil pelo NOT NULL).

---

## 10. Dependências e riscos

### Dependências
- AWS RDS PostgreSQL (sem upgrade necessário; suporta partial indexes desde 9.0).
- DynamoDB `ConversationSessions` — payload do `context` cresce em ~36 bytes (UUID), sem mudança de capacidade.
- Painel React: `currentUnit` no context implica refator de hooks que hoje pegam `clinic_id` direto do AuthContext. Trabalho linear, não complexo.
- z-api: webhook payload já contém `instance_id` — sem dependência externa.

### Riscos
- **R1 — Backfill incorreto**: appointments existentes da Nobre Laser podem não ter info clara de qual unit (antigos não têm metadata.unit). **Mitigação**: backfill atribui tudo à unit Jardins (a "principal") e log detalhado para correção manual posterior. Documentar no `tests/integration/multi-unit.md`.
- **R2 — Quebra de painel durante Fase 2**: hooks que ainda não migraram chamam endpoints antigos que retornam dados de uma única unit (a default). **Mitigação**: testes de smoke por página antes de promover; feature flag por página se necessário.
- **R3 — Conversação WhatsApp em sessão ativa quando deploy**: usuários no meio de uma conversação. Se o session.context não tem `unit_id` e a clinic agora tem 2+ units, o handler precisa lidar com isso. **Mitigação**: handler resiliente — se faltar `unit_id` em qualquer estado, redireciona para `ASK_UNIT` antes de continuar (state recovery). Sessão TTL 30 min naturalmente limpa o problema.
- **R4 — Override órfão**: se admin deleta uma unit, overrides ficam órfãos (FK ON DELETE SET NULL). **Mitigação**: soft delete obrigatório (`active=false`); hard delete protegido com check de FKs.
- **R5 — Cache stale do painel**: `currentUnit` muda mas alguma query não invalida. **Mitigação**: query keys de TanStack Query incluem `unitId` por construção (não é refetch trigger; é query-key change).
- **R6 — Tempo de implementação**: PRD grande, ~5–7 dias de implementação contínua + testes. **Mitigação**: faseamento (cada fase é independente e deployable).
- **R7 — Esquecer de incluir `unit_id` em uma query nova durante o desenvolvimento**: introduz vazamento entre units. **Mitigação**: testes unitários `test_no_cross_unit_leak.py` que verifica todos os services retornam apenas dados da unit pedida; revisão obrigatória em PR para tocar em `.py` de service.

### Custos
- Storage: tabela `units` + `professionals_units` ~ KB. `unit_id` em outras = INT8 por linha. Total: irrelevante.
- Lambda: novos handlers cold-start. Com provisioned concurrency atual: zero impacto.
- Custos zero adicionais.

---

## 11. Critérios de aceite

### Funcionais — Schema e migração
- [ ] `setup_database.py` roda 2× sem erro, cria todas as estruturas novas (idempotente).
- [ ] Após Fase 1 backfill, `SELECT COUNT(*) FROM scheduler.appointments WHERE unit_id IS NULL` = 0 em qualquer clinic (operacionais).
- [ ] Catálogo (`services`, `areas`, `service_areas`, `faq_items`, `message_templates`) mantém `unit_id IS NULL` para registros existentes (clinic-default preservado).
- [ ] Nobre Laser tem 2 units (Jardins + Tatuapé) populadas e ativas após backfill.

### Funcionais — API
- [ ] `POST /clinics/{c}/units` cria unit; retorna 201 com payload completo.
- [ ] `GET /clinics/{c}/units/{u}/services` retorna catálogo resolvido (clinic-default + overrides da unit).
- [ ] Criar override de serviço com unit_id da unit específica não afeta outras units (testado com 2 units, 3 SELECTs).
- [ ] `POST /clinics/{c}/units/{u}/appointments` cria appointment com `unit_id` correto.
- [ ] Conflict check: 2 appointments no mesmo `(unit_id, date, time)` → segundo recebe 409. Mesmo `(date, time)` em units diferentes → ambos passam (não há conflito).
- [ ] `available-slots` por unit reflete apenas appointments e regras daquela unit.

### Funcionais — Conversação WhatsApp
- [ ] Webhook recebe mensagem com `instance_id` que pertence a uma `unit.zapi_instance_id` → unit detectada, `ASK_UNIT` é skipped.
- [ ] Webhook recebe mensagem com `instance_id` que pertence a `clinic.zapi_instance_id` (clinic com 2+ units) → fluxo passa por `ASK_UNIT`, lead seleciona, conversação continua.
- [ ] Em clinic com 1 única unit ativa, `ASK_UNIT` é auto-skipped mesmo sem unit-level instance.
- [ ] Sessão expirada (DynamoDB TTL) que perdeu `unit_id` → handler redireciona para `ASK_UNIT` e recupera.

### Funcionais — Painel
- [ ] Topbar exibe `UnitSelector`. Selecionar outra unit invalida cache TanStack e refetch das páginas.
- [ ] Reload mantém a unit selecionada (localStorage).
- [ ] Clinic com 1 unit → badge readonly (sem dropdown).
- [ ] Página `Configurações > Unidades` permite CRUD.
- [ ] Página `Configurações > Catálogo` exibe badges `[Padrão]`/`[Customizado]` e toggle de modo de visualização.
- [ ] Editar serviço com toggle "Apenas esta unidade" cria row `unit_id != NULL` sem alterar o default.

### Não-funcionais
- [ ] Testes unitários cobrem `CatalogResolver.list_services` para 4 casos: clinic sem overrides, clinic com 1 override, override inativo, default inativo.
- [ ] Test `test_no_cross_unit_leak.py` itera todos os services e valida zero leakage.
- [ ] Logs do conversation_engine incluem `[unit_id: ...]` em todas as transições.
- [ ] Migrations idempotentes (re-run safe).
- [ ] Postman collection cobre 100% dos novos endpoints.
- [ ] Documentação `tests/integration/multi-unit.md` com curl examples.

---

## 12. Decisões técnicas-chave

### 12.1. `unit_id` nullable em catálogo, NOT NULL em operacionais — por quê?
Catálogo (services/areas/templates) tem padrão "clinic-default + override por unit", então `NULL` significa "vale para todas as units da clinic". Operacionais (appointments, availability_rules) sempre pertencem a uma unit específica — não faz sentido um appointment "de toda a clinic". `NOT NULL` força integridade.

### 12.2. Por que partial unique indexes em vez de UNIQUE composto com NULL?
Postgres trata cada NULL como distinto em UNIQUE constraints — duas rows com `(name='X', unit_id=NULL)` passariam, gerando dois "clinic-defaults" do mesmo nome (bug). Partial indexes garantem unicidade em cada caso (default e override) sem ambiguidade.

### 12.3. Por que professionals com M2M (`professionals_units`) e não FK simples?
Realidade operacional: profissionais experientes podem rodar entre unidades (ex: cobertura, plantão). FK simples força duplicação. M2M com flag `active` por linha permite ativar/desativar profissional por unit independentemente. Custo: 1 join a mais nas queries — desprezível.

### 12.4. Por que clinic-level z-api continua funcionando?
Cenário atual da Nobre Laser e maioria das clinics. Migrar todas para per-unit instances de uma vez é trabalho operacional desnecessário. Quando uma clinic decidir separar números, é só popular `units.zapi_instance_id` e remover `clinics.zapi_instance_id` da clinic. Zero código novo.

### 12.5. Por que `discount_rules` clinic-wide (mesmo tendo aceitado bucket 2)?
Política comercial é da marca — desconto de 30% em primeira sessão é compromisso da Nobre Laser, não da unit Jardins isoladamente. Manter clinic-wide simplifica e é o que o PO confirmou. Se virar requisito futuro, criar tabela dedicada com override pattern (mas não vejo demanda).

### 12.6. Por que não criar uma `units` view consolidando clinic + unit info?
Tentação inicial. Mas: (a) FKs reais são mais limpas para integridade, (b) API responses ficam mais simples e cacheable, (c) admins entendem a hierarquia melhor com tabelas explícitas. View materializada pode entrar v2 se virar problema de performance.

### 12.7. Por que não migrar todos os clients para o novo path imediatamente?
Backward compat permite deploy incremental — painel migra primeiro, webhook depois, integração externa (Lovable PRD 010) por último. Cada qual em PR pequeno. Se quebrar algo, rollback de 1 component é fácil; rollback de tudo junto é caos.

---

## 13. Referências

- `Traffic-Manager/CLAUDE.md` — padrões do projeto.
- `scheduler/src/scripts/setup_database.py` — schema atual (~700 linhas).
- `scheduler/src/services/conversation_engine.py` — state machine.
- `scheduler/src/services/availability_engine.py` — engine de slots.
- PRD 010 (`010-lovable-integration.md`) — depende deste PRD.
- Postgres docs — partial indexes: https://www.postgresql.org/docs/current/indexes-partial.html
- TanStack Query — query keys com dependências: https://tanstack.com/query/latest/docs/framework/react/guides/query-keys

---

## Status (preencher após conclusão)

- [ ] Pendente
- [ ] Spec gerada: `spec/009-multi-unit-architecture.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
