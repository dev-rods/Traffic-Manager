# Fase 0.5 — `revenue_projected` + Analisador de Integridade de Conta

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fechar as duas lacunas que a Fatia 0 deixou: dar ao snapshot uma métrica de receita utilizável hoje (`revenue_projected`) e um bloco de integridade que detecte configuração quebrada na conta do Google Ads antes que ela derrube a entrega.

**Architecture:** Duas extensões ao pacote `analysis/`, ambas determinísticas e sem LLM, seguindo a separação já estabelecida: pulls de dados em `analysis/data/`, funções puras em `analysis/metrics.py` e no novo `analysis/integrity.py`, montagem em `analysis/snapshot.py`. Os parâmetros de negócio saem de `analysis/business_params.json`, que passa a ser a fonte canônica lida pelo código, com a skill `business-context` apontando para ele.

**Tech Stack:** Python 3.13, `google-ads==31.2.0` (API v25), `psycopg2`, `pytest`.

## Global Constraints

- **Zero LLM nesta fase.** Todo cálculo e todo julgamento de integridade é determinístico e testável.
- **`analysis/` nunca escreve na conta do Google Ads.** É somente leitura. Mutações são Fatia 4.
- **Dinheiro em centavos** (`*_cents`, `int`). Micros do Google viram centavos com `/ 10_000`.
- **`analysis/metrics.py` e `analysis/integrity.py` não fazem I/O.** Recebem dados prontos, devolvem dados. É o que os torna 100% testáveis.
- **Docstrings e comentários em português; nomes de código em inglês.** É o padrão vigente no pacote.
- **Nunca inventar dado.** Onde a cobertura não existe, o campo é `None`/`null` — regra já valendo para `revenue_real` em dimensões sem `click_view`.
- **Testes com `pytest`, funções soltas, sem classes.** Padrão de `analysis/tests/`.
- **Nunca usar travessão (`—`) em texto novo.** Usar hífen simples.
- Rodar a suíte inteira com `python -m pytest analysis/ -v` antes de cada commit.

## File Structure

| Arquivo | Responsabilidade |
|---|---|
| `analysis/business_params.json` | **Novo.** Fonte canônica dos parâmetros de negócio por customer (taxa, ticket, LTV, alvos, teto de orçamento). |
| `analysis/business_params.py` | **Novo.** Carrega e valida os parâmetros. Única porta de entrada para eles. |
| `analysis/metrics.py` | **Modificar.** Ganha `revenue_projected_cents`; `aggregate_dimension` passa a emitir `revenue_projected`/`roas_projected`. |
| `analysis/data/account_config.py` | **Novo.** Pulls de *configuração* da conta (ad_schedule, keywords, negativas, anúncios, orçamentos, ações de conversão, change_events). Separado de `google_ads.py`, que puxa *métricas*. |
| `analysis/integrity.py` | **Novo.** Funções puras de verificação. Cada check recebe config e devolve uma lista de findings. |
| `analysis/snapshot.py` | **Modificar.** Ganha os blocos `targets`, `period.totals` e `integrity`. |
| `analysis/pull.py` | **Modificar.** Carrega parâmetros, orquestra os pulls de config, aceita `--skip-integrity`. |
| `analysis/README.md` | **Modificar.** Documenta o contrato novo e a relação com a `business-context`. |
| `.claude/skills/business-context/SKILL.md` | **Modificar.** Aponta para o JSON como fonte canônica. |

Testes espelham a estrutura: `analysis/tests/test_business_params.py`, `test_integrity.py`, `test_account_config.py`, e extensões em `test_metrics.py` / `test_snapshot.py`.

---

# PARTE A — `revenue_projected`

Entrega isolada: ao fim da Task 3 o `snapshot.json` já traz receita projetada e alvos, e a Parte B pode ficar para depois.

---

### Task 1: Parâmetros de negócio

**Files:**
- Create: `analysis/business_params.json`
- Create: `analysis/business_params.py`
- Test: `analysis/tests/test_business_params.py`

**Interfaces:**
- Consumes: nada.
- Produces: `load_business_params(customer: str, path: Path | None = None) -> Dict`. O dict tem exatamente as chaves `taxa_conversao_agendamento: float`, `ticket_medio_cents: int`, `ltv_meses: int`, `cpa_alvo_cents: int`, `roas_piso: float`, `ctr_alvo: float`, `orcamento_mensal_cents: int`, `nome: str`. Todas as tasks seguintes recebem esse dict inteiro sob o nome `business_params`.

- [ ] **Step 1: Escrever o teste que falha**

```python
# analysis/tests/test_business_params.py
import json

import pytest

from analysis.business_params import load_business_params


def test_carrega_parametros_da_essencia():
    params = load_business_params("4601912200")

    assert params["taxa_conversao_agendamento"] == 0.20
    assert params["ticket_medio_cents"] == 25000
    assert params["ltv_meses"] == 8
    assert params["cpa_alvo_cents"] == 7800
    assert params["roas_piso"] == 4.52
    assert params["ctr_alvo"] == 0.052
    assert params["orcamento_mensal_cents"] == 300000


def test_customer_desconhecido_levanta_keyerror(tmp_path):
    arquivo = tmp_path / "params.json"
    arquivo.write_text(json.dumps({"111": {}}), encoding="utf-8")

    with pytest.raises(KeyError, match="999"):
        load_business_params("999", path=arquivo)


def test_parametros_incompletos_levantam_valueerror(tmp_path):
    arquivo = tmp_path / "params.json"
    arquivo.write_text(
        json.dumps({"111": {"nome": "X", "ticket_medio_cents": 100}}), encoding="utf-8"
    )

    with pytest.raises(ValueError, match="taxa_conversao_agendamento"):
        load_business_params("111", path=arquivo)
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_business_params.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'analysis.business_params'`

- [ ] **Step 3: Criar o JSON de parâmetros**

```json
{
  "4601912200": {
    "nome": "Essência",
    "taxa_conversao_agendamento": 0.20,
    "ticket_medio_cents": 25000,
    "ltv_meses": 8,
    "cpa_alvo_cents": 7800,
    "roas_piso": 4.52,
    "ctr_alvo": 0.052,
    "orcamento_mensal_cents": 300000
  }
}
```

- [ ] **Step 4: Implementar o loader**

```python
"""Parâmetros de negócio por customer — fonte canônica dos valores usados no cálculo.

Espelhado na skill `business-context` para leitura humana; este arquivo é o que
o código lê. Ao alterar um valor aqui, atualizar a tabela da skill junto.
"""
import json
from pathlib import Path
from typing import Dict, Optional

_DEFAULT_PATH = Path(__file__).with_name("business_params.json")

_CAMPOS_OBRIGATORIOS = (
    "taxa_conversao_agendamento",
    "ticket_medio_cents",
    "ltv_meses",
    "cpa_alvo_cents",
    "roas_piso",
    "ctr_alvo",
    "orcamento_mensal_cents",
)


def load_business_params(customer: str, path: Optional[Path] = None) -> Dict:
    source = path or _DEFAULT_PATH
    with open(source, encoding="utf-8") as f:
        todos = json.load(f)

    if customer not in todos:
        raise KeyError(
            f"Sem parâmetros de negócio para customer={customer}. Cadastre em {source}."
        )

    params = todos[customer]
    faltando = [campo for campo in _CAMPOS_OBRIGATORIOS if campo not in params]
    if faltando:
        raise ValueError(
            f"Parâmetros incompletos para customer={customer}: faltam {', '.join(faltando)}"
        )
    return params
```

- [ ] **Step 5: Rodar os testes para confirmar que passam**

Run: `python -m pytest analysis/tests/test_business_params.py -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add analysis/business_params.json analysis/business_params.py analysis/tests/test_business_params.py
git commit -m "feat(analysis): parâmetros de negócio por customer em JSON canônico"
```

---

### Task 2: `revenue_projected` em `metrics.py`

**Files:**
- Modify: `analysis/metrics.py:29-61` (`aggregate_dimension`)
- Modify: `analysis/tests/test_metrics.py:43-77` (os dois testes de `aggregate_dimension`)
- Test: `analysis/tests/test_metrics.py`

**Interfaces:**
- Consumes: o dict `business_params` da Task 1.
- Produces:
  - `revenue_projected_cents(conversions: float, taxa_conversao_agendamento: float, ticket_medio_cents: int, ltv_meses: int) -> int`
  - `aggregate_dimension(rows, revenue_by_gclid, gclid_by_dimension_id, *, business_params) -> List[Dict]` — **assinatura alterada**, `business_params` é keyword-only obrigatório. Cada linha ganha as chaves `revenue_projected: int` e `roas_projected: Optional[float]`.

> **Atenção:** os dois testes existentes de `aggregate_dimension` comparam o dict inteiro com `==`. Eles vão quebrar e precisam ser atualizados neste mesmo commit. O código completo atualizado está no Step 1.

- [ ] **Step 1: Escrever os testes que falham**

Adicionar ao final de `analysis/tests/test_metrics.py`:

```python
from analysis.metrics import revenue_projected_cents

PARAMS_TESTE = {
    "taxa_conversao_agendamento": 0.20,
    "ticket_medio_cents": 25000,
    "ltv_meses": 8,
}


def test_revenue_projected_multiplica_conv_taxa_ticket_ltv():
    # 10 conv x 0,20 x R$250,00 x 8 = R$4.000,00 = 400000 centavos
    assert revenue_projected_cents(
        conversions=10,
        taxa_conversao_agendamento=0.20,
        ticket_medio_cents=25000,
        ltv_meses=8,
    ) == 400000


def test_revenue_projected_e_zero_sem_conversoes():
    assert revenue_projected_cents(
        conversions=0,
        taxa_conversao_agendamento=0.20,
        ticket_medio_cents=25000,
        ltv_meses=8,
    ) == 0


def test_revenue_projected_arredonda_para_centavo_inteiro():
    # 3 conv x 0,20 x 25000 x 8 = 120000,0 exato; 1 conv -> 40000
    assert revenue_projected_cents(1, 0.20, 25000, 8) == 40000
    assert isinstance(revenue_projected_cents(1.5, 0.20, 25000, 8), int)


def test_aggregate_dimension_inclui_revenue_projected():
    rows = [
        {"id": "111", "impressions": 1000, "clicks": 50, "cost_micros": 100_000_000, "conversions": 4.0},
    ]

    result = aggregate_dimension(
        rows, revenue_by_gclid={}, gclid_by_dimension_id=None, business_params=PARAMS_TESTE
    )

    # 4 conv x 0,20 x 25000 x 8 = 160000 centavos; custo 10000 centavos -> ROAS 16.0
    assert result[0]["revenue_projected"] == 160000
    assert result[0]["roas_projected"] == 16.0


def test_roas_projected_e_none_quando_custo_zero():
    rows = [
        {"id": "111", "impressions": 10, "clicks": 0, "cost_micros": 0, "conversions": 1.0},
    ]

    result = aggregate_dimension(
        rows, revenue_by_gclid={}, gclid_by_dimension_id=None, business_params=PARAMS_TESTE
    )

    assert result[0]["revenue_projected"] == 40000
    assert result[0]["roas_projected"] is None
```

Substituir os dois testes existentes (`test_aggregate_dimension_with_click_view_coverage` e `test_aggregate_dimension_without_click_view_coverage_is_null`) por estas versões:

```python
def test_aggregate_dimension_with_click_view_coverage():
    rows = [
        {"id": "111", "impressions": 1000, "clicks": 50, "cost_micros": 100_000_000, "conversions": 4.0},
    ]
    revenue_by_gclid = {"gclid-a": 20000, "gclid-b": 10000}
    gclid_by_dimension_id = {"111": ["gclid-a", "gclid-b"]}

    result = aggregate_dimension(
        rows, revenue_by_gclid, gclid_by_dimension_id, business_params=PARAMS_TESTE
    )

    assert result == [
        {
            "id": "111",
            "impressions": 1000,
            "clicks": 50,
            "cost_micros": 100_000_000,
            "conversions": 4.0,
            "cost_cents": 10000,
            "ctr": 0.05,
            "revenue_real": 30000,
            "roas_real": 3.0,
            "cpa_real": 2500.0,
            "revenue_projected": 160000,
            "roas_projected": 16.0,
        }
    ]


def test_aggregate_dimension_without_click_view_coverage_is_null():
    rows = [
        {"id": "kw-1", "impressions": 200, "clicks": 10, "cost_micros": 20_000_000, "conversions": 1.0},
    ]

    result = aggregate_dimension(
        rows, revenue_by_gclid={}, gclid_by_dimension_id=None, business_params=PARAMS_TESTE
    )

    assert result[0]["revenue_real"] is None
    assert result[0]["roas_real"] is None
    assert result[0]["cpa_real"] == 2000.0
    # projected não depende do click_view: sempre disponível
    assert result[0]["revenue_projected"] == 40000
```

- [ ] **Step 2: Rodar os testes para confirmar que falham**

Run: `python -m pytest analysis/tests/test_metrics.py -v`
Expected: FAIL com `ImportError: cannot import name 'revenue_projected_cents'`

- [ ] **Step 3: Implementar**

Adicionar a `analysis/metrics.py`, logo após `conversion_rate`:

```python
def revenue_projected_cents(
    conversions: float,
    taxa_conversao_agendamento: float,
    ticket_medio_cents: int,
    ltv_meses: int,
) -> int:
    """Receita projetada a partir das conversões do Google Ads.

    revenue_projected = conversoes * taxa_conversao_agendamento * ticket_medio * ltv_meses

    Não é receita confirmada. `revenue_real` continua sendo a receita observada de
    fato e segue suspenso enquanto não houver fonte confiável de realização de
    sessão (ver skill `business-context`).
    """
    return round(conversions * taxa_conversao_agendamento * ticket_medio_cents * ltv_meses)
```

Substituir `aggregate_dimension` por:

```python
def aggregate_dimension(
    rows: List[Dict],
    revenue_by_gclid: Dict[str, int],
    gclid_by_dimension_id: Optional[Dict[str, List[str]]],
    *,
    business_params: Dict,
) -> List[Dict]:
    """Junta métricas do Google com receita real e receita projetada por dimensão.

    `gclid_by_dimension_id=None` sinaliza que o click_view não cobre essa
    dimensão inteira (ex.: keywords, search_terms, geo, audiences) — nesse
    caso revenue_real/roas_real ficam null para todas as linhas, conforme o
    contrato do snapshot.

    `revenue_projected` não depende do click_view: é derivado das conversões do
    próprio Google Ads, então existe em toda dimensão.
    """
    aggregated = []
    for row in rows:
        dimension_id = str(row["id"])
        cost_cents = round(row["cost_micros"] / 10_000)
        conversions = row["conversions"]

        if gclid_by_dimension_id is None:
            revenue_real = None
        else:
            gclids = gclid_by_dimension_id.get(dimension_id, [])
            revenue_real = sum(revenue_by_gclid.get(g, 0) for g in gclids)

        revenue_proj = revenue_projected_cents(
            conversions,
            business_params["taxa_conversao_agendamento"],
            business_params["ticket_medio_cents"],
            business_params["ltv_meses"],
        )

        aggregated.append({
            **row,
            "cost_cents": cost_cents,
            "ctr": ctr(row["clicks"], row["impressions"]),
            "revenue_real": revenue_real,
            "roas_real": roas(revenue_real, cost_cents) if revenue_real is not None else None,
            "cpa_real": cpa(cost_cents, conversions),
            "revenue_projected": revenue_proj,
            "roas_projected": roas(revenue_proj, cost_cents),
        })
    return aggregated
```

- [ ] **Step 4: Rodar a suíte inteira**

Run: `python -m pytest analysis/ -v`
Expected: todos passando. Se `test_snapshot.py` quebrar por causa da assinatura nova, isso é esperado e será corrigido na Task 3 — anote quais falharam e siga.

- [ ] **Step 5: Commit**

```bash
git add analysis/metrics.py analysis/tests/test_metrics.py
git commit -m "feat(analysis): revenue_projected e roas_projected por dimensão"
```

---

### Task 3: Ligar `revenue_projected` ao snapshot e à CLI

**Files:**
- Modify: `analysis/snapshot.py:37-82` (`build_snapshot`)
- Modify: `analysis/pull.py:37-69` (`run`)
- Test: `analysis/tests/test_snapshot.py`

**Interfaces:**
- Consumes: `load_business_params` (Task 1), `aggregate_dimension(..., business_params=...)` e `revenue_projected_cents` (Task 2).
- Produces: `build_snapshot(..., business_params: Dict)` — novo argumento keyword obrigatório. O snapshot ganha:
  - `meta.business_params` — cópia dos parâmetros usados, para o resultado ser auditável.
  - `targets` — `{cpa_alvo_cents, roas_piso, ctr_alvo}`.
  - `period.totals` — `{cost_cents, clicks, impressions, conversions, revenue_projected, roas_projected, cpa}`.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar a `analysis/tests/test_snapshot.py`:

```python
PARAMS_TESTE = {
    "nome": "Teste",
    "taxa_conversao_agendamento": 0.20,
    "ticket_medio_cents": 25000,
    "ltv_meses": 8,
    "cpa_alvo_cents": 7800,
    "roas_piso": 4.52,
    "ctr_alvo": 0.052,
    "orcamento_mensal_cents": 300000,
}


def _google_ads_data_minimo():
    return {
        "campaigns": [
            {"id": "1", "name": "C1", "impressions": 1000, "clicks": 50,
             "cost_micros": 100_000_000, "conversions": 4.0},
        ],
    }


def test_snapshot_expoe_targets_e_business_params():
    snapshot = build_snapshot(
        customer="4601912200",
        clinic_id="clinica-x",
        period_start="2026-07-01",
        period_end="2026-07-31",
        google_ads_data=_google_ads_data_minimo(),
        gclid_map={},
        leads=[],
        historical_cohort=[],
        business_params=PARAMS_TESTE,
    )

    assert snapshot["targets"] == {
        "cpa_alvo_cents": 7800,
        "roas_piso": 4.52,
        "ctr_alvo": 0.052,
    }
    assert snapshot["meta"]["business_params"] == PARAMS_TESTE


def test_snapshot_totals_agrega_periodo():
    snapshot = build_snapshot(
        customer="4601912200",
        clinic_id="clinica-x",
        period_start="2026-07-01",
        period_end="2026-07-31",
        google_ads_data=_google_ads_data_minimo(),
        gclid_map={},
        leads=[],
        historical_cohort=[],
        business_params=PARAMS_TESTE,
    )

    totals = snapshot["period"]["totals"]
    assert totals["cost_cents"] == 10000
    assert totals["clicks"] == 50
    assert totals["impressions"] == 1000
    assert totals["conversions"] == 4.0
    assert totals["revenue_projected"] == 160000
    assert totals["roas_projected"] == 16.0
    assert totals["cpa"] == 2500.0
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_snapshot.py -v`
Expected: FAIL com `TypeError: build_snapshot() got an unexpected keyword argument 'business_params'`

- [ ] **Step 3: Implementar em `snapshot.py`**

Trocar a linha de import do topo por esta, que é a versão final (inclui `cpa`, `ctr`, `revenue_projected_cents` e `roas`):

```python
from analysis.metrics import aggregate_dimension, baseline, cpa, ctr, revenue_projected_cents, roas
```

Substituir `build_snapshot` por:

```python
def build_snapshot(
    *,
    customer: str,
    clinic_id: str,
    period_start: str,
    period_end: str,
    google_ads_data: Dict[str, List[Dict]],
    gclid_map: Dict[str, Dict],
    leads: List[Dict],
    historical_cohort: List[Dict],
    business_params: Dict,
    integrity_findings: Optional[List[Dict]] = None,
    currency: str = "BRL",
) -> Dict:
    revenue_by_gclid = _revenue_by_gclid(historical_cohort)

    period_google_ads = {}
    for dimension, rows in google_ads_data.items():
        coverage_key = _CLICK_VIEW_COVERED_DIMENSIONS.get(dimension)
        gclid_by_dimension_id = (
            _gclid_by_dimension_id(gclid_map, coverage_key) if coverage_key else None
        )
        period_google_ads[dimension] = aggregate_dimension(
            rows, revenue_by_gclid, gclid_by_dimension_id, business_params=business_params
        )

    leads_com_gclid = [lead for lead in leads if lead.get("gclid")]
    ads_totals = _ads_totals(google_ads_data)
    conversions = sum(row["conversions"] for row in google_ads_data.get("campaigns", []))
    revenue_proj = revenue_projected_cents(
        conversions,
        business_params["taxa_conversao_agendamento"],
        business_params["ticket_medio_cents"],
        business_params["ltv_meses"],
    )

    return {
        "meta": {
            "customer": customer,
            "clinic_id": clinic_id,
            "period": {"start": period_start, "end": period_end},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "currency": currency,
            "business_params": business_params,
        },
        "targets": {
            "cpa_alvo_cents": business_params["cpa_alvo_cents"],
            "roas_piso": business_params["roas_piso"],
            "ctr_alvo": business_params["ctr_alvo"],
        },
        "baseline": baseline(historical_cohort, ads_totals),
        "period": {
            "google_ads": period_google_ads,
            "totals": {
                **ads_totals,
                "conversions": conversions,
                "ctr": ctr(ads_totals["clicks"], ads_totals["impressions"]),
                "revenue_projected": revenue_proj,
                "roas_projected": roas(revenue_proj, ads_totals["cost_cents"]),
                "cpa": cpa(ads_totals["cost_cents"], conversions),
            },
            "leads": {
                "total": len(leads),
                "com_gclid": len(leads_com_gclid),
            },
        },
        "integrity": {
            "findings": integrity_findings if integrity_findings is not None else [],
        },
        "historical_cohort": {
            "customers": historical_cohort,
        },
    }
```

- [ ] **Step 4: Ligar na CLI**

Em `analysis/pull.py`, adicionar ao bloco de imports:

```python
from analysis.business_params import load_business_params
```

E dentro de `run`, logo após `start, end = parse_period(period)`:

```python
    business_params = load_business_params(customer)
```

E passar para o `build_snapshot`, adicionando a linha `business_params=business_params,` junto dos demais argumentos.

- [ ] **Step 5: Rodar a suíte inteira**

Run: `python -m pytest analysis/ -v`
Expected: todos passando.

- [ ] **Step 6: Validar contra prod com dados reais**

Run: `python -m analysis.pull --customer 4601912200 --period 30d --stage prod --out snapshot-teste.json`

Conferir no arquivo gerado:
- `targets.cpa_alvo_cents == 7800`
- `period.totals.conversions` próximo de 21 (valor observado em 2026-08-12 na janela de 30 dias)
- `period.totals.roas_projected` próximo de 4.7

Se `roas_projected` sair muito distante de 4.7, a causa provável é a composição das ações de conversão ter mudado — a Task 7 cria o check que detecta isso automaticamente.

Apagar o arquivo depois: `rm snapshot-teste.json`

- [ ] **Step 7: Commit**

```bash
git add analysis/snapshot.py analysis/pull.py analysis/tests/test_snapshot.py
git commit -m "feat(analysis): expõe targets, totals e revenue_projected no snapshot"
```

---

# PARTE B — Analisador de Integridade de Conta

Motivação registrada: em 2026-08-09 uma programação de anúncios com cobertura incompleta (faltando segunda, terça, quarta e sábado das 06:00 às 24:00) derrubou as impressões da campanha ativa em 89%, e o problema só apareceu três dias depois, na inspeção manual. Nenhum analisador previsto nas Fatias 1-3 teria detectado, porque o `snapshot.json` não carrega configuração da conta.

---

### Task 4: Pulls de configuração da conta

**Files:**
- Create: `analysis/data/account_config.py`
- Test: `analysis/tests/test_account_config.py`

**Interfaces:**
- Consumes: um `GoogleAdsClient` já autenticado (mesmo padrão de `analysis/data/google_ads.py`).
- Produces, todas recebendo `(client, customer_id)` e devolvendo `List[Dict]`:
  - `fetch_ad_schedules` → `{campaign_id, campaign_name, campaign_status, criterion_id, day_of_week, start_hour, start_minute, end_hour, end_minute, bid_modifier}`
  - `fetch_negative_keywords` → `{campaign_id, campaign_name, text, match_type}`
  - `fetch_positive_keywords` → `{campaign_id, campaign_name, ad_group_name, text, match_type, status}`
  - `fetch_ad_group_ads` → `{campaign_id, campaign_name, ad_group_name, ad_group_status, ad_id, status, approval_status, review_status}`
  - `fetch_campaign_budgets` → `{campaign_id, campaign_name, campaign_status, amount_cents}`
  - `fetch_conversion_action_breakdown(client, customer_id, start, end)` → `{name, category, conversions}`

> `start_minute` e `end_minute` vêm da API como enum (`ZERO`, `FIFTEEN`, `THIRTY`, `FORTY_FIVE`) e devem ser devolvidos como **string do nome do enum**, não como inteiro. A conversão para minutos acontece na Task 5.

- [ ] **Step 1: Escrever o teste que falha**

```python
# analysis/tests/test_account_config.py
from unittest.mock import MagicMock

from analysis.data.account_config import (
    fetch_ad_schedules,
    fetch_campaign_budgets,
    fetch_negative_keywords,
)


def _client_com_linhas(linhas):
    """Simula o search_stream: um batch com as linhas dadas."""
    batch = MagicMock()
    batch.results = linhas
    service = MagicMock()
    service.search_stream.return_value = [batch]
    client = MagicMock()
    client.get_service.return_value = service
    return client


def _linha_ad_schedule():
    linha = MagicMock()
    linha.campaign.id = 23449039185
    linha.campaign.name = "[Gestor]Depilacao_primeira_jardins"
    linha.campaign.status.name = "ENABLED"
    linha.campaign_criterion.criterion_id = 300024
    linha.campaign_criterion.ad_schedule.day_of_week.name = "MONDAY"
    linha.campaign_criterion.ad_schedule.start_hour = 0
    linha.campaign_criterion.ad_schedule.start_minute.name = "ZERO"
    linha.campaign_criterion.ad_schedule.end_hour = 6
    linha.campaign_criterion.ad_schedule.end_minute.name = "ZERO"
    linha.campaign_criterion.bid_modifier = 0.1
    return linha


def test_fetch_ad_schedules_mapeia_enums_como_nome():
    client = _client_com_linhas([_linha_ad_schedule()])

    result = fetch_ad_schedules(client, "4601912200")

    assert result == [
        {
            "campaign_id": "23449039185",
            "campaign_name": "[Gestor]Depilacao_primeira_jardins",
            "campaign_status": "ENABLED",
            "criterion_id": "300024",
            "day_of_week": "MONDAY",
            "start_hour": 0,
            "start_minute": "ZERO",
            "end_hour": 6,
            "end_minute": "ZERO",
            "bid_modifier": 0.1,
        }
    ]


def test_fetch_negative_keywords_traz_texto_e_match_type():
    linha = MagicMock()
    linha.campaign.id = 1
    linha.campaign.name = "C1"
    linha.campaign_criterion.keyword.text = "laser sp"
    linha.campaign_criterion.keyword.match_type.name = "BROAD"
    client = _client_com_linhas([linha])

    result = fetch_negative_keywords(client, "4601912200")

    assert result == [
        {"campaign_id": "1", "campaign_name": "C1", "text": "laser sp", "match_type": "BROAD"}
    ]


def test_fetch_campaign_budgets_converte_micros_para_centavos():
    linha = MagicMock()
    linha.campaign.id = 1
    linha.campaign.name = "C1"
    linha.campaign.status.name = "ENABLED"
    linha.campaign_budget.amount_micros = 85_000_000
    client = _client_com_linhas([linha])

    result = fetch_campaign_budgets(client, "4601912200")

    assert result == [
        {"campaign_id": "1", "campaign_name": "C1", "campaign_status": "ENABLED", "amount_cents": 8500}
    ]
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_account_config.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'analysis.data.account_config'`

