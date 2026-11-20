# 052 - Registro de sessão: Grandes lábios, compostas desmembradas e Energia no HR

Roteiro em **dev**, depois prod. Migration pequena (`source_area_name`) e
seeds do protocolo (renomes) e do mapa (ligações novas da virilha), via
`setup_database.py` com `/{stage}/SUPABASE_DB_*`.

## Pré-requisitos

```bash
export MSYS_NO_PATHCONV=1 AWS_PROFILE=dev-andre AWS_DEFAULT_REGION=us-east-1
get(){ aws ssm get-parameter --name "$1" --with-decryption --query Parameter.Value --output text; }
STAGE=dev; API_KEY=$(get /$STAGE/SCHEDULER_API_KEY)
URL=$(aws cloudformation describe-stacks --stack-name clinic-scheduler-infra-$STAGE \
  --query "Stacks[0].Outputs[?contains(OutputKey,'ServiceEndpoint')].OutputValue" --output text)
H=(-H "x-api-key: $API_KEY" -H "Content-Type: application/json")
C=clinicadepilacaopremium-3fbce9; S=<service_id>; D=2026-11-27
```

## Casos

| # | Chamada | Esperado |
|---|---|---|
| 1 | SQL `SELECT method, protocol_area_name FROM scheduler.laser_protocol_parameters WHERE protocol_area_key IN ('interno_virilha','regiao_perianal')` | "Grandes lábios" ×6 (3 métodos × 2 peles), "Perianal" ×2 |
| 2 | SQL ligações de `Virilha Cavada`, `Virilha Completa`, `Virilha Completa + ânus` em `area_protocol_map` (por clínica) | 2, 2 e 3 chaves; `interno_virilha` entre a virilha e o perianal |
| 3 | `GET .../appointments/{A}/session-applications`, A com Virilha Completa + ânus e Perna Completa | `Virilha completa` (SHR), `Grandes lábios` (null), `Perianal` (Stacking), os três com `source_area_name` = nome comercial; `Perna Completa` sem origem |
| 4 | idem, A com Virilha Cavada | `Virilha cavada` e `Grandes lábios`, origem "Virilha Cavada" |
| 5 | idem, A com Virilha Simples | 1 aplicação, sem origem |
| 6 | `POST session-records` com `sourceAreaName` | 201; `GET` lista devolve `source_area_name` |
| 7 | `GET appointments?date=` antes e depois do POST | áreas, `original_price_cents`, `final_price_cents`, `discount_pct` iguais |
| 8 | Painel: HR em qualquer área → Energia 1, editável; apagar e Salvar → pendência do 051; "+ Adicionar área" → "Grandes lábios"; bloco de parte mostra "de: ..." | ok |

## Resultado

**Dev, 20/11/2026** (layer 201; `setup_database.py` em dev: coluna criada,
seed do protocolo renomeou, seed do mapa inseriu 4 ligações):

- 1 → "Grandes lábios" em HR, SHR e Stacking (2 peles cada), "Perianal" ×2.
- 2 → `Virilha Cavada` = `virilha_cavada > interno_virilha`; `Virilha Completa`
  = `virilha_completa > interno_virilha`; `Virilha Simples` = uma chave. A
  composta de dev é "Virilha Comp. + ânus" (abreviada, sem mapa), então o caso
  de três partes só é conferível em prod, onde o nome é o completo.
- 3/4 → agendamento com Virilha Cavada + Perna Completa: `Perna Completa`
  (sem origem, SHR), `Virilha cavada` (origem "Virilha Cavada", SHR),
  `Grandes lábios` (origem "Virilha Cavada", sem método). Paciente de teste sem
  pele: sem sugestão.
- 5 → Virilha Simples: uma aplicação, sem origem.
- 6 → POST com `sourceAreaName` → 201; a lista devolve `source_area_name`.
- 7 → `original_price_cents`, `final_price_cents`, `discount_pct` e
  `discount_reason` iguais antes e depois do registro.
- Fixtures canceladas e registro apagado. Smoke do painel (caso 8) pendente:
  sobe pela Vercel no merge.

**Prod, 20/11/2026** (layer 159; `setup_database.py` em prod: coluna criada,
protocolo renomeado, mapa com as ligações novas):

- 1 → "Grandes lábios" ×6, "Perianal" ×2.
- 2 → na primeira passada a composta ficou `virilha_completa > regiao_perianal >
  interno_virilha` em Premium e Essência: o seed era `ON CONFLICT DO NOTHING` e
  a ligação antiga do perianal guardou a ordem velha (Nobre, inserção nova,
  saiu certa). Seed passou a `DO UPDATE SET display_order`; reaplicado, as três
  clínicas ficaram `virilha_completa > interno_virilha > regiao_perianal`.
  Cavada e Completa com `interno_virilha` em segundo nas três.
- 3 → agendamento real da Essência com Axilas e Virilha Completa + ânus:
  `Axilas` (sem origem), `Virilha completa` (SHR), `Grandes lábios` (sem
  método), `Perianal` (Stacking), os três com origem "Virilha Completa + ânus".
  Paciente sem pele cadastrada: sem fluência sugerida, como esperado.
- 6/7 não repetidos em prod (sem fixture de escrita em dados reais); cobertos
  em dev e por teste unitário. Caso 8 (painel) é do André após a Vercel.
