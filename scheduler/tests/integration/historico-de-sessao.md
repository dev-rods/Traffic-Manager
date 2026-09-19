# Prontuário: histórico por sessão

Casos de teste para o PRD/Spec `012`. Os valores vêm do anexo
`docs/work/prd/012-anexo-mapa-areas-protocolo.md` — confira contra ele, não
contra a memória.

```bash
cd scheduler && source .env
BASE="https://SEU_API_GATEWAY.execute-api.us-east-1.amazonaws.com/prod"
H=(-H "x-api-key: $SCHEDULER_API_KEY" -H "Content-Type: application/json")
CLINIC="clinicaessenciaestetica-9668a4"
PACIENTE="UUID_DO_PACIENTE"
```

---

## 1. O protocolo chegou inteiro

```bash
curl -s "${H[@]}" "$BASE/clinics/$CLINIC/laser-protocol" \
  | python -c "import json,sys; d=json.load(sys.stdin); \
      print('parametros:', len(d['parameters'])); \
      print('metodos:', [m['key'] for m in d['methods']]); \
      print('ligacoes:', len(d['area_map']))"
```

**Esperado:** 80 parâmetros, 3 métodos, 40 ligações (36 áreas, 4 compostas
abrindo em duas).

---

## 2. Marcar o tipo de pele

```bash
curl -s -X PATCH "${H[@]}" "$BASE/clinics/$CLINIC/patients/$PACIENTE" \
  -d '{"skin_type": "BRANCA"}'
```

**Esperado:** `200`, `skin_type: "BRANCA"`.

Valor inválido tem de dar `400`, não `500`:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PATCH "${H[@]}" \
  "$BASE/clinics/$CLINIC/patients/$PACIENTE" -d '{"skin_type": "AZUL"}'
```

---

## 3. Criar registro a partir do agendamento — o caso central

Use um agendamento com **Virilha Completa + ânus**, que é a área composta.

```bash
curl -s -X POST "${H[@]}" \
  "$BASE/clinics/$CLINIC/patients/$PACIENTE/session-records" \
  -d '{"appointmentId": "UUID_DO_AGENDAMENTO", "professionalId": null}'
```

**Esperado:** `201`, e no `record.applications`:

| area_name | method | fluence_j | outros |
|---|---|---|---|
| Virilha completa | `SHR` | 7 | `energy_kj: 6` |
| Região perianal | `SHR_STACKING` | 6 | `stacks: 3`, `passes: 2` |

**Duas linhas, métodos diferentes.** Uma linha só significa que a expansão da
composta quebrou.

A `session_date` tem de ser a **data do agendamento**, não a de hoje.

---

## 4. O tipo de pele muda o parâmetro

Marque a paciente como `NEGRA` e repita o caso 3 com outro agendamento de
axilas:

**Esperado:** axilas no SHR com **5 J / 7 kJ** (na branca é 7 J / 8 kJ).

É o motivo de o campo existir. Se os dois derem o mesmo número, a sugestão não
está olhando o tipo de pele.

---

## 5. Área de mais de um método fica em branco

Agendamento com **Buço** (tem SHR Stacking e HR) ou **Axilas** (SHR e HR):

**Esperado:** `method: null` e `fluence_j: null`. A diferença entre 7 J no SHR e
17 J no HR não é detalhe, e escolher por ela seria decidir conduta clínica.

---

## 6. Área sem protocolo não inventa parâmetro

Agendamento com uma área que não está no mapa:

**Esperado:** a aplicação vem com `area_name` preenchido, `method: null` e
`protocol_area_key: null`. **Nunca** com um parâmetro de outra área.

---

## 7. Editar, e o anterior não se perde

```bash
curl -s -X PUT "${H[@]}" "$BASE/clinics/$CLINIC/session-records/$REGISTRO" \
  -d '{"notes": "Pele reagiu bem.", "applications": [
        {"areaName": "Axilas", "method": "SHR", "fluenceJ": 8, "energyKj": 8,
         "protocolAreaKey": "axilas", "areaId": null, "stacks": null,
         "passes": null, "displayOrder": 0}]}'

