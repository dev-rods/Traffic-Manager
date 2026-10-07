# Testes de Integração — Exclusão e Edição de Disponibilidade

Cobre os endpoints da task 009: `DELETE`/`PATCH` de availability rules e `DELETE` de exceptions.

## Setup

```bash
cd scheduler
source .env
BASE_URL="https://<api-id>.execute-api.us-east-1.amazonaws.com/dev"
CLINIC_ID="clinic-test"
AUTH=(-H "x-api-key: $SCHEDULER_API_KEY" -H "Content-Type: application/json")
```

> Nunca colar a API key nos comandos. Sempre via `$SCHEDULER_API_KEY` do `.env`.

---

## 1. Hard delete permite recadastrar o mesmo dia da semana

O caso que motivou a escolha por hard delete: com soft delete, a constraint
`uq_availability_rules_clinic_day` continuaria ocupada e este teste falharia com 409.

```bash
# Cria regra de Segunda
RULE_ID=$(curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-rules" "${AUTH[@]}" \
  -d '{"day_of_week":1,"start_time":"09:00","end_time":"18:00"}' | jq -r '.data.id')

# Exclui
curl -s -X DELETE "$BASE_URL/clinics/$CLINIC_ID/availability-rules/$RULE_ID" "${AUTH[@]}"
# Esperado: 200 {"status":"SUCCESS","message":"Regra excluida"}

# Recria no MESMO dia com outra faixa
curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-rules" "${AUTH[@]}" \
  -d '{"day_of_week":1,"start_time":"08:00","end_time":"17:00"}'
# Esperado: 201. Se vier 409, o delete nao removeu a linha de fato.
```

## 2. Isolamento multi-tenant

```bash
curl -s -o /dev/null -w "%{http_code}\n" \
  -X DELETE "$BASE_URL/clinics/outra-clinica-xyz/availability-rules/$RULE_ID" "${AUTH[@]}"
# Esperado: 404 (nao 200, nao 403 — nao vazar existencia entre tenants)
```

## 3. Regra inexistente e id malformado

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "$BASE_URL/clinics/$CLINIC_ID/availability-rules/00000000-0000-0000-0000-000000000999" "${AUTH[@]}"
# Esperado: 404

curl -s -o /dev/null -w "%{http_code}\n" -X DELETE \
  "$BASE_URL/clinics/$CLINIC_ID/availability-rules/nao-e-uuid" "${AUTH[@]}"
# Esperado: 400 "ruleId invalido" (antes: 500 pelo cast ::uuid explodindo)
```

## 4. Data fixa duplicada retorna 409, não 500

Regressão do `except UniqueViolation`, que indexava `DAY_NAMES[None]` e levantava
`TypeError` dentro do proprio except.

```bash
curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-rules" "${AUTH[@]}" \
  -d '{"rule_date":"2026-09-15","start_time":"09:00","end_time":"12:00"}'
# Esperado: 201

curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-rules" "${AUTH[@]}" \
  -d '{"rule_date":"2026-09-15","start_time":"09:00","end_time":"12:00"}'
# Esperado: 409 com mensagem legivel citando a data. NUNCA 500.
```

## 5. Duas faixas distintas na mesma data continuam válidas

O indice unico inclui `start_time` justamente para nao bloquear manha + tarde.

```bash
curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-rules" "${AUTH[@]}" \
  -d '{"rule_date":"2026-09-15","start_time":"14:00","end_time":"18:00"}'
# Esperado: 201
```

## 6. PATCH de horário

```bash
curl -s -X PATCH "$BASE_URL/clinics/$CLINIC_ID/availability-rules/$RULE_ID" "${AUTH[@]}" \
  -d '{"start_time":"10:00","end_time":"16:00"}'
# Esperado: 200 com a regra atualizada

curl -s "$BASE_URL/clinics/$CLINIC_ID/available-slots?date=2026-09-14&serviceId=<SERVICE_ID>" "${AUTH[@]}"
# Esperado: slots refletem a nova faixa
```

## 7. Validação de faixa invertida

Antes desta task, uma faixa invertida era aceita e gerava zero slots em silêncio.

```bash
curl -s -X PATCH "$BASE_URL/clinics/$CLINIC_ID/availability-rules/$RULE_ID" "${AUTH[@]}" \
  -d '{"start_time":"18:00","end_time":"09:00"}'
# Esperado: 400 "start_time must be earlier than end_time"

# PATCH parcial que inverte combinando com o valor ja gravado:
curl -s -X PATCH "$BASE_URL/clinics/$CLINIC_ID/availability-rules/$RULE_ID" "${AUTH[@]}" \
  -d '{"start_time":"23:00"}'
# Esperado: 400 (valida o intervalo final, nao so o campo enviado)

# Mesma validacao no create:
curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-rules" "${AUTH[@]}" \
  -d '{"day_of_week":3,"start_time":"18:00","end_time":"09:00"}'
# Esperado: 400
```

## 8. Exclusão de exceção

```bash
EXC_ID=$(curl -s -X POST "$BASE_URL/clinics/$CLINIC_ID/availability-exceptions" "${AUTH[@]}" \
  -d '{"exception_date":"2026-09-07","exception_type":"BLOCKED","reason":"Feriado"}' | jq -r '.data.id')

curl -s -X DELETE "$BASE_URL/clinics/$CLINIC_ID/availability-exceptions/$EXC_ID" "${AUTH[@]}"
# Esperado: 200

curl -s "$BASE_URL/clinics/$CLINIC_ID/availability-exceptions" "${AUTH[@]}" | jq '.data[].id'
# Esperado: $EXC_ID ausente
```

---

## Invocação local (sem deploy)

```bash
cd scheduler
serverless invoke local -s dev -f DeleteAvailabilityRule \
  -p tests/mocks/availability/delete_rule.json --aws-profile traffic-manager

serverless invoke local -s dev -f UpdateAvailabilityRule \
  -p tests/mocks/availability/update_rule.json --aws-profile traffic-manager

serverless invoke local -s dev -f DeleteAvailabilityException \
  -p tests/mocks/availability/delete_exception.json --aws-profile traffic-manager
```

Substituir `REPLACE_WITH_ENV_KEY` nos mocks pela key do `.env` antes de invocar,
e os UUIDs por ids reais do banco de dev.

---

## Checklist de UI (painel `/horarios`)

| Caso | Esperado |
|---|---|
| Excluir um chip de horário | Some imediatamente, antes da resposta da API |
| Toast "Desfazer" | Restaura o horário excluído |
| API falha no delete | Chip reaparece + toast de erro |
| Desfazer após recadastrar o mesmo dia | Toast de erro com a mensagem de 409, não falha silenciosa |
| Muitos dias fixos | Lista rola dentro de 320px; fade aparece só quando há corte |
| Lista curta | Sem scroll, sem área vazia, sem fade |
| Seleção múltipla | Contador correto; "Excluir selecionadas" remove todas as faixas das datas |
| Falha parcial em lote | Toast de erro com "N de M", nunca sucesso genérico |
| Editar horário | Salva via PATCH; modal não trava em loading |
| Query de exceções falha | `ErrorState` com retry, não o empty state "Nenhuma exceção" |
| Teclado | Chip e botão de excluir são focáveis e acionáveis por Enter/Espaço |
