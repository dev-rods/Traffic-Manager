# Plan: Appointment Modal Improvements + Discount Rules Page

## Context
The CreateAppointmentModal currently uses a raw `<input type="time">` for time selection (no awareness of availability), has no way to create a new patient inline, and there's no UI for clinic owners to manage their progressive discount rules. The backend already supports all three: slots endpoint, patient creation, and discount rules CRUD.

## Design Constraint
All new UI **must** follow the Impeccable design principles defined in `frontend/CLAUDE.md` "Design Principles (Impeccable)" section. Key rules for this plan:
- **4pt grid** spacing (8, 12, 16, 24, 32px)
- **60-30-10** color distribution — accent is rare and intentional
- Tinted neutrals, never pure black/white
- **Progressive disclosure** — simple first, advanced behind expandable
- **Empty states teach** — guide user to action, not just inform
- **No AI slop** — no gradient text, no identical card grids, no decorative glassmorphism
- Animation: 100-150ms for feedback, 200-300ms for state changes, ease-out curves
- Touch targets min 44px
- Button hierarchy: not everything is primary

---

## Feature 1: Available Time Slots Picker

**Problem:** Time input is free-form; user can pick any time even if the clinic isn't available.

**Approach:** When a date AND service are selected, fetch available slots from `GET /clinics/{clinicId}/available-slots?date=X&serviceId=Y` and render a grid of clickable time buttons instead of a raw input.

### Files to change:
- **`frontend/src/services/availability.service.ts`** — add `getSlots(clinicId, date, serviceId)` method
- **`frontend/src/hooks/useAvailabilityRules.ts`** — add `useAvailableSlots(date, serviceId)` query hook
- **`frontend/src/pages/agenda/components/CreateAppointmentModal.tsx`** — replace `<Input type="time">` with a slot picker grid. Slots fetch is enabled only when both `date` and `serviceId` are set. Show loading spinner while fetching, empty state if no slots.

### Slot picker UX:
- Grid of pill buttons showing "HH:MM" times
- Selected slot gets brand highlight
- If no slots: "Nenhum horario disponivel" message
- If date or service not selected yet: prompt "Selecione data e servico"

---

## Feature 2: Inline Patient Creation

**Problem:** If a patient doesn't exist, the user must leave the modal, go to Pacientes, create the patient, come back.

**Approach:** Add a "Cadastrar novo paciente" link below the search results. Clicking it expands inline fields (name, phone, gender) inside the same modal. On save, call `useCreatePatient()`, then auto-select the new patient.

### Files to change:
- **`frontend/src/pages/agenda/components/CreateAppointmentModal.tsx`** — add inline patient creation form toggled by a button. Uses existing `useCreatePatient()` hook from `usePatients.ts`. Fields: name (required), phone (required), gender (optional M/F toggle). After successful creation, auto-selects the patient and collapses the form.

### UX flow:
1. User types in patient search → no results
2. "Nenhum paciente encontrado" + "+ Cadastrar novo paciente" button
3. Click → inline form slides in (name, phone, gender)
4. Submit → creates patient via API → auto-selects → form collapses back to search

---

## Feature 3: Discount Rules Management Page

**Problem:** Clinic owners can't configure their progressive discount tiers from the UI. Currently only editable via API.

**Approach:** New page at `/descontos` (or a section in settings) with a form matching the backend schema. Uses existing `catalogService.getDiscountRules()` to fetch and a new `upsertDiscountRules` method to save.

### Discount rules schema (from DB):
- `first_session_discount_pct` — first visit discount %
- `tier_2_min_areas` / `tier_2_max_areas` / `tier_2_discount_pct` — tier 2
- `tier_3_min_areas` / `tier_3_discount_pct` — tier 3
- `is_active` — toggle

### Files to create/change:
- **`frontend/src/services/catalog.service.ts`** — add `upsertDiscountRules(clinicId, payload)` (POST, since backend upserts on POST)
- **`frontend/src/hooks/useDiscountRules.ts`** — new hook: `useDiscountRules()` query + `useUpsertDiscountRules()` mutation
- **`frontend/src/pages/descontos/DescontosPage.tsx`** — new page with the form
- **`frontend/src/types/index.ts`** — `DiscountRule` type already exists with the right fields
- **`frontend/src/router.tsx`** — add route for `/descontos`
- **`frontend/src/layouts/AppLayout.tsx`** — add nav item to sidebar

### Form layout:
- Toggle: "Descontos ativos" (is_active)
- Section "Primeira sessao": input for discount %
- Section "Descontos progressivos":
  - Tier 2: min areas, max areas, discount %
  - Tier 3: min areas, discount %
- Save button with loading state
- Visual summary showing the tiers (like the WhatsApp message format)

---

## Implementation Order
1. Feature 1 (slots picker) — smallest scope, self-contained
2. Feature 2 (inline patient creation) — modifies same modal
3. Feature 3 (discount rules page) — new page, independent

## Verification
- Feature 1: Open modal, select date + service → slots appear. Pick one → time is set. Change date → slots refetch.
- Feature 2: Search a non-existent patient → see creation form. Fill in → patient created & selected.
- Feature 3: Navigate to /descontos → form loads current rules. Edit values → save → reload shows persisted values.
- TypeScript: `npx tsc --noEmit` passes with no errors
