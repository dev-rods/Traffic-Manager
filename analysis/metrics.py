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
