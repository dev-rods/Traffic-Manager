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

    assert snapshot["baseline"] == {"roas": 2.0, "cpa": 10000.0, "ctr": 0.05}

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
