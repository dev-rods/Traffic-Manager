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
