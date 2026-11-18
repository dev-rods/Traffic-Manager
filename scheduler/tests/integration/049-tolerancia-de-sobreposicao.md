# 049 - Edição pelo painel tolera até 15 min de sobreposição

Roteiro de conferência em **dev**, depois repetido como smoke em prod se
houver sessão de teste. Só o `PUT appointments/{id}` do painel ganha a
tolerância; criação, bot e site seguem com zero.

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev; API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
  --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
H=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")
C=clinicadepilacaopremium-3fbce9; S=<service_id>; AX=<area Axilas>
D=2026-11-25   # dia com availability_rule em dev (fixture do 045)
```

## Fixtures

```bash
# A às 16:30 (Axilas, 10 min → termina 16:40) e B às 16:40 (Axilas)
curl -s -X POST "${H[@]}" "$URL/appointments" -d "{\"clinicId\":\"$C\",\"phone\":\"5511999990049\",\"fullName\":\"Paciente Teste 049\",\"serviceId\":\"$S\",\"date\":\"$D\",\"time\":\"16:30\",\"serviceAreaPairs\":[{\"serviceId\":\"$S\",\"areaId\":\"$AX\"}]}"
curl -s -X POST "${H[@]}" "$URL/appointments" -d "{\"clinicId\":\"$C\",\"phone\":\"5511999990050\",\"fullName\":\"Vizinha Teste 049\",\"serviceId\":\"$S\",\"date\":\"$D\",\"time\":\"16:40\",\"serviceAreaPairs\":[{\"serviceId\":\"$S\",\"areaId\":\"$AX\"}]}"
A=<id de A>
```

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `PUT $URL/appointments/$A` `{"manualDurationMinutes":20}` (termina 16:50, invade B em 10) | **200** |
| 2 | `PUT ... {"manualDurationMinutes":25}` (16:55, invade 15) | **200** (limite inclusivo) |
| 3 | `PUT ... {"manualDurationMinutes":26}` (16:56, invade 16) | **409**, mensagem com "mais de 15 minutos" |
| 4 | `PUT ... {"manualDurationMinutes":null}` | 200, volta a 16:40 |
| 5 | `PUT ... {"time":"16:35"}` (16:35-16:45, invade 5) | 200 |
| 6 | `PUT ... {"time":"16:45"}` (16:45-16:55, dentro de B em 10) | 200 |
| 7 | `PUT ... {"time":"16:30"}` | 200, volta |
| 8 | `POST $URL/appointments` às 16:45 (criação) | **409** sem tolerância (mensagem antiga) |

```bash
curl -s -o /dev/null -w "%{http_code}\n" -X PUT "${H[@]}" "$URL/appointments/$A" -d '{"manualDurationMinutes":20}'
curl -s -w "\n%{http_code}\n" -X PUT "${H[@]}" "$URL/appointments/$A" -d '{"manualDurationMinutes":26}'
```

## Limpeza

`PUT ... {"status":"CANCELLED"}` em A e B (ou apagar pelo painel de dev).

## Resultado

Preencher ao rodar: data, stage, códigos obtidos por caso.
