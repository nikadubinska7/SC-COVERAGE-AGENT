from __future__ import annotations

from typing import Any

import pandas as pd

from src.agent import run_react_analysis
from src.services.transformations import build_coverage_report, prepare_coverage_dataframe
from src.tools.pinecone_tool import retrieve_reporting_rules
from src.tools.supabase_tool import query_orderbook


DEFAULT_BANNER = "Snipes"
DEFAULT_SEASONS = ["HO2026", "SP2027"]
DEFAULT_ORDER_TYPE = "Standard Order - Futures"

FILTER_COLUMNS = [
    "banner",
    "season",
    "requested_month",
    "status",
    "timing_bucket",
    "brand",
    "age_division",
    "order_type",
    "category",
    "sub_category",
    "gender",
    "campaign",
    "ship_to_name",
    "sold_to_name",
]

RULES_QUERY = (
    "How is SC coverage calculated, which statuses are included, "
    "how are value and volume reported, and how is validation performed?"
)


def load_orderbook_records(
    banner: str = DEFAULT_BANNER,
    seasons: list[str] | None = None,
    order_type: str = DEFAULT_ORDER_TYPE,
) -> list[dict[str, Any]]:
    return query_orderbook(
        banner=banner,
        seasons=seasons or DEFAULT_SEASONS,
        order_type=order_type,
    )


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    return pd.DataFrame(records)


def records_to_filter_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        return pd.DataFrame()

    try:
        return prepare_coverage_dataframe(records)
    except Exception:
        return records_to_dataframe(records)


def normalize_filter_value(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_filter_options(df: pd.DataFrame) -> dict[str, list[str]]:
    options: dict[str, list[str]] = {}

    if df.empty:
        return {column: [] for column in FILTER_COLUMNS}

    for column in FILTER_COLUMNS:
        if column not in df.columns:
            options[column] = []
            continue

        values = [
            normalize_filter_value(value)
            for value in df[column].dropna().unique().tolist()
        ]
        options[column] = sorted(value for value in values if value)

    return options


def apply_dashboard_filters(
    df: pd.DataFrame,
    selected_filters: dict[str, list[str]],
) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    filtered = df.copy()

    for column, selected_values in selected_filters.items():
        if not selected_values or column not in filtered.columns:
            continue

        allowed = {normalize_filter_value(value) for value in selected_values}
        filtered = filtered[
            filtered[column].map(normalize_filter_value).isin(allowed)
        ]

    return filtered.reset_index(drop=True)


def build_fallback_observations(report_data: dict[str, Any]) -> list[str]:
    summary = report_data.get("executive_summary", {})
    validation = report_data.get("validation", {})
    risk_level = summary.get("risk_level", "N/A")

    return [
        (
            f"Value coverage is {summary.get('value_coverage_percentage', 0):.1%} "
            f"and volume coverage is {summary.get('volume_coverage_percentage', 0):.1%}."
        ),
        (
            f"Open order exposure is {summary.get('open_order_value', 0):,.0f} in value "
            f"and {summary.get('open_order_volume', 0):,.0f} units."
        ),
        f"Current coverage risk level is {risk_level}.",
        (
            "Validation passed for value and volume reconciliation."
            if validation.get("passes_reconciliation")
            else "Validation did not pass; review reconciliation and unexpected statuses."
        ),
    ]


def safe_generate_observations(report_data: dict[str, Any]) -> tuple[list[str], str | None]:
    try:
        observations = run_react_analysis(report_data)
        if observations:
            return observations, None
        return build_fallback_observations(report_data), "Agent returned no observations."
    except Exception as exc:
        return build_fallback_observations(report_data), str(exc)


def safe_retrieve_reporting_rules() -> tuple[list[dict[str, Any]], str | None]:
    try:
        return retrieve_reporting_rules(query=RULES_QUERY, top_k=5), None
    except Exception as exc:
        return [], str(exc)


def build_dashboard_payload(
    records: list[dict[str, Any]],
    selected_filters: dict[str, list[str]] | None = None,
) -> dict[str, Any]:
    base_df = records_to_filter_dataframe(records)
    filter_options = build_filter_options(base_df)
    filtered_df = apply_dashboard_filters(base_df, selected_filters or {})

    if filtered_df.empty:
        return {
            "records": [],
            "dataframe": filtered_df,
            "filter_options": filter_options,
            "report_data": None,
            "observations": [],
            "observation_error": None,
            "reporting_rules": [],
            "rules_error": None,
        }

    filtered_records = filtered_df.to_dict(orient="records")
    report_data = build_coverage_report(filtered_records)
    observations, observation_error = safe_generate_observations(report_data)
    reporting_rules, rules_error = safe_retrieve_reporting_rules()

    return {
        "records": filtered_records,
        "dataframe": filtered_df,
        "filter_options": filter_options,
        "report_data": report_data,
        "observations": observations,
        "observation_error": observation_error,
        "reporting_rules": reporting_rules,
        "rules_error": rules_error,
    }
