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
