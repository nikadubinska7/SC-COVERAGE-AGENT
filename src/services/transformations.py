from __future__ import annotations

from typing import Any

import pandas as pd


INCLUDED_STATUSES = ["Booked/Shipped", "Available", "Open Order"]
EXCLUDED_STATUSES = ["Cancelled"]

# Small tolerance to avoid false failures from floating-point cent-level differences.
VALUE_RECONCILIATION_TOLERANCE = 0.05
VOLUME_RECONCILIATION_TOLERANCE = 0


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
        "report_volume",
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
        "category",
        "sub_category",
        "gender",
        "campaign",
        "ship_to_name",
        "sold_to_name",
    ]

    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype("string").str.strip()

    numeric_columns = [
        "confirmed_wholesale",
        "available_wholesale",
        "report_wholesale_value",
        "report_volume",
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


def risk_level(coverage_percentage: float) -> str:
    if coverage_percentage >= 0.75:
        return "Low"
    if coverage_percentage >= 0.5:
        return "Medium"
    return "High"


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
            report_value=("report_wholesale_value", "sum"),
            report_volume=("report_volume", "sum"),
            confirmed_wholesale=("confirmed_wholesale", "sum"),
            available_wholesale=("available_wholesale", "sum"),
        )
    )

    total_by_period = (
        grouped.groupby(["season", "requested_month"], as_index=False)
        .agg(
            period_total_value=("report_value", "sum"),
            period_total_volume=("report_volume", "sum"),
        )
    )

    grouped = grouped.merge(total_by_period, on=["season", "requested_month"], how="left")

    grouped["share_of_period_value"] = grouped.apply(
        lambda row: row["report_value"] / row["period_total_value"]
        if row["period_total_value"]
        else 0,
        axis=1,
    )

    grouped["share_of_period_volume"] = grouped.apply(
        lambda row: row["report_volume"] / row["period_total_volume"]
        if row["period_total_volume"]
        else 0,
        axis=1,
    )

    return grouped.sort_values(
        ["season", "requested_month", "status", "timing_bucket"]
    ).reset_index(drop=True)


