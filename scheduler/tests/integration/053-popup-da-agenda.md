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

**Dev:** pendente.

**Prod:** pendente.
