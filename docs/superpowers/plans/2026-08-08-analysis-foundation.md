# Analysis Foundation (Fatia 0) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the standalone `analysis/` Python package that, given a `customer` and a `period`, pulls Google Ads data and real-conversion data from the scheduler's Supabase DB, computes deterministic KPIs (ROAS/CPA/CTR/LTV/latency), and emits a `snapshot.json` — the contract the next slices of the multi-agent optimizer will consume — plus the declarative `business-context` skill.

**Architecture:** Isolated package (`analysis/`), zero LLM calls, zero writes to `infra/` or `scheduler/`. Three layers: `data/` (I/O — Google Ads GAQL + Supabase SQL, returns raw dicts), `metrics.py` (pure functions, 100% unit-tested), `snapshot.py`/`pull.py` (assembly + CLI). Credentials load from SSM at runtime via a dedicated AWS profile (no serverless env injection, since this runs as a local script).

**Tech Stack:** Python 3.11+, `google-ads` (GoogleAdsClient, same `load_from_dict` pattern as `infra/`), `psycopg2-binary`, `boto3` (SSM), `pytest` + `unittest.mock`.

## Global Constraints

- **Zero LLM in this slice** — every number in the snapshot must be computed in Python and covered by a test (spec §7).
- **Secrets via SSM** `/${stage}/...`, AWS profile `dev-andre`, never hardcoded (spec §7, CLAUDE.md "Secrets management").
- **Google Ads client** initialized via `GoogleAdsClient.load_from_dict` with the standard dict shape from CLAUDE.md (`developer_token`, `client_id`, `client_secret`, `refresh_token`, `use_proto_plus: True`).
- **DB access**: `search_path=scheduler,public`; conversion definition is `appointments.status = 'CONFIRMED'` AND `appointments.appointment_date < CURRENT_DATE` — identical to `LeadService.get_pending_conversions` (`scheduler/src/services/lead_service.py:308-326`).
- **Naming**: `clinic_id` kebab-case; `customer_id` numeric string (e.g. `4601912200`).
- **Scope**: v1 only for Essência (the only clinic with `google_ads_customer_id` set).
- **No changes to `infra/` or `scheduler/`** — `analysis/` is a new, isolated top-level package.

## Resolved: origin of the Google Ads refresh_token (spec §6 open question)

