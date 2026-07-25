import pytest

from src.services.transformations import build_coverage_report


@pytest.fixture
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
            "season": "HO2026",
            "status": "Available",
            "order_type": "Standard Order - Futures",
            "requested_month": "202610",
            "confirmed_wholesale": 0,
            "available_wholesale": 500,
            "report_wholesale_value": 500,
            "report_volume": 50,
            "coverage_performance": "",
            "eta_vs_crd": "",
            "brand": "Nike",
            "age_division": "Mens",
        },
        {
            "source_row_number": 4,
            "banner": "Snipes",
            "season": "HO2026",
            "status": "Open Order",
            "order_type": "Standard Order - Futures",
            "requested_month": "202610",
            "confirmed_wholesale": 1500,
            "available_wholesale": 0,
            "report_wholesale_value": 1500,
            "report_volume": 150,
            "coverage_performance": "",
            "eta_vs_crd": "10",
            "brand": "Nike",
            "age_division": "Mens",
        },
    ]


def test_build_coverage_report_reconciles(sample_records):
    report = build_coverage_report(sample_records)

    assert report["validation"]["source_total_value"] == 3000
    assert report["validation"]["report_total_value"] == 3000
    assert report["validation"]["value_difference"] == 0

    assert report["validation"]["source_total_volume"] == 300
    assert report["validation"]["report_total_volume"] == 300
    assert report["validation"]["volume_difference"] == 0

    assert report["validation"]["passes_reconciliation"] is True


def test_executive_summary_values(sample_records):
    report = build_coverage_report(sample_records)
    summary = report["executive_summary"]

    assert summary["source_rows"] == 3
    assert summary["included_rows"] == 3

    assert summary["booked_shipped_value"] == 1000
    assert summary["available_value"] == 500
    assert summary["open_order_value"] == 1500
    assert summary["covered_value"] == 1500
    assert summary["value_coverage_percentage"] == 0.5

    assert summary["booked_shipped_volume"] == 100
    assert summary["available_volume"] == 50
    assert summary["open_order_volume"] == 150
    assert summary["covered_volume"] == 150
    assert summary["volume_coverage_percentage"] == 0.5

    assert summary["risk_level"] == "Medium"


def test_open_order_timing_bucket(sample_records):
    report = build_coverage_report(sample_records)

    open_order_rows = [
        row for row in report["coverage_by_season"]
        if row["status"] == "Open Order"
    ]

    assert len(open_order_rows) == 1
    assert open_order_rows[0]["timing_bucket"] == "+2 weeks"


def test_coverage_summary_created(sample_records):
    report = build_coverage_report(sample_records)

    coverage_summary = report["coverage_summary"]

    assert len(coverage_summary) == 1

    row = coverage_summary[0]

    assert row["season"] == "HO2026"
    assert row["requested_month"] == "202610"

    assert row["total_value"] == 3000
    assert row["booked_shipped_value"] == 1000
    assert row["available_value"] == 500
    assert row["open_order_value"] == 1500
    assert row["covered_value"] == 1500
    assert row["value_coverage_percentage"] == 0.5

    assert row["total_volume"] == 300
    assert row["booked_shipped_volume"] == 100
    assert row["available_volume"] == 50
    assert row["open_order_volume"] == 150
    assert row["covered_volume"] == 150
    assert row["volume_coverage_percentage"] == 0.5


def test_timing_risk_summary_created(sample_records):
    report = build_coverage_report(sample_records)

    timing_risk = report["timing_risk"]

    assert len(timing_risk) == 1

    row = timing_risk[0]

    assert row["season"] == "HO2026"
    assert row["requested_month"] == "202610"

    assert row["plus_2_weeks_value"] == 1500
    assert row["total_open_order_value"] == 1500
    assert row["late_open_order_value"] == 1500
    assert row["late_open_order_value_percentage"] == 1

    assert row["plus_2_weeks_volume"] == 150
    assert row["total_open_order_volume"] == 150
    assert row["late_open_order_volume"] == 150
    assert row["late_open_order_volume_percentage"] == 1


def test_filter_options_created(sample_records):
    report = build_coverage_report(sample_records)

    filters = report["filter_options"]

    assert "season" in filters
    assert "status" in filters
    assert "HO2026" in filters["season"]
    assert "Booked/Shipped" in filters["status"]
    assert "Available" in filters["status"]
    assert "Open Order" in filters["status"]


def test_empty_records_fail():
    with pytest.raises(ValueError, match="No records provided"):
        build_coverage_report([])