# 053 - Pop-up da agenda: confirmação e política de desconto como padrão

Roteiro em **dev**, depois prod. Sem migration. Deploy do backend antes do
painel (a Vercel sobe no merge).

A cotação mora em `POST appointments?simular=true`, e não numa rota própria:
prod está em 494 dos 500 recursos do CloudFormation (medido em 20/11/2026) e
uma Lambda nova custa 5.

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev; API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
  --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
H=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")
C=clinicadepilacaopremium-3fbce9; S=<service_id>
T1=<telefone sem combinado e sem sessao confirmada>; T2=<telefone com combinado>
```

A clínica precisa de `discount_rules` ativa (primeira sessão e faixa 2/3).

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | `POST appointments?simular=true` `{clinicId, serviceIds:[S], serviceAreaPairs:[1 área], phone:T1}` | `discountReason: "first_session"`, `isFirst: true`, `finalPriceCents` < `originalPriceCents` |
| 2 | idem com 3 áreas e um telefone com sessão `CONFIRMED` anterior | razão `tier_2`, `isFirst: false` |
| 3 | idem com `T2` | razão `personalizado`, pct do cadastro |
| 4 | `POST appointments` sem bloco de desconto, `T1`, 3 áreas | gravado `discount_reason = tier_2` (ou `first_session`, o maior), `final_price_cents` igual ao da cotação |
| 5 | `POST appointments` com `discountPct: 0, discountReason: "none"` | gravado `none`, pct 0, final = original |
| 5b | `POST appointments` com `discountPct: 10, discountReason: "none"` | 400 |
| 6 | `PUT appointments/{A}` com `serviceAreaPairs` (5 áreas) + `discountPolicy: true` | razão `tier_3`, `discount_cents` null; `discountPolicy` + `discountPct` → 400 |
| 7 | Painel: "Novo agendamento" | abre em "Política da clínica"; cotação muda ao trocar áreas; paciente com combinado abre em Personalizado; "Sem desconto" grava `none` |
| 8 | Painel: pop-up | os seis botões (link de cobrança, link dos documentos, recebi em dinheiro, pedir nova assinatura, marcar falta, marcar como confirmado) mostram a confirmação; "Voltar" não chama nada; confirmar chama uma vez; desmarcar falta e desfazer confirmação seguem diretos |
| 9 | Painel: Caixa | o link de cobrança pede confirmação |
| 10 | `GET appointments?date=` antes/depois | áreas e preços coerentes; fixtures canceladas ao fim |

## Resultado

**Dev, 20/11/2026** (layer 202; regras de dev: estreia 0%, faixa 2 = 10%,
faixa 3 = 15%):

- 1 → 1 área, T1: pct 0, razão `null`, `isFirst: true` (estreia é 0% em dev).
- 2 → 3 áreas, T1: `tier_2` 10%, 31500 → 28350.
- 3 → não conferido pela API: `PUT patients/{id}` com `custom_discount_pct`
  devolveu 403 com a chave de dev (campo restrito). Coberto pelo teste
  unitário `test_o_combinado_da_paciente_segue_vencendo` e por `decide`, que
  não mudou. 3b (sem telefone): só a faixa, `isFirst: false`.
- 4 → `POST appointments` sem desconto, 3 áreas: gravado `tier_2` 10%,
  final 28350 = cotação.
- 5 → `discountPct: 0, discountReason: "none"`: gravado `none`, final =
  original. 5b (`none` + pct 10) → 400.
- 6 → `PUT` com 5 áreas + `discountPolicy: true`: `tier_3` 15%, 58000 → 49300,
  `discount_cents` null, mensagem "serviço/áreas, desconto pela política".
  6b (`discountPolicy` + `discountPct`) → 400.
- 10 → lista do dia coerente; fixtures canceladas.
- 7, 8, 9 (painel): pelo André após a Vercel subir.

**Prod, 20/11/2026** (layer 160; stack seguiu em 494/500 recursos, como
previsto: nenhuma Lambda nova). Smoke de LEITURA, Essência:

- `POST appointments?simular=true` com 1 área: pct 0, razão `null`,
  `isFirst: false`. Com 3 áreas: `tier_2` 10%, 28500 → 25650.
- Nenhuma clínica de prod tem desconto de estreia (as três estão com
  `first_session_discount_pct = 0`): a razão `first_session` só aparece se
  alguém ligar a regra na página Descontos. Nada a conferir hoje.
- Sem escrita em dados reais; casos 4-6 cobertos em dev e por teste unitário.
- Painel (7-9): conferido pelo André em prod em 20/11: ok.