Decision: **reuse the MCC-level SSM credentials**, the same ones `infra/src/services/google_ads_config.py::GoogleAdsConfig.get_google_ads_config()` and `GoogleAdsClientService.upload_offline_conversions` already use for cross-account calls — **not** the per-client Fernet-encrypted tokens in DynamoDB `Clients`. Reasoning: Essência is accessed as a child account under the MCC's `login_customer_id`, exactly like the offline-conversions uploader already does; there's no need to touch the encrypted per-client path (`google_ads_client_service.py::get_client_for_customer`), which exists for a different concern (managing multiple *system* clients, not pulling one known customer's data via the MCC).

SSM parameter names to read (mirrors `infra/serverless.yml:26-31`):
- `/${stage}/MCC_DEVELOPER_TOKEN` → `developer_token`
- `/${stage}/OAUTH2_CLIENT_ID` → `client_id`
- `/${stage}/OAUTH2_CLIENT_SECRET` → `client_secret`
- `/${stage}/GOOGLE_ADS_REFRESH_TOKEN` → `refresh_token`
- `/${stage}/MCC_ACCOUNT_ID` → `login_customer_id`
- `/${stage}/SUPABASE_DB_HOST`, `_PORT`, `_NAME`, `_USER`, `_PASSWORD` → Supabase/RDS connection (mirrors `scheduler/serverless.yml:38-42`)

---

## File Structure

| File | Responsibility |
|---|---|
| `analysis/__init__.py` | Package marker. |
| `analysis/config.py` | Loads Google Ads + Supabase config from SSM (profile `dev-andre`). |
| `analysis/data/__init__.py` | Package marker. |
| `analysis/data/conversions.py` | Supabase queries: resolve `clinic_id` from `customer_id`, leads in period, historical cohort. |
| `analysis/data/google_ads.py` | GAQL per dimension + `click_view` gclid map. |
| `analysis/metrics.py` | Pure functions: roas, cpa, ctr, dimension aggregation, baseline. |
| `analysis/snapshot.py` | Assembles + serializes `snapshot.json` per the contract. |
| `analysis/pull.py` | CLI orchestrator (`python -m analysis.pull`). |
| `analysis/tests/__init__.py` | Package marker. |
| `analysis/tests/test_metrics.py` | Unit tests for `metrics.py`. |
| `analysis/tests/test_conversions.py` | Unit tests for `data/conversions.py` (mocked DB cursor). |
| `analysis/tests/test_config.py` | Unit tests for `config.py` (mocked SSM). |
| `analysis/tests/test_snapshot.py` | Unit tests for `snapshot.py`. |
| `analysis/README.md` | How to run the pull, snapshot format, deps. |
| `requirements-analysis.txt` | `google-ads`, `psycopg2-binary`, `boto3`. |
| `.claude/skills/business-context/SKILL.md` | Declarative business context + ROAS/CPA/CTR targets. |

---

### Task 1: Package scaffolding + `config.py`

**Files:**
- Create: `analysis/__init__.py`
- Create: `analysis/config.py`
- Create: `analysis/tests/__init__.py`
- Create: `analysis/tests/test_config.py`
- Create: `requirements-analysis.txt`

**Interfaces:**
- Produces: `analysis.config.load_google_ads_config(stage: str) -> dict` — returns `{developer_token, client_id, client_secret, refresh_token, use_proto_plus: True, login_customer_id}`.
- Produces: `analysis.config.load_supabase_config(stage: str) -> dict` — returns `{host, port, dbname, user, password}`.
- Produces: `analysis.config.AWS_PROFILE = "dev-andre"` module constant.

- [ ] **Step 1: Create package markers**

```bash
mkdir -p analysis/tests
touch analysis/__init__.py analysis/tests/__init__.py
```

- [ ] **Step 2: Write the failing test for `load_google_ads_config`**

Create `analysis/tests/test_config.py`:

```python
from unittest.mock import MagicMock, patch

from analysis.config import load_google_ads_config, load_supabase_config

SSM_VALUES = {
    "/dev/MCC_DEVELOPER_TOKEN": "dev-token-123",
    "/dev/OAUTH2_CLIENT_ID": "client-id-abc",
    "/dev/OAUTH2_CLIENT_SECRET": "client-secret-xyz",
    "/dev/GOOGLE_ADS_REFRESH_TOKEN": "refresh-token-456",
    "/dev/MCC_ACCOUNT_ID": "123-456-7890",
    "/dev/SUPABASE_DB_HOST": "db.example.com",
    "/dev/SUPABASE_DB_PORT": "5432",
    "/dev/SUPABASE_DB_NAME": "postgres",
    "/dev/SUPABASE_DB_USER": "scheduler_app",
    "/dev/SUPABASE_DB_PASSWORD": "s3cr3t",
}


def _fake_ssm_client():
    def get_parameter(Name, WithDecryption=True):
        return {"Parameter": {"Value": SSM_VALUES[Name]}}

    client = MagicMock()
    client.get_parameter.side_effect = get_parameter
    return client


@patch("analysis.config.boto3.Session")
def test_load_google_ads_config_reads_mcc_params_from_ssm(mock_session_cls):
    mock_session = MagicMock()
    mock_session.client.return_value = _fake_ssm_client()
    mock_session_cls.return_value = mock_session

    config = load_google_ads_config("dev")

    mock_session_cls.assert_called_once_with(profile_name="dev-andre")
    assert config == {
        "developer_token": "dev-token-123",
        "client_id": "client-id-abc",
        "client_secret": "client-secret-xyz",
        "refresh_token": "refresh-token-456",
        "use_proto_plus": True,
        "login_customer_id": "1234567890",
    }


@patch("analysis.config.boto3.Session")
def test_load_supabase_config_reads_db_params_from_ssm(mock_session_cls):
    mock_session = MagicMock()
    mock_session.client.return_value = _fake_ssm_client()
    mock_session_cls.return_value = mock_session

    config = load_supabase_config("dev")

    assert config == {
        "host": "db.example.com",
        "port": "5432",
        "dbname": "postgres",
        "user": "scheduler_app",
        "password": "s3cr3t",
    }
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest analysis/tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.config'`

- [ ] **Step 4: Implement `analysis/config.py`**

```python
"""Carrega credenciais do Google Ads (MCC) e do Supabase via SSM."""
import boto3

AWS_PROFILE = "dev-andre"


def _ssm_client(stage: str):
    session = boto3.Session(profile_name=AWS_PROFILE)
    return session.client("ssm")


def _get_parameter(ssm, stage: str, name: str) -> str:
    response = ssm.get_parameter(Name=f"/{stage}/{name}", WithDecryption=True)
    return response["Parameter"]["Value"]


def load_google_ads_config(stage: str) -> dict:
    """Mesmo formato do infra/ (CLAUDE.md "Google Ads client initialization"),
    usando as credenciais do MCC — o mesmo caminho usado por
    infra/src/services/google_ads_config.py e pelo upload de conversões offline.
    """
    ssm = _ssm_client(stage)
    login_customer_id = _get_parameter(ssm, stage, "MCC_ACCOUNT_ID").replace("-", "")
    return {
        "developer_token": _get_parameter(ssm, stage, "MCC_DEVELOPER_TOKEN"),
        "client_id": _get_parameter(ssm, stage, "OAUTH2_CLIENT_ID"),
        "client_secret": _get_parameter(ssm, stage, "OAUTH2_CLIENT_SECRET"),
        "refresh_token": _get_parameter(ssm, stage, "GOOGLE_ADS_REFRESH_TOKEN"),
        "use_proto_plus": True,
        "login_customer_id": login_customer_id,
    }


def load_supabase_config(stage: str) -> dict:
    """Mesmos parâmetros SSM usados por scheduler/serverless.yml (SUPABASE_DB_*)."""
    ssm = _ssm_client(stage)
    return {
        "host": _get_parameter(ssm, stage, "SUPABASE_DB_HOST"),
        "port": _get_parameter(ssm, stage, "SUPABASE_DB_PORT"),
        "dbname": _get_parameter(ssm, stage, "SUPABASE_DB_NAME"),
        "user": _get_parameter(ssm, stage, "SUPABASE_DB_USER"),
        "password": _get_parameter(ssm, stage, "SUPABASE_DB_PASSWORD"),
    }
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest analysis/tests/test_config.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Create `requirements-analysis.txt`**

```
google-ads==27.0.0
psycopg2-binary==2.9.9
boto3==1.26.161
```

- [ ] **Step 7: Install deps and confirm imports resolve**

Run: `pip install -r requirements-analysis.txt`
Expected: install succeeds (or already satisfied, since `infra/requirements.txt` overlaps).

- [ ] **Step 8: Commit**

```bash
git add analysis/__init__.py analysis/config.py analysis/tests/__init__.py analysis/tests/test_config.py requirements-analysis.txt
git commit -m "feat(analysis): add SSM-backed config loader for Google Ads MCC + Supabase"
```

---

### Task 2: `data/conversions.py` — Supabase queries

**Files:**
- Create: `analysis/data/__init__.py`
- Create: `analysis/data/conversions.py`
- Create: `analysis/tests/test_conversions.py`

**Interfaces:**
- Consumes: `load_supabase_config(stage) -> dict` from Task 1 (used only by callers of `get_connection`, not by the tests below, which mock the connection directly).
- Produces: `analysis.data.conversions.get_connection(supabase_config: dict) -> psycopg2.connection`
- Produces: `analysis.data.conversions.resolve_clinic_id(conn, customer_id: str) -> str`
- Produces: `analysis.data.conversions.leads_in_period(conn, clinic_id: str, start: date, end: date) -> list[dict]` — each dict has `id, gclid, created_at, metadata`.
- Produces: `analysis.data.conversions.historical_cohort(conn, clinic_id: str) -> list[dict]` — each dict has `gclid, ltv_cents, latencia_dias, recompras`.

- [ ] **Step 1: Create `analysis/data/__init__.py`**

```bash
mkdir -p analysis/data
touch analysis/data/__init__.py
```

- [ ] **Step 2: Write the failing tests**

Create `analysis/tests/test_conversions.py`:

```python
from datetime import date, datetime
from unittest.mock import MagicMock

from analysis.data.conversions import (
    historical_cohort,
    leads_in_period,
    resolve_clinic_id,
)


def _conn_returning(rows):
    """Fake psycopg2 connection whose cursor().fetchone()/fetchall() return `rows`."""
    cursor = MagicMock()
    cursor.__enter__.return_value = cursor
    cursor.__exit__.return_value = False
    cursor.fetchall.return_value = rows
    cursor.fetchone.return_value = rows[0] if rows else None

    conn = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_resolve_clinic_id_returns_clinic_id_for_customer():
    conn, cursor = _conn_returning([{"clinic_id": "essencia-sp-abc123"}])

    clinic_id = resolve_clinic_id(conn, "4601912200")

    assert clinic_id == "essencia-sp-abc123"
    cursor.execute.assert_called_once()
    query, params = cursor.execute.call_args[0]
    assert "google_ads_customer_id" in query
    assert params == ("4601912200",)


def test_resolve_clinic_id_raises_when_customer_not_found():
    conn, _ = _conn_returning([])

    try:
        resolve_clinic_id(conn, "0000000000")
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "0000000000" in str(exc)


def test_leads_in_period_returns_rows_from_query():
    expected_rows = [
        {"id": "lead-1", "gclid": "abc", "created_at": datetime(2026, 7, 1), "metadata": {}},
    ]
    conn, cursor = _conn_returning(expected_rows)

    rows = leads_in_period(conn, "essencia-sp-abc123", date(2026, 7, 1), date(2026, 7, 31))

    assert rows == expected_rows
    query, params = cursor.execute.call_args[0]
    assert "leads" in query
    assert params == ("essencia-sp-abc123", date(2026, 7, 1), date(2026, 7, 31))


def test_historical_cohort_computes_latencia_and_recompras():
    raw_rows = [
        {
            "gclid": "abc",
            "click_date": datetime(2026, 1, 1),
            "first_conversion_date": date(2026, 1, 10),
            "total_conversions": 3,
            "ltv_cents": 45000,
        }
    ]
    conn, cursor = _conn_returning(raw_rows)

    cohort = historical_cohort(conn, "essencia-sp-abc123")

    assert cohort == [
        {
            "gclid": "abc",
            "click_date": datetime(2026, 1, 1),
            "first_conversion_date": date(2026, 1, 10),
            "total_conversions": 3,
            "ltv_cents": 45000,
            "latencia_dias": 9,
            "recompras": 2,
        }
    ]
    query = cursor.execute.call_args[0][0]
    assert "CONFIRMED" in query
    assert "appointment_date < CURRENT_DATE" in query
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `python -m pytest analysis/tests/test_conversions.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.data.conversions'`

- [ ] **Step 4: Implement `analysis/data/conversions.py`**

```python
"""Consultas determinísticas de conversão real no Supabase do scheduler."""
from datetime import date
from typing import Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor


def get_connection(supabase_config: Dict):
    return psycopg2.connect(
        host=supabase_config["host"],
        port=supabase_config["port"],
        dbname=supabase_config["dbname"],
        user=supabase_config["user"],
        password=supabase_config["password"],
        options="-c search_path=scheduler,public",
    )


def resolve_clinic_id(conn, customer_id: str) -> str:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            "SELECT clinic_id FROM clinics WHERE google_ads_customer_id = %s",
            (customer_id,),
        )
        row = cur.fetchone()
    if row is None:
        raise ValueError(f"Nenhuma clinic encontrada para customer_id={customer_id}")
    return row["clinic_id"]


def leads_in_period(conn, clinic_id: str, start: date, end: date) -> List[Dict]:
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT id, gclid, created_at, metadata
            FROM leads
            WHERE clinic_id = %s
              AND created_at::date BETWEEN %s AND %s
            """,
            (clinic_id, start, end),
        )
        return cur.fetchall()


def historical_cohort(conn, clinic_id: str) -> List[Dict]:
    """Coorte all-time: para cada gclid com >=1 conversão real, LTV/latência/recompras.

    Conversão real = appointments.status = 'CONFIRMED' AND appointment_date < CURRENT_DATE,
    idêntico a LeadService.get_pending_conversions.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT
                lc.gclid,
                MIN(lc.click_date) AS click_date,
                MIN(lc.conversion_date) AS first_conversion_date,
                COUNT(*) AS total_conversions,
                SUM(lc.value_cents) AS ltv_cents
            FROM lead_conversions lc
            JOIN appointments a ON a.id = lc.appointment_id
            WHERE lc.clinic_id = %s
              AND a.status = 'CONFIRMED'
              AND a.appointment_date < CURRENT_DATE
            GROUP BY lc.gclid
            """,
            (clinic_id,),
        )
        rows = cur.fetchall()

    for row in rows:
        click_date = row["click_date"]
        first_conversion = row["first_conversion_date"]
        click_date_only = click_date.date() if hasattr(click_date, "date") else click_date
        row["latencia_dias"] = (first_conversion - click_date_only).days
        row["recompras"] = max(row["total_conversions"] - 1, 0)

    return rows
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `python -m pytest analysis/tests/test_conversions.py -v`
Expected: PASS (4 tests)

- [ ] **Step 6: Commit**

```bash
git add analysis/data/__init__.py analysis/data/conversions.py analysis/tests/test_conversions.py
git commit -m "feat(analysis): add Supabase queries for clinic resolution and conversion cohort"
```

---

### Task 3: `metrics.py` — pure deterministic functions

**Files:**
- Create: `analysis/metrics.py`
- Create: `analysis/tests/test_metrics.py`

**Interfaces:**
- Consumes: nothing (pure functions, no I/O).
- Produces: `roas(revenue_cents, cost_cents) -> float | None`
- Produces: `cpa(cost_cents, conversions) -> float | None`
- Produces: `ctr(clicks, impressions) -> float | None`
- Produces: `conversion_rate(conversions, clicks) -> float | None`
- Produces: `aggregate_dimension(rows: list[dict], revenue_by_gclid: dict[str,int], gclid_by_dimension_id: dict[str, list[str]] | None) -> list[dict]` — each input row must have `id, impressions, clicks, cost_micros, conversions`; each output row adds `cost_cents, ctr, revenue_real, roas_real, cpa_real`. `gclid_by_dimension_id=None` means "no click_view coverage for this dimension" → `revenue_real/roas_real` always `None` for every row.
- Produces: `baseline(historical_cohort: list[dict], ads_totals: dict) -> dict` — `ads_totals` has `cost_cents, clicks, impressions`; returns `{roas, cpa, ctr}`.

- [ ] **Step 1: Write the failing tests**

Create `analysis/tests/test_metrics.py`:

```python
from analysis.metrics import (
    aggregate_dimension,
    baseline,
    conversion_rate,
    cpa,
    ctr,
    roas,
)


def test_roas_divides_revenue_by_cost():
    assert roas(revenue_cents=30000, cost_cents=10000) == 3.0


def test_roas_returns_none_when_cost_is_zero():
    assert roas(revenue_cents=30000, cost_cents=0) is None


def test_cpa_divides_cost_by_conversions():
    assert cpa(cost_cents=10000, conversions=4) == 2500.0


def test_cpa_returns_none_when_no_conversions():
    assert cpa(cost_cents=10000, conversions=0) is None


def test_ctr_divides_clicks_by_impressions():
    assert ctr(clicks=50, impressions=1000) == 0.05


def test_ctr_returns_none_when_no_impressions():
    assert ctr(clicks=0, impressions=0) is None


def test_conversion_rate_divides_conversions_by_clicks():
    assert conversion_rate(conversions=5, clicks=100) == 0.05


def test_conversion_rate_returns_none_when_no_clicks():
    assert conversion_rate(conversions=0, clicks=0) is None


def test_aggregate_dimension_with_click_view_coverage():
    rows = [
        {"id": "111", "impressions": 1000, "clicks": 50, "cost_micros": 100_000_000, "conversions": 4.0},
    ]
    revenue_by_gclid = {"gclid-a": 20000, "gclid-b": 10000}
    gclid_by_dimension_id = {"111": ["gclid-a", "gclid-b"]}

    result = aggregate_dimension(rows, revenue_by_gclid, gclid_by_dimension_id)

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
        }
    ]


