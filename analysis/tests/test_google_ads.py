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


def test_fetch_dimension_resolves_device_enum_name_not_raw_int():
    row = _make_row(
        **{
            "metrics.impressions": 100,
            "metrics.clicks": 5,
            "metrics.cost_micros": 10_000_000,
            "metrics.conversions": 1.0,
        }
    )
    row.segments.device.name = "MOBILE"
    client, _ = _client_with_rows([row])

    result = fetch_dimension(client, "4601912200", "devices", "2026-08-01", "2026-08-09")

    assert result[0]["id"] == "MOBILE"
    assert result[0]["name"] == "MOBILE"


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

    result = click_view_gclid_map(client, "4601912200", "2026-06-15", "2026-06-15")

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
    assert "segments.date = '2026-06-15'" in query


def test_click_view_gclid_map_issues_one_query_per_day():
    client, service = _client_with_rows([])

    click_view_gclid_map(client, "4601912200", "2026-06-01", "2026-06-03")

    assert service.search_stream.call_count == 3
    queried_days = [
        call.kwargs["query"] for call in service.search_stream.call_args_list
    ]
    assert any("2026-06-01" in q for q in queried_days)
    assert any("2026-06-02" in q for q in queried_days)
    assert any("2026-06-03" in q for q in queried_days)
