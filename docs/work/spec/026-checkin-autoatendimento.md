# Spec — 026 Check-in de autoatendimento com pagamento

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/026-checkin-autoatendimento.md`
- **Branch:** `feat/026-checkin-autoatendimento`
- **Deploy:** só dev nesta fase. O `booking-site/` não é tocado.

---

## 1. Banco (`scheduler/src/scripts/setup_database.py`, migrations idempotentes)

```sql
ALTER TABLE scheduler.appointments ADD COLUMN IF NOT EXISTS checked_in_at TIMESTAMPTZ;

CREATE TABLE IF NOT EXISTS scheduler.appointment_payments (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  clinic_id VARCHAR(100) NOT NULL REFERENCES scheduler.clinics(clinic_id),
  appointment_id UUID NOT NULL REFERENCES scheduler.appointments(id),
  method VARCHAR(20) NOT NULL CHECK (method IN ('PIX','CREDIT_CARD','DEBIT_CARD','CASH')),
  amount_cents INTEGER NOT NULL CHECK (amount_cents > 0),
  status VARCHAR(20) NOT NULL DEFAULT 'PENDING'
    CHECK (status IN ('PENDING','AWAITING_CASH','PAID','CANCELLED','FAILED','REFUNDED')),
  provider VARCHAR(20) NOT NULL CHECK (provider IN ('asaas','simulado')),
  provider_payment_id VARCHAR(100),
  invoice_url TEXT,
  pix_payload TEXT,
  payer_name VARCHAR(255),
  payer_cpf VARCHAR(11),
  paid_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
-- um pagamento ativo por agendamento
CREATE UNIQUE INDEX IF NOT EXISTS uq_appointment_payments_ativo
  ON scheduler.appointment_payments (appointment_id)
  WHERE status IN ('PENDING','AWAITING_CASH','PAID');
CREATE INDEX IF NOT EXISTS idx_appointment_payments_provider
  ON scheduler.appointment_payments (provider, provider_payment_id);

CREATE TABLE IF NOT EXISTS scheduler.payment_webhook_events (
  event_id VARCHAR(100) PRIMARY KEY,
  provider VARCHAR(20) NOT NULL,
  event VARCHAR(50),
  provider_payment_id VARCHAR(100),
  received_at TIMESTAMPTZ DEFAULT NOW()
);
```

## 2. Provedores (`scheduler/src/providers/`)

| Arquivo | Conteúdo |
|---|---|
| `payment_provider.py` | `Cobranca` (id, status, invoice_url, pix_payload), `PagadorAsaas`, `PaymentProvider` (interface): `cria_cobranca(pagador, metodo, valor_cents, vencimento, descricao, referencia)`, `cancela(id)`, `consulta_status(id)`, `recebe_em_dinheiro(id, valor_cents, data)`, `simula(id)` com `pode_simular` (só simulado e Asaas sandbox); `cobranca_de_teste(provider)` (simulado, ou Asaas com `ASAAS_BASE_URL` de sandbox) alimenta `simulated`/`canSimulate` da tela; `provedor_ativo()`: Asaas com `ASAAS_API_KEY`, simulado só com `STAGE=dev`, senão `PagamentoIndisponivel`. |
| `asaas_provider.py` | REST v3 (`access_token`): cliente por CPF (`GET /customers?cpfCnpj`, senão `POST /customers` com `notificationDisabled`), `POST /payments` (`PIX` → `GET /payments/{id}/pixQrCode`; `CREDIT_CARD` para crédito e débito, devolve `invoiceUrl`; `UNDEFINED` para dinheiro), `DELETE /payments/{id}`, `GET /payments/{id}`, `POST /payments/{id}/receiveInCash`; no sandbox, `POST /sandbox/payment/{id}/confirm` (só Pix: o sandbox recusa cartão). Base: `ASAAS_BASE_URL`. |
| `simulated_payment_provider.py` | Ids `sim_*`, payload Pix e fatura fictícios; status em memória do banco (a confirmação vem do endpoint `simulate`). |

Mapa de status do Asaas: `RECEIVED|CONFIRMED|RECEIVED_IN_CASH` → `PAID`;
`REFUNDED` → `REFUNDED`; `DELETED` → `CANCELLED`.

## 3. Serviço (`scheduler/src/services/checkin.py`)

- `agendamentos_do_numero(db, clinic_id, phone)` → próximos confirmados (via
  `AppointmentService.get_active_appointments_by_phone`), com áreas, preço,
  `checked_in_at` e o pagamento ativo.
- `confirma(db, clinic_id, phone, appointment_id)` → grava `checked_in_at`
  (idempotente); devolve se o CPF de quem paga já é conhecido.
- `cobra(db, provider, clinic_id, phone, appointment_id, metodo, cpf)` →
  valida dono, valor e CPF (dígitos verificadores); já pago devolve o
  existente; outro método ativo é cancelado no provedor e no banco;
  cria a cobrança e grava. Dinheiro nasce `AWAITING_CASH`.
- `status(db, provider, clinic_id, phone, payment_id)` → devolve o
  pagamento; se pendente no Asaas, consulta o provedor (rede de segurança
  para webhook atrasado).
- `aplica_evento(db, evento)` → idempotente por `event_id`.
- `marca_recebido_em_dinheiro(...)` → só `AWAITING_CASH`, chama
  `receiveInCash`.

`utils/cadastro.py` ganha `cpf_valido(digitos)` (dígitos verificadores).
Validação só no check-in: o bot continua aceitando CPF sem checar dígito, de
propósito.

## 4. Rotas (Lambda `PublicBooking`)

| Método | Rota | Auth | Uso |
|---|---|---|---|
| ANY | `public/clinics/{clinicId}/checkin/{proxy+}` | chave do booking + token OTP | sub-rotas abaixo |
| POST | `public/asaas/webhook` | header `asaas-access-token` = `ASAAS_WEBHOOK_TOKEN` | eventos do Asaas |

Sub-rotas (`checkin.py`):

| Método | `proxy` | Corpo/query |
|---|---|---|
| GET | `appointments` | `?phone&token` |
| POST | `appointments/{id}/confirm` | `{phone, token}` |
| POST | `appointments/{id}/payments` | `{phone, token, method, cpf?}` |
| GET | `payments/{id}` | `?phone&token` |
| POST | `payments/{id}/simulate` | `{phone, token}`, só em teste: simulado (qualquer método) ou Asaas sandbox (só Pix; cartão: 400). Produção: 404 |

A baixa em dinheiro não fica aqui: é da Lambda `Caixa` (§5.1).

Env novas (`serverless.yml`): `ASAAS_API_KEY`, `ASAAS_WEBHOOK_TOKEN` (SSM,
fallback vazio), `ASAAS_BASE_URL` (sandbox em dev, produção em prod).

## 5. App `checkin/` (novo, React 19 + Vite 7 + Tailwind v4 + TanStack Query)

Mesma stack e tokens visuais do booking-site, sem compartilhar código (o
booking-site fica intocado).

- Rota `/:clinicId`. Etapas: `phone → otp → appointments → cpf? → method →
  pay → done`.
- `useIdleReset(90s)` volta ao início e limpa o estado; `done` volta em 15 s.
- QR gerado no front a partir do payload/URL (`qrcode`).
- Status do pagamento por polling (3 s) enquanto pendente.
- Testes: fluxo feliz (Pix simulado), escolha entre agendamentos, CPF
  inválido, troca de método, dinheiro, idle reset.

## 5.1 Fase 2: painel

| Arquivo | Alteração |
|---|---|
| `scheduler/src/services/caixa.py` (novo) | `resumo(db, clinic_id, date_from, date_to)`: previsto por data da sessão, recebido por `paid_at` no fuso da clínica (por dia e por método), `pendentes` (confirmada até hoje, com valor, sem `PAID`) e `pagamentos`. Período máximo de 92 dias. |
| `scheduler/src/functions/caixa/router.py` (novo) + `sls/functions/caixa/interface.yml` | Lambda `Caixa`, `ANY clinics/{clinicId}/caixa/{proxy+}`: `GET resumo` (`require_api_key`) e `POST pagamentos/{id}/dinheiro` (`require_acesso("agenda.escrever")`). |
| `scheduler/src/functions/public_booking/checkin.py` | Sai a sub-rota `cash-received`. |
| `scheduler/src/functions/appointment/list.py` | `checked_in_at` e o pagamento vivo (`payment_id`, `payment_method`, `payment_status`, `payment_paid_at`, `payment_price_cents`, que `para_o_staff` remove). |
| `frontend/src/services/caixa.service.ts`, `hooks/useCaixa.ts`, `utils/pagamento.ts`, `utils/caixa.ts` (novos) | Service, hooks (a baixa invalida caixa e agenda), rótulos e períodos. |
| `frontend/src/pages/agenda/components/PagamentoDoAgendamento.tsx` (novo) | Check-in, situação do pagamento e "Recebi em dinheiro" no popover. |
| `frontend/src/pages/relatorios/components/CaixaPanel.tsx` (novo) + `RelatoriosPage.tsx` | Abas Faturamento / Caixa. |

## 6. Testes backend

`tests/unit/test_checkin.py` (serviço e handler), `test_asaas_provider.py`
(HTTP mockado), `test_cpf_valido.py`. Integração em
`tests/integration/026-checkin-autoatendimento.md`, Postman e mocks.
