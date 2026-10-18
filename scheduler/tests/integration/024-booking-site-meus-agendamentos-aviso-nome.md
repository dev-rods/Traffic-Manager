# Testes de integração — 024 Booking-site: "Meus agendamentos", faixas de desconto, aviso de repetido e nome

PRD: `docs/work/prd/024-booking-site-meus-agendamentos-aviso-nome.md` ·
Spec: `docs/work/spec/024-booking-site-meus-agendamentos-aviso-nome.md`

Rotas públicas da Lambda `PublicBooking`. Autenticação pela chave do
booking-site (`x-api-key`, a mesma de `VITE_BOOKING_API_KEY`), nunca copiada
para este arquivo.

## Preparação

```bash
source booking-site/.env   # VITE_API_BASE_URL e VITE_BOOKING_API_KEY de dev
BASE="$VITE_API_BASE_URL"; KEY="$VITE_BOOKING_API_KEY"
C="<clinic-id de dev com profissional e agenda>"   # ex.: a de mais regras em dev
SVC="<uuid de serviço com áreas>"; A1="<uuid área>"
FONE="(11) 90000-0024"   # fictício: a confirmação por WhatsApp não chega a ninguém
```

O `token` de "Meus agendamentos" sai de `/verify/confirm`. O código vai por
WhatsApp, e por isso não chega a um número fictício. Para testar com ele, gere
o token com o `BOOKING_VERIFICATION_SECRET` do stage. É o mesmo formato de
`booking_verification._issue_token`: base64url de `clinic|telefone
normalizado|expira|hmac`.

Mocks para `serverless invoke local`: `tests/mocks/public_booking/bootstrap.json`,
`create_appointment_confirma_repetido.json`, `my_appointments_telefone_formatado.json`.

---

## 1. Faixas de desconto — `GET /public/clinics/{clinicId}/bootstrap`

| # | Caso | Esperado |
|---|------|----------|
| 1.1 | Clínica com faixas 2 e 3 | `discountTiers` = `[{minAreas: t2_min, maxAreas: t3_min-1, pct: t2}, {minAreas: t3_min, maxAreas: null, pct: t3}]` |
| 1.2 | `tier_2_max_areas` diferente de `t3_min-1` | Igual a 1.1: o anúncio segue a cobrança (`decide`), não o teto gravado |
| 1.3 | Só a faixa 2 com pct > 0 | Uma faixa, `maxAreas: null` |
| 1.4 | Sem `discount_rules` ativa | `discountTiers: []`; o site não mostra a nota |

```bash
curl -s "$BASE/public/clinics/$C/bootstrap" -H "x-api-key: $KEY" | jq .discountTiers
```

## 2. Aviso de agendamento repetido — `POST /public/clinics/{clinicId}/appointments`

| # | Caso | Esperado |
|---|------|----------|
| 2.1 | Número sem agendamento futuro | 201, sem aviso |
| 2.2 | Número com agendamento futuro, sem `confirmDuplicate` | 409 `{"code":"HAS_FUTURE_APPOINTMENT","existingCount":n}`; nada criado; nenhum WhatsApp |
| 2.3 | O 409 não vaza agenda | Corpo sem data, horário, serviço nem nome do agendamento existente |
| 2.4 | Com `"confirmDuplicate": true` | 201 |
| 2.5 | `confirmDuplicate` `"true"`/`1` | 409 (só o booleano `true` confirma) |
| 2.6 | Horário ocupado | 409 **sem** `code` (o site volta para a agenda) |
| 2.7 | Confirmação no WhatsApp | Começa com `Agendamento confirmado para *<nome digitado>*!` |

```bash
BODY="{\"phone\":\"$FONE\",\"fullName\":\"Teste 024 Bia\",\"serviceIds\":[\"$SVC\"],\"serviceAreaPairs\":[{\"serviceId\":\"$SVC\",\"areaId\":\"$A1\"}],\"date\":\"<livre>\",\"time\":\"<livre>\"}"
curl -s -X POST "$BASE/public/clinics/$C/appointments" -H "x-api-key: $KEY" -H 'content-type: application/json' -d "$BODY"
```

## 3. Meus agendamentos — `GET /public/clinics/{clinicId}/my-appointments`

| # | Caso | Esperado |
|---|------|----------|
| 3.1 | `phone` formatado `(11) 9xxxx-xxxx` | 200 com os agendamentos (antes da 024: lista vazia) |
| 3.2 | `phone` normalizado `5511…` | 200, mesma lista |
| 3.3 | Paciente gravado sem o nono dígito (DDD fora de 11-28) | Aparece para quem digita com o 9 |
| 3.4 | São Paulo sem o 9 | Não casa (seria outra pessoa) |
| 3.5 | Dois agendamentos com nomes diferentes no mesmo número | Cada item com o próprio `full_name` |
| 3.6 | Cancelar um item da lista | 200 `CANCELLED` (mesmas variantes de telefone) |

```bash
curl -s -G "$BASE/public/clinics/$C/my-appointments" -H "x-api-key: $KEY" \
  --data-urlencode "phone=$FONE" --data-urlencode "token=$TOKEN" | jq '.appointments[] | {full_name, appointment_date, start_time}'
```

## 4. Site

| # | Caso | Esperado |
|---|------|----------|
| 4.1 | Etapa de áreas, clínica com faixas | "Desconto progressivo · 2 a 3 áreas: 10% off · 4 ou mais áreas: 20% off" |
| 4.2 | 1 área marcada | "Falta 1 área para 10% de desconto" |
| 4.3 | Na última faixa | Sem dica |
| 4.4 | Número com agendamento futuro | Modal "Você já tem agendamento"; "Manter os dois" cria; "Voltar" fecha sem criar |
| 4.5 | "Meus agendamentos" | Nome de quem agendou em cada cartão |

## Resultado (dev, 18/10/2026)

Clínica `clinicadorods-da7b62`, telefone fictício:

- 1º agendamento: 201, `full_name` gravado.
- 2º sem confirmar: 409 `HAS_FUTURE_APPOINTMENT`, `existingCount: 1`.
- 2º confirmado: 201.
- Listagem com `(11) 90000-0024` devolveu os dois, cada um com o seu nome.
- Os dois foram cancelados.
- `discountTiers` da `clinicaessenciaestetica-9668a4`:
  `[{2, 4, 10}, {5, null, 15}]`.
- Site em 375 e 1280 px: nota de faixas e modal, sem overflow nem erro de
  console.
