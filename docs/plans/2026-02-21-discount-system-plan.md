# Discount System Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add configurable discount rules (first-session + progressive) to the WhatsApp scheduling flow, showing discounts in messages and persisting them on appointments.

**Architecture:** New `discount_rules` table stores per-clinic config. Discount logic runs in `conversation_engine.py` at two points: (1) informational message in `_on_enter_select_areas`, (2) price calculation in `_on_enter_available_days`. Four new columns on `appointments` persist the discount. `appointment_service.py` receives and stores discount data. Sheets sync includes discount columns.

**Tech Stack:** Python, PostgreSQL, DynamoDB (sessions), Google Sheets API

**Design doc:** `docs/plans/2026-02-21-discount-system-design.md`

---

### Task 1: Database schema — new table + ALTER appointments

**Files:**
- Modify: `scheduler/src/scripts/setup_database.py` (append to `SQL_STATEMENTS` list, lines 288-290)

**Step 1: Add discount_rules table and appointment columns to SQL_STATEMENTS**

Append these statements at the end of the `SQL_STATEMENTS` list (before the closing `]` at line 290):

```python
    # Discount rules per clinic (configurable progressive discounts)
    """
    CREATE TABLE IF NOT EXISTS scheduler.discount_rules (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
        first_session_discount_pct INTEGER NOT NULL DEFAULT 0,
        tier_2_min_areas INTEGER NOT NULL DEFAULT 2,
        tier_2_max_areas INTEGER NOT NULL DEFAULT 4,
        tier_2_discount_pct INTEGER NOT NULL DEFAULT 0,
        tier_3_min_areas INTEGER NOT NULL DEFAULT 5,
        tier_3_discount_pct INTEGER NOT NULL DEFAULT 0,
        is_active BOOLEAN NOT NULL DEFAULT true,
        created_at TIMESTAMP DEFAULT NOW(),
        updated_at TIMESTAMP DEFAULT NOW(),
        UNIQUE(clinic_id)
    )
    """,

    # Discount fields on appointments
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS discount_pct INTEGER DEFAULT 0",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS discount_reason VARCHAR(50)",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS original_price_cents INTEGER",
    "ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS final_price_cents INTEGER",
```

**Step 2: Run migration to verify**

Run: `cd scheduler && python -m src.scripts.setup_database`
Expected: All statements OK, no errors.

**Step 3: Commit**

```bash
git add scheduler/src/scripts/setup_database.py
git commit -m "feat: add discount_rules table and discount columns to appointments"
```

---

### Task 2: Seed discount_rules for test clinic

**Files:**
- Modify: `scheduler/src/scripts/seed_clinic.py` (add section 6 after FAQ items)

**Step 1: Add discount_rules seed after the FAQ section**

After the FAQ section (after `print(f"[5/5] FAQ items: ...")`), add:

```python
    # ── 6. Discount Rules ────────────────────────────────────────────────
    cursor.execute(
        """
        INSERT INTO discount_rules (id, clinic_id, first_session_discount_pct,
            tier_2_min_areas, tier_2_max_areas, tier_2_discount_pct,
            tier_3_min_areas, tier_3_discount_pct, is_active)
        VALUES (gen_random_uuid(), %s, %s, %s, %s, %s, %s, %s, TRUE)
        ON CONFLICT (clinic_id) DO NOTHING
        RETURNING id
        """,
        (clinic_id, 20, 2, 4, 10, 5, 15),
    )
    conn.commit()
    row = cursor.fetchone()
    if row:
        print(f"[6/6] Discount rules criada: id={row[0]}")
    else:
        print("[6/6] Discount rules ja existe - skip")
```

Also update the earlier print labels from `[X/5]` to `[X/6]`.

**Step 2: Run seed to verify**

Run: `cd scheduler && python -m src.scripts.seed_clinic`
Expected: Discount rules inserted (or skip if already exists).

**Step 3: Commit**

```bash
git add scheduler/src/scripts/seed_clinic.py
git commit -m "feat: seed discount_rules for laser-beauty-sp test clinic"
```

---

### Task 3: Add discount info message in `_on_enter_select_areas`