def test_aggregate_dimension_without_click_view_coverage_is_null():
    rows = [
        {"id": "kw-1", "impressions": 200, "clicks": 10, "cost_micros": 20_000_000, "conversions": 1.0},
    ]

    result = aggregate_dimension(rows, revenue_by_gclid={}, gclid_by_dimension_id=None)

    assert result[0]["revenue_real"] is None
    assert result[0]["roas_real"] is None
    assert result[0]["cpa_real"] == 2000.0


def test_baseline_computes_roas_cpa_ctr_from_cohort_and_ads_totals():
    historical_cohort = [
        {"gclid": "a", "ltv_cents": 20000},
        {"gclid": "b", "ltv_cents": 10000},
    ]
    ads_totals = {"cost_cents": 15000, "clicks": 300, "impressions": 6000}

    result = baseline(historical_cohort, ads_totals)

    assert result == {"roas": 2.0, "cpa": 7500.0, "ctr": 0.05}
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest analysis/tests/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.metrics'`

- [ ] **Step 3: Implement `analysis/metrics.py`**

```python
"""Funções puras de métricas do analysis/. Sem I/O — 100% testável."""
from typing import Dict, List, Optional


def roas(revenue_cents: int, cost_cents: int) -> Optional[float]:
    if not cost_cents:
        return None
    return round(revenue_cents / cost_cents, 4)


def cpa(cost_cents: int, conversions: float) -> Optional[float]:
    if not conversions:
        return None
    return round(cost_cents / conversions, 2)


def ctr(clicks: int, impressions: int) -> Optional[float]:
    if not impressions:
        return None
    return round(clicks / impressions, 6)


def conversion_rate(conversions: float, clicks: int) -> Optional[float]:
    if not clicks:
        return None
    return round(conversions / clicks, 6)


def aggregate_dimension(
    rows: List[Dict],
    revenue_by_gclid: Dict[str, int],
    gclid_by_dimension_id: Optional[Dict[str, List[str]]],
) -> List[Dict]:
    """Junta métricas do Google com receita real por dimensão.

    `gclid_by_dimension_id=None` sinaliza que o click_view não cobre essa
    dimensão inteira (ex.: keywords, search_terms, geo, audiences) — nesse
    caso revenue_real/roas_real ficam null para todas as linhas, conforme o
    contrato do snapshot.
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

        aggregated.append({
            **row,
            "cost_cents": cost_cents,
            "ctr": ctr(row["clicks"], row["impressions"]),
            "revenue_real": revenue_real,
            "roas_real": roas(revenue_real, cost_cents) if revenue_real is not None else None,
            "cpa_real": cpa(cost_cents, conversions),
        })
    return aggregated


def baseline(historical_cohort: List[Dict], ads_totals: Dict) -> Dict:
    revenue_cents = sum(row["ltv_cents"] for row in historical_cohort)
    conversions = len(historical_cohort)
    return {
        "roas": roas(revenue_cents, ads_totals["cost_cents"]),
        "cpa": cpa(ads_totals["cost_cents"], conversions),
        "ctr": ctr(ads_totals["clicks"], ads_totals["impressions"]),
    }
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest analysis/tests/test_metrics.py -v`
Expected: PASS (10 tests)