def build_coverage_summary(df: pd.DataFrame) -> pd.DataFrame:
    included = df[df["is_included"]].copy()

    grouped = (
        included.groupby(["season", "requested_month", "status"], as_index=False)
        .agg(
            report_value=("report_wholesale_value", "sum"),
            report_volume=("report_volume", "sum"),
        )
    )

    value_pivot = grouped.pivot_table(
        index=["season", "requested_month"],
        columns="status",
        values="report_value",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    volume_pivot = grouped.pivot_table(
        index=["season", "requested_month"],
        columns="status",
        values="report_volume",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    value_pivot = value_pivot.rename(
        columns={
            "Booked/Shipped": "booked_shipped_value",
            "Available": "available_value",
            "Open Order": "open_order_value",
        }
    )

    volume_pivot = volume_pivot.rename(
        columns={
            "Booked/Shipped": "booked_shipped_volume",
            "Available": "available_volume",
            "Open Order": "open_order_volume",
        }
    )

    summary = value_pivot.merge(
        volume_pivot,
        on=["season", "requested_month"],
        how="outer",
    ).fillna(0)

    required_columns = [
        "booked_shipped_value",
        "available_value",
        "open_order_value",
        "booked_shipped_volume",
        "available_volume",
        "open_order_volume",
    ]

    for col in required_columns:
        if col not in summary.columns:
            summary[col] = 0

    summary["total_value"] = (
        summary["booked_shipped_value"]
        + summary["available_value"]
        + summary["open_order_value"]
    )
    summary["covered_value"] = (
        summary["booked_shipped_value"] + summary["available_value"]
    )
    summary["value_coverage_percentage"] = summary.apply(
        lambda row: row["covered_value"] / row["total_value"]
        if row["total_value"]
        else 0,
        axis=1,
    )
    summary["open_order_value_percentage"] = summary.apply(
        lambda row: row["open_order_value"] / row["total_value"]
        if row["total_value"]
        else 0,
        axis=1,
    )

    summary["total_volume"] = (
        summary["booked_shipped_volume"]
        + summary["available_volume"]
        + summary["open_order_volume"]
    )
    summary["covered_volume"] = (
        summary["booked_shipped_volume"] + summary["available_volume"]
    )
    summary["volume_coverage_percentage"] = summary.apply(
        lambda row: row["covered_volume"] / row["total_volume"]
        if row["total_volume"]
        else 0,
        axis=1,
    )
    summary["open_order_volume_percentage"] = summary.apply(
        lambda row: row["open_order_volume"] / row["total_volume"]
        if row["total_volume"]
        else 0,
        axis=1,
    )

    summary["risk_level"] = summary["value_coverage_percentage"].apply(risk_level)

    value_cols = [
        "total_value",
        "booked_shipped_value",
        "available_value",
        "open_order_value",
        "covered_value",
    ]

    volume_cols = [
        "total_volume",
        "booked_shipped_volume",
        "available_volume",
        "open_order_volume",
        "covered_volume",
    ]

    for col in value_cols:
        summary[col] = summary[col].round(2)

    for col in volume_cols:
        summary[col] = summary[col].round(0)

    return summary.sort_values(["season", "requested_month"]).reset_index(drop=True)


def build_timing_risk_summary(df: pd.DataFrame) -> pd.DataFrame:
    open_orders = df[
        (df["is_included"]) & (df["status"] == "Open Order")
    ].copy()

    output_cols = [
        "season",
        "requested_month",
        "early_on_time_value",
        "plus_1_week_value",
        "plus_2_weeks_value",
        "plus_3_weeks_value",
        "plus_4_weeks_or_later_value",
        "total_open_order_value",
        "late_open_order_value",
        "late_open_order_value_percentage",
        "early_on_time_volume",
        "plus_1_week_volume",
        "plus_2_weeks_volume",
        "plus_3_weeks_volume",
        "plus_4_weeks_or_later_volume",
        "total_open_order_volume",
        "late_open_order_volume",
        "late_open_order_volume_percentage",
    ]

    if open_orders.empty:
        return pd.DataFrame(columns=output_cols)

    grouped = (
        open_orders.groupby(
            ["season", "requested_month", "timing_bucket"],
            as_index=False,
        )
        .agg(
            report_value=("report_wholesale_value", "sum"),
            report_volume=("report_volume", "sum"),
        )
    )

    value_pivot = grouped.pivot_table(
        index=["season", "requested_month"],
        columns="timing_bucket",
        values="report_value",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    volume_pivot = grouped.pivot_table(
        index=["season", "requested_month"],
        columns="timing_bucket",
        values="report_volume",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()

    bucket_name_map_value = {
        "Early/On Time": "early_on_time_value",
        "+1 week": "plus_1_week_value",
        "+2 weeks": "plus_2_weeks_value",
        "+3 weeks": "plus_3_weeks_value",
        "+4 weeks or later": "plus_4_weeks_or_later_value",
        "Unclassified Open Order": "unclassified_open_order_value",
    }

    bucket_name_map_volume = {
        "Early/On Time": "early_on_time_volume",
        "+1 week": "plus_1_week_volume",
        "+2 weeks": "plus_2_weeks_volume",
        "+3 weeks": "plus_3_weeks_volume",
        "+4 weeks or later": "plus_4_weeks_or_later_volume",
        "Unclassified Open Order": "unclassified_open_order_volume",
    }

    value_pivot = value_pivot.rename(columns=bucket_name_map_value)
    volume_pivot = volume_pivot.rename(columns=bucket_name_map_volume)

    timing = value_pivot.merge(
        volume_pivot,
        on=["season", "requested_month"],
        how="outer",
    ).fillna(0)

    value_bucket_cols = [
        "early_on_time_value",
        "plus_1_week_value",
        "plus_2_weeks_value",
        "plus_3_weeks_value",
        "plus_4_weeks_or_later_value",
    ]

    volume_bucket_cols = [
        "early_on_time_volume",
        "plus_1_week_volume",
        "plus_2_weeks_volume",
        "plus_3_weeks_volume",
        "plus_4_weeks_or_later_volume",
    ]

    for col in value_bucket_cols + volume_bucket_cols:
        if col not in timing.columns:
            timing[col] = 0

    timing["total_open_order_value"] = timing[value_bucket_cols].sum(axis=1)
    timing["late_open_order_value"] = (
        timing["plus_1_week_value"]
        + timing["plus_2_weeks_value"]
        + timing["plus_3_weeks_value"]
        + timing["plus_4_weeks_or_later_value"]
    )
    timing["late_open_order_value_percentage"] = timing.apply(
        lambda row: row["late_open_order_value"] / row["total_open_order_value"]
        if row["total_open_order_value"]
        else 0,
        axis=1,
    )

    timing["total_open_order_volume"] = timing[volume_bucket_cols].sum(axis=1)
    timing["late_open_order_volume"] = (
        timing["plus_1_week_volume"]
        + timing["plus_2_weeks_volume"]
        + timing["plus_3_weeks_volume"]
        + timing["plus_4_weeks_or_later_volume"]
    )
    timing["late_open_order_volume_percentage"] = timing.apply(
        lambda row: row["late_open_order_volume"] / row["total_open_order_volume"]
        if row["total_open_order_volume"]
        else 0,
        axis=1,
    )

    for col in value_bucket_cols + [
        "total_open_order_value",
        "late_open_order_value",
    ]:
        timing[col] = timing[col].round(2)

    for col in volume_bucket_cols + [
        "total_open_order_volume",
        "late_open_order_volume",
    ]:
        timing[col] = timing[col].round(0)

    return timing[output_cols].sort_values(["season", "requested_month"]).reset_index(drop=True)


def build_filter_options(df: pd.DataFrame) -> dict[str, list[str]]:
    filter_columns = [
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

    options: dict[str, list[str]] = {}

    for col in filter_columns:
        if col in df.columns:
            values = (
                df[col]
                .dropna()
                .astype(str)
                .str.strip()
                .replace("", pd.NA)
                .dropna()
                .unique()
                .tolist()
            )
            options[col] = sorted(values)

    return options


def build_executive_summary(df: pd.DataFrame) -> dict[str, Any]:
    included = df[df["is_included"]].copy()
    cancelled = df[df["is_cancelled"]].copy()

    total_value = float(included["report_wholesale_value"].sum())
    total_volume = float(included["report_volume"].sum())

    value_by_status = (
        included.groupby("status")["report_wholesale_value"]
        .sum()
        .to_dict()
    )

    volume_by_status = (
        included.groupby("status")["report_volume"]
        .sum()
        .to_dict()
    )

    booked_value = float(value_by_status.get("Booked/Shipped", 0))
    available_value = float(value_by_status.get("Available", 0))
    open_order_value = float(value_by_status.get("Open Order", 0))

    booked_volume = float(volume_by_status.get("Booked/Shipped", 0))
    available_volume = float(volume_by_status.get("Available", 0))
    open_order_volume = float(volume_by_status.get("Open Order", 0))

    covered_value = booked_value + available_value
    covered_volume = booked_volume + available_volume

    value_coverage_percentage = covered_value / total_value if total_value else 0
    volume_coverage_percentage = covered_volume / total_volume if total_volume else 0

    return {
        "source_rows": int(len(df)),
        "included_rows": int(len(included)),
        "cancelled_rows": int(len(cancelled)),

        "total_value": round(total_value, 2),
        "booked_shipped_value": round(booked_value, 2),
        "available_value": round(available_value, 2),
        "open_order_value": round(open_order_value, 2),
        "covered_value": round(covered_value, 2),
        "value_coverage_percentage": round(value_coverage_percentage, 4),

        "total_volume": round(total_volume, 0),
        "booked_shipped_volume": round(booked_volume, 0),
        "available_volume": round(available_volume, 0),
        "open_order_volume": round(open_order_volume, 0),
        "covered_volume": round(covered_volume, 0),
        "volume_coverage_percentage": round(volume_coverage_percentage, 4),

        "risk_level": risk_level(value_coverage_percentage),

        "seasons": sorted(included["season"].dropna().unique().tolist()),
        "requested_months": sorted(included["requested_month"].dropna().unique().tolist()),
    }


def build_validation_summary(df: pd.DataFrame, coverage_df: pd.DataFrame) -> dict[str, Any]:
    included = df[df["is_included"]].copy()

    source_total_value = float(included["report_wholesale_value"].sum())
    report_total_value = float(coverage_df["report_value"].sum())
    value_difference = round(source_total_value - report_total_value, 2)

    source_total_volume = float(included["report_volume"].sum())
    report_total_volume = float(coverage_df["report_volume"].sum())
    volume_difference = round(source_total_volume - report_total_volume, 0)

    unexpected_statuses = sorted(
        set(df["status"].dropna().unique().tolist())
        - set(INCLUDED_STATUSES)
        - set(EXCLUDED_STATUSES)
    )

    passes_reconciliation = (
        abs(value_difference) <= VALUE_RECONCILIATION_TOLERANCE
        and abs(volume_difference) <= VOLUME_RECONCILIATION_TOLERANCE
    )

    return {
        "source_rows": int(len(df)),
        "included_rows": int(len(included)),
        "excluded_cancelled_rows": int(df["is_cancelled"].sum()),

        "source_total_value": round(source_total_value, 2),
        "report_total_value": round(report_total_value, 2),
        "value_difference": value_difference,

        "source_total_volume": round(source_total_volume, 0),
        "report_total_volume": round(report_total_volume, 0),
        "volume_difference": volume_difference,

        "passes_reconciliation": passes_reconciliation,

        "unexpected_statuses": unexpected_statuses,
        "missing_required_values": {
            "season": int(df["season"].isna().sum()),
            "status": int(df["status"].isna().sum()),
            "requested_month": int(df["requested_month"].isna().sum()),
            "report_wholesale_value": int(df["report_wholesale_value"].isna().sum()),
            "report_volume": int(df["report_volume"].isna().sum()),
        },
    }


def build_coverage_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    df = prepare_coverage_dataframe(records)

    coverage_df = build_coverage_by_season(df)
    coverage_summary_df = build_coverage_summary(df)
    timing_risk_df = build_timing_risk_summary(df)

    executive_summary = build_executive_summary(df)
    validation_summary = build_validation_summary(df, coverage_df)
    filter_options = build_filter_options(df)

    return {
        "executive_summary": executive_summary,
        "coverage_summary": coverage_summary_df.to_dict(orient="records"),
        "timing_risk": timing_risk_df.to_dict(orient="records"),
        "coverage_by_season": coverage_df.to_dict(orient="records"),
        "filter_options": filter_options,
        "validation": validation_summary,
    }