**Files:**
- Modify: `scheduler/src/services/conversation_engine.py`
  - `_on_enter_select_areas()` method (lines 950-995)
  - Add helper `_get_discount_rules()`
  - Add helper `_is_first_session()`
  - Add helper `_build_discount_info_message()`
  - Add `discount_pct`, `discount_reason`, `original_price_cents`, `discounted_price_cents` to `FLOW_SESSION_KEYS` (line 343-354)

**Step 1: Add discount session keys to FLOW_SESSION_KEYS**

At `scheduler/src/services/conversation_engine.py` line 344, add to the list:

```python
    "discount_pct", "discount_reason", "original_price_cents", "discounted_price_cents",
```

**Step 2: Add three helper methods to ConversationEngine class**

Add these methods right before `_on_enter_select_areas` (around line 949):

```python
    def _get_discount_rules(self, clinic_id: str) -> Optional[dict]:
        """Fetch active discount rules for a clinic. Returns None if no rules configured."""
        rows = self.db.execute_query(
            "SELECT * FROM scheduler.discount_rules WHERE clinic_id = %s AND is_active = TRUE",
            (clinic_id,),
        )
        return rows[0] if rows else None

    def _is_first_session(self, clinic_id: str, phone: str) -> bool:
        """Check if patient has zero CONFIRMED appointments in this clinic."""
        rows = self.db.execute_query(
            """SELECT COUNT(*) as cnt FROM scheduler.appointments a
               JOIN scheduler.patients p ON a.patient_id = p.id
               WHERE a.clinic_id = %s AND p.phone = %s AND a.status = 'CONFIRMED'""",
            (clinic_id, phone),
        )
        return int(rows[0]["cnt"]) == 0 if rows else True

    def _build_discount_info_message(self, rules: dict, is_first: bool) -> str:
        """Build the discount informational message shown before area selection."""
        if is_first:
            pct = rules["first_session_discount_pct"]
            return (
                f"\U0001f389 *Desconto especial de primeira sessão!*\n\n"
                f"Por ser sua primeira vez, você tem *{pct}% de desconto* "
                f"em qualquer combinação de áreas. Aproveite! \u2728"
            )

        t2_min = rules["tier_2_min_areas"]
        t2_max = rules["tier_2_max_areas"]
        t2_pct = rules["tier_2_discount_pct"]
        t3_min = rules["tier_3_min_areas"]
        t3_pct = rules["tier_3_discount_pct"]

        return (
            f"\u2705 *Descontos progressivos* (válidos para áreas realizadas no mesmo dia):\n"
            f"• 1 área: valor de tabela\n"
            f"• {t2_min} a {t2_max} áreas: {t2_pct}% de desconto\n"
            f"• {t3_min} ou mais áreas: {t3_pct}% de desconto\n\n"
            f"\U0001f50e Como contar as áreas: cada item/linha da tabela = 1 área.\n\n"
            f"Exemplos: buço = 1 área | rosto completo = 1 área | 1/2 perna = 1 área | perna completa = 1 área.\n"
            f"Então: buço + perna completa = 2 áreas ({t2_pct}%)"
        )
```

**Step 3: Modify `_on_enter_select_areas` to prepend discount message**

The current method (line 950) fetches areas and returns a content string. Modify it so that **after** fetching areas and **before** returning, it:

1. Calls `_get_discount_rules(clinic_id)`
2. If rules exist, calls `_is_first_session(clinic_id, phone)` — **note:** `_on_enter_select_areas` doesn't receive `phone` today, so we need to add it.
3. Builds the discount info message and prepends it to the areas list content.
4. Stores `is_first_session` in session for later use in price calc.

**Important:** The method signature needs `phone` added. Update the call site too.

In the `_on_enter` dispatcher (around line 651-663), the SELECT_AREAS call currently is:
```python
result = self._on_enter_select_areas(clinic_id, session)
```

Change to:
```python
result = self._on_enter_select_areas(clinic_id, phone, session)
```

Then modify `_on_enter_select_areas` signature and body:

