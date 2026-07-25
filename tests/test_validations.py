from src.services.transformations import (
    prepare_coverage_dataframe,
    build_coverage_by_season,
    build_validation_summary,
)


def test_cancelled_rows_excluded_from_report_total():
    records = [
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
        },
        {
            "source_row_number": 3,
            "banner": "Snipes",
            "season": "HO2026",
            "status": "Cancelled",
            "order_type": "Standard Order - Futures",
            "requested_month": "202610",
            "confirmed_wholesale": 9999,
            "available_wholesale": 0,
            "report_wholesale_value": 9999,
            "report_volume": 999,
        },
    ]

    df = prepare_coverage_dataframe(records)
    coverage_df = build_coverage_by_season(df)
    validation = build_validation_summary(df, coverage_df)

    assert validation["source_rows"] == 2
    assert validation["included_rows"] == 1
    assert validation["excluded_cancelled_rows"] == 1

    assert validation["source_total_value"] == 1000
    assert validation["report_total_value"] == 1000
    assert validation["value_difference"] == 0

    assert validation["source_total_volume"] == 100
    assert validation["report_total_volume"] == 100
    assert validation["volume_difference"] == 0

    assert validation["passes_reconciliation"] is True


def test_unexpected_status_is_flagged():
    records = [
        {
            "source_row_number": 2,
            "banner": "Snipes",
            "season": "HO2026",
            "status": "Blocked",
            "order_type": "Standard Order - Futures",
            "requested_month": "202610",
            "confirmed_wholesale": 1000,
            "available_wholesale": 0,
            "report_wholesale_value": 1000,
            "report_volume": 100,
        }
    ]

    df = prepare_coverage_dataframe(records)
    coverage_df = build_coverage_by_season(df)
    validation = build_validation_summary(df, coverage_df)

    assert "Blocked" in validation["unexpected_statuses"]
    assert validation["included_rows"] == 0
    assert validation["source_total_value"] == 0
    assert validation["source_total_volume"] == 0