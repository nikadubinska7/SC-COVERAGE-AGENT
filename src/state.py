from typing import Any, TypedDict


class CoverageState(TypedDict, total=False):
    banner: str
    seasons: list[str]
    order_type: str
    reporting_date: str
    recipient_email: str

    rules_query: str
    reporting_rules: list[dict[str, Any]]

    raw_records: list[dict[str, Any]]
    report_data: dict[str, Any]

    validation_results: dict[str, Any]
    observations: list[str]

    report_url: str | None
    errors: list[str]
    status: str