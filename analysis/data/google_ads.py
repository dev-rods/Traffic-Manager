"""GAQL por dimensão + click_view (gclid -> dimensões finas), via GoogleAdsService."""
from datetime import date, timedelta
from typing import Dict, List

DIMENSIONS = [
    "campaigns", "ad_groups", "ads", "keywords",
    "search_terms", "geo", "devices", "audiences",
    "age_ranges", "genders",
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
    "age_ranges": (
        "SELECT ad_group_criterion.age_range.type, ad_group_criterion.age_range.type, {metrics} "
        "FROM age_range_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
    "genders": (
        "SELECT ad_group_criterion.gender.type, ad_group_criterion.gender.type, {metrics} "
        "FROM gender_view WHERE segments.date BETWEEN '{start}' AND '{end}'"
    ),
}

_ID_NAME_PATHS = {
    "campaigns": ("campaign.id", "campaign.name"),
    "ad_groups": ("ad_group.id", "ad_group.name"),
    "ads": ("ad_group_ad.ad.id", "ad_group_ad.ad.name"),
    "keywords": ("ad_group_criterion.criterion_id", "ad_group_criterion.keyword.text"),
    "search_terms": ("search_term_view.search_term", "search_term_view.search_term"),
    "geo": ("geographic_view.country_criterion_id", "geographic_view.country_criterion_id"),
    "devices": ("segments.device.name", "segments.device.name"),
    "audiences": ("campaign_audience_view.resource_name", "campaign_audience_view.resource_name"),
    "age_ranges": ("ad_group_criterion.age_range.type.name", "ad_group_criterion.age_range.type.name"),
    "genders": ("ad_group_criterion.gender.type.name", "ad_group_criterion.gender.type.name"),
}

_CLICK_VIEW_QUERY = (
    "SELECT click_view.gclid, campaign.id, ad_group.id, segments.device, segments.date "
    "FROM click_view WHERE segments.date = '{day}'"
)


def _date_range(start: str, end: str) -> List[str]:
    start_date = date.fromisoformat(start)
    end_date = date.fromisoformat(end)
    days = []
    current = start_date
    while current <= end_date:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


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


def fetch_all_dimensions(client, customer_id: str, start: str, end: str) -> Dict[str, List[Dict]]:
    return {
        dimension: fetch_dimension(client, customer_id, dimension, start, end)
        for dimension in DIMENSIONS
    }


def click_view_gclid_map(client, customer_id: str, start: str, end: str) -> Dict[str, Dict]:
    """Mapeia gclid -> {campaign_id, ad_group_id, device, date}, janela de até 90 dias.

    click_view exige segments.date filtrado a um único dia por query (limitação da
    API), então iteramos dia a dia dentro do intervalo pedido e agregamos.

    click_view não cobre keyword nem geo diretamente — dimensões finas sem
    cobertura ficam de fora deste mapa (o chamador trata como null).
    """
    ga_service = client.get_service("GoogleAdsService")
    gclid_map = {}

    for day in _date_range(start, end):
        query = _CLICK_VIEW_QUERY.format(day=day)
        stream = ga_service.search_stream(customer_id=customer_id, query=query)
        for batch in stream:
            for row in batch.results:
                gclid_map[row.click_view.gclid] = {
                    "campaign_id": str(row.campaign.id),
                    "ad_group_id": str(row.ad_group.id),
                    "device": row.segments.device.name,
                    "date": row.segments.date,
                }
    return gclid_map
