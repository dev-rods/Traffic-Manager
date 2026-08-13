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