- [ ] **Step 5: Commit**

```bash
git add analysis/metrics.py analysis/tests/test_metrics.py
git commit -m "feat(analysis): add pure metrics functions (roas, cpa, ctr, dimension aggregation, baseline)"
```

---

### Task 4: `data/google_ads.py` — GAQL per dimension + click_view

**Files:**
- Create: `analysis/data/google_ads.py`
- Create: `analysis/tests/test_google_ads.py`

**Interfaces:**
- Consumes: a `GoogleAdsClient`-shaped object (mocked in tests) whose `.get_service("GoogleAdsService").search_stream(customer_id, query)` yields batches with `.results`.
- Produces: `analysis.data.google_ads.DIMENSIONS = ["campaigns", "ad_groups", "ads", "keywords", "search_terms", "geo", "devices", "audiences"]`
- Produces: `analysis.data.google_ads.fetch_dimension(client, customer_id: str, dimension: str, start: str, end: str) -> list[dict]` — each dict has `id, name, impressions, clicks, cost_micros, conversions`.
- Produces: `analysis.data.google_ads.fetch_all_dimensions(client, customer_id: str, start: str, end: str) -> dict[str, list[dict]]` keyed by entries of `DIMENSIONS`.
- Produces: `analysis.data.google_ads.click_view_gclid_map(client, customer_id: str, start: str, end: str) -> dict[str, dict]` — keyed by `gclid`, value has `campaign_id, ad_group_id, device, date` (fields not covered by `click_view` — keyword, geo — are simply absent).

- [ ] **Step 1: Write the failing tests**

Create `analysis/tests/test_google_ads.py`:

