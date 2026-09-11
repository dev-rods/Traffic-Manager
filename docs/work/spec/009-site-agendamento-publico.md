# Spec — 009 Site de Agendamento Público

> Lida a partir de `prd/009-site-agendamento-publico.md`. Decisões que estavam pendentes no PRD foram resolvidas aqui (ver §0) para destravar a implementação, já que o backend/DB existentes (`scheduler/`) determinam o que é viável sem reescrever nada.

---

## 0. Decisões (resolvendo os pendentes do PRD)

| # | Pendente no PRD | Decisão | Justificativa |
|---|------------------|---------|----------------|
| 1 | Nome da pasta | `booking-site/` | Direto, sem ambiguidade |
| 2 | Pagamento (iugu) | **Fora do MVP** | Confirmado — recomendação do PRD |
| 3 | Estado do backend | **`scheduler/` já cobre tudo**: `AppointmentService.create_appointment/cancel_appointment/get_active_appointments_by_phone` e `AvailabilityEngine.get_available_slots(_multi)` já implementam a lógica de negócio. Falta só a **camada HTTP pública** (sem o `x-api-key` do painel) | Reuso total — zero duplicação de regra de negócio |
| 4 | Provedor de SMS OTP | **Sem SMS. Código de verificação enviado por WhatsApp** via `ZApiProvider.send_text` (já integrado) | O campo já se chama "Celular (WhatsApp)" no site original; evita contratar/configurar um provedor de SMS novo; reaproveita 100% da infra de mensageria existente |
| 5 | Domínio / multi-tenant | Multi-tenant real, por `clinic_id` na URL (`/:clinicId`), igual ao padrão já usado no resto do `scheduler/` | Consistente com o resto do sistema; funciona pro salão do dono e para futuros clientes |

**Divergência assumida vs. o site de referência** (documentar, não esconder):
- `AvailabilityEngine` calcula disponibilidade **por clínica**, não por profissional (sem filtro `professional_id` nas regras/agendamentos). O site novo lista profissionais ativos (informativo) mas os horários oferecidos são os da clínica como um todo. Se o dono precisar de agenda por profissional de verdade, é um épico à parte no `scheduler/` (fora desta task).
- **"Meus agendamentos" exige verificação por WhatsApp** antes de listar (o original só pedia o número, sem confirmar posse). Isso corrige uma falha de privacidade do original (qualquer um digitando um número alheio via o site antigo veria os agendamentos dele) — mantém a mesma UX (usuário só digita o celular) mas adiciona um passo de código por trás.

---

## 1. Contrato de API pública (novo domínio `public_booking` no `scheduler/`)

Base: mesma API Gateway do `scheduler` (`serverless.yml` atual), path prefix `/public/clinics/{clinicId}/...`. Autenticação: header `x-api-key` com `BOOKING_INTAKE_API_KEY` (chave dedicada, restrita a este domínio — mesmo padrão de `LEADS_INTAKE_API_KEY`). Todas com `cors: true`.

| Método | Path | Body / Query | Faz | Reaproveita |
|--------|------|---------------|-----|-------------|
| GET | `/public/clinics/{clinicId}/bootstrap` | — | Dados do salão (nome, logo, timezone) + serviços ativos + profissionais ativos | Query direta (`clinics`, `services`, `professionals`) |
| GET | `/public/clinics/{clinicId}/available-slots` | `?date=YYYY-MM-DD&serviceId=&totalDuration=` | Horários livres do dia | `AvailabilityEngine` (idêntico ao endpoint autenticado) |
| POST | `/public/clinics/{clinicId}/verify/send` | `{ phone }` | Gera código de 6 dígitos, guarda no DynamoDB (TTL 5min, rate-limit), envia por WhatsApp | `ZApiProvider.send_text` + nova tabela `booking-otp-codes` |
| POST | `/public/clinics/{clinicId}/verify/confirm` | `{ phone, code }` | Valida o código; se ok, emite **token de sessão** HMAC (15 min, escopado a `clinicId+phone`) | Novo util `booking_verification.py` |
| POST | `/public/clinics/{clinicId}/appointments` | `{ token, phone, fullName, serviceIds:[], date, time, professionalId? }` | Cria o agendamento (valida token) | `AppointmentService.create_appointment` |
| GET | `/public/clinics/{clinicId}/my-appointments` | `?phone=&token=` | Lista agendamentos futuros do telefone (valida token) | `AppointmentService.get_active_appointments_by_phone` |
| POST | `/public/clinics/{clinicId}/appointments/{appointmentId}/cancel` | `{ phone, token }` | Cancela (valida token + posse) | `AppointmentService.cancel_appointment` |

**Token de verificação**: `base64url(clinicId|phone_normalizado|expiresAtEpoch|hmac_sha256(BOOKING_VERIFICATION_SECRET, clinicId|phone|expiresAt))`. Stateless — não precisa de tabela própria. Validado em toda mutação/consulta que exige posse do telefone.

**Rate limit do OTP**: no item do DynamoDB, contador `send_count` + `window_started_at`; máx. 3 envios / 15 min por (clinic_id, phone). Código de 6 dígitos, máx. 5 tentativas de confirmação antes de invalidar e exigir reenvio.

---

## 2. Arquivos — Backend (`scheduler/`)

