# analysis/

Camada de dados determinística (zero LLM) do sistema multi-agente de otimização.
Dado um `customer` (Google Ads customer ID) e um `period`, gera um `snapshot.json`
com métricas reais (ROAS/CPA/CTR/LTV/latência) juntando dados do Google Ads com
vendas reais do banco do scheduler (via `gclid`).

## Instalação

```bash
pip install -r requirements-analysis.txt
```

Requer AWS profile `dev-andre` configurado localmente (credenciais lidas via SSM,
`/${stage}/...` — ver `analysis/config.py`).

## Uso

```bash
python -m analysis.pull --customer 4601912200 --period 30d --stage prod --out snapshot.json
python -m analysis.pull --customer 4601912200 --period 2026-06-01:2026-06-30 --stage prod
```

- `--period`: `Nd` (últimos N dias) ou `YYYY-MM-DD:YYYY-MM-DD`.
- `--out`: caminho do arquivo de saída; omitir imprime no stdout.
- `--stage`: `dev` ou `prod` — use `prod` para dados reais, já que o mapeamento
  `clinics.google_ads_customer_id` só está preenchido em produção.

## Formato do `snapshot.json`

```
meta:        { customer, clinic_id, period{start,end}, generated_at, currency }
baseline:    { roas, cpa, ctr }
period:
  google_ads:
    campaigns[], ad_groups[], ads[], keywords[],
    search_terms[], geo[], devices[], audiences[]
    # cada linha: id, name, impressions, clicks, cost_micros, cost_cents,
    #             conversions, ctr, revenue_real, roas_real, cpa_real
    #             (revenue_real/roas_real = null nas dimensões sem cobertura de click_view)
  leads: { total, com_gclid }
historical_cohort:
  customers[]: { gclid, ltv_cents, latencia_dias, recompras }
```

## Testes

```bash
python -m pytest analysis/ -v
```

## Escopo

v1 cobre apenas a Essência (`customer_id = 4601912200`), a única clínica com
`google_ads_customer_id` preenchido em `scheduler.clinics` (produção).

## Notas operacionais

- **Credenciais Google Ads via MCC**: `analysis/config.py` usa o mesmo caminho de
  credenciais MCC que `infra/src/services/google_ads_config.py` (SSM
  `MCC_DEVELOPER_TOKEN`, `OAUTH2_CLIENT_ID/SECRET`, `GOOGLE_ADS_REFRESH_TOKEN`,
  `MCC_ACCOUNT_ID`), não o caminho cifrado por cliente no DynamoDB.
- **OAuth consent screen em modo Testing**: se o app OAuth do Google Cloud estiver
  em "Testing" (não publicado), o `refresh_token` pode ficar inválido de forma
  imprevisível. Publicar o app ("Audience → Publish App") resolve de forma
  definitiva; verificação completa do Google não costuma ser exigida para o
  escopo `adwords`. Para regenerar um `refresh_token` manualmente, use
  `infra/src/scripts/generate_refresh_token.py` — nunca cole o token gerado em
  texto puro fora do comando que grava no SSM.
- **`click_view` exige filtro de um único dia por query** — `click_view_gclid_map`
  já itera dia a dia internamente; não passe períodos muito longos sem necessidade,
  já que cada dia é uma chamada separada à API.
- **Versão do pacote `google-ads`**: mantenha atualizado — a API do Google Ads
  deprecia versões antigas periodicamente (`google-ads==27.0.0` falhava porque
  usava a v20, já bloqueada; hoje fixado em `31.2.0`).
