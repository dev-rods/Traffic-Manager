# 050 - Desconto por valor ou percentual com centavos

Roteiro de conferência em **dev**, depois prod. Só o painel manda
`discountCents`; bot e site seguem com a política automática.

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev; API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
  --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
H=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")
C=clinicadepilacaopremium-3fbce9; S=<service_id>; AX=<area Axilas>; AX2=<segunda área>
D=2026-11-27   # dia com availability_rule em dev (fixture do 049)
```

Migration antes do deploy: `setup_database.py` com `/dev/SUPABASE_DB_*`
(coluna `discount_cents` e CHECK `appointments_discount_cents_positivo`).

## Fixture

```bash
curl -s -X POST "${H[@]}" "$URL/appointments" -d "{\"clinicId\":\"$C\",\"phone\":\"5511999990050\",\"fullName\":\"Paciente Teste 050\",\"serviceId\":\"$S\",\"date\":\"$D\",\"time\":\"18:00\",\"serviceAreaPairs\":[{\"serviceId\":\"$S\",\"areaId\":\"$AX\"}]}"
A=<id>; ORIG=<original_price_cents>
```

## Casos

| # | Chamada (`PUT $URL/appointments/$A`) | Esperado |
|---|---|---|
| 1 | `{"discountPct": 12.5, "discountReason": "custom"}` | 200; `discount_pct 12.50`, `discount_cents null`, `final = trunc(ORIG*0.875)` |
| 2 | `{"discountPct": "12,5", "discountReason": "custom"}` | 200, igual ao 1 |
| 3 | `{"discountCents": 2000, "discountReason": "custom"}` | 200; `discount_cents 2000`, `discount_pct` = equivalente, `final = ORIG - 2000` |
| 4 | `{"discountCents": 999999, "discountReason": "custom"}` | **400** "maior que o valor" |
| 5 | `{"discountPct": 10, "discountCents": 100}` | **400** "nao os dois" |
| 6 | `{"serviceId": S, "serviceAreaPairs": [AX, AX2]}` com o desconto do caso 3 | 200; `final = novo ORIG - 2000`; `discount_pct` reescrito |
| 7 | `{"discountPct": 0, "discountReason": null}` | 200; `discount_cents null`, `final = ORIG` |
| 8 | `POST $URL/appointments {... "discountCents": 500, "discountReason": "custom"}` às 18:30 | 201; `discount_cents 500` |
| 9 | `GET $URL/clinics/$C/appointments?date=$D` e `GET $URL/clinics/$C/dashboard` | `discount_cents` presente |
| 10 | `{"discountCents": 0}` / `{"discountCents": "20,00"}` / `{"discountPct": 12.555}` | **400** |

```bash
put(){ curl -s -w "\n%{http_code}\n" -X PUT "${H[@]}" "$URL/appointments/$A" -d "$1"; }
put '{"discountCents": 2000, "discountReason": "custom"}' | python -X utf8 -c "import sys,json; l=sys.stdin.read().split(chr(10)); a=json.loads(l[0])['appointment']; print(l[1], a['discount_pct'], a['discount_cents'], a['original_price_cents'], a['final_price_cents'])"
```

## Painel (smoke)

1. Editar a fixture → Personalizado → **R$** → `20` → resumo mostra "Desconto (R$ 20,00)" e total exato → Salvar → Confirmar.
2. Reabrir: R$ selecionado com `20,00`. Popover mostra `-R$ 20,00 (personalizado)`.
3. Personalizado → **%** → `12,5` → Salvar → reabrir mostra `12,5`.
4. Duração: Ajustar → apagar → o campo fica e diz "Informe a duração ou volte ao cálculo" → Salvar acusa → digitar `45` → Salvar grava.

## Limpeza

`PUT ... {"status":"CANCELLED"}` na fixture e no agendamento do caso 8.

## Resultado

Preencher ao rodar: data, stage, códigos por caso.
