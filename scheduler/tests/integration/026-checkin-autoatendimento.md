# Testes de integração — 026 Check-in de autoatendimento com pagamento

PRD: `docs/work/prd/026-checkin-autoatendimento.md` ·
Spec: `docs/work/spec/026-checkin-autoatendimento.md`

Rotas da Lambda `PublicBooking`. Chave do booking-site (`x-api-key`) e token
do código de WhatsApp (`verify/confirm`), nunca copiados para este arquivo.
Só **dev** nesta fase; dev usa o Asaas **sandbox** (`/dev/ASAAS_API_KEY`) e,
sem chave, o provedor **simulado**.

## Preparação

```bash
source booking-site/.env   # VITE_API_BASE_URL e VITE_BOOKING_API_KEY de dev
BASE="$VITE_API_BASE_URL"; KEY="$VITE_BOOKING_API_KEY"
C="<clinic-id de dev com profissional e agenda>"
PHONE="5511900000026"      # fictício: o WhatsApp não chega a ninguém
TOKEN="<token de verify/confirm>"
CK="$BASE/public/clinics/$C/checkin"
```

Com número fictício o código não chega; gere o token com o
`BOOKING_VERIFICATION_SECRET` do stage, no formato de
`booking_verification._issue_token`. Crie antes um agendamento para o número
(`POST /appointments` com `confirmDuplicate: true`) e cancele no fim.

Rota nova no API Gateway: depois do `serverless deploy`, rode
`aws apigateway create-deployment` no stage (ver a memória do projeto), senão
a rota responde 403 `Missing Authentication Token`.

Mocks para `serverless invoke local`: `tests/mocks/public_booking/checkin_*.json`.

---

## 1. Agendamentos do número — `GET checkin/appointments?phone&token`

| # | Caso | Esperado |
|---|------|----------|
| 1.1 | Token válido | 200; próximos confirmados (até 5), com `fullName`, `date`, `startTime`, `areas`, `finalPriceCents`, `checkedInAt`, `payment` |
| 1.2 | Token de outro número ou vencido | 401 |
| 1.3 | Sem `phone`/`token` | 400 |
| 1.4 | Número sem agendamento | 200, lista vazia |

```bash
curl -s -G "$CK/appointments" -H "x-api-key: $KEY" --data-urlencode "phone=$PHONE" --data-urlencode "token=$TOKEN"
```

## 2. Confirmar — `POST checkin/appointments/{id}/confirm`

| # | Caso | Esperado |
|---|------|----------|
| 2.1 | Agendamento do número | 200 `{checkedIn: true, payerCpfKnown}`; grava `checked_in_at` uma vez |
| 2.2 | Agendamento de outro número / id inválido | 404 |
| 2.3 | Cadastro com CPF, mas o agendamento é de outra pessoa do mesmo número | `payerCpfKnown: false` |

## 3. Pagar — `POST checkin/appointments/{id}/payments`

| # | Caso | Corpo | Esperado |
|---|------|-------|----------|
| 3.1 | CPF desconhecido | `{method: "PIX"}` | 400 "Informe o CPF de quem vai pagar." |
| 3.2 | CPF com dígito errado | `cpf: "529.982.247-24"` | 400 "Confira o CPF…" |
| 3.3 | Pix | `method: "PIX", cpf` | 201; `status: PENDING`, `pixPayload` |
| 3.4 | Crédito / débito | `CREDIT_CARD` / `DEBIT_CARD` | 201; `invoiceUrl` (débito sai na fatura do Asaas) |
| 3.5 | Dinheiro | `CASH` | 201; `status: AWAITING_CASH` |
| 3.6 | Mesmo método de novo | igual a 3.3 | mesmo `id`, sem nova cobrança |
| 3.7 | Troca de método | Pix e depois crédito | Pix vira `CANCELLED` (cancelado no provedor), crédito `PENDING` |
| 3.8 | Já pago | qualquer | devolve o pago, sem nova cobrança |
| 3.9 | Sem valor gravado | — | 400 "…combinado na recepção." |
| 3.10 | Prod sem `ASAAS_API_KEY` | — | 503 |

## 4. Status — `GET checkin/payments/{id}?phone&token`