| Arquivo | Ação | Conteúdo |
|---------|------|----------|
| `src/scripts/setup_database.py` | modificar | + coluna `logo_url` em `clinics` (CREATE TABLE e `ALTER ... ADD COLUMN IF NOT EXISTS`), + coluna `photo_url` em `professionals` (idem) |
| `sls/resources/dynamodb/booking-otp-table.yml` | criar | Tabela `${resourcePrefix}-booking-otp-codes`, PK `clinic_phone` (S), TTL `expires_at`, PAY_PER_REQUEST |
| `src/utils/auth.py` | modificar | `validate_booking_intake_api_key()` — mesmo padrão de `validate_intake_api_key` |
| `src/utils/http.py` | modificar | `require_booking_intake_api_key()` |
| `src/utils/booking_verification.py` | criar | `generate_and_send_code(clinic, phone)`, `confirm_code(clinic_id, phone, code) -> token`, `verify_token(clinic_id, phone, token) -> bool` |
| `src/functions/public_booking/__init__.py` | criar | vazio |
| `src/functions/public_booking/bootstrap.py` | criar | handler GET bootstrap |
| `src/functions/public_booking/slots.py` | criar | handler GET available-slots (wrapper fino sobre `AvailabilityEngine`) |
| `src/functions/public_booking/send_otp.py` | criar | handler POST verify/send |
| `src/functions/public_booking/confirm_otp.py` | criar | handler POST verify/confirm |
| `src/functions/public_booking/create_appointment.py` | criar | handler POST appointments |
| `src/functions/public_booking/list_appointments.py` | criar | handler GET my-appointments |
| `src/functions/public_booking/cancel_appointment.py` | criar | handler POST appointments/{id}/cancel |
| `sls/functions/public_booking/interface.yml` | criar | 7 funções Lambda, `cors: true`, roles mínimas (ssm, logs; dynamodb para as de OTP) |
| `serverless.yml` | modificar | env vars `BOOKING_INTAKE_API_KEY`, `BOOKING_VERIFICATION_SECRET`, `BOOKING_OTP_TABLE`; include do novo `functions` e `resources` |

**Ordem de implementação:** migration → tabela DynamoDB → utils (auth/http/verification) → handlers → interface.yml → serverless.yml.

---

## 3. Arquivos — Frontend (`booking-site/`, novo app)

Mesma stack/convenções de `frontend/` (ver `frontend/CLAUDE.md`), adaptada para site público sem auth.

```
booking-site/
├── package.json, vite.config.ts, tsconfig*.json, eslint.config.js, vitest.config.ts
├── index.html, vercel.json, .env.example, CLAUDE.md
└── src/
    ├── main.tsx, router.tsx, index.css, vite-env.d.ts
    ├── types/index.ts                      # Clinic, Service, Professional, Slot, CartItem, Appointment
    ├── services/api.ts                     # axios + x-api-key (BOOKING_INTAKE_API_KEY) fixo no client
    ├── services/booking.service.ts         # bootstrap, slots, verify, appointments (create/list/cancel)
    ├── hooks/useBooking.ts                 # useClinicBootstrap, useAvailableSlots, useSendOtp,
    │                                        #   useConfirmOtp, useCreateAppointment, useMyAppointments, useCancelAppointment
    ├── store/CartContext.tsx               # carrinho multi-serviço + wizard step + sessão OTP (token/phone em memória, não localStorage)
    ├── components/ui/{Button,Input,Spinner,EmptyState,ErrorState}.tsx
    ├── components/ServiceList.tsx, ServiceCard.tsx
    ├── components/ProfessionalPicker.tsx
    ├── components/WeekPicker.tsx, TimeSlotGrid.tsx
    ├── components/CartSummary.tsx, CartAddedModal.tsx
    ├── components/CustomerInfoForm.tsx, OtpConfirmModal.tsx
    ├── components/MyAppointmentsModal.tsx
    ├── layouts/BookingLayout.tsx           # header (logo do salão + botão "Meus agendamentos")
    ├── pages/Home.tsx                      # /:clinicId
    ├── pages/Booking.tsx                   # /:clinicId/:serviceId (wizard controlado por estado, sem sub-rotas)
    ├── pages/NotFound.tsx
    └── utils/format.ts                     # moeda BRL, duração "1h:30min", telefone, data DD/MM/YYYY
```

**Regras de estado (fiel ao mapeamento em `prd/009-...md` §3.3):**
- Home busca `bootstrap` 1x (TanStack Query, `staleTime` alto) → lista de serviços com duração/preço.
- Wizard: seleção de profissional (se >1 ativo) → semana com setas ‹/› → slots do dia (`available-slots`, refetch a cada mudança de data/serviços do carrinho) → modal "Serviço adicionado" (Continuar / Adicionar + serviço / Ver carrinho) → carrinho (remover item) → nome + celular → **Finalizar** dispara `verify/send` e abre `OtpConfirmModal` → confirma código → `POST /appointments` → tela de sucesso.
- "Meus agendamentos": botão no header → modal pede celular → `verify/send` + `OtpConfirmModal` reutilizado → `verify/confirm` → `GET /my-appointments` → lista com cancelar (`POST /appointments/{id}/cancel`, reusa o mesmo token).
- 4 estados (loading/erro/vazio/sucesso) em toda tela com fetch, conforme `frontend/CLAUDE.md`.

---

## 4. Fora desta implementação (ver PRD §4)

- Pagamento/iugu, agenda por profissional (limite do `AvailabilityEngine` atual), SSR/OG por clínica, i18n.
- Provisionamento real do domínio e projeto Vercel (é uma ação de infraestrutura do dono, fora do repo).