```python
from unittest.mock import MagicMock

from analysis.data.google_ads import (
    DIMENSIONS,
    click_view_gclid_map,
    fetch_all_dimensions,
    fetch_dimension,
)


def _make_row(**attrs):
    row = MagicMock()
    for path, value in attrs.items():
        target = row
        parts = path.split(".")
        for part in parts[:-1]:
            target = getattr(target, part)
        setattr(target, parts[-1], value)
    return row


def _client_with_rows(rows):
    batch = MagicMock()
    batch.results = rows
    service = MagicMock()
    service.search_stream.return_value = [batch]
    client = MagicMock()
    client.get_service.return_value = service
    return client, service


def test_fetch_dimension_maps_campaign_rows():
    row = _make_row(
        **{
            "campaign.id": 111,
            "campaign.name": "Campanha SP",
            "metrics.impressions": 1000,
            "metrics.clicks": 50,
            "metrics.cost_micros": 100_000_000,
            "metrics.conversions": 4.0,
        }
    )
    client, service = _client_with_rows([row])

    result = fetch_dimension(client, "4601912200", "campaigns", "2026-07-01", "2026-07-31")

    assert result == [
        {
            "id": "111",
            "name": "Campanha SP",
            "impressions": 1000,
            "clicks": 50,
            "cost_micros": 100_000_000,
            "conversions": 4.0,
        }
    ]
    query = service.search_stream.call_args.kwargs["query"]
    assert "campaign" in query
    assert "2026-07-01" in query and "2026-07-31" in query


def test_fetch_dimension_rejects_unknown_dimension():
    client = MagicMock()
    try:
        fetch_dimension(client, "4601912200", "not-a-dimension", "2026-07-01", "2026-07-31")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_fetch_all_dimensions_covers_every_dimension():
    client, _ = _client_with_rows([])

    result = fetch_all_dimensions(client, "4601912200", "2026-07-01", "2026-07-31")

    assert set(result.keys()) == set(DIMENSIONS)


def test_click_view_gclid_map_keys_by_gclid():
    row = _make_row(
        **{
            "click_view.gclid": "gclid-a",
            "campaign.id": 111,
            "ad_group.id": 222,
            "segments.device": MagicMock(name="DESKTOP"),
            "segments.date": "2026-06-15",
        }
    )
    row.segments.device.name = "DESKTOP"
    client, service = _client_with_rows([row])

    result = click_view_gclid_map(client, "4601912200", "2026-04-01", "2026-07-31")

    assert result == {
        "gclid-a": {
            "campaign_id": "111",
            "ad_group_id": "222",
            "device": "DESKTOP",
            "date": "2026-06-15",
        }
    }
    query = service.search_stream.call_args.kwargs["query"]
    assert "click_view" in query
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest analysis/tests/test_google_ads.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.data.google_ads'`

- [ ] **Step 3: Implement `analysis/data/google_ads.py`**

```python
"""GAQL por dimensão + click_view (gclid -> dimensões finas), via GoogleAdsService."""
from typing import Dict, List

DIMENSIONS = [
    "campaigns", "ad_groups", "ads", "keywords",
    "search_terms", "geo", "devices", "audiences",
]

_METRICS_FIELDS = (
    "metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions"
)

_DIMENSION_QUERIES = {
    "campaigns": (
        "SELECT campaign.id, campaign.name, {metrics} "
        "FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "ad_groups": (
        "SELECT ad_group.id, ad_group.name, {metrics} "
        "FROM ad_group WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "ads": (
        "SELECT ad_group_ad.ad.id, ad_group_ad.ad.name, {metrics} "
        "FROM ad_group_ad WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "keywords": (
        "SELECT ad_group_criterion.criterion_id, ad_group_criterion.keyword.text, {metrics} "
        "FROM keyword_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "search_terms": (
        "SELECT search_term_view.search_term, search_term_view.search_term, {metrics} "
        "FROM search_term_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "geo": (
        "SELECT geographic_view.country_criterion_id, geographic_view.country_criterion_id, {metrics} "
        "FROM geographic_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "devices": (
        "SELECT segments.device, segments.device, {metrics} "
        "FROM campaign WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "audiences": (
        "SELECT campaign_audience_view.resource_name, campaign_audience_view.resource_name, {metrics} "
        "FROM campaign_audience_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
}

_CLICK_VIEW_QUERY = (
    "SELECT click_view.gclid, campaign.id, ad_group.id, segments.device, segments.date "
    "FROM click_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
)


def _resolve(row, path: str):
    target = row
    for part in path.split("."):
        target = getattr(target, part)
    return target


def fetch_dimension(client, customer_id: str, dimension: str, start: str, end: str) -> List[Dict]:
    if dimension not in _DIMENSION_QUERIES:
        raise ValueError(f"Dimensão desconhecida: {dimension}")

    template = _DIMENSION_QUERIES[dimension]
    query = template.format(metrics=_METRICS_FIELDS, start=start, end=end)
    id_path, name_path = _ID_NAME_PATHS[dimension]

    ga_service = client.get_service("GoogleAdsService")
    stream = ga_service.search_stream(customer_id=customer_id, query=query)

    rows = []
    for batch in stream:
        for row in batch.results:
            rows.append({
                "id": str(_resolve(row, id_path)),
                "name": str(_resolve(row, name_path)),
                "impressions": row.metrics.impressions,
                "clicks": row.metrics.clicks,
                "cost_micros": row.metrics.cost_micros,
                "conversions": row.metrics.conversions,
            })
    return rows


_ID_NAME_PATHS = {
    "campaigns": ("campaign.id", "campaign.name"),
    "ad_groups": ("ad_group.id", "ad_group.name"),
    "ads": ("ad_group_ad.ad.id", "ad_group_ad.ad.name"),
    "keywords": ("ad_group_criterion.criterion_id", "ad_group_criterion.keyword.text"),
    "search_terms": ("search_term_view.search_term", "search_term_view.search_term"),
    "geo": ("geographic_view.country_criterion_id", "geographic_view.country_criterion_id"),
    "devices": ("segments.device", "segments.device"),
    "audiences": ("campaign_audience_view.resource_name", "campaign_audience_view.resource_name"),
}


def fetch_all_dimensions(client, customer_id: str, start: str, end: str) -> Dict[str, List[Dict]]:
    return {
        dimension: fetch_dimension(client, customer_id, dimension, start, end)
        for dimension in DIMENSIONS
    }


def click_view_gclid_map(client, customer_id: str, start: str, end: str) -> Dict[str, Dict]:
    """Mapeia gclid -> {campaign_id, ad_group_id, device, date}, janela de até 90 dias.

    click_view não cobre keyword nem geo diretamente — dimensões finas sem
    cobertura ficam de fora deste mapa (o chamador trata como null).
    """
    query = _CLICK_VIEW_QUERY.format(start=start, end=end)
    ga_service = client.get_service("GoogleAdsService")
    stream = ga_service.search_stream(customer_id=customer_id, query=query)

    gclid_map = {}
    for batch in stream:
        for row in batch.results:
            gclid_map[row.click_view.gclid] = {
                "campaign_id": str(row.campaign.id),
                "ad_group_id": str(row.ad_group.id),
                "device": row.segments.device.name,
                "date": row.segments.date,
            }
    return gclid_map
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest analysis/tests/test_google_ads.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add analysis/data/google_ads.py analysis/tests/test_google_ads.py
git commit -m "feat(analysis): add GAQL pulls per dimension and click_view gclid map"
```

