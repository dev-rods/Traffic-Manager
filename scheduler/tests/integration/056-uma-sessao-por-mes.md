# 056 - Uma sessão por mês, código sempre no site

Regra única em `AppointmentService`: criar ou mover a data para um mês em que
a paciente já tem sessão `CONFIRMED` futura responde 409
`SAME_MONTH_APPOINTMENT` com a sessão existente. Cada tela avisa ("sua sessão
de X será cancelada e remarcada para Y") e repete o pedido com
`substituir: true`: a existente sai com o desfecho da antecedência (PRD 054:
falta nas últimas 24 h) e a nova nasce vinculada, levando pagamento vivo,
link dos documentos e conversão. Mês diferente nunca interfere.

Só ADMIN, pelo painel, mantém as duas (`manterAsDuas` + `motivoDasDuas`,
gravados em `second_in_month_by/_reason`). O bot nunca; `segunda_sessao` saiu.

Criar pelo site passa a exigir `token` de `verify/confirm` (401 sem ele).

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
API=https://tuvr5sfhz3.execute-api.us-east-1.amazonaws.com/dev
KEY=$(get /dev/SCHEDULER_API_KEY)          # painel (ADMIN, chave mestra)
BKEY=$(get /dev/BOOKING_INTAKE_API_KEY)    # site
C=<clinic_id>; FONE=5511999990056
```

Migração antes do deploy: `python src/scripts/setup_database.py` com
`RDS_*` de `/dev/SUPABASE_DB_*` (colunas `second_in_month_by/_reason`).

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | Site: `POST public/clinics/$C/appointments` sem `token` | 401 |
| 2 | Site: `verify/send` (dev devolve `devCode` com o WhatsApp fora) e `verify/confirm` → `token`; criar com token em mês livre | 201 |
| 3 | Site: criar com token para OUTRA data no mesmo mês | 409 `SAME_MONTH_APPOINTMENT`, `existing` com `id/date/time/areas` |
| 4 | Site: o mesmo pedido com `"substituir": true` | 201 "remarcado"; antigo `CANCELLED` (ou `NO_SHOW` se < 24 h) com `rescheduled_to_id`; novo com `rescheduled_from_id` |
| 5 | Site: criar no mês seguinte com sessão neste | 201, nada cancelado |
| 6 | Painel STAFF: `POST /appointments` no mesmo mês | 409 com `existing.patientName`; com `manterAsDuas` → 403 |
| 7 | Painel ADMIN: `manterAsDuas` sem motivo | 400; com `motivoDasDuas` → 201 e colunas gravadas |
| 8 | Painel: `PUT /appointments/{id}` com `date` em mês ocupado | 409; com `substituir` cancela a outra e remarca |
| 9 | Bot (unit): `test_bot_mesmo_mes.py` | mesmo mês recusa sem saída; outro mês cria com `sessao_anterior_mantida` |
| 10 | Browser: site de dev (`checkin-dev`/preview) agenda com código; conflito mostra o aviso com `wa.me`; painel mostra o aviso inline | sem erro |
| 11 | Relatório (`GET clinics/$C/reports/...`): a troca conta como remarcação; antigo < 24 h conta como falta | |

## Resultado

(preencher no deploy em dev)