- [ ] **Step 3: Implementar**

```python
"""Pulls de CONFIGURAÇÃO da conta (não de métricas).

Separado de `google_ads.py` de propósito: lá ficam as métricas por dimensão,
aqui fica o estado de configuração que o analisador de integridade inspeciona.
Somente leitura — este pacote nunca escreve na conta.
"""
from typing import Dict, List


def _rows(client, customer_id: str, query: str):
    service = client.get_service("GoogleAdsService")
    for batch in service.search_stream(customer_id=customer_id, query=query):
        for row in batch.results:
            yield row


def fetch_ad_schedules(client, customer_id: str) -> List[Dict]:
    query = """
        SELECT campaign.id, campaign.name, campaign.status,
               campaign_criterion.criterion_id,
               campaign_criterion.ad_schedule.day_of_week,
               campaign_criterion.ad_schedule.start_hour,
               campaign_criterion.ad_schedule.start_minute,
               campaign_criterion.ad_schedule.end_hour,
               campaign_criterion.ad_schedule.end_minute,
               campaign_criterion.bid_modifier
        FROM campaign_criterion
        WHERE campaign_criterion.type = 'AD_SCHEDULE'
    """
    resultado = []
    for row in _rows(client, customer_id, query):
        agenda = row.campaign_criterion.ad_schedule
        resultado.append({
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "campaign_status": row.campaign.status.name,
            "criterion_id": str(row.campaign_criterion.criterion_id),
            "day_of_week": agenda.day_of_week.name,
            "start_hour": agenda.start_hour,
            "start_minute": agenda.start_minute.name,
            "end_hour": agenda.end_hour,
            "end_minute": agenda.end_minute.name,
            "bid_modifier": row.campaign_criterion.bid_modifier,
        })
    return resultado


def fetch_negative_keywords(client, customer_id: str) -> List[Dict]:
    query = """
        SELECT campaign.id, campaign.name,
               campaign_criterion.keyword.text,
               campaign_criterion.keyword.match_type
        FROM campaign_criterion
        WHERE campaign_criterion.type = 'KEYWORD'
          AND campaign_criterion.negative = TRUE
    """
    return [
        {
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "text": row.campaign_criterion.keyword.text,
            "match_type": row.campaign_criterion.keyword.match_type.name,
        }
        for row in _rows(client, customer_id, query)
    ]


def fetch_positive_keywords(client, customer_id: str) -> List[Dict]:
    query = """
        SELECT campaign.id, campaign.name, ad_group.name,
               ad_group_criterion.keyword.text,
               ad_group_criterion.keyword.match_type,
               ad_group_criterion.status
        FROM ad_group_criterion
        WHERE ad_group_criterion.type = 'KEYWORD'
          AND ad_group_criterion.negative = FALSE
    """
    return [
        {
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "ad_group_name": row.ad_group.name,
            "text": row.ad_group_criterion.keyword.text,
            "match_type": row.ad_group_criterion.keyword.match_type.name,
            "status": row.ad_group_criterion.status.name,
        }
        for row in _rows(client, customer_id, query)
    ]


def fetch_ad_group_ads(client, customer_id: str) -> List[Dict]:
    query = """
        SELECT campaign.id, campaign.name, ad_group.name, ad_group.status,
               ad_group_ad.ad.id, ad_group_ad.status,
               ad_group_ad.policy_summary.approval_status,
               ad_group_ad.policy_summary.review_status
        FROM ad_group_ad
    """
    return [
        {
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "ad_group_name": row.ad_group.name,
            "ad_group_status": row.ad_group.status.name,
            "ad_id": str(row.ad_group_ad.ad.id),
            "status": row.ad_group_ad.status.name,
            "approval_status": row.ad_group_ad.policy_summary.approval_status.name,
            "review_status": row.ad_group_ad.policy_summary.review_status.name,
        }
        for row in _rows(client, customer_id, query)
    ]


def fetch_campaign_budgets(client, customer_id: str) -> List[Dict]:
    query = """
        SELECT campaign.id, campaign.name, campaign.status,
               campaign_budget.amount_micros
        FROM campaign
    """
    return [
        {
            "campaign_id": str(row.campaign.id),
            "campaign_name": row.campaign.name,
            "campaign_status": row.campaign.status.name,
            "amount_cents": round(row.campaign_budget.amount_micros / 10_000),
        }
        for row in _rows(client, customer_id, query)
    ]


def fetch_conversion_action_breakdown(
    client, customer_id: str, start: str, end: str
) -> List[Dict]:
    """Conversões por ação de conversão no período.

    É o que revela dupla contagem: duas ações registrando o mesmo evento
    (ex.: submit de formulário + pageview da página de obrigado).
    """
    query = f"""
        SELECT segments.conversion_action_name,
               segments.conversion_action_category,
               metrics.conversions
        FROM campaign
        WHERE segments.date BETWEEN '{start}' AND '{end}'
    """
    acumulado: Dict[str, Dict] = {}
    for row in _rows(client, customer_id, query):
        nome = row.segments.conversion_action_name
        if nome not in acumulado:
            acumulado[nome] = {
                "name": nome,
                "category": row.segments.conversion_action_category.name,
                "conversions": 0.0,
            }
        acumulado[nome]["conversions"] += row.metrics.conversions
    return list(acumulado.values())
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest analysis/tests/test_account_config.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add analysis/data/account_config.py analysis/tests/test_account_config.py
git commit -m "feat(analysis): pulls de configuração da conta para o analisador de integridade"
```

---

### Task 5: Check de lacuna na programação de anúncios

**Files:**
- Create: `analysis/integrity.py`
- Test: `analysis/tests/test_integrity.py`

**Interfaces:**
- Consumes: saída de `fetch_ad_schedules` (Task 4).
- Produces: `check_ad_schedule_gaps(ad_schedules: List[Dict], *, hora_inicio_comercial: int = 6, hora_fim_comercial: int = 24) -> List[Dict]`.
  Cada finding tem a forma canônica usada por **todos** os checks:
  `{"check": str, "severity": "high"|"medium"|"low", "campaign_id": str, "campaign_name": str, "message": str, "details": dict}`

Regra que o check codifica: no Google Ads, se uma campanha tem **qualquer** critério de `ad_schedule`, ela só veicula dentro das janelas declaradas. Toda hora não coberta é entrega zero.

- [ ] **Step 1: Escrever o teste que falha**

