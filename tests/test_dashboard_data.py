from src.services.dashboard_data import (
    build_dashboard_payload,
    build_filter_options,
    records_to_filter_dataframe,
)


def sample_records():
    return [
        {
            "source_row_number": 2,
            "banner": "Snipes",
            "season": "HO2026",
            "status": "Booked/Shipped",
            "order_type": "Standard Order - Futures",
            "requested_month": "202610",
            "confirmed_wholesale": 1000,
            "available_wholesale": 0,
            "report_wholesale_value": 1000,
            "report_volume": 100,
            "coverage_performance": "",
            "eta_vs_crd": "",
            "brand": "Nike",
            "age_division": "Mens",
        },
        {
            "source_row_number": 3,
            "banner": "Snipes",
            "season": "SP2027",
            "status": "Open Order",
            "order_type": "Standard Order - Futures",
            "requested_month": "202701",
            "confirmed_wholesale": 1500,
            "available_wholesale": 0,
            "report_wholesale_value": 1500,
            "report_volume": 150,
            "coverage_performance": "",
            "eta_vs_crd": "10",
            "brand": "Jordan",
            "age_division": "Kids",
        },
    ]


def test_filter_options_include_derived_timing_bucket():
    df = records_to_filter_dataframe(sample_records())
    options = build_filter_options(df)

    assert "+2 weeks" in options["timing_bucket"]
    assert "Booked/Shipped" in options["timing_bucket"]
    assert "HO2026" in options["season"]
    assert "SP2027" in options["season"]


def test_dashboard_payload_filters_records_without_network(monkeypatch):
    monkeypatch.setattr(
        "src.services.dashboard_data.safe_generate_observations",
        lambda report_data: (["Fallback observation"], None),
    )
    monkeypatch.setattr(
        "src.services.dashboard_data.safe_retrieve_reporting_rules",
        lambda: ([], "offline"),
    )

    payload = build_dashboard_payload(
        sample_records(),
        selected_filters={"season": ["SP2027"], "timing_bucket": ["+2 weeks"]},
    )

    assert len(payload["records"]) == 1
    assert payload["report_data"]["executive_summary"]["seasons"] == ["SP2027"]
    assert payload["observations"] == ["Fallback observation"]


def test_dashboard_payload_handles_empty_filter_result(monkeypatch):
    monkeypatch.setattr(
        "src.services.dashboard_data.safe_generate_observations",
        lambda report_data: (["Fallback observation"], None),
    )
    monkeypatch.setattr(
        "src.services.dashboard_data.safe_retrieve_reporting_rules",
        lambda: ([], "offline"),
    )

    payload = build_dashboard_payload(
        sample_records(),
        selected_filters={"season": ["UNKNOWN"]},
    )

    assert payload["records"] == []
    assert payload["report_data"] is None
    assert payload["dataframe"].empty


def test_export_orderbook_endpoint_returns_sheet_payload(monkeypatch):
    import dash_app

    monkeypatch.setattr(dash_app, "load_orderbook_records", lambda **kwargs: sample_records())
    monkeypatch.setattr(
        dash_app,
        "safe_generate_observations",
        lambda report_data: (["Agent observation"], None),
    )

    client = dash_app.server.test_client()
    response = client.post(
        "/export-orderbook",
        json={
            "banner": "Snipes",
            "seasons": ["HO2026", "SP2027"],
            "order_type": "Standard Order - Futures",
            "dashboard_url": "https://example.com",
            "google_sheet_url": "https://docs.google.com/spreadsheets/d/test",
        },
    )

    assert response.status_code == 200

    payload = response.get_json()

    assert payload["status"] == "success"
    assert payload["mode"] == "google_sheets_export"
    assert payload["rows_count"] == 2
    assert payload["columns_count"] == len(payload["columns"])
    assert payload["header_row"] == payload["columns"]
    assert payload["rows"][0]["source_row_number"] == 2
    assert payload["values"][0][0] == 2
    assert payload["agent_observations"] == ["Agent observation"]
    assert payload["agent_observation_error"] is None
    assert payload["summary"]["included_rows"] == 2