```python
    def _on_enter_select_areas(self, clinic_id: str, phone: str, session: dict) -> tuple:
        selected_service_ids = session.get("selected_service_ids", [])
        logger.info(f"[ConversationEngine] _on_enter_select_areas: service_ids={selected_service_ids}")
        if not selected_service_ids:
            logger.warning("[ConversationEngine] _on_enter_select_areas: no services in session")
            return {}, "Nenhum serviço selecionado.", None

        # Fetch areas for all selected services (JOIN with areas table)
        placeholders = ", ".join(["%s"] * len(selected_service_ids))
        areas = self.db.execute_query(
            f"""
            SELECT a.id, a.name, sa.service_id, s.name as service_name
            FROM scheduler.service_areas sa
            JOIN scheduler.areas a ON sa.area_id = a.id
            JOIN scheduler.services s ON sa.service_id = s.id
            WHERE sa.service_id::text IN ({placeholders})
            AND sa.active = TRUE AND a.active = TRUE
            ORDER BY s.name, a.display_order, a.name
            """,
            tuple(selected_service_ids),
        )

        if not areas:
            # No areas configured — skip to AVAILABLE_DAYS
            logger.info(f"[ConversationEngine] _on_enter_select_areas: no areas configured for services -> skipping to AVAILABLE_DAYS")
            session["selected_areas_display"] = ""
            return None

        logger.info(f"[ConversationEngine] _on_enter_select_areas: {len(areas)} areas found")

        # Cache areas for later use in CONFIRM_AREAS (includes service_id for pair tracking)
        session["_available_areas"] = [
            {"id": str(a["id"]), "name": a["name"], "service_id": str(a["service_id"]), "service_name": a.get("service_name", "")}
            for a in areas
        ]

        # Determine distinct services that have areas
        service_names = list(dict.fromkeys(a.get("service_name", "") for a in areas))
        multi_service = len(service_names) > 1

        areas_list = self._build_areas_list(session["_available_areas"], multi_service)

        # Build discount info message (if rules configured for this clinic)
        discount_msg = ""
        rules = self._get_discount_rules(clinic_id)
        if rules:
            is_first = self._is_first_session(clinic_id, phone)
            session["_is_first_session"] = is_first
            discount_msg = self._build_discount_info_message(rules, is_first) + "\n\n"

        content = f"{discount_msg}Selecione as áreas de tratamento (digite os números separados por vírgula):\n\n{areas_list}"

        back_button = [{"id": "back", "label": "Voltar"}]
        session["dynamic_buttons"] = back_button
        return {}, content, back_button
```

**Step 4: Commit**

```bash
git add scheduler/src/services/conversation_engine.py
git commit -m "feat: show discount info message before area selection"
```

---

### Task 4: Calculate discount in `_on_enter_available_days`

**Files:**
- Modify: `scheduler/src/services/conversation_engine.py`
  - `_on_enter_available_days()` method (lines 1054-1137)
  - Add helper `_calculate_discount()`

**Step 1: Add `_calculate_discount` helper method**

Add this method to ConversationEngine (near the other discount helpers):

```python
    def _calculate_discount(self, clinic_id: str, phone: str, session: dict) -> None:
        """Calculate and store discount info in session based on clinic rules."""
        total_price = session.get("total_price_cents", 0)
        if not total_price:
            return

        rules = self._get_discount_rules(clinic_id)
        if not rules:
            session["discount_pct"] = 0
            session["discount_reason"] = None
            session["original_price_cents"] = total_price
            session["discounted_price_cents"] = total_price
            return

        # Use cached value from _on_enter_select_areas if available, otherwise query
        is_first = session.get("_is_first_session")
        if is_first is None:
            is_first = self._is_first_session(clinic_id, phone)

        if is_first:
            discount_pct = rules["first_session_discount_pct"]
            discount_reason = "first_session"
        else:
            # Count areas (service_area_pairs). Services without areas don't count.
            area_count = len(session.get("selected_service_area_pairs") or [])
            t2_min = rules["tier_2_min_areas"]
            t2_max = rules["tier_2_max_areas"]
            t3_min = rules["tier_3_min_areas"]

            if area_count >= t3_min:
                discount_pct = rules["tier_3_discount_pct"]
                discount_reason = "tier_3"
            elif area_count >= t2_min:
                discount_pct = rules["tier_2_discount_pct"]
                discount_reason = "tier_2"
            else:
                discount_pct = 0
                discount_reason = None

        discounted_price = total_price * (100 - discount_pct) // 100

        session["discount_pct"] = discount_pct
        session["discount_reason"] = discount_reason
        session["original_price_cents"] = total_price
        session["discounted_price_cents"] = discounted_price

        logger.info(
            f"[ConversationEngine] _calculate_discount: pct={discount_pct} reason={discount_reason} "
            f"original={total_price} discounted={discounted_price}"
        )
```