```python
# analysis/tests/test_integrity.py
from analysis.integrity import check_ad_schedule_gaps

DIAS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]


def _janela(dia, inicio, fim, campaign_id="1", campaign_name="C1", status="ENABLED"):
    return {
        "campaign_id": campaign_id,
        "campaign_name": campaign_name,
        "campaign_status": status,
        "criterion_id": f"{dia}-{inicio}",
        "day_of_week": dia,
        "start_hour": inicio,
        "start_minute": "ZERO",
        "end_hour": fim,
        "end_minute": "ZERO",
        "bid_modifier": 1.0,
    }


def test_cobertura_completa_nao_gera_finding():
    agendas = [_janela(dia, 0, 24) for dia in DIAS]

    assert check_ad_schedule_gaps(agendas) == []


def test_campanha_sem_nenhum_ad_schedule_nao_gera_finding():
    # sem critério nenhum a campanha roda 24/7 — nada a reportar
    assert check_ad_schedule_gaps([]) == []


def test_detecta_o_incidente_real_de_2026_08_09():
    """Todos os dias 00-06, mas 06-24 só em quinta, sexta e domingo."""
    agendas = [_janela(dia, 0, 6) for dia in DIAS]
    agendas += [_janela(dia, 6, 24) for dia in ["THURSDAY", "FRIDAY", "SUNDAY"]]

    findings = check_ad_schedule_gaps(agendas)

    assert len(findings) == 1
    finding = findings[0]
    assert finding["check"] == "ad_schedule_gap"
    assert finding["severity"] == "high"
    assert finding["campaign_id"] == "1"

    dias_descobertos = {lacuna["dia"] for lacuna in finding["details"]["lacunas"]}
    assert dias_descobertos == {"MONDAY", "TUESDAY", "WEDNESDAY", "SATURDAY"}
    for lacuna in finding["details"]["lacunas"]:
        assert lacuna["inicio"] == "06:00"
        assert lacuna["fim"] == "24:00"
    assert finding["details"]["horas_descobertas_semana"] == 72
    assert finding["details"]["dias_totalmente_descobertos"] == [
        "MONDAY", "TUESDAY", "WEDNESDAY", "SATURDAY"
    ]


def test_respeita_minutos_do_enum():
    agendas = [_janela(dia, 0, 24) for dia in DIAS if dia != "MONDAY"]
    monday = _janela("MONDAY", 0, 24)
    monday["start_minute"] = "THIRTY"  # começa 00:30, deixa 00:00-00:30 descoberto
    agendas.append(monday)

    findings = check_ad_schedule_gaps(agendas, hora_inicio_comercial=0)

    assert len(findings) == 1
    assert findings[0]["details"]["lacunas"] == [
        {"dia": "MONDAY", "inicio": "00:00", "fim": "00:30"}
    ]


def test_ignora_campanha_pausada():
    agendas = [_janela("MONDAY", 0, 6, status="PAUSED")]

    assert check_ad_schedule_gaps(agendas) == []


def test_janela_mais_estreita_em_todo_dia_e_medium_nao_high():
    """Rodar 09:00-18:00 todo dia é escolha legítima, não configuração quebrada.

    High fica reservado para dia inteiro sem cobertura, que é o modo de falha
    catastrófico. Sem essa distinção o check vira ruído em qualquer conta que
    restringe horário de propósito.
    """
    agendas = [_janela(dia, 9, 18) for dia in DIAS]

    findings = check_ad_schedule_gaps(agendas)

    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"
    assert findings[0]["details"]["dias_totalmente_descobertos"] == []
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: FAIL com `ModuleNotFoundError: No module named 'analysis.integrity'`

- [ ] **Step 3: Implementar**

```python
"""Checks determinísticos de integridade de configuração da conta.

Funções puras: recebem configuração já puxada por `analysis/data/account_config.py`
e devolvem findings. Sem I/O, sem LLM.

Formato do finding (idêntico em todos os checks):
    {
        "check": str,              # identificador estável do check
        "severity": str,           # "high" | "medium" | "low"
        "campaign_id": str,
        "campaign_name": str,
        "message": str,            # frase pronta para leitura humana
        "details": dict,           # dados estruturados do achado
    }
"""
from typing import Dict, List

_DIAS = ["MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"]
_INDICE_DIA = {dia: i for i, dia in enumerate(_DIAS)}
_MINUTOS_POR_DIA = 24 * 60
_MINUTOS_POR_SEMANA = 7 * _MINUTOS_POR_DIA
_MINUTO_ENUM = {"ZERO": 0, "FIFTEEN": 15, "THIRTY": 30, "FORTY_FIVE": 45}


def _minuto_da_semana(dia: str, hora: int, minuto_enum: str) -> int:
    return _INDICE_DIA[dia] * _MINUTOS_POR_DIA + hora * 60 + _MINUTO_ENUM[minuto_enum]


def _formata_hora(minuto_do_dia: int) -> str:
    return f"{minuto_do_dia // 60:02d}:{minuto_do_dia % 60:02d}"


def _para_minutos(hhmm: str) -> int:
    horas, minutos = hhmm.split(":")
    return int(horas) * 60 + int(minutos)


def check_ad_schedule_gaps(
    ad_schedules: List[Dict],
    *,
    hora_inicio_comercial: int = 6,
    hora_fim_comercial: int = 24,
) -> List[Dict]:
    """Detecta horário comercial descoberto em campanhas que têm ad_schedule.

    Uma campanha com qualquer critério de ad_schedule só veicula dentro das
    janelas declaradas. Se a soma das janelas não cobre o horário comercial,
    a campanha fica no ar zero minuto naquele intervalo.

    Campanhas sem nenhum ad_schedule rodam 24/7 e não aparecem aqui.
    """
    por_campanha: Dict[tuple, List[Dict]] = {}
    for agenda in ad_schedules:
        if agenda["campaign_status"] != "ENABLED":
            continue
        chave = (agenda["campaign_id"], agenda["campaign_name"])
        por_campanha.setdefault(chave, []).append(agenda)

    findings = []
    for (campaign_id, campaign_name), janelas in sorted(por_campanha.items()):
        coberto = bytearray(_MINUTOS_POR_SEMANA)
        for janela in janelas:
            inicio = _minuto_da_semana(
                janela["day_of_week"], janela["start_hour"], janela["start_minute"]
            )
            fim = _minuto_da_semana(
                janela["day_of_week"], janela["end_hour"], janela["end_minute"]
            )
            for minuto in range(inicio, min(fim, _MINUTOS_POR_SEMANA)):
                coberto[minuto] = 1

        minutos_da_janela_comercial = (hora_fim_comercial - hora_inicio_comercial) * 60
        lacunas = []
        dias_totalmente_descobertos = []

        for indice, dia in enumerate(_DIAS):
            base = indice * _MINUTOS_POR_DIA
            inicio_comercial = base + hora_inicio_comercial * 60
            fim_comercial = base + hora_fim_comercial * 60
            descobertos_no_dia = 0

            minuto = inicio_comercial
            while minuto < fim_comercial:
                if coberto[minuto]:
                    minuto += 1
                    continue
                inicio_lacuna = minuto
                while minuto < fim_comercial and not coberto[minuto]:
                    minuto += 1
                descobertos_no_dia += minuto - inicio_lacuna
                lacunas.append({
                    "dia": dia,
                    "inicio": _formata_hora(inicio_lacuna - base),
                    "fim": _formata_hora(minuto - base),
                })

            if descobertos_no_dia == minutos_da_janela_comercial:
                dias_totalmente_descobertos.append(dia)

        if not lacunas:
            continue

        minutos_descobertos = sum(
            _para_minutos(lacuna["fim"]) - _para_minutos(lacuna["inicio"])
            for lacuna in lacunas
        )
        dias_afetados = sorted({lacuna["dia"] for lacuna in lacunas}, key=_INDICE_DIA.get)

        # High só quando existe dia inteiro sem cobertura — o modo de falha que derruba
        # a entrega. Janela mais estreita em todo dia é escolha legítima, fica medium.
        severidade = "high" if dias_totalmente_descobertos else "medium"

        if dias_totalmente_descobertos:
            mensagem = (
                f"Campanha '{campaign_name}' não veicula em nenhum minuto do horário "
                f"comercial em {len(dias_totalmente_descobertos)} dia(s): "
                f"{', '.join(dias_totalmente_descobertos)}. Fora das janelas declaradas "
                f"a entrega é zero."
            )
        else:
            mensagem = (
                f"Campanha '{campaign_name}' tem {round(minutos_descobertos / 60)}h "
                f"do horário comercial sem cobertura na semana, distribuídas em "
                f"{len(dias_afetados)} dia(s)."
            )

        findings.append({
            "check": "ad_schedule_gap",
            "severity": severidade,
            "campaign_id": campaign_id,
            "campaign_name": campaign_name,
            "message": mensagem,
            "details": {
                "lacunas": lacunas,
                "horas_descobertas_semana": round(minutos_descobertos / 60),
                "dias_totalmente_descobertos": dias_totalmente_descobertos,
                "janelas_declaradas": len(janelas),
            },
        })
    return findings
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add analysis/integrity.py analysis/tests/test_integrity.py
git commit -m "feat(analysis): check de lacuna na programação de anúncios"
```

---

### Task 6: Checks de palavras-chave negativas

**Files:**
- Modify: `analysis/integrity.py`
- Test: `analysis/tests/test_integrity.py`

**Interfaces:**
- Consumes: `fetch_negative_keywords`, `fetch_positive_keywords` (Task 4) e a dimensão `search_terms` já presente no snapshot (linhas com `name`, `clicks`, `conversions`).
- Produces:
  - `negative_blocks(negative_text: str, match_type: str, query: str) -> bool`
  - `check_negatives_blocking_own_keywords(negatives, positives) -> List[Dict]`
  - `check_negatives_blocking_converting_terms(negatives, search_terms, *, min_clicks: int = 1) -> List[Dict]`

Regras de bloqueio implementadas: `EXACT` bloqueia só quando a consulta é idêntica; `PHRASE` quando a sequência de tokens aparece contígua; `BROAD` quando todos os tokens aparecem em qualquer ordem.

> Simplificação assumida: a normalização é lowercase + split em não-alfanuméricos, sem remoção de acentos e sem stemming. O Google faz normalizações adicionais, então este check pode ter falsos negativos — nunca falsos positivos de bloqueio que o Google não faria. Preferimos errar para o lado de não alarmar.

- [ ] **Step 1: Escrever o teste que falha**

Adicionar a `analysis/tests/test_integrity.py`:

```python
from analysis.integrity import (
    check_negatives_blocking_converting_terms,
    check_negatives_blocking_own_keywords,
    negative_blocks,
)