Pendente no Asaas: o backend consulta o Asaas (rede para webhook atrasado).
Outro número: 404/401.

## 5. Simular (só teste) — `POST checkin/payments/{id}/simulate`

Simulado, qualquer método: 200 `status: PAID`. Asaas sandbox: Pix 200 `PAID`
(confirma pelo `/sandbox/payment/{id}/confirm` e o webhook chega); cartão 400
(pague a fatura com o cartão de teste). Asaas de produção: 404.

## 6. Baixa em dinheiro (recepção) — `POST /clinics/{clinicId}/caixa/pagamentos/{id}/dinheiro`

Lambda `Caixa` (fase 2), não a rota pública: `checkin/payments/{id}/cash-received`
responde 404. Auth do painel com `agenda.escrever` (recepção). Só
`AWAITING_CASH`; chama `receiveInCash` no Asaas e marca `PAID`. Já pago: 200 sem
nova baixa; outro status: 409; pagamento de outra clínica: 404. O resumo (`GET caixa/resumo?date_from&date_to`)
é só do admin.

## 7. Webhook do Asaas — `POST /public/asaas/webhook`

| # | Caso | Esperado |
|---|------|----------|
| 7.1 | Sem header / token errado / segredo não configurado | 401 |
| 7.2 | `PAYMENT_RECEIVED`/`PAYMENT_CONFIRMED` de cobrança nossa | 200; pagamento `PAID` |
| 7.3 | Mesmo `id` de evento de novo | 200 `repetido` |
| 7.4 | `PAYMENT_DELETED` depois de pago | não volta a cancelado |
| 7.5 | Pago de uma cobrança já trocada | ela vira a viva; a outra é cancelada |
| 7.6 | Cobrança que não é nossa | 200 `ignorado` |

## Resultado (dev, 19/10/2026)

`clinicadorods-da7b62`, telefone fictício, provedor simulado:

- **Sem token:** 401.
- **Lista:** veio com nome, áreas e valor.
- **Check-in:** gravou o horário e respondeu `payerCpfKnown: false`.
- **CPF:** sem CPF, 400; com dígito errado, 400.
- **Pix:** 201 com o "copia e cola".
- **Troca para cartão:** criou a fatura e o Pix virou `CANCELLED`.
- **Simulação:** `PAID`.
- **Nova cobrança:** pedir dinheiro depois devolveu o pagamento de cartão já pago.
- **Webhook sem token:** 401.
- **Outro número:** 401.
- **Limpeza:** agendamento cancelado.

Site `checkin-dev-ten.vercel.app` em iPad retrato (820×1180) e paisagem
(1180×820): fluxo completo até "Tudo certo", sem overflow nem erro de console.

## Resultado com o Asaas sandbox (dev, 28/10/2026)

Webhook cadastrado na conta sandbox para `/dev/public/asaas/webhook`, com
`authToken`. Telefone fictício `5511900000026`, CPF de teste válido:

- **Pix:** `201 PENDING` com "copia e cola" real; "Simular pagamento" deu
  `200 PAID`, e o webhook `PAYMENT_RECEIVED` chegou.
- **Troca Pix → cartão:** o Pix virou `CANCELLED` (`DELETE` no Asaas; webhook
  `PAYMENT_DELETED` registrado e ignorado, porque já estava cancelado). A
  fatura do sandbox foi gerada.
- **Simular cartão:** `400`. O sandbox não confirma cartão por API; a fatura
  foi paga com o cartão 4444 4444 4444 4444 (`payWithCreditCard`), o webhook
  `PAYMENT_CONFIRMED` chegou e o status virou `PAID`.
- **Já pago:** pedir Pix depois devolveu o cartão pago, sem nova cobrança.
- **Dinheiro:** `AWAITING_CASH`; a baixa pelo `caixa/pagamentos/{id}/dinheiro`
  (chave do painel) deu `PAID` e chamou `receiveInCash` no Asaas.
- **Caixa do dia:** os recebimentos aparecem marcados como teste.
- **Limpeza:** os agendamentos foram cancelados.

Antes da chave Pix existir na conta sandbox, o `pixQrCode` respondia 400
("Você não possui uma chave Pix cadastrada"). O check-in respondeu 502 e
cancelou a cobrança órfã, como previsto.

