# Site público: próximas N datas (PRD `030`)

A pergunta: **o site oferece as próximas N datas com horário, atravessando a
virada do mês, e recusa o que não ofereceu?**

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/dev"
H=(-H "x-api-key: $BOOKING_API_KEY")
CLINIC="clinicadorods-da7b62"; SVC="<serviceId>"; AREA="<areaId>"
```

## 1. Grade

```bash
curl -s "${H[@]}" "$BASE/public/clinics/$CLINIC/availability?serviceIds=$SVC&serviceAreaPairs=$SVC:$AREA"
```

**Esperado:** `200`, `days` com no máximo `max_future_dates` datas (5 por
padrão), todas `AVAILABLE` com `slots`, em ordem, podendo cair no mês seguinte.
Sem `window`. Hoje aparece só se ainda houver horário à frente.

## 2. `dates` legado é ignorado

Mesma chamada com `&dates=2026-01-01`: mesma resposta.

## 3. Criação fora da grade

```bash
curl -s -X POST "${H[@]}" -H "Content-Type: application/json" \
  -d "{\"phone\":\"5511999990000\",\"fullName\":\"Teste 030\",\"serviceIds\":[\"$SVC\"],\"date\":\"2030-01-01\",\"time\":\"10:00\",\"serviceAreaPairs\":[{\"serviceId\":\"$SVC\",\"areaId\":\"$AREA\"}]}" \
  "$BASE/public/clinics/$CLINIC/appointments"
```

**Esperado:** `400` "Esta data não está disponível para agendamento online."
O mesmo para uma data oferecida com um horário que não está em `slots`.

## 4. Configuração

`PUT /clinics/{clinicId}` com `{"max_future_dates": 2}` (chave de admin) e
repetir o passo 1: `days` com 2 datas.
