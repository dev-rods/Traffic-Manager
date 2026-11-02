# Reagendamento não é cancelamento (PRD/Spec `035`)

A pergunta: **quem muda de dia continua contando como "tem sessão marcada", e
só quem desmarcou sem remarcar aparece em "Cancelamentos"?**

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/dev"
HA=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")           # painel
HS=(-H "x-api-key: $BOOKING_API_KEY" -H "Content-Type: application/json")   # site
CLINIC="clinicadorods-da7b62"; SVC="<serviceId>"; AREA="<areaId>"
FONE="5511999990035"
```

Antes de tudo, a migration: `python -m src.scripts.setup_database` (dev). Confirmar
`rescheduled_to_id` em `scheduler.appointments`.

## 1. Remarcar pelo site não gera cancelamento

Pedir o código e confirmar: `POST $BASE/public/clinics/$CLINIC/verify/send` com
`{"phone":"$FONE"}` e `POST .../verify/confirm` com `{"phone","code"}` -> `TOKEN`.

```bash
# criar pelo site (ou pelo painel) para a data D1
curl -s "${HS[@]}" "$BASE/public/clinics/$CLINIC/my-appointments?phone=$FONE&token=$TOKEN"
```

**Esperado:** cada agendamento traz `service_ids`, `service_area_pairs` e
`total_duration_minutes`. Guardar `APPT`.

```bash
curl -s "${HS[@]}" "$BASE/public/clinics/$CLINIC/availability?serviceIds=$SVC&serviceAreaPairs=$SVC:$AREA&excludeAppointmentId=$APPT"
```

**Esperado:** o dia D1 oferece o próprio horário do agendamento como livre (sem
`excludeAppointmentId` ele some).

```bash
curl -s -X POST "${HS[@]}" -d "{\"phone\":\"$FONE\",\"token\":\"$TOKEN\",\"date\":\"<D2>\",\"time\":\"<hora>\"}" \
  "$BASE/public/clinics/$CLINIC/appointments/$APPT/reschedule"
```

**Esperado:** `200`, `appointment.id == APPT`, `appointment_date == D2`. Em
`GET /clinics/$CLINIC/appointments?date=D1` (painel) não há nenhum `CANCELLED`
para esse telefone.

Erros: token de outro número -> `404`; token expirado -> `401`; horário já
ocupado -> `409 "Esse horário acabou de ser ocupado. Escolha outro."`; data
passada -> `400`.

## 2. Cancelar e criar em seguida vira vínculo, por qualquer canal

```bash
curl -s -X PUT "${HA[@]}" -d '{"status":"CANCELLED"}' "$BASE/appointments/$APPT"
curl -s -X POST "${HA[@]}" -d "{\"clinicId\":\"$CLINIC\",\"phone\":\"$FONE\",\"fullName\":\"Teste 035\",\"serviceIds\":[\"$SVC\"],\"serviceAreaPairs\":[{\"serviceId\":\"$SVC\",\"areaId\":\"$AREA\"}],\"date\":\"<D3>\",\"time\":\"<hora>\"}" "$BASE/appointments"
```

**Esperado:** `201` com `appointment.rescheduled_from_id == APPT`. Em
`GET /clinics/$CLINIC/appointments?date=D2`, o `APPT` está `CANCELLED` com
`rescheduled_to_id = <novo>` e `rescheduled_to_date = D3`. O log do
`CreateAppointment` tem `[Reagendamento] antecessor=... novo=...`.

Mesma coisa criando pelo site (`POST /public/.../appointments`) ou pelo bot.

Cancelar e criar **depois de 30 min**, ou para **outro paciente** do mesmo
telefone: sem vínculo (cancelamento de verdade).

## 3. Relatórios separam os três desfechos

```bash
curl -s "${HA[@]}" "$BASE/clinics/$CLINIC/dashboard?date=<D2>"
curl -s "${HA[@]}" "$BASE/clinics/$CLINIC/reports?period=current_month"
curl -s "${HA[@]}" "$BASE/clinics/$CLINIC/agenda-summary?start=<D1>&end=<D3>"
```

**Esperado:** o par do passo 2 conta `rescheduled_appointments = 1` (dashboard
e reports) e `rescheduled = 1` no dia D2 do agenda-summary, com
`cancelled = 0` e `lost_cents = 0` nesse dia. Um cancelamento sem criação
posterior conta em `cancelled` e em `lost_cents`. Uma falta (`PUT status
NO_SHOW`) não entra em nenhum dos dois.

## 4. Conversão do Google Ads acompanha a pessoa

Com um lead com `gclid` para `$FONE`: depois do passo 2,
`SELECT appointment_id FROM scheduler.lead_conversions WHERE appointment_id IN (APPT, novo)`
devolve **uma** linha, apontando para o novo. Nada em "aguardando" para o `APPT`.

## 5. Backfill

```bash
python -m src.scripts.backfill_reagendamentos $CLINIC            # lista, não grava
python -m src.scripts.backfill_reagendamentos $CLINIC --aplicar
python -m src.scripts.backfill_reagendamentos $CLINIC --aplicar  # "ligados: 0"
```

**Esperado em prod (Essência):** o dry-run lista os pares medidos em 01/11/2026
(37, menos os de importação de 08 e 09/09). Depois do `--aplicar`, o relatório
de outubro mostra os cancelamentos reduzidos na mesma proporção.

## 6. Lembrete

Com site configurado, o bloco de prompt do lembrete diz "por lá ela remarca ou
cancela em um minuto". Conferir em `tests/unit/test_lembrete*.py` ou numa
conversa de dev respondendo "quero mudar o dia" ao lembrete: o bot manda o link.

## 7. Stack

Depois do deploy em dev: `aws cloudformation describe-stack-resources
--stack-name clinic-scheduler-infra-dev --query 'length(StackResources)'`
abaixo de 500 (estava em 435 antes da rota nova).