**Step 2: Call `_calculate_discount` in `_on_enter_available_days`**

After `session["total_price_cents"] = total_price` (line 1104), and the logger line (1105), add:

```python
                # Calculate discount
                self._calculate_discount(clinic_id, phone, session)
```

**Important:** `_on_enter_available_days` doesn't receive `phone` today. Update its signature from:
```python
def _on_enter_available_days(self, clinic_id: str, session: dict) -> tuple:
```
to:
```python
def _on_enter_available_days(self, clinic_id: str, phone: str, session: dict) -> tuple:
```

And update its call site in `_on_enter` (around line 667):
```python
# Current:
template_vars, dynamic_buttons = self._on_enter_available_days(clinic_id, session)
# Change to:
template_vars, dynamic_buttons = self._on_enter_available_days(clinic_id, phone, session)
```

**Step 3: Commit**

```bash
git add scheduler/src/services/conversation_engine.py
git commit -m "feat: calculate discount in _on_enter_available_days"
```

---

### Task 5: Display discount in CONFIRM_BOOKING and BOOKED

**Files:**
- Modify: `scheduler/src/services/conversation_engine.py`
  - `_on_enter_confirm_booking()` (lines 1175-1218)
  - `_on_enter_booked()` (lines 1220-1296)
  - Add helper `_format_price_with_discount()`

**Step 1: Add `_format_price_with_discount` helper**

```python
    def _format_price_with_discount(self, session: dict) -> str:
        """Format price string showing discount if applicable."""
        discount_pct = session.get("discount_pct", 0)
        original = session.get("original_price_cents") or session.get("total_price_cents", 0)
        discounted = session.get("discounted_price_cents", original)

        if not original:
            return ""

        if not discount_pct:
            return self._format_price_brl(original)

        original_str = self._format_price_brl(original)
        discounted_str = self._format_price_brl(discounted)

        reason = session.get("discount_reason", "")
        if reason == "first_session":
            label = f"primeira sessão \u2728"
        elif reason in ("tier_2", "tier_3"):
            area_count = len(session.get("selected_service_area_pairs") or [])
            label = f"{area_count} áreas"
        else:
            label = ""

        return f"~{original_str}~ → *{discounted_str}* ({discount_pct}% off - {label})"
```

**Step 2: Update `_on_enter_confirm_booking` to use discount-aware price**

Replace line 1206:
```python
        price_str = self._format_price_brl(session.get("total_price_cents"))
```
with:
```python
        price_str = self._format_price_with_discount(session)
```

**Step 3: Update `_on_enter_booked` to use discount-aware price**

Replace line 1283:
```python
        price_str = self._format_price_brl(session.get("total_price_cents"))
```
with:
```python
        price_str = self._format_price_with_discount(session)
```

**Step 4: Commit**

```bash
git add scheduler/src/services/conversation_engine.py
git commit -m "feat: display discount in CONFIRM_BOOKING and BOOKED messages"
```

---

### Task 6: Persist discount fields in `create_appointment`

**Files:**
- Modify: `scheduler/src/services/appointment_service.py`
  - `create_appointment()` method (lines 29-204)

**Step 1: Add discount parameters to `create_appointment` signature**

Add these params after `service_area_pairs`:

```python
        discount_pct: int = 0,
        discount_reason: Optional[str] = None,
        original_price_cents: Optional[int] = None,
        final_price_cents: Optional[int] = None,
```

**Step 2: Update the INSERT statement (line 117-133)**

Change the INSERT to include the 4 new columns:

```python
        result = self.db.execute_write_returning(
            """
            INSERT INTO scheduler.appointments (
                clinic_id, patient_id, professional_id, service_id,
                appointment_date, start_time, end_time,
                total_duration_minutes,
                discount_pct, discount_reason, original_price_cents, final_price_cents,
                status, created_at, updated_at, version
            ) VALUES (
                %s, %s::uuid, %s::uuid, %s::uuid,
                %s, %s::time, %s::time,
                %s,
                %s, %s, %s, %s,
                'CONFIRMED', NOW(), NOW(), 1
            )
            RETURNING *
            """,
            (clinic_id, patient_id, prof_id_param, primary_service_id,
             date, time, end_time,
             duration_minutes,
             discount_pct, discount_reason, original_price_cents, final_price_cents),
        )
```