def test_negative_broad_bloqueia_em_qualquer_ordem():
    assert negative_blocks("laser sp", "BROAD", "depilacao a laser em sp") is True
    assert negative_blocks("laser sp", "BROAD", "sp clinica laser") is True
    assert negative_blocks("laser sp", "BROAD", "depilacao a laser sao paulo") is False


def test_negative_phrase_exige_sequencia_contigua():
    assert negative_blocks("espaco laser", "PHRASE", "depilacao espaco laser preco") is True
    assert negative_blocks("espaco laser", "PHRASE", "laser no espaco") is False


def test_negative_exact_exige_igualdade():
    assert negative_blocks("cera", "EXACT", "cera") is True
    assert negative_blocks("cera", "EXACT", "cera quente") is False


def test_negativa_que_bloqueia_keyword_propria_gera_finding_high():
    negatives = [{"campaign_id": "1", "campaign_name": "C1", "text": "laser", "match_type": "BROAD"}]
    positives = [
        {
            "campaign_id": "1", "campaign_name": "C1", "ad_group_name": "G1",
            "text": "depilacao laser", "match_type": "PHRASE", "status": "ENABLED",
        }
    ]

    findings = check_negatives_blocking_own_keywords(negatives, positives)

    assert len(findings) == 1
    assert findings[0]["check"] == "negative_blocks_own_keyword"
    assert findings[0]["severity"] == "high"
    assert findings[0]["details"]["negativa"] == "laser"
    assert findings[0]["details"]["keywords_bloqueadas"] == ["depilacao laser"]


def test_ignora_keyword_propria_pausada():
    negatives = [{"campaign_id": "1", "campaign_name": "C1", "text": "laser", "match_type": "BROAD"}]
    positives = [
        {
            "campaign_id": "1", "campaign_name": "C1", "ad_group_name": "G1",
            "text": "depilacao laser", "match_type": "PHRASE", "status": "PAUSED",
        }
    ]

    assert check_negatives_blocking_own_keywords(negatives, positives) == []


def test_negativa_que_bloqueia_termo_que_converteu():
    negatives = [{"campaign_id": "1", "campaign_name": "C1", "text": "laser sp", "match_type": "BROAD"}]
    search_terms = [
        {"name": "depilacao a laser sp zona sul", "clicks": 12, "conversions": 3.0},
        {"name": "depilacao a laser jardins", "clicks": 20, "conversions": 5.0},
    ]

    findings = check_negatives_blocking_converting_terms(negatives, search_terms)

    assert len(findings) == 1
    assert findings[0]["check"] == "negative_blocks_converting_term"
    assert findings[0]["severity"] == "high"  # teve conversão
    assert findings[0]["details"]["conversoes_bloqueadas"] == 3.0
    assert findings[0]["details"]["termos"] == ["depilacao a laser sp zona sul"]


def test_negativa_que_bloqueia_termo_sem_conversao_e_medium():
    negatives = [{"campaign_id": "1", "campaign_name": "C1", "text": "preco", "match_type": "BROAD"}]
    search_terms = [{"name": "depilacao laser preco", "clicks": 4, "conversions": 0.0}]

    findings = check_negatives_blocking_converting_terms(negatives, search_terms)

    assert findings[0]["severity"] == "medium"


def test_negativa_sem_termo_atingido_nao_gera_finding():
    negatives = [{"campaign_id": "1", "campaign_name": "C1", "text": "curso", "match_type": "BROAD"}]
    search_terms = [{"name": "depilacao laser jardins", "clicks": 10, "conversions": 1.0}]

    assert check_negatives_blocking_converting_terms(negatives, search_terms) == []
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: FAIL com `ImportError: cannot import name 'negative_blocks'`

- [ ] **Step 3: Implementar**

Adicionar `import re` ao topo de `analysis/integrity.py` e o código abaixo ao final:

```python
def _tokens(texto: str) -> List[str]:
    return [t for t in re.split(r"[^0-9a-zA-Zà-ÿÀ-Ÿ]+", texto.lower()) if t]


def negative_blocks(negative_text: str, match_type: str, query: str) -> bool:
    """Diz se uma palavra-chave negativa bloquearia a consulta dada.

    EXACT  -> só se a consulta for idêntica
    PHRASE -> só se a sequência aparecer contígua
    BROAD  -> se todos os tokens aparecerem, em qualquer ordem
    """
    negativa = _tokens(negative_text)
    consulta = _tokens(query)
    if not negativa:
        return False

    if match_type == "EXACT":
        return negativa == consulta

    if match_type == "PHRASE":
        limite = len(consulta) - len(negativa) + 1
        return any(consulta[i:i + len(negativa)] == negativa for i in range(max(limite, 0)))

    return set(negativa).issubset(set(consulta))


def check_negatives_blocking_own_keywords(
    negatives: List[Dict], positives: List[Dict]
) -> List[Dict]:
    """Negativa de campanha que bloqueia uma palavra-chave ativa da própria conta.

    É erro de configuração puro: a conta paga para ter a keyword e se impede de
    entregá-la.
    """
    findings = []
    for negativa in negatives:
        bloqueadas = [
            positiva["text"]
            for positiva in positives
            if positiva["campaign_id"] == negativa["campaign_id"]
            and positiva["status"] == "ENABLED"
            and negative_blocks(negativa["text"], negativa["match_type"], positiva["text"])
        ]
        if not bloqueadas:
            continue

        findings.append({
            "check": "negative_blocks_own_keyword",
            "severity": "high",
            "campaign_id": negativa["campaign_id"],
            "campaign_name": negativa["campaign_name"],
            "message": (
                f"Negativa '{negativa['text']}' [{negativa['match_type']}] bloqueia "
                f"{len(bloqueadas)} palavra(s)-chave ativa(s) da própria campanha."
            ),
            "details": {
                "negativa": negativa["text"],
                "match_type": negativa["match_type"],
                "keywords_bloqueadas": sorted(bloqueadas),
            },
        })
    return findings


def check_negatives_blocking_converting_terms(
    negatives: List[Dict], search_terms: List[Dict], *, min_clicks: int = 1
) -> List[Dict]:
    """Negativa que atinge termos de busca que já geraram clique ou conversão.

    Não é necessariamente erro — pode ser exclusão deliberada. Por isso o finding
    reporta o volume atingido em vez de afirmar que está errado.
    """
    findings = []
    for negativa in negatives:
        atingidos = [
            termo for termo in search_terms
            if termo.get("clicks", 0) >= min_clicks
            and negative_blocks(negativa["text"], negativa["match_type"], termo["name"])
        ]
        if not atingidos:
            continue

        conversoes = sum(termo.get("conversions", 0.0) for termo in atingidos)
        cliques = sum(termo.get("clicks", 0) for termo in atingidos)

        findings.append({
            "check": "negative_blocks_converting_term",
            "severity": "high" if conversoes > 0 else "medium",
            "campaign_id": negativa["campaign_id"],
            "campaign_name": negativa["campaign_name"],
            "message": (
                f"Negativa '{negativa['text']}' [{negativa['match_type']}] atinge "
                f"{len(atingidos)} termo(s) de busca com {cliques} clique(s) e "
                f"{conversoes:g} conversão(ões) no período."
            ),
            "details": {
                "negativa": negativa["text"],
                "match_type": negativa["match_type"],
                "termos": sorted(termo["name"] for termo in atingidos),
                "cliques_bloqueados": cliques,
                "conversoes_bloqueadas": conversoes,
            },
        })
    return findings
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: 14 passed

- [ ] **Step 5: Commit**

```bash
git add analysis/integrity.py analysis/tests/test_integrity.py
git commit -m "feat(analysis): checks de negativas bloqueando keywords e termos que convertem"
```

---

### Task 7: Checks de veiculação, ações de conversão e orçamento

**Files:**
- Modify: `analysis/integrity.py`
- Test: `analysis/tests/test_integrity.py`

**Interfaces:**
- Consumes: `fetch_ad_group_ads`, `fetch_campaign_budgets`, `fetch_conversion_action_breakdown` (Task 4) e `orcamento_mensal_cents` de `business_params` (Task 1).
- Produces:
  - `check_ad_serving_status(ad_group_ads) -> List[Dict]`
  - `check_conversion_action_composition(breakdown, *, limite_ruido: float = 0.05) -> List[Dict]`
  - `check_budget_ceiling(budgets, orcamento_mensal_cents) -> List[Dict]`

- [ ] **Step 1: Escrever o teste que falha**

Adicionar a `analysis/tests/test_integrity.py`:

```python
from analysis.integrity import (
    check_ad_serving_status,
    check_budget_ceiling,
    check_conversion_action_composition,
)


def _ad(**kwargs):
    base = {
        "campaign_id": "1", "campaign_name": "C1", "ad_group_name": "G1",
        "ad_group_status": "ENABLED", "ad_id": "10", "status": "ENABLED",
        "approval_status": "APPROVED", "review_status": "REVIEWED",
    }
    base.update(kwargs)
    return base


