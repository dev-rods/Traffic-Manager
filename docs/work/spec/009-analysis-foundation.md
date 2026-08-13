# Spec — 009 Fundação de Análise (Fatia 0 do sistema multi-agente)

> Gerado na fase **Spec**. Use como input para a fase Code (implementação).

- **Design de origem:** `docs/plans/2026-08-05-multi-agent-optimizer-design.md`
- **Fatia:** 0 (Fundação) — `business-context` + camada de dados determinística `analysis/` + contrato do snapshot.

---

## 1. Resumo

Cria a **camada de dados determinística** (`analysis/`, pacote Python standalone) que, dado
um `customer` e um `period`, puxa dados do Google Ads e junta com as vendas reais do banco
do scheduler (via `gclid`), computa KPIs em Python (ROAS/CPA/CTR/LTV/latência) e emite um
**`snapshot.json`** — o contrato consumido pelos analisadores das fatias seguintes. Cria
também a skill declarativa **`business-context`**. **Zero LLM nesta fatia**: só coleta e
cálculo determinístico + testes.

---

## 2. Arquivos a criar

| Arquivo | Descrição |
|---------|-----------|
| `analysis/__init__.py` | Marca o pacote. |
| `analysis/config.py` | Carrega credenciais via SSM (perfil `dev-andre`): Google Ads (`developer_token`, `client_id`, `client_secret`, `refresh_token`) e Supabase (`SUPABASE_DB_*`). Espelha o `google_ads_config` do `infra/`. |
| `analysis/pull.py` | CLI: `python -m analysis.pull --customer 4601912200 --period 30d --stage dev --out snapshot.json`. Orquestra coleta → métricas → snapshot. |
| `analysis/data/__init__.py` | — |
| `analysis/data/google_ads.py` | GAQL por dimensão (campanha, ad_group, ad, keyword, search_term, geo, device, audience) + `click_view` (gclid → dimensão, janela 90d). Retorna dicts crus. |
| `analysis/data/conversions.py` | SQL no Supabase (`scheduler.leads ⋈ lead_conversions ⋈ appointments`): leads do período e **coorte histórica all-time**. |
| `analysis/metrics.py` | Funções determinísticas puras: ROAS, CPA, CTR, conv-rate, LTV, latência, agregação por dimensão, baseline. |
| `analysis/snapshot.py` | Monta e serializa o `snapshot.json` conforme o contrato. |
| `analysis/tests/__init__.py` | — |
| `analysis/tests/test_metrics.py` | Testes unitários determinísticos de `metrics.py` (o ponto central: garantir o cálculo). |
| `analysis/tests/test_conversions.py` | Testes da montagem de queries/agregação de conversão (com fixtures). |
| `analysis/README.md` | Como rodar o pull, formato do snapshot, dependências. |
| `requirements-analysis.txt` | `google-ads`, `psycopg2-binary`, `boto3`. |
| `.claude/skills/business-context/SKILL.md` | Skill declarativa: orçamento mensal, negócio de depilação a laser, público que converte (visão do dono), diferenciais, **alvos** ROAS/CPA/CTR. |

---

## 3. Arquivos a modificar

| Arquivo | Alterações |
|---------|------------|
| — | Nenhum nesta fatia (pacote novo isolado; não altera `infra/` nem `scheduler/`). |

---

## 4. Arquivos a remover (se aplicável)

Nenhum.

---

## 5. Ordem de implementação sugerida

1. `config.py` — resolver a fonte das credenciais Google Ads (ver §6; confirmar de onde vem o `refresh_token` do customer, espelhando `infra/`). Validar conexão à API e ao Supabase.
2. `data/conversions.py` — período + coorte histórica (dados já existem no banco; testável primeiro).
3. `metrics.py` + `tests/test_metrics.py` — cálculo determinístico com testes.
4. `data/google_ads.py` — GAQL por dimensão + `click_view`.
5. `snapshot.py` — montar o contrato; `pull.py` — CLI que amarra tudo.
6. `business-context/SKILL.md` — preencher com baseline computado + inputs do dono.
7. `README.md` + `requirements-analysis.txt`.

---

## 6. Detalhes por arquivo

