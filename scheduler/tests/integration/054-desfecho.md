# 054 - Cancelamento, falta e remarcação pela antecedência; relatórios sem falta

Roteiro em **dev**, depois prod. Migration de três colunas
(`rescheduled_from_id`, `outcome_overridden_by`, `outcome_reason`) via
`setup_database.py` com `/{stage}/SUPABASE_DB_*`. Sem Lambda nova.

A linha das 24 h é contada até a **abertura da agenda do dia** (o `start_time`
das `availability_rules` daquele dia), não até a hora da sessão. Em dev as
regras são por data (`rule_date`) e abrem às 15:30/16:00; uma sessão de HOJE à
noite já está dentro das 24 h.

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev; API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
  --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
H=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")
C=clinicadepilacaopremium-3fbce9; S=<service_id>
```

Script equivalente: `valida_054.py` (Python/urllib) no scratchpad da sessão.

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `PUT {A}` `{status: CANCELLED}`, A daqui a 5 dias | `outcome CANCELLED`, mensagem "cancelado" |
| 2 | idem, A hoje à noite | `outcome NO_SHOW`, mensagem "Falta registrada: menos de 24 h..." |
| 3a | caso 2 + `outcome: CANCELLED` sem motivo | 400 "informe o motivo" |
| 3b | idem com `outcomeReason` | 200, `CANCELLED`, `outcome_reason` gravado |
| 4 | `PUT {A}` `{date: +8 dias, time}`, A daqui a 5 dias | `appointment` novo `CONFIRMED` com `rescheduled_from_id = A`, mesmas áreas/desconto; `previous` = A `CANCELLED` com `rescheduled_to_id`; `outcome CANCELLED` |
| 5 | idem, A hoje à noite | `previous` em `NO_SHOW` com vínculo |
| 6 | `PUT {A}` `{time}` mesma data, hoje | mesmo id, `CONFIRMED`, sem `previous` |
| 7 | `PUT {A}` `{serviceAreaPairs}` mesma data, hoje | `CONFIRMED`, sem desfecho |
| 8 | `GET reports?period=current_month`, `GET dashboard?date=` | `no_show_appointments` e `attendance_rate` presentes; dinheiro só de ativos |
| 9 | Público: `reschedule` com data nova; `cancel` hoje | id novo; `cancel` grava `NO_SHOW` sem dizer à pessoa |
| 10 | Painel | cancelar mostra o desfecho e o seletor; trocar exige motivo; editar data mostra "Confirmar remarcação" com o aviso; popover "Falta · remarcado para", "Remarcado de"; cards Faltas/Presença |

## Resultado

**Dev, 20/11/2026** (migration aplicada; deploy dev concluído):

- 1 → `CANCELLED`, "Agendamento cancelado com sucesso".
- 2 → `NO_SHOW`, "Falta registrada: menos de 24 h para a agenda do dia".
- 3a → 400 "Para registrar um desfecho diferente do automatico, informe o
  motivo". 3b → `CANCELLED` com `outcome_reason = "avisou doença"`.
- 4 → novo em 30/11 `CONFIRMED`, `rescheduled_from_id` = antigo, desconto
  `tier_2` 10% e preço iguais; antigo (25/11) `CANCELLED` com
  `rescheduled_to_id` = novo; `outcome CANCELLED`.
- 5 → antigo (hoje à noite) em `NO_SHOW` com vínculo; `outcome NO_SHOW`.
- 6 → mesmo id, `CONFIRMED`, sem `previous`. 7 → `CONFIRMED`, só
  "serviço/áreas" na mensagem.
- 8 → relatório: `no_show_appointments: 2`, `attendance_rate` presente,
  `rescheduled_appointments` conta os pares criados; dashboard do dia:
  `no_show_appointments: 2`, receita sem as faltas.
- 9 e 10: pelo André (9 exige OTP do site; 10 sobe pela Vercel no merge).
- Observação: a primeira rodada usou "amanhã" = segunda-feira para os casos
  < 24 h e deu `CANCELLED`, corretamente (faltavam mais de 24 h para a
  abertura de segunda). O roteiro passou a usar HOJE à noite.
- Fixtures: as vivas foram canceladas; as `NO_SHOW` de teste ficaram em dev
  (telefone 5511999990541).

**Prod:** pendente (migration + deploy com o André). Atenção: ao mergear, o
painel sobe antes do backend de prod e passa a mostrar "vai contar como
falta" enquanto o backend antigo ainda grava `CANCELLED`; fechar a janela com
o deploy logo em seguida.