**Step 3: Update the call site in `_on_enter_booked` (conversation_engine.py line 1233)**

Add the discount fields to the `create_appointment` call:

```python
                result = self.appointment_service.create_appointment(
                    clinic_id=clinic_id,
                    phone=phone,
                    service_id=primary_service_id,
                    date=session.get("selected_date"),
                    time=session.get("selected_time"),
                    service_ids=selected_ids if selected_ids else None,
                    total_duration_minutes=session.get("total_duration_minutes"),
                    service_area_pairs=session.get("selected_service_area_pairs") or None,
                    discount_pct=session.get("discount_pct", 0),
                    discount_reason=session.get("discount_reason"),
                    original_price_cents=session.get("original_price_cents"),
                    final_price_cents=session.get("discounted_price_cents"),
                )
```

**Step 4: Commit**

```bash
git add scheduler/src/services/appointment_service.py scheduler/src/services/conversation_engine.py
git commit -m "feat: persist discount fields in appointments table"
```

---

### Task 7: Include discount in Sheets sync

**Files:**
- Modify: `scheduler/src/services/sheets_sync.py` (lines 16-19, 255-266)

**Step 1: Update SHEET_HEADERS**

Change line 16-19:
```python
SHEET_HEADERS = [
    "Data", "Horário", "Paciente", "Telefone", "Serviço",
    "Áreas", "Desconto", "Valor Original", "Valor Final",
    "Status", "Observações", "AppointmentId", "UltimaAtualização"
]
```

**Step 2: Update row_values in `sync_appointment` (line 255)**

After fetching service_name and before building `row_values`, fetch discount info:

```python
            # Fetch discount info
            discount_pct = appointment.get("discount_pct", 0)
            original_price = appointment.get("original_price_cents")
            final_price = appointment.get("final_price_cents")

            discount_str = f"{discount_pct}%" if discount_pct else ""
            original_str = f"R$ {original_price / 100:.2f}" if original_price else ""
            final_str = f"R$ {final_price / 100:.2f}" if final_price else ""
```

Update `row_values`:
```python
            row_values = [
                str(appointment.get("appointment_date", "")),
                str(appointment.get("start_time", "")),
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

**Step 3: Update ranges from J to M (10 → 13 columns)**

Update all range references:
- `_write_headers`: `A1:J1` → `A1:M1`
- `_append_row`: `A:J` → `A:M`
- `_update_row`: `A{row_number}:J{row_number}` → `A{row_number}:M{row_number}`
- `_find_row_by_appointment_id`: column `I:I` → `L:L` (AppointmentId moved to column L)
- `bulk_sync_month`: `A2:J` → `A2:M` and `A2:J{row_count + 1}` → `A2:M{row_count + 1}`

Also update the `bulk_sync_month` row builder to include the 3 new columns.

**Step 4: Commit**

```bash
git add scheduler/src/services/sheets_sync.py
git commit -m "feat: include discount columns in Google Sheets sync"
```

---

### Task 8: Deploy and test

**Step 1: Run setup_database to apply migrations**

Run: `cd scheduler && python -m src.scripts.setup_database`

**Step 2: Run seed_clinic to insert discount rules**

Run: `cd scheduler && python -m src.scripts.seed_clinic`

**Step 3: Deploy to dev**

Run: `cd scheduler && serverless deploy --stage dev --aws-profile traffic-manager`

**Step 4: Test via WhatsApp**

Test scenarios:
1. **New patient** (no prior appointments): Should see first-session discount message before areas, and 20% discount in confirmation.
2. **Returning patient with 1 area**: Should see progressive discount message, 0% discount (1 area = full price).
3. **Returning patient with 3 areas**: Should see 10% discount in confirmation.
4. **Returning patient with 5+ areas**: Should see 15% discount in confirmation.
5. **Clinic without discount_rules**: Should see no discount message, full price everywhere.

**Step 5: Final commit**

```bash
git add -A
git commit -m "feat: discount system - complete implementation"
```