### `analysis/config.py`
- **Criar.** Função `load_google_ads_config(customer_id, stage)` retornando o dict
  `{developer_token, client_id, client_secret, refresh_token, use_proto_plus: True,
  login_customer_id}` — **mesmo formato do `infra/` (ver CLAUDE.md "Google Ads client
  initialization")**.
- **A confirmar na implementação:** de onde vem o `refresh_token` do customer. No `infra/`
  as credenciais do cliente ficam **cifradas (Fernet) na tabela `Clients`** do DynamoDB.
  Opções: (a) reusar o caminho do `infra/` (SSM developer token + refresh token do cliente),
  ou (b) SSM dedicado `/${stage}/GOOGLE_ADS_REFRESH_TOKEN`. Decidir no início da §5.1.
- `load_supabase_config(stage)` — busca `/{stage}/SUPABASE_DB_*` via SSM (padrão já usado
  nos scripts de validação da sessão).

### `analysis/data/conversions.py`
- **Criar.** Conexão psycopg2 (search_path `scheduler,public`).
- `leads_in_period(clinic_id, start, end)` — leads criados no período, com `gclid` e segmento.
- `historical_cohort(clinic_id)` — **all-time**: para cada `gclid` com ≥1 conversão real,
  retorna `ltv_cents`, `latencia_dias` (1ª conversão − click_date) e `recompras`.
- **Definição de conversão real (travada):** agendamento `status = 'CONFIRMED'` **e**
  `appointment_date < CURRENT_DATE`; `ltv_cents = SUM(lc.value_cents)`. Consistente com
  `LeadService.get_pending_conversions`.
- Recebe `clinic_id`; o mapeamento para `customer_id` vem de
  `scheduler.clinics.google_ads_customer_id` (Essência → `4601912200`).

### `analysis/data/google_ads.py`
- **Criar.** `GoogleAdsClient.load_from_dict(config)`.
- Uma função por dimensão retornando linhas com `impressions, clicks, cost_micros,
  conversions` (métricas do Google): `campaigns`, `ad_groups`, `ads`, `keywords`,
  `search_terms`, `geo`, `devices`, `audiences`.
- `click_view_gclid_map(start, end)` — GAQL em `click_view` mapeando `gclid` →
  campaign/ad_group/keyword/device/geo, **janela 90d**. Usado para atribuir `revenue_real`
  às dimensões finas. Onde o `click_view` não cobrir, os campos finos ficam `null`.

### `analysis/metrics.py`
- **Criar.** Funções **puras** (sem I/O), 100% testáveis:
  - `roas(revenue_cents, cost_cents)`, `cpa(cost, conversions)`, `ctr(clicks, impressions)`.
  - `aggregate_dimension(rows, revenue_by_gclid, gclid_map)` — junta métricas do Google com
    receita real por dimensão; devolve `revenue_real, roas_real, cpa_real` (ou `null` nas
    finas sem cobertura).
  - `baseline(historical_cohort, ads_totals)` — ROAS/CPA/CTR atuais para semear os alvos.
  - `ltv`, `latency_days`, `repeat_count` a partir das linhas de conversão.

### `analysis/snapshot.py`
- **Criar.** Monta o dict conforme o **contrato** (abaixo) e serializa (datas ISO, `Decimal`→`float`).

### `analysis/pull.py`
- **Criar.** `argparse`: `--customer` (obrigatório), `--period` (`Nd` ou `YYYY-MM-DD:YYYY-MM-DD`),
  `--stage` (default `dev`), `--out` (default stdout). Resolve `clinic_id` a partir do
  `customer` via `scheduler.clinics`. Chama coleta → métricas → snapshot.

### `.claude/skills/business-context/SKILL.md`
- **Criar.** Frontmatter `name: business-context`, `description` de trigger. Corpo declarativo:
  orçamento mensal, descrição do negócio (depilação a laser), público que converte (visão do
  dono), diferenciais, e os **alvos** ROAS/CPA/CTR (preenchidos a partir do baseline calculado).

### Contrato do `snapshot.json`
```
meta:        { customer, clinic_id, period{start,end}, generated_at, currency }
baseline:    { roas, cpa, ctr }
period:
  google_ads:
    campaigns[], ad_groups[], ads[], keywords[],
    search_terms[], geo[], devices[], audiences[]
    # linha: impressions, clicks, cost, ctr, conv_google,
    #        revenue_real, roas_real, cpa_real   (finas: null se sem click_view)
  leads:      { total, com_gclid, por_segmento{geo,device,...} }
historical_cohort:
  customers[]: { gclid, ltv_cents, latencia_dias, recompras }
  perfil_alto_ltv: { distrib por geo/device/audience/termo_origem }
```

---

## 7. Convenções a respeitar

- **Determinismo:** nenhuma LLM em `analysis/`; todo número calculado em Python e coberto por teste.
- **Secrets:** credenciais via SSM `/${stage}/...` (perfil `dev-andre`); nunca hardcode.
- **Google Ads:** init via `GoogleAdsClient.load_from_dict` com o dict-padrão do `CLAUDE.md`.
- **DB:** `search_path=scheduler,public`; definição de conversão idêntica à do `ConversionUploader`.
- **Naming:** clinic_id kebab-case; customer_id = string numérica (`4601912200`).
- **Escopo:** v1 só para a Essência (única clínica com `google_ads_customer_id` preenchido).
```