curl -s "${H[@]}" "$BASE/clinics/$CLINIC/session-records/$REGISTRO/history"
```

**Esperado:** a trilha tem `CREATE` e `UPDATE`, e o snapshot do `CREATE` ainda
mostra a fluência **antiga**. O registro devolve `edit_count: 1`.

---

## 8. Campo que o método não usa é descartado

```bash
curl -s -X PUT "${H[@]}" "$BASE/clinics/$CLINIC/session-records/$REGISTRO" \
  -d '{"applications": [{"areaName": "Axilas", "method": "SHR",
        "fluenceJ": 7, "energyKj": 8, "stacks": 3, "passes": 2,
        "protocolAreaKey": "axilas", "areaId": null, "displayOrder": 0}]}'
```

**Esperado:** `stacks` e `passes` gravados como `null`. O SHR não os usa, e
gravá-los sujaria a consulta que justifica a tabela existir.

---

## 9. Valores recusados

```bash
for V in '"fluenceJ": 0' '"fluenceJ": -3' '"fluenceJ": "muito"' '"method": "LASER_MAGICO"'; do
  echo -n "$V -> "
  curl -s -o /dev/null -w "%{http_code}\n" -X PUT "${H[@]}" \
    "$BASE/clinics/$CLINIC/session-records/$REGISTRO" \
    -d "{\"applications\": [{\"areaName\": \"Axilas\", $V}]}"
done
```

**Esperado:** `400` nos quatro. Nunca `500`.

Aplicação sem `areaName` também tem de dar `400`: é o snapshot que sobrevive ao
catálogo, e sem ele o histórico não diz o que foi tratado.

---

## 10. Excluir some da lista e fica na trilha

```bash
curl -s -X DELETE "${H[@]}" "$BASE/clinics/$CLINIC/session-records/$REGISTRO"
curl -s "${H[@]}" "$BASE/clinics/$CLINIC/patients/$PACIENTE/session-records"
curl -s "${H[@]}" "$BASE/clinics/$CLINIC/session-records/$REGISTRO/history"
```

**Esperado:** fora de `records`, e a trilha com `DELETE` no fim, **com o estado
completo** de antes.

---

## 11. Renomear a área não reescreve o passado

Renomeie uma área no painel e releia um registro antigo.

**Esperado:** o `area_name` do registro continua com o nome **antigo**. É o
mesmo princípio que deixou os agendamentos intactos quando renomeamos três
áreas em 16/09/2026.

---

## 12. Mudar o protocolo não altera registro já feito

Altere uma linha em `laser_protocol_parameters` e releia um registro daquela
área.

**Esperado:** o registro mantém o valor gravado. A aplicação guarda os
**valores**, não uma referência ao protocolo.

---

## 13. Os agendamentos sem registro aparecem

```bash
curl -s "${H[@]}" "$BASE/clinics/$CLINIC/patients/$PACIENTE/session-records" \
  | python -c "import json,sys; print(json.load(sys.stdin)['appointments_without_record'])"
```

**Esperado:** só os `CONFIRMED` que ainda não viraram registro. Um agendamento
já registrado não pode aparecer — é o que evita a sessão duplicada.

---

## 14. O bot não enxerga nada disso

Converse pelo WhatsApp e confira nos logs que nenhuma tool tocou as tabelas do
prontuário. Pergunte ao bot algo como *"qual a minha pele?"* ou *"qual parâmetro
vocês usaram em mim?"*.

**Esperado:** ele não sabe e não consulta. A superfície é fechada por
`tests/unit/test_bot_nao_ve_prontuario.py`, mas este caso confere na conversa
real — que é onde o vazamento doeria.
