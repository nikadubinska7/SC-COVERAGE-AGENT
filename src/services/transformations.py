from __future__ import annotations

from typing import Any

import pandas as pd


INCLUDED_STATUSES = ["Booked/Shipped", "Available", "Open Order"]
EXCLUDED_STATUSES = ["Cancelled"]


def records_to_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    if not records:
        raise ValueError("No records provided for transformation.")

    df = pd.DataFrame(records)

    required_columns = [
        "banner",
        "season",
        "status",
        "order_type",
        "requested_month",
        "confirmed_wholesale",
        "available_wholesale",
        "report_wholesale_value",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    return df


def normalize_orderbook(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()

    text_columns = [
        "banner",
        "season",
        "status",
        "order_type",
        "requested_month",
        "coverage_performance",
        "eta_vs_crd",
        "brand",
        "age_division",
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    numeric_columns = [
        "confirmed_wholesale",
        "available_wholesale",
        "report_wholesale_value",
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df


def assign_timing_bucket(row: pd.Series) -> str:
    status = str(row.get("status", "")).strip()

    if status != "Open Order":
        return status

    coverage_performance = str(row.get("coverage_performance", "")).strip()
    eta_vs_crd = str(row.get("eta_vs_crd", "")).strip()

    combined = f"{coverage_performance} {eta_vs_crd}".lower()

    if "early" in combined or "on time" in combined or "ontime" in combined:
        return "Early/On Time"

    numeric_delay = pd.to_numeric(row.get("eta_vs_crd"), errors="coerce")

    if pd.notna(numeric_delay):
        if numeric_delay <= 0:
            return "Early/On Time"
        if numeric_delay <= 7:
            return "+1 week"
        if numeric_delay <= 14:
            return "+2 weeks"
        if numeric_delay <= 21:
            return "+3 weeks"
        return "+4 weeks or later"

    if "+1" in combined or "1 week" in combined:
        return "+1 week"
    if "+2" in combined or "2 week" in combined:
        return "+2 weeks"
    if "+3" in combined or "3 week" in combined:
        return "+3 weeks"
    if "+4" in combined or "4 week" in combined or "later" in combined:
        return "+4 weeks or later"

    return "Unclassified Open Order"


def prepare_coverage_dataframe(records: list[dict[str, Any]]) -> pd.DataFrame:
    df = records_to_dataframe(records)
    df = normalize_orderbook(df)

    df["is_cancelled"] = df["status"].isin(EXCLUDED_STATUSES)
    df["is_included"] = df["status"].isin(INCLUDED_STATUSES)
    df["timing_bucket"] = df.apply(assign_timing_bucket, axis=1)

    return df


def build_coverage_by_season(df: pd.DataFrame) -> pd.DataFrame:
    included = df[df["is_included"]].copy()

    grouped = (
        included.groupby(
            ["season", "requested_month", "status", "timing_bucket"],
            dropna=False,
            as_index=False,
        )
        .agg(
            rows=("source_row_number", "count"),
            report_wholesale_value=("report_wholesale_value", "sum"),
            confirmed_wholesale=("confirmed_wholesale", "sum"),
            available_wholesale=("available_wholesale", "sum"),
        )
    )

    total_by_period = (
        grouped.groupby(["season", "requested_month"], as_index=False)
        ["report_wholesale_value"]
        .sum()
        .rename(columns={"report_wholesale_value": "period_total_value"})
    )

    grouped = grouped.merge(total_by_period, on=["season", "requested_month"], how="left")

    grouped["share_of_period"] = grouped.apply(
        lambda row: row["report_wholesale_value"] / row["period_total_value"]
        if row["period_total_value"] else 0,
        axis=1,
    )

    return grouped.sort_values(
        ["season", "requested_month", "status", "timing_bucket"]
    ).reset_index(drop=True)


def build_executive_summary(df: pd.DataFrame) -> dict[str, Any]:
    included = df[df["is_included"]].copy()
    cancelled = df[df["is_cancelled"]].copy()

    total_value = float(included["report_wholesale_value"].sum())

    value_by_status = (
        included.groupby("status")["report_wholesale_value"]
        .sum()
        .to_dict()
    )

    booked_value = float(value_by_status.get("Booked/Shipped", 0))
    available_value = float(value_by_status.get("Available", 0))
    open_order_value = float(value_by_status.get("Open Order", 0))

    covered_value = booked_value + available_value
    coverage_percentage = covered_value / total_value if total_value else 0

    return {
        "source_rows": int(len(df)),
        "included_rows": int(len(included)),
        "cancelled_rows": int(len(cancelled)),
        "total_value": round(total_value, 2),
        "booked_shipped_value": round(booked_value, 2),
        "available_value": round(available_value, 2),
        "open_order_value": round(open_order_value, 2),
        "covered_value": round(covered_value, 2),
        "coverage_percentage": round(coverage_percentage, 4),
        "seasons": sorted(included["season"].dropna().unique().tolist()),
        "requested_months": sorted(included["requested_month"].dropna().unique().tolist()),
    }


def build_validation_summary(df: pd.DataFrame, coverage_df: pd.DataFrame) -> dict[str, Any]:
    included = df[df["is_included"]].copy()

    source_total = float(included["report_wholesale_value"].sum())
    report_total = float(coverage_df["report_wholesale_value"].sum())
    difference = round(source_total - report_total, 2)

    unexpected_statuses = sorted(
        set(df["status"].dropna().unique().tolist())
        - set(INCLUDED_STATUSES)
        - set(EXCLUDED_STATUSES)
    )

    return {
        "source_rows": int(len(df)),
        "included_rows": int(len(included)),
        "excluded_cancelled_rows": int(df["is_cancelled"].sum()),
        "source_total": round(source_total, 2),
        "report_total": round(report_total, 2),
        "difference": difference,
        "passes_reconciliation": abs(difference) <= 0.01,
        "unexpected_statuses": unexpected_statuses,
        "missing_required_values": {
            "season": int(df["season"].isna().sum()),
            "status": int(df["status"].isna().sum()),
            "requested_month": int(df["requested_month"].isna().sum()),
            "report_wholesale_value": int(df["report_wholesale_value"].isna().sum()),
        },
    }


def build_coverage_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    df = prepare_coverage_dataframe(records)
    coverage_df = build_coverage_by_season(df)
    executive_summary = build_executive_summary(df)
    validation_summary = build_validation_summary(df, coverage_df)

    return {
        "executive_summary": executive_summary,
        "coverage_by_season": coverage_df.to_dict(orient="records"),
        "validation": validation_summary,
    }