def test_anuncio_aprovado_em_grupo_ativo_nao_gera_finding():
    assert check_ad_serving_status([_ad()]) == []


def test_anuncio_reprovado_gera_finding_high():
    findings = check_ad_serving_status([_ad(approval_status="DISAPPROVED")])

    assert len(findings) == 1
    assert findings[0]["check"] == "ad_not_serving"
    assert findings[0]["severity"] == "high"


def test_anuncio_ativo_em_grupo_removido_gera_finding_low():
    findings = check_ad_serving_status([_ad(ad_group_status="REMOVED")])

    assert len(findings) == 1
    assert findings[0]["check"] == "ad_in_inactive_ad_group"
    assert findings[0]["severity"] == "low"


def test_uma_unica_acao_de_conversao_nao_gera_finding():
    breakdown = [{"name": "Lead - Formulário", "category": "SUBMIT_LEAD_FORM", "conversions": 41.0}]

    assert check_conversion_action_composition(breakdown) == []


def test_duas_acoes_relevantes_geram_finding_de_dupla_contagem():
    breakdown = [
        {"name": "Lead - Formulário", "category": "SUBMIT_LEAD_FORM", "conversions": 183.0},
        {"name": "Viu Obrigado Laser", "category": "SIGNUP", "conversions": 166.0},
    ]

    findings = check_conversion_action_composition(breakdown)

    assert len(findings) == 1
    assert findings[0]["check"] == "conversion_action_composition"
    assert findings[0]["severity"] == "high"
    assert findings[0]["details"]["acoes"][0]["name"] == "Lead - Formulário"
    assert len(findings[0]["details"]["acoes"]) == 2


def test_acao_residual_abaixo_do_limite_e_ignorada():
    breakdown = [
        {"name": "Lead - Formulário", "category": "SUBMIT_LEAD_FORM", "conversions": 100.0},
        {"name": "Ruído", "category": "CONTACT", "conversions": 1.0},
    ]

    assert check_conversion_action_composition(breakdown) == []


def test_orcamento_acima_do_teto_gera_finding():
    # R$ 100,00/dia x 30,4 = R$ 3.040,00, acima do teto de R$ 3.000,00
    budgets = [
        {"campaign_id": "1", "campaign_name": "C1", "campaign_status": "ENABLED", "amount_cents": 10000},
    ]

    findings = check_budget_ceiling(budgets, orcamento_mensal_cents=300000)

    assert len(findings) == 1
    assert findings[0]["check"] == "budget_over_monthly_ceiling"
    assert findings[0]["details"]["projecao_mensal_cents"] == 304000
    assert findings[0]["details"]["diario_maximo_para_o_teto_cents"] == 9868


def test_orcamento_dentro_do_teto_nao_gera_finding():
    # estado real da conta em 2026-08-12: R$ 85,00/dia x 30,4 = R$ 2.584,00 < R$ 3.000,00
    budgets = [
        {"campaign_id": "1", "campaign_name": "C1", "campaign_status": "ENABLED", "amount_cents": 8500},
    ]

    assert check_budget_ceiling(budgets, orcamento_mensal_cents=300000) == []


def test_campanha_pausada_nao_conta_para_o_teto():
    budgets = [
        {"campaign_id": "1", "campaign_name": "C1", "campaign_status": "PAUSED", "amount_cents": 50000},
    ]

    assert check_budget_ceiling(budgets, orcamento_mensal_cents=300000) == []
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: FAIL com `ImportError: cannot import name 'check_ad_serving_status'`

- [ ] **Step 3: Implementar**

Adicionar ao final de `analysis/integrity.py`:

```python
_DIAS_NO_MES = 30.4


def check_ad_serving_status(ad_group_ads: List[Dict]) -> List[Dict]:
    """Anúncio que não veicula: reprovado, ou ativo dentro de grupo inativo."""
    findings = []
    for anuncio in ad_group_ads:
        if anuncio["status"] != "ENABLED":
            continue

        if anuncio["approval_status"] != "APPROVED":
            findings.append({
                "check": "ad_not_serving",
                "severity": "high",
                "campaign_id": anuncio["campaign_id"],
                "campaign_name": anuncio["campaign_name"],
                "message": (
                    f"Anúncio {anuncio['ad_id']} (grupo '{anuncio['ad_group_name']}') está "
                    f"ativo mas com aprovação {anuncio['approval_status']}."
                ),
                "details": {
                    "ad_id": anuncio["ad_id"],
                    "ad_group_name": anuncio["ad_group_name"],
                    "approval_status": anuncio["approval_status"],
                    "review_status": anuncio["review_status"],
                },
            })

        if anuncio["ad_group_status"] in ("PAUSED", "REMOVED"):
            findings.append({
                "check": "ad_in_inactive_ad_group",
                "severity": "low",
                "campaign_id": anuncio["campaign_id"],
                "campaign_name": anuncio["campaign_name"],
                "message": (
                    f"Anúncio {anuncio['ad_id']} está ENABLED dentro do grupo "
                    f"'{anuncio['ad_group_name']}' que está {anuncio['ad_group_status']} - não veicula."
                ),
                "details": {
                    "ad_id": anuncio["ad_id"],
                    "ad_group_name": anuncio["ad_group_name"],
                    "ad_group_status": anuncio["ad_group_status"],
                },
            })
    return findings


def check_conversion_action_composition(
    breakdown: List[Dict], *, limite_ruido: float = 0.05
) -> List[Dict]:
    """Mais de uma ação de conversão relevante somando no mesmo total.

    Importa porque `revenue_projected` multiplica `metrics.conversions` por uma taxa
    de agendamento. Se duas ações registram o mesmo evento (ex.: submit de formulário
    e pageview da página de obrigado), a receita projetada infla na mesma proporção.
    """
    total = sum(acao["conversions"] for acao in breakdown)
    if total <= 0:
        return []

    relevantes = [
        acao for acao in breakdown
        if acao["conversions"] / total >= limite_ruido
    ]
    if len(relevantes) <= 1:
        return []

    ordenadas = sorted(relevantes, key=lambda a: -a["conversions"])
    return [{
        "check": "conversion_action_composition",
        "severity": "high",
        "campaign_id": "",
        "campaign_name": "(conta)",
        "message": (
            f"{len(ordenadas)} ações de conversão relevantes somam no mesmo total "
            f"({total:g} conversões). Verificar dupla contagem antes de confiar em "
            f"CPA e revenue_projected."
        ),
        "details": {
            "total_conversoes": total,
            "acoes": [
                {
                    "name": acao["name"],
                    "category": acao["category"],
                    "conversions": acao["conversions"],
                    "share": round(acao["conversions"] / total, 4),
                }
                for acao in ordenadas
            ],
        },
    }]


def check_budget_ceiling(
    budgets: List[Dict], orcamento_mensal_cents: int
) -> List[Dict]:
    """Soma dos orçamentos diários ativos projetada no mês contra o teto do cliente."""
    findings = []
    for orcamento in budgets:
        if orcamento["campaign_status"] != "ENABLED":
            continue

        projecao = round(orcamento["amount_cents"] * _DIAS_NO_MES)
        if projecao <= orcamento_mensal_cents:
            continue

        findings.append({
            "check": "budget_over_monthly_ceiling",
            "severity": "medium",
            "campaign_id": orcamento["campaign_id"],
            "campaign_name": orcamento["campaign_name"],
            "message": (
                f"Orçamento diário de R$ {orcamento['amount_cents'] / 100:.2f} projeta "
                f"R$ {projecao / 100:.2f} no mês, acima do teto de "
                f"R$ {orcamento_mensal_cents / 100:.2f}."
            ),
            "details": {
                "amount_cents": orcamento["amount_cents"],
                "projecao_mensal_cents": projecao,
                "teto_mensal_cents": orcamento_mensal_cents,
                "diario_maximo_para_o_teto_cents": round(orcamento_mensal_cents / _DIAS_NO_MES),
            },
        })
    return findings
```

- [ ] **Step 4: Rodar os testes**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: 23 passed

- [ ] **Step 5: Commit**

```bash
git add analysis/integrity.py analysis/tests/test_integrity.py
git commit -m "feat(analysis): checks de veiculação, ações de conversão e teto de orçamento"
```

---

### Task 8: Orquestrar os checks e ligar ao snapshot

**Files:**
- Modify: `analysis/integrity.py`
- Modify: `analysis/pull.py`
- Test: `analysis/tests/test_integrity.py`

**Interfaces:**
- Consumes: todos os checks das Tasks 5-7.
- Produces: `run_all_checks(*, ad_schedules, negatives, positives, search_terms, ad_group_ads, budgets, conversion_action_breakdown, business_params) -> List[Dict]` — findings de todos os checks, ordenados por severidade (`high`, `medium`, `low`) e depois por nome do check.

- [ ] **Step 1: Escrever o teste que falha**

