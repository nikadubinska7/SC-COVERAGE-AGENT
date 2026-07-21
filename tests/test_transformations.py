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
            "coverage_performance": "",
            "eta_vs_crd": "10",
            "brand": "Nike",
            "age_division": "Mens",
        },
    ]


def test_build_coverage_report_reconciles(sample_records):
    report = build_coverage_report(sample_records)

    assert report["validation"]["source_total"] == 3000
    assert report["validation"]["report_total"] == 3000
    assert report["validation"]["difference"] == 0
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
    assert summary["coverage_percentage"] == 0.5


def test_open_order_timing_bucket(sample_records):
    report = build_coverage_report(sample_records)

    open_order_rows = [
        row for row in report["coverage_by_season"]
        if row["status"] == "Open Order"
    ]

    assert len(open_order_rows) == 1
    assert open_order_rows[0]["timing_bucket"] == "+2 weeks"


def test_empty_records_fail():
    with pytest.raises(ValueError, match="No records provided"):
        build_coverage_report([])