---

### Task 5: `snapshot.py` — assemble and serialize the contract

**Files:**
- Create: `analysis/snapshot.py`
- Create: `analysis/tests/test_snapshot.py`

**Interfaces:**
- Consumes: `aggregate_dimension`, `baseline` from Task 3; raw dimension rows shaped like Task 4's output; `leads_in_period`/`historical_cohort` shaped like Task 2's output.
- Produces: `analysis.snapshot.build_snapshot(*, customer: str, clinic_id: str, period_start: str, period_end: str, google_ads_data: dict[str, list[dict]], gclid_map: dict[str, dict], leads: list[dict], historical_cohort: list[dict], currency: str = "BRL") -> dict` — returns the full snapshot contract (spec §6 "Contrato do snapshot.json").
- Produces: `analysis.snapshot.write_snapshot(snapshot: dict, out_path: str | None) -> None` — writes JSON to `out_path`, or prints to stdout if `None`.

- [ ] **Step 1: Write the failing tests**

Create `analysis/tests/test_snapshot.py`:

```python
import json

from analysis.snapshot import build_snapshot, write_snapshot


def _sample_inputs():
    google_ads_data = {
        "campaigns": [
            {"id": "111", "name": "Campanha SP", "impressions": 1000, "clicks": 50,
             "cost_micros": 100_000_000, "conversions": 4.0},
        ],
        "keywords": [
            {"id": "kw-1", "name": "depilação a laser", "impressions": 200, "clicks": 10,
             "cost_micros": 20_000_000, "conversions": 1.0},
        ],
    }
    gclid_map = {
        "gclid-a": {"campaign_id": "111", "ad_group_id": "222", "device": "DESKTOP", "date": "2026-06-15"},
    }
    leads = [
        {"id": "lead-1", "gclid": "gclid-a", "created_at": "2026-07-02T10:00:00", "metadata": {"device": "DESKTOP"}},
        {"id": "lead-2", "gclid": None, "created_at": "2026-07-03T11:00:00", "metadata": {}},
    ]
    historical_cohort = [
        {"gclid": "gclid-a", "ltv_cents": 20000, "latencia_dias": 9, "recompras": 1},
    ]
    return google_ads_data, gclid_map, leads, historical_cohort


def test_build_snapshot_matches_contract_shape():
    google_ads_data, gclid_map, leads, historical_cohort = _sample_inputs()

    snapshot = build_snapshot(
        customer="4601912200",
        clinic_id="essencia-sp-abc123",
        period_start="2026-07-01",
        period_end="2026-07-31",
        google_ads_data=google_ads_data,
        gclid_map=gclid_map,
        leads=leads,
        historical_cohort=historical_cohort,
    )

    assert snapshot["meta"]["customer"] == "4601912200"
    assert snapshot["meta"]["clinic_id"] == "essencia-sp-abc123"
    assert snapshot["meta"]["period"] == {"start": "2026-07-01", "end": "2026-07-31"}
    assert snapshot["meta"]["currency"] == "BRL"
    assert "generated_at" in snapshot["meta"]

    assert snapshot["baseline"] == {"roas": 2.0, "cpa": 20000.0, "ctr": None}

    campaigns = snapshot["period"]["google_ads"]["campaigns"]
    assert campaigns[0]["revenue_real"] == 20000
    assert campaigns[0]["roas_real"] == 2.0

    keywords = snapshot["period"]["google_ads"]["keywords"]
    assert keywords[0]["revenue_real"] is None
    assert keywords[0]["roas_real"] is None

    assert snapshot["period"]["leads"]["total"] == 2
    assert snapshot["period"]["leads"]["com_gclid"] == 1

    assert snapshot["historical_cohort"]["customers"] == historical_cohort


def test_write_snapshot_serializes_to_file(tmp_path):
    google_ads_data, gclid_map, leads, historical_cohort = _sample_inputs()
    snapshot = build_snapshot(
        customer="4601912200",
        clinic_id="essencia-sp-abc123",
        period_start="2026-07-01",
        period_end="2026-07-31",
        google_ads_data=google_ads_data,
        gclid_map=gclid_map,
        leads=leads,
        historical_cohort=historical_cohort,
    )
    out_file = tmp_path / "snapshot.json"

    write_snapshot(snapshot, str(out_file))

    loaded = json.loads(out_file.read_text())
    assert loaded["meta"]["customer"] == "4601912200"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest analysis/tests/test_snapshot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.snapshot'`

- [ ] **Step 3: Implement `analysis/snapshot.py`**

```python
"""Monta e serializa o snapshot.json — contrato consumido pelos analisadores."""
import json
from datetime import datetime, timezone
from typing import Dict, List, Optional

from analysis.metrics import aggregate_dimension, baseline

# Dimensões cobertas pelo click_view (campaign_id/ad_group_id via gclid_map).
# As demais (ads, keywords, search_terms, geo, audiences) não têm cobertura
# fina de click_view e ficam com revenue_real/roas_real = null.
_CLICK_VIEW_COVERED_DIMENSIONS = {"campaigns": "campaign_id", "ad_groups": "ad_group_id"}


def _revenue_by_gclid(historical_cohort: List[Dict]) -> Dict[str, int]:
    return {row["gclid"]: row["ltv_cents"] for row in historical_cohort}


def _gclid_by_dimension_id(gclid_map: Dict[str, Dict], key: str) -> Dict[str, List[str]]:
    mapping: Dict[str, List[str]] = {}
    for gclid, attrs in gclid_map.items():
        dimension_id = attrs.get(key)
        if dimension_id is None:
            continue
        mapping.setdefault(dimension_id, []).append(gclid)
    return mapping


def _ads_totals(google_ads_data: Dict[str, List[Dict]]) -> Dict:
    campaigns = google_ads_data.get("campaigns", [])
    return {
        "cost_cents": round(sum(row["cost_micros"] for row in campaigns) / 10_000),
        "clicks": sum(row["clicks"] for row in campaigns),
        "impressions": sum(row["impressions"] for row in campaigns),
    }


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
            rows, revenue_by_gclid, gclid_by_dimension_id
        )

    leads_com_gclid = [lead for lead in leads if lead.get("gclid")]

    return {
        "meta": {
            "customer": customer,
            "clinic_id": clinic_id,
            "period": {"start": period_start, "end": period_end},
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "currency": currency,
        },
        "baseline": baseline(historical_cohort, _ads_totals(google_ads_data)),
        "period": {
            "google_ads": period_google_ads,
            "leads": {
                "total": len(leads),
                "com_gclid": len(leads_com_gclid),
            },
        },
        "historical_cohort": {
            "customers": historical_cohort,
        },
    }


def write_snapshot(snapshot: Dict, out_path: Optional[str]) -> None:
    payload = json.dumps(snapshot, indent=2, ensure_ascii=False, default=str)
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(payload)
    else:
        print(payload)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest analysis/tests/test_snapshot.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add analysis/snapshot.py analysis/tests/test_snapshot.py
git commit -m "feat(analysis): assemble and serialize the snapshot.json contract"
```

