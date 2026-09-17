# Duração manual do agendamento

Casos de teste para o override de duração por agendamento (PRD/Spec `011`).

A pergunta que todos estes casos respondem é uma só: **a duração que uma pessoa
fixou sobrevive ao que o sistema faz com o agendamento, e a regra da clínica
continua intacta?**

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/prod"
H=(-H "x-api-key: $SCHEDULER_API_KEY" -H "Content-Type: application/json")
CLINIC="clinicaessenciaestetica-9668a4"
```

Guarde a regra da clínica antes de começar — o critério final é ela não ter
mudado:

```bash
curl -s "${H[@]}" "$BASE/clinics/$CLINIC/duration-rules" | tee /tmp/regra-antes.json
```

---

## 1. Criar com duração fixada

A regra da Essência tem teto de 50 minutos. Pedir 75 é o caso que motivou a task.

```bash
curl -s -X POST "${H[@]}" "$BASE/appointments" -d '{
  "clinicId": "'$CLINIC'",
  "phone": "5511999990000",
  "serviceId": "SERVICE_UUID",
  "date": "2026-10-01",
  "time": "14:00",
  "serviceAreaPairs": [{"serviceId":"SERVICE_UUID","areaId":"AREA_UUID"}],
  "isFirstVisit": false,
  "manualDurationMinutes": 75
}'
```

**Esperado:** `201`, `manual_duration_minutes: 75`, `total_duration_minutes: 75`,
`end_time: "15:15:00"`.

❌ **Falha conhecida se o teto voltar a valer:** `total_duration_minutes: 50` e
`end_time: "14:50:00"`.

---

## 2. Fixar a duração de um agendamento existente

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/$APPT_ID" \
  -d '{"manualDurationMinutes": 75}'
```

**Esperado:** `200`, `end_time` recalculado, `messages` contendo `duração`.

---

## 3. Remarcar NÃO pode perder o override

O caso central. Antes desta task, 75 virava 50 aqui.

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/$APPT_ID" \
  -d '{"date": "2026-10-08", "time": "09:00"}'

curl -s "${H[@]}" "$BASE/appointments?clinicId=$CLINIC&date=2026-10-08"
```

**Esperado:** `manual_duration_minutes: 75`, `total_duration_minutes: 75`,
`start_time 09:00`, `end_time 10:15`.

**Confira também:** `total_duration_minutes` e `end_time` **concordam**. Até
16/09/2026 o reschedule mudava o `end_time` e deixava a coluna com o valor velho,
e isso acontecia **mesmo sem override**.

---

## 4. Remarcar SEM override continua normalizando

A correção não pode desligar a normalização de agendamento antigo.

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/$OUTRO_APPT" \
  -d '{"date": "2026-10-08", "time": "11:00"}'
```

**Esperado:** a duração passa por piso/teto/passo da clínica, como sempre.

---

## 5. Trocar as áreas descarta o override

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/$APPT_ID" -d '{
  "serviceId": "SERVICE_UUID",
  "serviceAreaPairs": [{"serviceId":"SERVICE_UUID","areaId":"OUTRA_AREA_UUID"}]
}'
```

**Esperado:** `200`, `manual_duration_minutes: null`, duração de volta ao
calculado, e `message` citando **"duração manual descartada (as áreas mudaram)"**
— a atendente precisa saber por que o valor sumiu.

---

## 6. Soltar o override volta ao CÁLCULO

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/$APPT_ID" \
  -d '{"manualDurationMinutes": null}'
```

**Esperado:** `manual_duration_minutes: null` e `total_duration_minutes` igual ao
que a regra calcula para as áreas gravadas — **não** ao último valor.

⚠️ `null` explícito é o que solta. Omitir o campo não mexe em nada: são coisas
diferentes, e o handler distingue com `"manualDurationMinutes" in body`.

---

## 7. Valores recusados

```bash
for V in 0 4 481 -10 '"abc"' 3.5; do
  echo -n "$V -> "
  curl -s -o /dev/null -w "%{http_code}\n" -X PUT "${H[@]}" \
    "$BASE/appointments/$APPT_ID" -d "{\"manualDurationMinutes\": $V}"
done
```

**Esperado:** `400` nos seis, com mensagem citando a faixa 5–480. Nunca `500` —
dedo errado no formulário não é falha do servidor.

---

## 8. Conflito com a paciente seguinte

Com um agendamento às 15:00, fixar 240 minutos no das 14:00:

```bash
curl -s -X PUT "${H[@]}" "$BASE/appointments/$APPT_ID" \
  -d '{"manualDurationMinutes": 240}'
```

**Esperado:** `409`, com a mensagem citando a duração e o intervalo.

---

## 9. O bot enxerga a sala ocupada pela duração manual

Com um agendamento de 75 min às 14:00:

```bash
curl -s "${H[@]}" "$BASE/availability/slots?clinicId=$CLINIC&date=2026-10-01&totalDuration=30"
```

**Esperado:** nenhum horário entre 14:00 e 15:15. O motor de disponibilidade
bloqueia por `end_time`, então ele respeita o override sem saber que ele existe.

---

## 10. A regra da clínica ficou intacta — o critério do André

```bash
curl -s "${H[@]}" "$BASE/clinics/$CLINIC/duration-rules" > /tmp/regra-depois.json
diff /tmp/regra-antes.json /tmp/regra-depois.json && echo "OK: regra inalterada"
```

**Esperado:** sem diferença nenhuma, depois de todos os casos acima.

---

## 11. O bot continua sem opinar sobre duração

Agende pelo WhatsApp e confira que o agendamento criado tem
`manual_duration_minutes: null`. Nenhuma tool do agente expõe o campo; se algum
dia aparecer um agendamento do bot com override, a fiação quebrou.
