# PRD — 010 Integração do site Lovable (Nobre Laser) com o Scheduler

> Gerado na fase **Research**. Use como input para a fase Spec.
>
> ⚠️ **Bloqueado por PRD 009 — Multi-unit architecture.** Esta task assume que clínica suporta múltiplas unidades com serviços/preços/agenda configuráveis por unidade. Após 009 ser implementada, reler este PRD e ajustar todas as referências de `clinic_id` para `unit_id` onde aplicável (catálogo, agenda, slot-holds, appointments, leads, endpoints de API).

---

## 1. Objetivo

Conectar o site público da Nobre Laser (https://nobrelaser.com.br, repo `rodsebaiano-bot/noble-laser-capture`, stack TanStack Start + Cloudflare Pages) ao backend do Scheduler (AWS Lambda + RDS PostgreSQL + DynamoDB) para que o site passe a:

1. Persistir **leads** capturados no banco (hoje só ficam em `sessionStorage`).
2. Exibir **preços de procedimentos/áreas** lidos em tempo quase-real do banco — sem hardcode no front.
3. Criar **agendamentos** diretamente no banco a partir do site (novo fluxo, hoje inexistente no site).
4. Mostrar **disponibilidade de horários em tempo quase-real** (SLA ≤ 5 s) tanto no site público quanto no painel da clínica, com mecanismo anti-double-booking robusto.

A solução deve ser ready-for-prod: rate limiting, anti-bot (Turnstile), idempotência, observabilidade, e migrações idempotentes.

---

## 2. Contexto

- O site Lovable tem **2 rotas** com forms:
  - `/` (`src/routes/index.tsx`): captura inicial com `name`, `email`, `whatsapp`. Hoje salva só em `sessionStorage` e redireciona para `/oferta`. Nada chega ao banco.
  - `/oferta` (`src/routes/oferta.tsx`): tabela de áreas com **catálogo inteiro hardcoded** no array `AREAS: Area[]` (`{ id: slug, name, price (BRL int), gender: 'Mulher'|'Homem', category: 'Rosto'|'Tronco'|'Membros'|'Íntima' }`). A renderização agrupa por `category` e filtra por `gender` selecionado no toggle "ATENDIMENTO". Form de booking com `name`, `whatsapp`, `gender`, `unit` (Jardins/Tatuapé), `date`, `time`. Submit atual **apenas monta uma mensagem e abre `wa.me`** — não grava lead nem agendamento. Há também um botão "Agendar pelo WhatsApp" como fallback explícito.
- **Schema atual de `scheduler.areas`** tem apenas `id (UUID)`, `clinic_id`, `name`, `display_order`, `active`. **Não tem `gender` nem `category`** — a taxonomia do site precisa ser refletida no banco para o front virar 100% data-driven (lista, labels, agrupamento, filtro por gender, ordenação — tudo vindo do banco, não só preço).
- O Scheduler já tem REST API completa protegida por `x-api-key` com endpoints para `services`, `service_areas`, `available-slots`, `appointments`, `leads` (com GCLID e tracking `booked`), `discount-rules`. CORS está habilitado.
- O Scheduler já tem **conflict detection com MVCC** em `AppointmentService.create_appointment()` (lê conflitos antes do INSERT).
- **Não existe infra de tempo real** (sem WebSockets, AppSync, EventBridge configurado pra esse fluxo). Hoje o painel da clínica usa TanStack Query sem polling.
- A Nobre Laser tem 2 unidades (Jardins + Tatuapé) e **o `/oferta` permite o lead escolher** entre elas. **Decisão**: tratar como 1 único `clinic_id` (`nobre-laser-sp-<suffix>`) e gravar a unidade escolhida em `appointments.metadata.unit` (`'jardins' | 'tatuape'`). Mesmo tratamento para `gender` (`appointments.metadata.attendance_type`: `'mulher' | 'homem'`). A operação usa esses metadados para distribuir o atendimento. Migration idempotente adiciona a coluna `metadata JSONB DEFAULT '{}'` em `scheduler.appointments` (ainda não existe — só `leads` tem).
- Stack do site: TanStack Start (server functions disponíveis) + TanStack Router + TanStack Query v5 + react-hook-form + zod + react-day-picker + shadcn/ui + Cloudflare Pages/Workers (wrangler).

---

## 3. Escopo

### Dentro do escopo

**Backend (scheduler/)**
- Nova tabela DynamoDB `SlotHolds` com TTL de 5 min para reserva temporária de horário.
- Novo endpoint `POST /clinics/{clinicId}/slot-holds` (cria hold com conditional write).
- Novo endpoint `DELETE /clinics/{clinicId}/slot-holds/{holdToken}` (libera hold).
- Modificação em `POST /appointments`: aceitar `holdToken` opcional; se presente, valida e consome o hold dentro de uma transação lógica (DB conflict-check + DynamoDB delete).
- Suporte a `Idempotency-Key` header em `POST /appointments` e `POST /leads` (DynamoDB `IdempotencyKeys` table, TTL 24 h).
- Validação de **Cloudflare Turnstile** em endpoints públicos (chamados via BFF do site): novo middleware `verify_turnstile.py` que consulta `https://challenges.cloudflare.com/turnstile/v0/siteverify`. Secret em SSM `/${stage}/TURNSTILE_SECRET_KEY`.
- Novo endpoint `POST /clinics/{clinicId}/leads/public`: cria lead com Turnstile + Idempotency-Key + `source='website'`. Reusa `LeadService.upsert_lead`. Aceita `metadata` no payload (gender, unit preference quando vier do `/oferta`, etc) gravado em `leads.metadata`.
- Modificação em `AppointmentService.create_appointment()`: aceitar parâmetro `metadata: dict` opcional, persistir em `appointments.metadata`. Após criar appointment, **sempre** chamar `LeadService.upsert_lead` (se ainda não existir pelo `phone`) e `LeadService.mark_as_booked(lead_id, appointment_id, final_price_cents)` na mesma transação lógica.
- Migrações idempotentes em `setup_database.py`:
  - Migration `M00W_add_appointments_metadata`: `ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'`. Atualizar também o `CREATE TABLE` em `TABLES`.
  - Migration `M00X_add_areas_metadata`: `ALTER TABLE scheduler.areas ADD COLUMN IF NOT EXISTS metadata JSONB NOT NULL DEFAULT '{}'`. Convenção do payload (validada na escrita pelo serviço): `{ "gender": "Mulher" | "Homem" | "Unissex", "category": "Rosto" | "Tronco" | "Membros" | "Íntima" | "<custom>" }`. Atualizar `CREATE TABLE`.
  - Migration `M00Y_idx_leads_source`: `CREATE INDEX IF NOT EXISTS idx_leads_source_created ON scheduler.leads(clinic_id, source, created_at DESC)`.
  - Migration `M00Z_idx_appointments_metadata_unit`: `CREATE INDEX IF NOT EXISTS idx_appointments_unit ON scheduler.appointments((metadata->>'unit'))`.
  - Migration `M010_idx_areas_metadata_gin`: `CREATE INDEX IF NOT EXISTS idx_areas_metadata ON scheduler.areas USING GIN (metadata)`.
- Endpoint `GET /clinics/{clinicId}/services/areas` (novo, agregado): retorna catálogo completo já joinado para o site público em **uma única chamada**:
  ```json
  {
    "services": [{ "id": "...", "name": "Depilação a Laser", "duration_minutes": 30 }],
    "areas": [
      {
        "id": "<uuid>",
        "name": "Buço",
        "display_order": 10,
        "active": true,
        "metadata": { "gender": "Mulher", "category": "Rosto" },
        "service_areas": [
          { "service_id": "<uuid>", "price_cents": 6500, "duration_minutes": 10, "pre_session_instructions": null }
        ]
      }
    ],
    "discount_rules": { "first_session_discount_pct": 30, "tier_2_min_areas": 2, "tier_2_discount_pct": 10, "tier_3_min_areas": 5, "tier_3_discount_pct": 20 }
  }
  ```
  Resposta `Cache-Control: public, max-age=60` para CDN. Endpoint **não precisa de `x-api-key`** (é leitura pública não-sensível) — autorização opcional para hardening posterior.
- Script de seed `scheduler/src/scripts/seed_nobre_laser_areas.py`: popula `services`, `areas` e `service_areas` da Nobre Laser a partir do catálogo atual hardcoded em `oferta.tsx`. Script idempotente (UPSERT por `(clinic_id, name)` em `areas`, `(clinic_id, name)` em `services`, `(service_id, area_id)` em `service_areas`). Mapeia `metadata = { gender, category }`. Define `display_order` por categoria e ordem de listagem do front (`Rosto` < `Tronco` < `Membros` < `Íntima`, com offset de 100 entre categorias). Serve também como fonte de verdade para futuras edições via painel admin.
- Eventos EventBridge publicados (mas sem subscriber neste PRD, prep para v2 SSE):
  - `appointment.created` `{ clinic_id, appointment_id, date, start_time, end_time }`
  - `appointment.cancelled` `{ clinic_id, appointment_id }`
  - `service.price_updated` `{ clinic_id, service_id }`
  - `slot.held` / `slot.released` `{ clinic_id, date, start_time }`

**Frontend Lovable (noble-laser-capture)**
- Server functions (TanStack Start `createServerFn`) que atuam como BFF:
  - `submitLead({ name, email?, whatsapp, metadata? }, turnstileToken)` — chama `POST /leads/public` com `x-api-key` server-side. Retorna `lead_id`.
  - `getCatalog()` — lê `GET /clinics/{id}/services/areas` (endpoint agregado). Retorna **catálogo completo** (services, areas com `metadata.gender` e `metadata.category`, `service_areas` com `price_cents` e `duration_minutes`, `discount_rules`). Resposta cacheada via Cloudflare Cache API (TTL 60 s, `stale-while-revalidate: 300`).
  - `getAvailableSlots({ date, serviceIds, areaIds })` — lê `GET /available-slots`.
  - `holdSlot({ date, time, serviceIds, areaIds })` — chama `POST /slot-holds`. Retorna `holdToken`, `expiresAt`.
  - `releaseSlot(holdToken)` — chama `DELETE /slot-holds/{holdToken}` (cancelamento explícito do usuário).
  - `confirmAppointment({ holdToken, lead, serviceAreaPairs, metadata, idempotencyKey }, turnstileToken)` — chama `POST /appointments`. Backend grava `appointments.metadata = { unit, attendance_type, source: 'website' }` e marca o lead como `booked`.
- Wire da `/` (`src/routes/index.tsx`):
  - `handleSubmit` chama `submitLead` server-side **antes** de redirecionar para `/oferta`. Lead gravado mesmo se usuário não completar o agendamento.
  - Lead `id` retornado é guardado no `sessionStorage` ("nobre_lead_id") junto com os campos atuais.
- Wire da `/oferta` (`src/routes/oferta.tsx`) — modificação cirúrgica:
  - **Eliminar completamente** os literais `AREAS`, `CATEGORIES`, `GENDERS`, `discountFor()` e qualquer label/preço hardcoded. O componente passa a se montar inteiro a partir do retorno de `getCatalog()` (TanStack Query, `staleTime: 60_000`):
    - **Lista de áreas**: `data.areas` filtradas por `metadata.gender === selectedGender || metadata.gender === 'Unissex'`.
    - **Agrupamento visual**: agrupar por `metadata.category` (categorias na ordem de primeira ocorrência no `display_order`); render do header de categoria usa o próprio valor de `metadata.category` como label (sem map estático).
    - **Ordenação dentro de categoria**: por `display_order` ASC.
    - **Label da área**: `area.name` (do banco).
    - **Preço exibido**: `service_areas[selectedServiceId].price_cents` formatado em BRL.
    - **`id` referenciado em estado interno**: o `Set<string> selected` passa a guardar UUIDs vindos do banco (não slugs `f-buco`). Sem fallback para slugs antigos.
    - **Toggle de gender** (Mulher/Homem) renderizado a partir dos valores distintos de `metadata.gender` no catálogo (se a clínica adicionar "Unissex" depois, o toggle reflete sem code change).
    - **Instruções pré-sessão** (se `service_areas.pre_session_instructions != null`): exibir tooltip/info ao lado da área.
    - **Regras de desconto**: `data.discount_rules` (não mais `discountFor()` hardcoded). Cálculo client-side é só preview UX; o backend recalcula no `confirmAppointment` e o valor final exibido na confirmação vem do response do appointment.
  - **Estados obrigatórios** (4 estados sempre): loading (skeleton da grid de áreas), error (mensagem + botão "Tentar novamente"), empty (catálogo retornou vazio: "Catálogo indisponível, fale conosco no WhatsApp" — botão fallback), success.
  - **Sem fallback estático**: se `getCatalog()` falhar, NÃO renderizar lista de áreas estática (evitar inconsistência de preço). Mostrar empty/error state e oferecer fluxo WhatsApp.
  - Substituir submit do botão "**Agendar com Desconto**":
    1. Validar campos via zod (já existente).
    2. Chamar `holdSlot` com data/hora/áreas escolhidas → recebe `holdToken`.
    3. Se a `/` não foi visitada (lead vem direto), chamar `submitLead` agora.
    4. Mostrar Turnstile invisible challenge.
    5. Chamar `confirmAppointment` com `holdToken`, `metadata.unit`, `metadata.attendance_type`, `idempotencyKey` (UUID gerado no mount do form).
    6. Em sucesso, navegar para tela de confirmação (nova: `/agendamento-confirmado/:appointmentId`) ou modal in-page.
    7. Em erro `409 SLOT_TAKEN`, exibir toast e re-fetch slots.
  - Manter botão "**Agendar pelo WhatsApp**" como fallback explícito, **mas agora chamando `submitLead`** com `metadata.fallback='whatsapp'` antes de abrir `wa.me`. Lead nunca se perde.
  - Adicionar grade de slots disponíveis no campo `time` (substituir input `type="time"` por dropdown/grid populado por `getAvailableSlots`, com `refetchInterval: 10_000`).
- Integração do Turnstile widget invisible em todos os forms públicos (`/` e `/oferta`).
- Variáveis de ambiente Cloudflare (via `wrangler secret`):
  - Server-only: `SCHEDULER_API_BASE_URL`, `SCHEDULER_API_KEY`, `SCHEDULER_CLINIC_ID`, `TURNSTILE_SECRET_KEY`.
  - Públicas (em `wrangler.jsonc` `vars`): `VITE_TURNSTILE_SITE_KEY`.

**Painel da clínica (Traffic-Manager/frontend)**
- Habilitar `refetchInterval: 10000` no hook de listagem de slots/agenda (`hooks/useAppointments.ts`, `useAvailableSlots.ts`).
- Banner visual de "atualizado há Xs" no header da agenda.

**Operação / DevOps**
- SSM params novos no `serverless.yml`: `TURNSTILE_SECRET_KEY`.
- IAM permissions para EventBridge `PutEvents` no novo bus `scheduler-${stage}-events`.
- CloudWatch alarms: 4xx > 5%/5min em `/leads/public` e `/slot-holds` (sinal de bot/abuso).

### Fora do escopo (v2)

- SSE/WebSocket para sub-second push (a infra de eventos já fica plantada nesse PRD, basta um Lambda subscriber depois).
- Pagamento online no agendamento.
- Multi-unidade no formulário do site (lead escolher Jardins vs Tatuapé).
- Sincronização reversa Postgres → Lovable static export (não aplicável — site lê via API).
- Mudança de provider Lovable → outra plataforma.
- Migração de dados históricos (não há leads antigos no site).

---

## 4. Áreas / arquivos impactados

### Backend (`scheduler/`)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `scheduler/sls/resources/slot-holds-table.yml` | criar | Tabela DynamoDB `SlotHolds` (pk `clinicSlot`, TTL `expiresAt`) |
| `scheduler/sls/resources/idempotency-keys-table.yml` | criar | Tabela DynamoDB `IdempotencyKeys` (pk `key`, TTL 24 h) |
| `scheduler/sls/resources/event-bus.yml` | criar | EventBridge custom bus `scheduler-${stage}-events` |
| `scheduler/sls/functions/slot-holds.yml` | criar | Interface das 2 functions (Create/Delete SlotHold) |
| `scheduler/sls/functions/leads-public.yml` | criar | Interface da function pública de leads |
| `scheduler/serverless.yml` | modificar | Importar resources, IAM EventBridge, SSM `TURNSTILE_SECRET_KEY` |
| `scheduler/src/services/slot_hold_service.py` | criar | `create_hold`, `release_hold`, `consume_hold` (conditional writes) |
| `scheduler/src/services/idempotency_service.py` | criar | `check_or_create(key, response)` |
| `scheduler/src/services/event_publisher.py` | criar | Wrapper EventBridge `PutEvents` com fallback log |
| `scheduler/src/utils/verify_turnstile.py` | criar | HTTP POST a Cloudflare siteverify; cache do secret |
| `scheduler/src/functions/slot_hold/create.py` | criar | Handler `POST /slot-holds` |
| `scheduler/src/functions/slot_hold/delete.py` | criar | Handler `DELETE /slot-holds/{holdToken}` |
| `scheduler/src/functions/lead/create_public.py` | criar | Handler `POST /leads/public` (Turnstile + idempotency) |
| `scheduler/src/functions/service/get_catalog_public.py` | criar | Handler `GET /clinics/{clinicId}/services/areas` (agregado público; sem `x-api-key`; `Cache-Control` 60s) |
| `scheduler/sls/functions/services-public.yml` | criar | Interface da function pública de catálogo |
| `scheduler/src/scripts/seed_nobre_laser_areas.py` | criar | Seed idempotente: services, areas (com `metadata.gender`/`category`), service_areas, discount_rules da Nobre Laser |
| `scheduler/src/services/appointment_service.py` | modificar | Aceitar `hold_token` + `metadata` opcionais, consumir hold, **upsert lead + mark_as_booked** na mesma operação, publicar event |
| `scheduler/src/services/lead_service.py` | modificar | Garantir `upsert_lead` aceita `metadata` arbitrário e merge não-destrutivo (preservar GCLID anterior) |
| `scheduler/src/functions/appointment/create.py` | modificar | Pass-through `hold_token`, `metadata`, `Idempotency-Key` |
| `scheduler/src/scripts/setup_database.py` | modificar | Migrations idempotentes: `appointments.metadata JSONB`, `idx_leads_source_created`, `idx_appointments_unit`. Atualizar também o `CREATE TABLE` em `TABLES`. |
| `scheduler/tests/mocks/slot_holds/*.json` | criar | Payloads de teste |
| `scheduler/tests/mocks/leads/public_create.json` | criar | Payload de teste |
| `scheduler/tests/integration/lovable-integration.md` | criar | Casos de teste integrados |
| `scheduler/tests/postman/lovable-integration.postman_requests.json` | criar | Coleção Postman |

### Frontend Lovable (`noble-laser-capture/` — repo separado)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `src/server/scheduler-client.ts` | criar | Cliente HTTP server-side (server functions only); injeta `x-api-key` |
| `src/server/turnstile.ts` | criar | Validação server-side de Turnstile token |
| `src/server/functions/leads.ts` | criar | `submitLead` server fn |
| `src/server/functions/services.ts` | criar | `getServices` server fn (com Cache API) |
| `src/server/functions/availability.ts` | criar | `getAvailableSlots`, `holdSlot`, `releaseSlot` |
| `src/server/functions/appointments.ts` | criar | `confirmAppointment` server fn |
| `src/components/turnstile.tsx` | criar | Widget Turnstile (carrega script, expõe `onVerify`) |
| `src/components/scheduling/SlotGrid.tsx` | criar | Grade de horários disponíveis (consome `getAvailableSlots` com refetchInterval 10s) |
| `src/components/scheduling/AreaPicker.tsx` | criar | Renderiza catálogo data-driven: filtra por `metadata.gender`, agrupa por `metadata.category`, ordena por `display_order`. Recebe `catalog` por prop, não tem dados embutidos. |
| `src/components/scheduling/CategorySection.tsx` | criar | Header + grid de áreas de uma categoria. Label = `metadata.category` puro do banco. |
| `src/components/scheduling/GenderToggle.tsx` | criar | Toggle dinâmico baseado nos valores distintos de `metadata.gender` no catálogo. |
| `src/components/EmptyCatalog.tsx` | criar | Empty/error state quando `getCatalog()` falha — CTA para WhatsApp. |
| `src/routes/__root.tsx` | modificar | Provider de TanStack Query (se ainda não houver) e Toaster |
| `src/routes/index.tsx` | modificar | `handleSubmit` chama `submitLead` server fn antes do redirect; persiste `lead_id` no sessionStorage |
| `src/routes/oferta.tsx` | modificar | Substituir `AREAS` hardcoded por `getServices`; substituir input `time` por `SlotGrid`; wirear submit "Agendar com Desconto" para `holdSlot` + `confirmAppointment`; "Agendar pelo WhatsApp" agora também chama `submitLead` antes de abrir `wa.me` |
| `src/routes/agendamento-confirmado.$appointmentId.tsx` | criar | Tela de confirmação pós-booking (lê GET appointment via server fn) |
| `src/lib/format.ts` | criar | Format BRL `price_cents` → "R$ 199,00", duração, datas pt-BR |
| `src/lib/idempotency.ts` | criar | `useIdempotencyKey()` hook (UUID estável durante a vida do form) |
| `wrangler.jsonc` | modificar | Adicionar `vars` públicas (`VITE_TURNSTILE_SITE_KEY`, `SCHEDULER_API_BASE_URL`, `SCHEDULER_CLINIC_ID`) |
| `.dev.vars` | criar | Template local com `SCHEDULER_API_KEY=...`, `TURNSTILE_SECRET_KEY=...` (gitignored) |
| `.env.example` | criar | Template de env vars (sem secrets) |

### Painel clínica (`Traffic-Manager/frontend/`)

| Caminho | Tipo | Descrição |
|---------|------|-----------|
| `frontend/src/hooks/useAvailableSlots.ts` | modificar | `refetchInterval: 10000` + `refetchOnWindowFocus` |
| `frontend/src/hooks/useAppointments.ts` | modificar | `refetchInterval: 10000` (apenas para visões "hoje" e "essa semana") |
| `frontend/src/components/agenda/StaleIndicator.tsx` | criar | Mostra "atualizado há Xs" |
| `frontend/src/pages/agenda/Agenda.tsx` | modificar | Inclui `StaleIndicator` no header |

---

## 5. Dependências e riscos

### Dependências
- **AWS**: nova tabela DynamoDB (custos: ~ centavos/mês no volume esperado), EventBridge custom bus (PutEvents free tier: 100k req/mês). IAM update.
- **Cloudflare**: conta Cloudflare na Nobre Laser (já existe — site Lovable usa Cloudflare Pages). Habilitar Turnstile (gratuito); criar widget e copiar `site-key` + `secret-key`.
- **SSM Parameter Store**: novo param `/{stage}/TURNSTILE_SECRET_KEY` (SecureString).
- **Wrangler secrets**: `wrangler secret put SCHEDULER_API_KEY`, idem `TURNSTILE_SECRET_KEY` no projeto Lovable.
- **clinic_id da Nobre Laser**: precisa existir no banco antes do deploy do site (criar via `POST /clinics` se ainda não existir; atualizar `business_hours`, `services`, `professionals`, `availability_rules`).

### Riscos
- **Bot spam em `/leads/public`** mesmo com Turnstile: mitigação por rate limit (API Gateway usage plan: 10 req/min por IP) + alarmes 4xx.
- **Race condition slot-hold ↔ appointment**: mitigado por conditional write no DynamoDB + conflict check no Postgres. Worst case: usuário recebe "slot indisponível, escolha outro".
- **Cache stale de preços**: 60 s de TTL no Cloudflare Cache API. Aceitável para preços (mudam raramente). Invalidação manual via `wrangler` se urgente.
- **TanStack Start em Cloudflare Workers**: server functions rodam no edge runtime (V8 isolates), não Node — `fetch` nativo OK, mas libs Node-specific podem quebrar. Dependências escolhidas (apenas `fetch`) são edge-safe.
- **Idempotency key colision**: TTL 24h é suficiente; chave gerada client-side com `crypto.randomUUID()`.
- **Lovable overwrites**: mudanças manuais no repo GitHub podem ser sobrescritas se alguém editar via UI Lovable depois. Mitigação: documentar e travar o repo Git como source of truth (ou aceitar trade-off e re-aplicar via prompt Lovable se necessário).
- **CORS**: as server functions chamam o backend de servidor pra servidor → não requer CORS no scheduler. Mas vale validar com `Origin` allowlist no API Gateway WAF para hardening.
- **Migrations**: nenhum DDL destrutivo. Apenas índice novo, idempotente.
- **Custos**: estimativa mensal incremental ~ US$ 0–5 (Lambda + DynamoDB + EventBridge no volume previsto).

---

## 6. Critérios de aceite

### Funcionais — Captura de Leads
- [ ] Submit em `/` grava registro em `scheduler.leads` com `source='website'`, `clinic_id` correto, e Turnstile validado server-side.
- [ ] Submit em `/oferta` (ambos os botões — "Agendar com Desconto" e "Agendar pelo WhatsApp") **sempre** grava/atualiza o lead, mesmo se o usuário desistir do agendamento depois. `metadata.fallback='whatsapp'` quando aplicável.
- [ ] Lead criado pelo `/` que depois completa booking em `/oferta` é o **mesmo registro** (upsert por `(clinic_id, phone)`); GCLID e `metadata` mergeados não-destrutivamente.
- [ ] Endpoint `/leads/public` recusa request sem Turnstile token (403) e duplicate (Idempotency-Key) retorna mesmo response sem criar duplicata.

### Funcionais — Catálogo data-driven
- [ ] Build do site **não contém** literais `AREAS`, `CATEGORIES`, `GENDERS`, `discountFor` (validar com `grep` no bundle de produção). Toda a lista é renderizada a partir de `getCatalog()`.
- [ ] Adicionar uma nova área no banco (via SQL, painel admin ou seed) e ela aparece em `/oferta` em até 60 s (TTL Cache API), com:
  - **label** = valor de `areas.name`
  - **categoria** definida por `metadata.category` (cria nova section se categoria nova)
  - **filtro de gender** respeitado (se `metadata.gender='Homem'`, área só aparece quando toggle "Homem" ativo; se `'Unissex'`, sempre)
  - **ordem** dada por `display_order`
  - **preço** formatado em BRL a partir de `service_areas.price_cents`
  - **instruções pré-sessão**, se preenchidas em `service_areas.pre_session_instructions`, exibidas como tooltip/info
- [ ] Editar preço de uma área no banco reflete em `/oferta` em até 60 s sem deploy.
- [ ] Renomear uma categoria no banco (`metadata.category`) altera o header da seção visual no site (sem code change).
- [ ] Seed `seed_nobre_laser_areas.py` roda 2× sem erro (idempotente) e popula 100% das áreas do `AREAS` original (validação por contagem + spot-check de 5 nomes).
- [ ] Estados de loading/error/empty/success todos implementados em `AreaPicker`. Loading mostra skeleton, error mostra retry, empty mostra CTA WhatsApp.
- [ ] Se `getCatalog()` falhar, **nada** de áreas estáticas é mostrado — apenas o empty/error state.

### Funcionais — Agendamento
- [ ] Botão "Agendar com Desconto" em `/oferta` cria registro em `scheduler.appointments` com `version=1`, `final_price_cents` calculado pelo backend (não confiar no client), `metadata.unit ∈ {'jardins','tatuape'}`, `metadata.attendance_type ∈ {'mulher','homem'}`, `metadata.source='website'`.
- [ ] Quando appointment é criado com sucesso, o lead correspondente tem `booked=true`, `first_appointment_id` e `first_appointment_value` preenchidos (`LeadService.mark_as_booked`). Tudo na mesma operação lógica.
- [ ] Campo `time` no `/oferta` exibe **apenas slots disponíveis** retornados por `GET /available-slots`, atualizando a cada 10 s.
- [ ] Slot escolhido é "segurado" por 5 min em DynamoDB `SlotHolds` antes da confirmação. Se 2 leads simultâneos pegarem o mesmo slot, o segundo recebe HTTP 409 e UI amigável reabre o seletor.
- [ ] Hold é liberado automaticamente após 5 min (TTL DynamoDB) ou explicitamente quando o usuário muda de horário (`releaseSlot`).
- [ ] Tela `/agendamento-confirmado/:id` mostra resumo (data, hora, áreas, total, unidade) e link para WhatsApp da clínica.

### Funcionais — Painel Clínica
- [ ] Painel da clínica mostra novo agendamento criado pelo site em até 10 s sem refresh manual.
- [ ] Coluna/badge na agenda mostra a unidade do appointment (`metadata.unit`) para a operação saber onde atender.

### Não-funcionais
- [ ] Latência P95 de `getAvailableSlots`: < 800 ms (com Cache API hit < 50 ms).
- [ ] `SCHEDULER_API_KEY` nunca aparece em bundle do front (validar com `wrangler dev` + DevTools Network).
- [ ] Migration de DB roda 2x sem erro (idempotência).
- [ ] Logs com `traceId` em todos os handlers novos (`logger.info(f"[traceId: {trace_id}] ...")`).
- [ ] Postman collection cobre 100% dos novos endpoints com casos: happy path, missing-Turnstile, duplicate-idempotency, expired-hold, conflict-hold.
- [ ] Documento `tests/integration/lovable-integration.md` com curl examples passando contra `dev`.

### Segurança
- [ ] Rate limit configurado em API Gateway: 10 req/min/IP em `/leads/public` e `/slot-holds`.
- [ ] CloudWatch alarm: > 5% 4xx em 5 min nesses endpoints.
- [ ] Turnstile secret nunca enviado ao client.
- [ ] CORS no scheduler mantém allowlist (sem `*` em produção).

---

## 7. Referências

- `Traffic-Manager/CLAUDE.md` — padrões do projeto (logging, naming, secrets, migrations).
- `scheduler/src/services/availability_engine.py` — engine de slots existente.
- `scheduler/src/services/appointment_service.py` — conflict detection MVCC.
- `scheduler/src/services/lead_service.py` — `upsert_lead` com GCLID.
- `scheduler/serverless.yml` — convenções de SSM, IAM, CORS.
- TanStack Start docs — `createServerFn` API.
- Cloudflare Turnstile — https://developers.cloudflare.com/turnstile/
- Cloudflare Cache API — `caches.default.put/match` em Workers.
- DynamoDB conditional writes — `ConditionExpression` + TTL.

---

## 8. Decisões técnicas-chave

### 8.1. Por que BFF (TanStack Start server functions) em vez de endpoints `/public/v1/...`?
- Mantém o `x-api-key` server-side; site nunca expõe credencial.
- Reusa endpoints existentes do Scheduler — menos código, menos surface de ataque.
- Cloudflare Workers (edge runtime) já está rodando; server fn é zero-overhead.
- Trade-off: BFF é responsabilidade do time do site; se houver outro consumer público no futuro, criamos `/public/v1/...` aí.

### 8.2. Por que polling 10 s em vez de SSE/WebSocket nesta versão?
- SLA pedido é **5 s**; polling 10 s + revalidate-on-action atende com folga (na pior hipótese, conflict é capturado no slot-hold).
- SSE adiciona Lambda streaming + EventBridge subscriber + reconexão — complexidade não justificada agora.
- EventBridge events **já serão publicados** nesta versão; v2 adiciona um único Lambda subscriber pra emitir SSE sem alterar o resto do código.

### 8.3. Por que slot-hold em DynamoDB e não pessimistic lock no Postgres?
- DynamoDB conditional write + TTL é zero-mantenimento (locks expiram sozinhos).
- Postgres advisory locks ou row locks acoplam o lock a uma transação aberta — não dá pra "segurar" pelo tempo do form do usuário.
- DynamoDB já é fonte de truth pra ConversationSessions (mesmo padrão TTL).

### 8.4. Idempotency-Key vs UUID natural
- Cliente (browser) gera `crypto.randomUUID()` ao montar o form. Mesmo lead pode dar duplo-clique sem criar duplicado.
- Servidor armazena `(key, response_body)` por 24 h. Re-tentativa devolve mesma resposta.

---

## 9. Persistência: leads × appointments × WhatsApp fallback

> Esta seção é a fonte de verdade do que é gravado, quando, e por qual caminho. **Lead nunca é perdido**, mesmo quando o usuário troca de fluxo.

### 9.1. Cenários e gravações esperadas

| # | Ação do usuário | `scheduler.leads` | `scheduler.appointments` | Observação |
|---|-----------------|-------------------|--------------------------|------------|
| 1 | Preenche form em `/` e clica "Quero Continuar" (sem ir adiante) | **CREATE/UPSERT** `source='website'`, `metadata.entry='hero_form'`, `booked=false` | — | Lead capturado mesmo se abandonar antes de `/oferta` |
| 2 | Preenche `/` e depois agenda com sucesso em `/oferta` | **MERGE** mesmo registro (upsert por `phone+clinic_id`); `booked=true`, `first_appointment_id`, `first_appointment_value` preenchidos | **CREATE** com `metadata={unit, attendance_type, source:'website'}` | Único lead, GCLID preservado |
| 3 | Vai direto para `/oferta` (ex: link compartilhado) e agenda | **CREATE/UPSERT** com `source='website'`, `metadata.entry='oferta_form'`, `booked=true` | **CREATE** | Mesmo registro de lead criado/atualizado dentro do `confirmAppointment` |
| 4 | Vai direto para `/oferta` e clica "Agendar pelo WhatsApp" | **CREATE/UPSERT** com `source='website'`, `metadata.fallback='whatsapp'`, `booked=false` | — | Lead gravado **antes** de abrir `wa.me` |
| 5 | Falha de rede / Turnstile no `confirmAppointment` (slot já indisponível, etc) | Mantém o que já foi criado em `submitLead` | — | Erro mostrado em toast, lead não se perde |
| 6 | Submit duplicado (duplo-clique, refresh) | **NO-OP** via `Idempotency-Key` no header | **NO-OP** mesma resposta retornada | Sem duplicatas |

### 9.2. Ordem garantida de operações em "Agendar com Desconto"

```
1. Cliente: gera idempotencyKey (UUID estável durante a vida do form)
2. Cliente: holdSlot(date, time, areas)              → backend: DynamoDB conditional write
3. Cliente: turnstile.execute() → token              → silent challenge
4. Cliente: confirmAppointment({ holdToken, idempotencyKey, lead, areas, metadata }, turnstileToken)
5. Backend: verify_turnstile(token)                  → siteverify Cloudflare
6. Backend: idempotency.check_or_create(key)         → DynamoDB
7. Backend: BEGIN (logical)
     a. consume_hold(holdToken)                       → DynamoDB conditional delete
     b. create_appointment(metadata, ...)             → Postgres INSERT (com conflict check)
     c. upsert_lead(phone, gclid, metadata)           → Postgres UPSERT
     d. mark_as_booked(lead_id, appointment_id, ...)  → Postgres UPDATE
     e. event_publisher.publish('appointment.created')→ EventBridge
   COMMIT
8. Backend: idempotency.store_response(key, body)
9. Cliente: navigate /agendamento-confirmado/:id
```

> "BEGIN/COMMIT lógico" = uma transação Postgres aberta no Lambda envolvendo 7b–7d. O hold (DynamoDB) é consumido **antes** do BEGIN — se INSERT falhar por conflito, o hold já está consumido, mas isso é aceitável (próximo retry vai falhar no slot-hold conditional write e cliente recebe 409 limpo). Eventos do EventBridge publicados após COMMIT.

### 9.3. Ordem em "Agendar pelo WhatsApp" (fallback)

```
1. Cliente: validar form
2. Cliente: turnstile.execute()
3. Cliente: submitLead(form, turnstileToken, metadata={fallback:'whatsapp', unit, attendance_type, areas})
4. Backend: cria/atualiza lead (booked=false)
5. Cliente: window.open(`https://wa.me/...?text=...`)
```

### 9.4. Onde fica cada metadado

| Metadado | Tabela | Campo |
|---------|--------|-------|
| Unidade escolhida (`jardins`/`tatuape`) | `appointments` | `metadata.unit` |
| Atendimento (`mulher`/`homem`) | `appointments` | `metadata.attendance_type` |
| Fonte do agendamento | `appointments` | `metadata.source` (`'website'`, `'whatsapp'`, `'admin'`) |
| Áreas escolhidas com preço efetivo | `appointment_service_areas` | linhas detalhadas (já existente) |
| Preferência de unidade do lead (sem booking) | `leads` | `metadata.preferred_unit` |
| Áreas de interesse do lead (sem booking) | `leads` | `metadata.interest_area_ids[]` |
| Origem da entrada no funil | `leads` | `metadata.entry` (`'hero_form'`, `'oferta_form'`) |
| Fallback WhatsApp | `leads` | `metadata.fallback='whatsapp'` |
| GCLID Google Ads | `leads` | `gclid` (coluna dedicada, não em metadata) |

### 9.5. Invariantes que precisam ser respeitadas

- Para todo `appointment` criado pelo site, **existe um `lead` correspondente** (mesmo `clinic_id` + `phone`) com `booked=true`.
- Para todo lead com `booked=true`, `first_appointment_id` é não-nulo e referencia um appointment ativo (`status='CONFIRMED'`).
- `appointments.metadata.unit` é não-nulo para appointments criados via `source='website'` (validar em handler).
- `Idempotency-Key`, se presente, garante que múltiplas chamadas iguais retornam a mesma resposta sem efeitos colaterais.

---

## Status (preencher após conclusão)

- [ ] Pendente
- [ ] Spec gerada: `spec/010-lovable-integration.md`
- [ ] Implementado em: (data)
- [ ] Registrado em `TASKS_LOG.md`
