# Design: Sistema de Descontos no Agendamento WhatsApp

**Data:** 2026-02-21
**Branch:** improve-details
**Status:** Aprovado

---

## Problema

O fluxo de agendamento via WhatsApp não tem conceito de descontos. A clínica precisa:
- Oferecer **20% de desconto na primeira sessão** de pacientes novos (qualquer número de áreas)
- Aplicar **descontos progressivos** por quantidade de áreas em sessões subsequentes

## Regras de Negócio

### Primeira sessão (paciente sem appointments CONFIRMED na clínica)
- Desconto flat configurável (ex: 20%) sobre o valor total
- Independe da quantidade de áreas

### Sessões seguintes (paciente com 1+ appointments CONFIRMED)
- Desconto progressivo baseado na quantidade de **áreas** no agendamento:
  - 1 área: valor de tabela (0%)
  - 2 a 4 áreas: desconto configurável (ex: 10%)
  - 5+ áreas: desconto configurável (ex: 15%)
- Contagem de áreas = número de `service_area_pairs` no agendamento
- Serviços SEM áreas NÃO contam para o desconto progressivo (pagam preço cheio)
- Cada agendamento conta separado (não soma entre agendamentos)

---

## Design

### 1. Nova tabela: `scheduler.discount_rules`

```sql
CREATE TABLE scheduler.discount_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    clinic_id VARCHAR(100) NOT NULL,
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
);
```

Uma row por clínica. Sem row = sem desconto (preço cheio).

### 2. Novos campos em `scheduler.appointments`

```sql
ALTER TABLE scheduler.appointments
    ADD COLUMN discount_pct INTEGER DEFAULT 0,
    ADD COLUMN discount_reason VARCHAR(50),
    ADD COLUMN original_price_cents INTEGER,
    ADD COLUMN final_price_cents INTEGER;
```

- `discount_pct`: percentual aplicado (0, 10, 15, 20...)
- `discount_reason`: `first_session`, `tier_2`, `tier_3`, ou NULL
- `original_price_cents`: soma dos preços sem desconto
- `final_price_cents`: valor efetivamente cobrado

### 3. Mensagem de desconto antes da seleção de áreas

Logo antes de mostrar as áreas disponíveis (entre CONFIRM_SERVICES e SELECT_AREAS), exibir uma mensagem informativa sobre o desconto disponível.

**Paciente novo (primeira sessão):**
```
🎉 *Desconto especial de primeira sessão!*

Por ser sua primeira vez, você tem *20% de desconto* em qualquer combinação de áreas. Aproveite! ✨
```

**Paciente retornante (desconto progressivo):**
```
✅ *Descontos progressivos* (válidos para áreas realizadas no mesmo dia):
• 1 área: valor de tabela
• 2 a 4 áreas: 10% de desconto
• 5 ou mais áreas: 15% de desconto

🔎 Como contar as áreas: cada item/linha da tabela = 1 área.

Exemplos: buço = 1 área | rosto completo = 1 área | 1/2 perna = 1 área | perna completa = 1 área.
Então: buço + perna completa = 2 áreas (10%)
```

**Implementação:** A mensagem é enviada como parte do `_on_enter_select_areas()`. Não cria estado novo — é uma mensagem adicional antes de listar as áreas.

Os percentuais exibidos vêm da tabela `discount_rules` da clínica (dinâmicos, não hardcoded).

### 4. Lógica de cálculo (conversation_engine.py)

No `_on_enter_available_days()`, após calcular `total_price_cents`:

```
1. Buscar discount_rules da clínica (WHERE clinic_id = X AND is_active = true)
2. Se não existe → discount_pct = 0, sem desconto
3. Se existe:
   a. Buscar COUNT de appointments CONFIRMED do paciente (by phone + clinic_id)
   b. Se COUNT == 0 → first_session_discount_pct
   c. Se COUNT > 0 → contar service_area_pairs:
      - < tier_2_min → 0%
      - entre tier_2_min e tier_2_max → tier_2_discount_pct
      - >= tier_3_min → tier_3_discount_pct
4. Calcular discounted_price_cents = total_price_cents * (100 - discount_pct) / 100
5. Guardar na session: discount_pct, discount_reason, original_price_cents, discounted_price_cents
```

### 5. Exibição na confirmação (CONFIRM_BOOKING)

**Com desconto:**
```
~~R$ 250,00~~ → *R$ 200,00* (20% off - primeira sessão ✨)
```

**Com desconto progressivo:**
```
~~R$ 500,00~~ → *R$ 450,00* (10% off - 3 áreas)
```

**Sem desconto:**
```
Valor: R$ 150,00
```

### 6. Persistência (appointment_service.py)

No `create_appointment()`, salvar os 4 novos campos no INSERT.

### 7. Sheets sync

Se houver integração com Google Sheets, incluir `discount_pct`, `original_price_cents`, `final_price_cents` no sync.

---

## O que NÃO muda

- Nenhum estado novo no fluxo (mensagem de desconto é inline no SELECT_AREAS)
- Seleção de serviços/áreas inalterada
- Tabela de preços mostra preço cheio (sem desconto)
- Estrutura das junction tables (appointment_services, appointment_service_areas)

## Arquivos impactados

| Arquivo | Mudança |
|---------|---------|
| `setup_database.py` | Nova tabela + ALTER em appointments |
| `conversation_engine.py` | Lógica de cálculo e exibição do desconto |
| `appointment_service.py` | Persistir campos de desconto no INSERT |
| `sheets_sync.py` | Incluir campos de desconto no sync |
| `seed_clinic.py` | Seed de discount_rules para clínica de teste |
