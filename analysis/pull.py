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
