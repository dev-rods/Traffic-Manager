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

**Dev, 21/11/2026** (migração + `serverless deploy --stage dev`, layer 205;
código do PR #241, rodado da branch antes do merge):

- Clínica de dev com datas na janela: Premium (`clinicadepilacaopremium-3fbce9`),
  datas 25/11 e 27/11, área Abdômen. Smoke por script, 13 de 13:
- 1 → criar sem `token`: 401.
- 2 → `verify/send` devolveu `devCode` (WhatsApp de dev fora); `verify/confirm`
  deu o token; criar com token (e cadastro CPF/nascimento/e-mail, PRD 032) em
  25/11: 201.
- 3 → criar em 27/11 com o mesmo token: 409 `SAME_MONTH_APPOINTMENT`,
  `existing` com id, `2026-11-25`, `20:50`, `Abdômen`; sem nome (site).
- 4 → mesmo pedido com `substituir: true`: 201 "Agendamento remarcado com
  sucesso", `rescheduled_from_id` = o de 25/11; o de 25/11 ficou `CANCELLED`
  com `rescheduled_to_id` apontando para o novo.
- 5 → dezembro (01/12) pelo painel com sessão em novembro: 201, sem vínculo.
- 6 → painel (chave mestra = ADMIN) criar em 25/11: 409 com
  `existing.patientName`. STAFF (403) coberto por unit test
  (`test_painel_manter_as_duas.py`): não há sessão STAFF por curl.
- 7 → `manterAsDuas` sem motivo: 400; com motivo: 201 e, no banco,
  `second_in_month_by = ADMIN`, `second_in_month_reason` gravado.
- 8 → mover a de dezembro para 25/11 (mês com duas sessões): 409; com
  `substituir`: 200 "remarcado (cancelamento no dia anterior)", a mais
  próxima do mês cancelada.
- 9 → `test_bot_mesmo_mes.py` (10 testes) verde; pytest 2470.
- 10 → browser (Playwright headless, apps locais com o proxy do Vite para a
  API de dev, antes do merge): site percorre áreas → dia → horário → dados →
  "Confirme seu celular" (o `devCode` vem na resposta de `verify/send`; em
  `npm run dev` o StrictMode monta o form duas vezes e vale o último código)
  → aviso "Sua sessão de 25/11/2026 às 16:00 será substituída por 27/11/2026
  às 20:50. Confirmar?" com o botão "Falar no WhatsApp" (`wa.me/<número da
  clínica>`) → "Confirmar remarcação" → "Agendamento remarcado!"; a sessão de
  25/11 ficou cancelada com `rescheduled_to_id`. Painel (sessão ADMIN): "Novo
  agendamento" no mesmo mês mostra o aviso inline no lugar dos botões, com
  "Manter as duas" visível para ADMIN; "Voltar" devolve o formulário. Sem
  erro no console além do próprio 409 esperado. Capturas no scratchpad da
  sessão (`shots/site-06-aviso.png`, `shots/painel-03-aviso.png`).
- Limpeza: as sessões do número de teste foram canceladas no fim.

**Prod, 21/11/2026** (PR #241 mergeado; painel e site pela Vercel; migração
`setup_database.py` com `/prod/SUPABASE_DB_*` e `serverless deploy --stage
prod`, layer 163). Clínica com datas na janela: Nobre (`nobrelaser-sjc`),
03/12 e 04/12, área Mãos; número de teste, tudo cancelado no fim (0 sessões
confirmadas do número no banco):

- 1 → criar pelo site sem `token`: 401.
- 2 a 4 → pelo script não dá: em prod `verify/send` manda o código pelo
  WhatsApp de verdade (sem `devCode`). A regra que o site dispara é a mesma do
  painel (casos 6 a 8); o fluxo com código real no celular fica a critério do
  André, como o caso 9 da 054.
- 5 → janeiro pelo painel com sessão em dezembro: 201, sem vínculo.
- 6 → painel criar em 04/12 com sessão em 03/12: 409 `SAME_MONTH_APPOINTMENT`,
  `existing` com id, data, hora, `Mãos` e `patientName`.
- 7 → `manterAsDuas` sem motivo: 400 "informe o motivo"; com motivo: 201 e,
  no banco, `second_in_month_by = ADMIN`, `second_in_month_reason` gravado
  (a listagem do painel não devolve essas colunas; conferido por SQL).
- 8 → mover a de janeiro para dezembro: 409; com `substituir`: 200
  "remarcado (cancelamento no dia anterior)".
- 10 e 11 → não repetidos em prod.