---

### Task 6: `pull.py` — CLI orchestrator

**Files:**
- Create: `analysis/pull.py`
- Create: `analysis/tests/test_pull.py`

**Interfaces:**
- Consumes: `load_google_ads_config`, `load_supabase_config` (Task 1); `get_connection`, `resolve_clinic_id`, `leads_in_period`, `historical_cohort` (Task 2); `fetch_all_dimensions`, `click_view_gclid_map` (Task 4); `build_snapshot`, `write_snapshot` (Task 5).
- Produces: `analysis.pull.parse_period(period: str) -> tuple[str, str]` — accepts `"Nd"` (e.g. `"30d"`) or `"YYYY-MM-DD:YYYY-MM-DD"`, returns `(start, end)` as ISO date strings.
- Produces: `analysis.pull.run(*, customer: str, period: str, stage: str, out: str | None) -> dict` — orchestrates the full pull and returns the snapshot dict (also written via `write_snapshot`).
- Produces: `analysis.pull.main()` — argparse entrypoint (`--customer`, `--period`, `--stage` default `dev`, `--out` default `None`).

- [ ] **Step 1: Write the failing tests**

Create `analysis/tests/test_pull.py`:

```python
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from analysis.pull import parse_period, run


def test_parse_period_accepts_relative_days():
    start, end = parse_period("30d")
    expected_end = date.today()
    expected_start = expected_end - timedelta(days=30)
    assert start == expected_start.isoformat()
    assert end == expected_end.isoformat()


def test_parse_period_accepts_explicit_range():
    start, end = parse_period("2026-06-01:2026-06-30")
    assert start == "2026-06-01"
    assert end == "2026-06-30"


@patch("analysis.pull.write_snapshot")
@patch("analysis.pull.click_view_gclid_map")
@patch("analysis.pull.fetch_all_dimensions")
@patch("analysis.pull.historical_cohort")
@patch("analysis.pull.leads_in_period")
@patch("analysis.pull.resolve_clinic_id")
@patch("analysis.pull.get_connection")
@patch("analysis.pull.load_supabase_config")
@patch("analysis.pull.load_google_ads_config")
@patch("analysis.pull.GoogleAdsClient")
def test_run_orchestrates_pull_and_returns_snapshot(
    mock_client_cls,
    mock_load_google_ads_config,
    mock_load_supabase_config,
    mock_get_connection,
    mock_resolve_clinic_id,
    mock_leads_in_period,
    mock_historical_cohort,
    mock_fetch_all_dimensions,
    mock_click_view_gclid_map,
    mock_write_snapshot,
):
    mock_load_google_ads_config.return_value = {"developer_token": "x"}
    mock_client_cls.load_from_dict.return_value = MagicMock()
    mock_resolve_clinic_id.return_value = "essencia-sp-abc123"
    mock_leads_in_period.return_value = []
    mock_historical_cohort.return_value = []
    mock_fetch_all_dimensions.return_value = {"campaigns": []}
    mock_click_view_gclid_map.return_value = {}

    snapshot = run(customer="4601912200", period="2026-07-01:2026-07-31", stage="dev", out=None)

    assert snapshot["meta"]["customer"] == "4601912200"
    assert snapshot["meta"]["clinic_id"] == "essencia-sp-abc123"
    mock_write_snapshot.assert_called_once()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest analysis/tests/test_pull.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'analysis.pull'`

- [ ] **Step 3: Implement `analysis/pull.py`**