```python
from analysis.integrity import run_all_checks


def test_run_all_checks_ordena_por_severidade():
    findings = run_all_checks(
        ad_schedules=[_janela("MONDAY", 0, 6)],  # gera high
        negatives=[],
        positives=[],
        search_terms=[],
        ad_group_ads=[_ad(ad_group_status="REMOVED")],  # gera low
        budgets=[
            {"campaign_id": "1", "campaign_name": "C1",
             "campaign_status": "ENABLED", "amount_cents": 10000},  # gera medium
        ],
        conversion_action_breakdown=[],
        business_params={"orcamento_mensal_cents": 300000},
    )

    severidades = [f["severity"] for f in findings]
    assert severidades == sorted(severidades, key=["high", "medium", "low"].index)
    assert {f["check"] for f in findings} == {
        "ad_schedule_gap", "budget_over_monthly_ceiling", "ad_in_inactive_ad_group",
    }


def test_run_all_checks_sem_problemas_devolve_lista_vazia():
    findings = run_all_checks(
        ad_schedules=[],
        negatives=[],
        positives=[],
        search_terms=[],
        ad_group_ads=[_ad()],
        budgets=[],
        conversion_action_breakdown=[],
        business_params={"orcamento_mensal_cents": 300000},
    )

    assert findings == []
```

- [ ] **Step 2: Rodar o teste para confirmar que falha**

Run: `python -m pytest analysis/tests/test_integrity.py -v`
Expected: FAIL com `ImportError: cannot import name 'run_all_checks'`

- [ ] **Step 3: Implementar o orquestrador**

Adicionar ao final de `analysis/integrity.py`:

```python
_ORDEM_SEVERIDADE = {"high": 0, "medium": 1, "low": 2}


def run_all_checks(
    *,
    ad_schedules: List[Dict],
    negatives: List[Dict],
    positives: List[Dict],
    search_terms: List[Dict],
    ad_group_ads: List[Dict],
    budgets: List[Dict],
    conversion_action_breakdown: List[Dict],
    business_params: Dict,
) -> List[Dict]:
    """Roda todos os checks e devolve os findings ordenados por severidade."""
    findings = [
        *check_ad_schedule_gaps(ad_schedules),
        *check_negatives_blocking_own_keywords(negatives, positives),
        *check_negatives_blocking_converting_terms(negatives, search_terms),
        *check_ad_serving_status(ad_group_ads),
        *check_conversion_action_composition(conversion_action_breakdown),
        *check_budget_ceiling(budgets, business_params["orcamento_mensal_cents"]),
    ]
    return sorted(
        findings,
        key=lambda f: (_ORDEM_SEVERIDADE[f["severity"]], f["check"], f["campaign_id"]),
    )
```

- [ ] **Step 4: Ligar na CLI**

Em `analysis/pull.py`, adicionar aos imports:

```python
from analysis.data.account_config import (
    fetch_ad_group_ads,
    fetch_ad_schedules,
    fetch_campaign_budgets,
    fetch_conversion_action_breakdown,
    fetch_negative_keywords,
    fetch_positive_keywords,
)
from analysis.integrity import run_all_checks
```

Alterar a assinatura de `run` para aceitar a flag:

```python
def run(*, customer: str, period: str, stage: str, out: str | None, skip_integrity: bool = False) -> dict:
```

Após a linha `gclid_map = click_view_gclid_map(...)`, inserir:

```python
    integrity_findings: list = []
    if not skip_integrity:
        integrity_findings = run_all_checks(
            ad_schedules=fetch_ad_schedules(client, customer),
            negatives=fetch_negative_keywords(client, customer),
            positives=fetch_positive_keywords(client, customer),
            search_terms=google_ads_data.get("search_terms", []),
            ad_group_ads=fetch_ad_group_ads(client, customer),
            budgets=fetch_campaign_budgets(client, customer),
            conversion_action_breakdown=fetch_conversion_action_breakdown(
                client, customer, start, end
            ),
            business_params=business_params,
        )
```

Passar `integrity_findings=integrity_findings,` ao `build_snapshot`.

Em `main()`, adicionar o argumento e repassá-lo:

```python
    parser.add_argument(
        "--skip-integrity",
        action="store_true",
        help="Pula os checks de integridade de configuração da conta",
    )
    args = parser.parse_args()

    run(
        customer=args.customer,
        period=args.period,
        stage=args.stage,
        out=args.out,
        skip_integrity=args.skip_integrity,
    )
```

- [ ] **Step 5: Rodar a suíte inteira**

Run: `python -m pytest analysis/ -v`
Expected: todos passando.

- [ ] **Step 6: Validar contra prod**

Run: `python -m analysis.pull --customer 4601912200 --period 30d --stage prod --out snapshot-teste.json`

Conferir `integrity.findings` no arquivo. Esperado hoje (2026-08-12), após as correções já aplicadas na conta:
- **Nenhum** `ad_schedule_gap` para a campanha ativa (os 10 critérios foram removidos em 2026-08-12).
- **Nenhum** finding de `laser sp` (a negativa foi removida em 2026-08-12).
- Um `ad_in_inactive_ad_group` para o anúncio `792441384201`, que está ENABLED dentro do grupo `Geral` (REMOVED).
- Provável `budget_over_monthly_ceiling` se o orçamento diário seguir em R$ 85 (projeta R$ 2.584 contra teto de R$ 3.000 — **não deve** disparar, já que 2584 < 3000; se disparar, há erro no cálculo).

Apagar o arquivo: `rm snapshot-teste.json`

- [ ] **Step 7: Commit**

```bash
git add analysis/integrity.py analysis/pull.py analysis/tests/test_integrity.py
git commit -m "feat(analysis): orquestra checks de integridade e liga ao snapshot"
```

---

### Task 9: Documentação

**Files:**
- Modify: `analysis/README.md`
- Modify: `.claude/skills/business-context/SKILL.md`

**Interfaces:**
- Consumes: contrato final do snapshot (Tasks 3 e 8).
- Produces: nada de código.

- [ ] **Step 1: Atualizar o contrato do snapshot no README**

Em `analysis/README.md`, substituir o bloco do contrato pelo formato novo:

```
meta:        { customer, clinic_id, period{start,end}, generated_at, currency, business_params }
targets:     { cpa_alvo_cents, roas_piso, ctr_alvo }
baseline:    { roas, cpa, ctr }            # do histórico real; roas/cpa suspensos (ver business-context)
period:
  google_ads:
    campaigns[], ad_groups[], ads[], keywords[],
    search_terms[], geo[], devices[], audiences[], age_ranges[], genders[]
    # cada linha: impressions, clicks, cost_cents, ctr, conversions,
    #             revenue_real, roas_real, cpa_real     (null onde falta click_view)
    #             revenue_projected, roas_projected      (sempre disponível)
  totals:     { cost_cents, clicks, impressions, conversions, ctr,
                revenue_projected, roas_projected, cpa }
  leads:      { total, com_gclid }
integrity:
  findings[]: { check, severity, campaign_id, campaign_name, message, details }
historical_cohort:
  customers[]: { gclid, ltv_cents, latencia_dias, recompras }
```

Adicionar uma seção documentando os 6 checks (`ad_schedule_gap`, `negative_blocks_own_keyword`, `negative_blocks_converting_term`, `ad_not_serving`, `ad_in_inactive_ad_group`, `conversion_action_composition`, `budget_over_monthly_ceiling`), com uma linha cada explicando o que detecta e por que importa, e a nota de que `--skip-integrity` desliga o bloco.

- [ ] **Step 2: Apontar a business-context para o JSON canônico**

Na seção "Receita: `revenue_projected`" de `.claude/skills/business-context/SKILL.md`, inserir logo acima da tabela de parâmetros:

```markdown
> **Fonte canônica:** os valores abaixo são lidos pelo código em
> `analysis/business_params.json`. A tabela aqui é espelho para leitura humana -
> ao mudar um valor, alterar os dois lugares no mesmo commit.
```

- [ ] **Step 3: Rodar a suíte inteira uma última vez**

Run: `python -m pytest analysis/ -v`
Expected: todos passando.

- [ ] **Step 4: Commit**

```bash
git add analysis/README.md .claude/skills/business-context/SKILL.md
git commit -m "docs(analysis): contrato do snapshot com integrity e revenue_projected"
```

---

## Fora de escopo (registrado para depois)

- **Fonte de verdade para realização de sessão.** Enquanto não existir, `revenue_real` segue suspenso e `baseline.roas`/`baseline.cpa` continuam sem sinal confiável. É o pré-requisito da Fatia 1 entregar receita real por termo.
- **Sincronização `scheduler.patients` x sistema da clínica.** Quebrada desde julho/2026 (cobertura 0%). Não é problema do pacote `analysis/`, mas invalida qualquer métrica derivada de `scheduler.appointments`.
- **Ajuste de lance por faixa etária.** Os dados já estão levantados (45+ consome 21,6% dos cliques e entrega 7,2% dos pacientes), mas recomendação de lance é `bid-optimizer`, da Fatia 2.
- **`change_event` no snapshot.** O histórico de mudanças ajudou muito no diagnóstico manual, mas a API só cobre 30 dias e o valor está em correlacionar mudança com queda de métrica - trabalho de analisador, não de fundação.
