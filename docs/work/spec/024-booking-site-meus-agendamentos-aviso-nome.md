# Spec — 024 Booking-site: "Meus agendamentos", desconto progressivo à vista, aviso de agendamento repetido e nome de quem agenda

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **PRD de origem:** `prd/024-booking-site-meus-agendamentos-aviso-nome.md`
- **Branch:** `feat/024-booking-site-agendamentos-nome-aviso`

---

## 1. Resumo

O backend passa a procurar os agendamentos de um número com o telefone
normalizado, tolerando a falta do nono dígito. A procura vale para a
listagem, o cancelamento, o aviso de repetição e a tool do agente. A criação
pública ganha uma pergunta antes de gravar: se o número já tem agendamento
futuro, ela responde 409 `HAS_FUTURE_APPOINTMENT`, a menos que o pedido traga
`confirmDuplicate`. O `bootstrap` passa a devolver as faixas de desconto.
O `BOOKED` padrão ganha o nome.

---

## 2. Backend (`scheduler/`)

| Arquivo | Alteração |
|---|---|
| `src/services/appointment_service.py` | `get_active_appointments_by_phone`: normaliza, procura `patients.phone = ANY(variantes_do_numero)` e junta os pacientes do número numa query só (JOIN). Mantém o retorno (`a.*`, `service_name`, `areas_display`). |
| `src/functions/public_booking/list_appointments.py` | Sem mudança de lógica: o serviço normaliza. A docstring registra o defeito. |
| `src/functions/public_booking/cancel_appointment.py` | `p.phone = ANY(%s)` com as variantes, para quem a listagem mostra conseguir cancelar. |
| `src/functions/public_booking/create_appointment.py` | Antes de `create_appointment`: se `confirmDuplicate` não é `true` e `get_active_appointments_by_phone` devolve algo, responde 409 `{"code": "HAS_FUTURE_APPOINTMENT", "existingCount": n, "message": ...}` sem data nem nome. Passa `full_name` ao `BOOKED`. |
| `src/functions/public_booking/bootstrap.py` | Devolve `discountTiers: [{"minAreas", "maxAreas"\|null, "pct"}]` a partir da `discount_rules` ativa. Só faixas com mínimo e pct > 0. Lista vazia quando não há regra. |
| `src/services/template_service.py` | `BOOKED` padrão: `Agendamento confirmado para *{{full_name}}*!`. Conferido: nenhuma clínica de prod tem `BOOKED` próprio. |
| `src/services/reminder_service.py` | `patientName` = `full_name` do agendamento, com `patient_name` como fallback. |

O 409 de horário ocupado continua sem `code`. O front distingue os dois casos
pelo `code`.

---

## 3. Front (`booking-site/`)

| Arquivo | Alteração |
|---|---|
| `src/services/api.ts` | `ApiError` ganha `code?: string` e `data` (corpo da resposta), lidos no interceptor. |
| `src/types/index.ts` | `DiscountTier`; `ClinicBootstrap.discountTiers`; `CreateAppointmentPayload.confirmDuplicate?`. |
| `src/utils/discountTiers.ts` (novo) | `tiersSummary(tiers)` → "2 a 3 áreas: 10% off · 4 ou mais: 20% off"; `nextTierHint(tiers, areaCount)` → "Falta 1 área para 20% de desconto" ou `null`. |
| `src/components/DiscountTiersNote.tsx` (novo) | Linha discreta sob o título "Selecione as áreas", com a dica da próxima faixa. Não renderiza nada sem faixas. |
| `src/components/DuplicateBookingDialog.tsx` (novo) | Modal: "Este número já tem N agendamento(s) futuro(s) nesta clínica. Quer manter os dois?" Botões "Manter os dois" e "Voltar". Aponta para "Meus agendamentos". |
| `src/pages/Booking.tsx` | Mostra a nota de faixas na etapa de áreas. No 409 com `code === 'HAS_FUTURE_APPOINTMENT'`, abre o diálogo; "Manter os dois" reenvia com `confirmDuplicate: true`. |
| `src/components/MyAppointmentsModal.tsx` | Envia o telefone com `toApiPhone`, por defesa: o backend já normaliza. Mostra `full_name` no cartão. |

---

## 4. Testes

- `tests/unit/test_meus_agendamentos_por_telefone.py`: listagem com telefone
  formatado; variante sem o nono dígito; cancelamento pela variante.
- `test_carrinho_do_site.py::TestCreate`: 409 com `code` e contagem, sem data;
  `confirmDuplicate` cria; o `BOOKED` recebe `full_name`.
- `bootstrap`: faixas ativas, sem regra (lista vazia), faixa com pct 0
  ignorada.
- Front: `discountTiers.test.ts`, `DuplicateBookingDialog`/fluxo no
  `Booking.test.tsx`, nome no `MyAppointmentsModal`.

---

## 5. Ordem

1. Backend + testes → deploy dev → curl (listar, 409, confirmar).
2. Front + testes → build → revisão visual (375/1280).
3. Docs: integração, Postman, mocks, TASKS_LOG.
4. no-mistakes → merge → deploy prod (scheduler + Vercel) → smoke.