```python
"""CLI: python -m analysis.pull --customer 4601912200 --period 30d --stage dev --out snapshot.json"""
import argparse
import re
from datetime import date, timedelta

from google.ads.googleads.client import GoogleAdsClient

from analysis.config import load_google_ads_config, load_supabase_config
from analysis.data.conversions import (
    get_connection,
    historical_cohort,
    leads_in_period,
    resolve_clinic_id,
)
from analysis.data.google_ads import click_view_gclid_map, fetch_all_dimensions
from analysis.snapshot import build_snapshot, write_snapshot

_RELATIVE_PERIOD = re.compile(r"^(\d+)d$")
_EXPLICIT_PERIOD = re.compile(r"^(\d{4}-\d{2}-\d{2}):(\d{4}-\d{2}-\d{2})$")


def parse_period(period: str) -> tuple[str, str]:
    relative_match = _RELATIVE_PERIOD.match(period)
    if relative_match:
        days = int(relative_match.group(1))
        end = date.today()
        start = end - timedelta(days=days)
        return start.isoformat(), end.isoformat()

    explicit_match = _EXPLICIT_PERIOD.match(period)
    if explicit_match:
        return explicit_match.group(1), explicit_match.group(2)

    raise ValueError(f"Período inválido: {period!r}. Use 'Nd' ou 'YYYY-MM-DD:YYYY-MM-DD'.")


def run(*, customer: str, period: str, stage: str, out: str | None) -> dict:
    start, end = parse_period(period)

    google_ads_config = load_google_ads_config(stage)
    supabase_config = load_supabase_config(stage)

    client = GoogleAdsClient.load_from_dict(google_ads_config)
    conn = get_connection(supabase_config)
    try:
        clinic_id = resolve_clinic_id(conn, customer)
        leads = leads_in_period(conn, clinic_id, date.fromisoformat(start), date.fromisoformat(end))
        cohort = historical_cohort(conn, clinic_id)
    finally:
        conn.close()

    google_ads_data = fetch_all_dimensions(client, customer, start, end)
    # click_view: janela de até 90 dias, ancorada no fim do período pedido.
    click_view_start = (date.fromisoformat(end) - timedelta(days=90)).isoformat()
    gclid_map = click_view_gclid_map(client, customer, click_view_start, end)

    snapshot = build_snapshot(
        customer=customer,
        clinic_id=clinic_id,
        period_start=start,
        period_end=end,
        google_ads_data=google_ads_data,
        gclid_map=gclid_map,
        leads=leads,
        historical_cohort=cohort,
    )

    write_snapshot(snapshot, out)
    return snapshot


def main() -> None:
    parser = argparse.ArgumentParser(description="Pull determinístico de dados para o snapshot de análise.")
    parser.add_argument("--customer", required=True, help="Customer ID do Google Ads (ex: 4601912200)")
    parser.add_argument("--period", required=True, help="'Nd' (ex: 30d) ou 'YYYY-MM-DD:YYYY-MM-DD'")
    parser.add_argument("--stage", default="dev")
    parser.add_argument("--out", default=None, help="Caminho do arquivo de saída (default: stdout)")
    args = parser.parse_args()

    run(customer=args.customer, period=args.period, stage=args.stage, out=args.out)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest analysis/tests/test_pull.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Run the full `analysis/` test suite**

Run: `python -m pytest analysis/ -v`
Expected: PASS (all tests from Tasks 1-6)

- [ ] **Step 6: Commit**

```bash
git add analysis/pull.py analysis/tests/test_pull.py
git commit -m "feat(analysis): add pull.py CLI orchestrating the full snapshot pull"
```

---

### Task 7: `business-context` skill

**Files:**
- Create: `.claude/skills/business-context/SKILL.md`

**Interfaces:**
- Consumes: baseline ROAS/CPA/CTR values produced by a real run of `analysis.pull` against Essência (Step 2 below) — these seed the "alvos" section.
- Produces: none consumed by later tasks in this slice (input for the next slice's analyzer subagents).

- [ ] **Step 1: Confirm the SSM parameters exist for stage `dev`**

Run (requires AWS profile `dev-andre` configured locally):
```bash
aws ssm get-parameter --name /dev/MCC_ACCOUNT_ID --profile dev-andre
```
Expected: returns a value. If `ParameterNotFound`, stop and ask the user where the MCC credentials actually live before continuing — Task 6's `run()` cannot succeed without them.

- [ ] **Step 2: Run a real pull against Essência to seed the baseline**

Run:
```bash
python -m analysis.pull --customer 4601912200 --period 90d --stage dev --out /tmp/essencia-snapshot.json
```
Expected: writes a snapshot; note the `baseline.roas`, `baseline.cpa`, `baseline.ctr` values printed/inspected via `python -c "import json; print(json.load(open('/tmp/essencia-snapshot.json'))['baseline'])"`.

- [ ] **Step 3: Write `.claude/skills/business-context/SKILL.md`**

```markdown
---
name: business-context
description: Contexto de negócio da Essência (depilação a laser) para análise e otimização de campanhas Google Ads — orçamento, público-alvo, diferenciais e alvos de ROAS/CPA/CTR. Use ao analisar ou recomendar mudanças em campanhas da Essência.
---

# Contexto de Negócio — Essência

## Negócio
Clínica de depilação a laser (Soprano Ice Platinum), sessão avulsa, ticket médio informado pelo dono do negócio. Intervalo médio de 30 dias entre sessões por área.

## Orçamento
Orçamento mensal de mídia: [preencher com valor informado pelo dono].

## Público que converte (visão do dono)
[preencher com a descrição do dono: faixa etária, região, gênero predominante, canais que mais convertem]

## Diferenciais
[preencher com os diferenciais que o dono destaca frente à concorrência]

## Alvos (seedados pelo baseline calculado em `analysis/`)
- ROAS alvo: [valor de `baseline.roas` da última pull, ajustado com o dono]
- CPA alvo (centavos): [valor de `baseline.cpa`]
- CTR alvo: [valor de `baseline.ctr`]

> Estes alvos vêm do `baseline` do `snapshot.json` (coorte histórica all-time ÷
> custo total do período) e devem ser revisados com o dono do negócio antes de
> virarem meta operacional — o baseline é um piso estatístico, não uma meta.
```

> Nota: os campos entre colchetes exigem input direto do dono do negócio (orçamento, público, diferenciais) — não são deriváveis do código nem do banco. Preencher em conversa com o usuário antes de considerar esta fatia "pronta pra prod".

- [ ] **Step 4: Commit**

```bash
git add .claude/skills/business-context/SKILL.md
git commit -m "docs: add business-context skill scaffolded from Essência baseline"
```

---

### Task 8: `analysis/README.md`

**Files:**
- Create: `analysis/README.md`

**Interfaces:**
- Consumes: nothing.
- Produces: nothing (documentation only).

- [ ] **Step 1: Write `analysis/README.md`**

```markdown
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
python -m analysis.pull --customer 4601912200 --period 30d --stage dev --out snapshot.json
python -m analysis.pull --customer 4601912200 --period 2026-06-01:2026-06-30 --stage dev
```

- `--period`: `Nd` (últimos N dias) ou `YYYY-MM-DD:YYYY-MM-DD`.
- `--out`: caminho do arquivo de saída; omitir imprime no stdout.

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
`google_ads_customer_id` preenchido em `scheduler.clinics`.
```

- [ ] **Step 2: Commit**

```bash
git add analysis/README.md
git commit -m "docs: add analysis/ README with usage and snapshot contract"
```

---

## Self-Review Notes

- **Spec coverage:** every file listed in spec §2 has a task (`config.py`→Task1, `pull.py`→Task6, `data/google_ads.py`→Task4, `data/conversions.py`→Task2, `metrics.py`→Task3, `snapshot.py`→Task5, `tests/*`→embedded per task, `README.md`→Task8, `requirements-analysis.txt`→Task1, `business-context/SKILL.md`→Task7). Spec §6 open question (refresh_token origin) resolved above before Task 1. Conversion definition (spec §6 conversions.py bullet) matches `LeadService.get_pending_conversions`.
- **Open item carried forward, not hidden:** `business-context/SKILL.md`'s orçamento/público/diferenciais fields require the business owner's input — Task 7 Step 3 flags this explicitly rather than inventing numbers.
- **Type consistency checked:** `historical_cohort` row shape (`gclid, ltv_cents, latencia_dias, recompras` + raw `click_date`/`first_conversion_date`/`total_conversions`) is produced identically in Task 2 and consumed identically in Tasks 3, 5, 6 tests. `aggregate_dimension`'s `gclid_by_dimension_id=None` convention (Task 3) is used the same way in `snapshot.py` (Task 5) for uncovered dimensions.
