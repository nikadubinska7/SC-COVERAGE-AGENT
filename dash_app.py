from __future__ import annotations

import os
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import pandas as pd
import plotly.graph_objects as go
from dash import Dash, Input, Output, State, dash_table, dcc, html
from dotenv import load_dotenv
from flask import jsonify, request
from langchain_openai import ChatOpenAI

from src.services.dashboard_data import (
    DEFAULT_BANNER,
    DEFAULT_ORDER_TYPE,
    DEFAULT_SEASONS,
    apply_dashboard_filters,
    build_filter_options,
    load_orderbook_records,
    records_to_filter_dataframe,
    safe_generate_observations,
)
from src.services.transformations import build_coverage_report
from src.tools.pinecone_tool import retrieve_reporting_rules


FILTER_CONFIG = [
    ("season", "Season"),
    ("requested_month", "Requested Month"),
    ("brand", "Brand"),
    ("category", "Category"),
    ("sub_category", "Sub Category"),
    ("gender", "Gender"),
    ("age_division", "Age Division"),
    ("timing_bucket", "Timing Bucket"),
    ("status", "Status"),
]

# Validated categorical palette, fixed order (dataviz skill palette.md).
CATEGORICAL_COLORS = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]

# Fixed status scale — reserved meaning, never reused for series identity.
STATUS_COLORS = {
    "good": "#0ca30c",
    "warning": "#fab219",
    "serious": "#ec835a",
    "critical": "#d03b3b",
    "muted": "#898781",
}

RISK_COLORS = {
    "Low": STATUS_COLORS["good"],
    "Medium": STATUS_COLORS["warning"],
    "High": STATUS_COLORS["critical"],
    "N/A": STATUS_COLORS["muted"],
}

# Coverage mix reflects state (secured -> exposed), so it borrows status semantics.
STATUS_MIX_COLORS = {
    "Booked/Shipped": STATUS_COLORS["good"],
    "Available": CATEGORICAL_COLORS[0],
    "Open Order": STATUS_COLORS["warning"],
}

# Timing buckets are ordinal (on-time -> increasingly late): one hue, light -> dark.
TIMING_RAMP = ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281"]

# Sequential ramp for the exposure heatmap (magnitude, light -> dark).
SEQUENTIAL_BLUE = [
    (0.0, "#f4f8fd"),
    (0.15, "#cde2fb"),
    (0.35, "#9ec5f4"),
    (0.55, "#5598e7"),
    (0.75, "#256abf"),
    (1.0, "#0d366b"),
]

# Chart chrome (light, executive theme).
INK_PRIMARY = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRIDLINE = "#e5e4dd"
AXIS_LINE = "#c3c2b7"
FONT_STACK = "'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif"


def metric_columns(metric_mode: str) -> dict[str, str]:
    prefix = "value" if metric_mode == "Value" else "volume"
    return {
        "prefix": prefix,
        "label": metric_mode,
        "total": f"total_{prefix}",
        "booked": f"booked_shipped_{prefix}",
        "available": f"available_{prefix}",
        "open": f"open_order_{prefix}",
        "covered": f"covered_{prefix}",
        "coverage_pct": f"{prefix}_coverage_percentage",
        "open_pct": f"open_order_{prefix}_percentage",
        "late_pct": f"late_open_order_{prefix}_percentage",
        "late_open": f"late_open_order_{prefix}",
    }


def format_number(value: Any, metric_mode: str | None = None) -> str:
    number = float(value or 0)

    if metric_mode == "Value":
        if abs(number) >= 1_000_000:
            return f"${number / 1_000_000:,.1f}M"
        if abs(number) >= 1_000:
            return f"${number / 1_000:,.1f}K"
        return f"${number:,.0f}"

    if abs(number) >= 1_000_000:
        return f"{number / 1_000_000:,.1f}M"
    if abs(number) >= 1_000:
        return f"{number / 1_000:,.1f}K"
    return f"{number:,.0f}"


def format_pct(value: Any) -> str:
    return f"{float(value or 0):.1%}"


def safe_ratio(numerator: Any, denominator: Any) -> float:
    denominator_value = float(denominator or 0)
    if denominator_value == 0:
        return 0.0
    return float(numerator or 0) / denominator_value


def filter_values_to_dict(**filters: list[str] | None) -> dict[str, list[str]]:
    return {key: value or [] for key, value in filters.items()}


@lru_cache(maxsize=2)
def load_base_dataframe(refresh_token: int = 0) -> pd.DataFrame:
    records = load_orderbook_records(
        banner=DEFAULT_BANNER,
        seasons=DEFAULT_SEASONS,
        order_type=DEFAULT_ORDER_TYPE,
    )
    return records_to_filter_dataframe(records)


def get_filter_options() -> dict[str, list[str]]:
    try:
        return build_filter_options(load_base_dataframe())
    except Exception:
        return {column: [] for column, _label in FILTER_CONFIG}


def make_options(values: list[str]) -> list[dict[str, str]]:
    return [{"label": value, "value": value} for value in values]


def normalize_payload_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return [item.strip() for item in str(value).split(",") if item.strip()]


def clean_json_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def clean_text_value(value: Any) -> str:
    cleaned = clean_json_value(value)
    if cleaned is None:
        return ""
    return str(cleaned).strip()


def clean_number_value(value: Any) -> float | int:
    cleaned = clean_json_value(value)
    if cleaned is None:
        return 0
    number = float(cleaned)
    if number.is_integer():
        return int(number)
    return round(number, 2)


def build_coverage_exceptions(
    df: pd.DataFrame,
    report_run_id: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    if df.empty or "status" not in df.columns:
        return []

    open_orders = df[df["status"].astype(str).str.strip() == "Open Order"].copy()
    if open_orders.empty:
        return []

    open_orders = open_orders.sort_values(
        ["report_wholesale_value", "report_volume"],
        ascending=[False, False],
    ).head(max(1, limit))

    exceptions: list[dict[str, Any]] = []

    for index, row in open_orders.reset_index(drop=True).iterrows():
        source_row = clean_json_value(row.get("source_row_number")) or index + 1
        category = clean_text_value(row.get("category"))
        sub_category = clean_text_value(row.get("sub_category"))
        season = clean_text_value(row.get("season"))
        requested_month = clean_text_value(row.get("requested_month"))
        timing_bucket = clean_text_value(row.get("timing_bucket"))
        value = clean_number_value(row.get("report_wholesale_value"))
        volume = clean_number_value(row.get("report_volume"))

        exceptions.append(
            {
                "exception_id": f"EXC-{source_row}",
                "report_run_id": report_run_id,
                "source_row_number": source_row,
                "division": clean_text_value(row.get("division")),
                "category": category,
                "sub_category": sub_category,
                "gender": clean_text_value(row.get("gender")),
                "age_division": clean_text_value(row.get("age_division")),
                "season": season,
                "requested_month": requested_month,
                "eta": clean_json_value(row.get("eta")),
                "customer_request_date": clean_json_value(
                    row.get("customer_request_date")
                ),
                "timing_bucket": timing_bucket,
                "open_order_value": value,
                "open_order_volume": volume,
                "coverage_performance": clean_text_value(
                    row.get("coverage_performance")
                ),
                "owner": "",
                "review_status": "New",
                "comment": (
                    f"Open order exposure of {format_number(value, 'Value')} "
                    f"and {format_number(volume)} units for {category or 'uncategorized'}"
                    f" / {sub_category or 'uncategorized'} in {season}"
                    f" {requested_month}. Timing: {timing_bucket or 'N/A'}."
                ),
                "brand": clean_text_value(row.get("brand")),
                "style_color": clean_text_value(row.get("style_color")),
                "style_name": clean_text_value(row.get("style_name")),
                "sold_to_name": clean_text_value(row.get("sold_to_name")),
                "ship_to_name": clean_text_value(row.get("ship_to_name")),
            }
        )

    return exceptions


@lru_cache(maxsize=64)
def retrieve_rules_cached(query: str, top_k: int = 4) -> tuple[tuple[tuple[str, Any], ...], ...]:
    rules = retrieve_reporting_rules(query=query, top_k=top_k)
    normalized_rules = []

    for rule in rules:
        normalized_rules.append(
            tuple(
                sorted(
                    {
                        "title": rule.get("title") or "Reporting rule",
                        "source": rule.get("source") or "Pinecone",
                        "score": rule.get("score"),
                        "text": rule.get("text") or "",
                    }.items()
                )
            )
        )

    return tuple(normalized_rules)


def rules_tuple_to_dicts(
    rules: tuple[tuple[tuple[str, Any], ...], ...],
) -> list[dict[str, Any]]:
    return [dict(rule) for rule in rules]


def build_rule_query(
    report_data: dict[str, Any] | None,
    selected_filters: dict[str, list[str]] | None = None,
) -> str:
    summary = (report_data or {}).get("executive_summary", {})
    filters = selected_filters or {}

    return (
        "Explain SC coverage calculation, included statuses, validation rules, "
        "open order timing buckets, and business interpretation for "
        f"risk level {summary.get('risk_level', 'N/A')}. "
        f"Filters: {filters}."
    )


def get_pinecone_rules(
    report_data: dict[str, Any] | None,
    selected_filters: dict[str, list[str]] | None = None,
    top_k: int = 4,
) -> tuple[list[dict[str, Any]], str | None]:
    try:
        query = build_rule_query(report_data, selected_filters)
        return rules_tuple_to_dicts(retrieve_rules_cached(query, top_k)), None
    except Exception as exc:
        return [], str(exc)


def build_report_chat_context(report_data: dict[str, Any] | None) -> dict[str, Any]:
    if not report_data:
        return {}

    return {
        "executive_summary": report_data.get("executive_summary", {}),
        "validation": report_data.get("validation", {}),
        "coverage_summary": report_data.get("coverage_summary", [])[:12],
        "timing_risk": report_data.get("timing_risk", [])[:12],
        "highest_category_risk": report_data.get("highest_category_risk", {}),
        "category_risk_summary": report_data.get("category_risk_summary", [])[:15],
        "sub_category_risk_summary": report_data.get("sub_category_risk_summary", [])[:15],
        "top_raw_open_order_rows": report_data.get("top_raw_open_order_rows", [])[:10],
    }


def answer_report_question(
    question: str,
    report_data: dict[str, Any] | None,
    rules: list[dict[str, Any]],
) -> str:
    load_dotenv()

    clean_question = question.strip()
    if not clean_question:
        return "Ask a specific question about coverage, risk, validation, timing, or open orders."

    if not report_data:
        return "No report context is loaded yet. Refresh the dashboard and try again."

    if not os.getenv("OPENAI_API_KEY"):
        return "OpenAI is not configured for this deployment. Add OPENAI_API_KEY to enable report chat."

    question_rules, question_rules_error = get_pinecone_rules(
        report_data,
        {"user_question": [clean_question]},
        top_k=4,
    )
    combined_rules = question_rules or rules

    rules_context = [
        {
            "title": rule.get("title"),
            "source": rule.get("source"),
            "text": str(rule.get("text") or "")[:900],
        }
        for rule in combined_rules[:4]
    ]

    prompt = f"""
You are a supply-chain coverage analyst embedded in an executive dashboard.

Answer the user's question using only:
1. The current report context, including raw orderbook-derived summaries.
2. The retrieved Pinecone business/reporting rules.

Rules:
- Be concise and business-like.
- Do not invent unavailable data.
- Explain which retrieved rule supports the answer when relevant.
- If the question asks for calculation logic, reference the rule text.
- If the question asks about category, product category, sub-category, or highest risk, use highest_category_risk and category_risk_summary first. Name the actual category and use its value/volume metrics.
- Do not answer category questions with season/month only when category_risk_summary is available.
- If the question asks for raw-data detail, use top_raw_open_order_rows and say these are the highest-exposure rows from the currently filtered orderbook.
- If the question asks for business interpretation, connect the answer to coverage, open-order exposure, timing risk, and validation.
- If Pinecone retrieval fails, still answer from report context and mention that rule retrieval was unavailable.

Current report context:
{build_report_chat_context(report_data)}

Retrieved Pinecone rules:
{rules_context}

Pinecone retrieval error:
{question_rules_error}

User question:
{clean_question}
"""

    try:
        llm = ChatOpenAI(
            model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4o-mini"),
            temperature=0,
        )
        response = llm.invoke(prompt)
        return str(response.content).strip()
    except Exception as exc:
        return f"AI answer unavailable: {exc}"


def empty_figure(message: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        x=0.5,
        y=0.5,
        xref="paper",
        yref="paper",
        showarrow=False,
        font=dict(size=13, color=INK_MUTED),
    )
    return polish_figure(fig, height=300)


def polish_figure(fig: go.Figure, height: int = 330) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=48, r=20, t=40, b=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT_STACK, size=12, color=INK_SECONDARY),
        title=dict(font=dict(size=12, color=INK_MUTED), x=0, xanchor="left"),
        legend=dict(
            orientation="h",
            y=1.12,
            x=0,
            xanchor="left",
            font=dict(size=11, color=INK_SECONDARY),
        ),
        hoverlabel=dict(
            bgcolor="#ffffff",
            bordercolor=GRIDLINE,
            font=dict(color=INK_PRIMARY, size=12, family=FONT_STACK),
        ),
    )
    fig.update_xaxes(
        showgrid=False,
        linecolor=AXIS_LINE,
        tickfont=dict(color=INK_MUTED, size=11),
        title_font=dict(color=INK_SECONDARY, size=11),
    )
    fig.update_yaxes(
        gridcolor=GRIDLINE,
        linecolor=AXIS_LINE,
        zeroline=False,
        tickfont=dict(color=INK_MUTED, size=11),
        title_font=dict(color=INK_SECONDARY, size=11),
    )
    return fig


def make_gauge(title: str, value: float, color: str) -> go.Figure:
    pct = max(0, min(value * 100, 100))
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=pct,
            domain={"x": [0.08, 0.92], "y": [0, 1]},
            number={"suffix": "%", "font": {"size": 30, "color": INK_PRIMARY}},
            title={"text": title, "font": {"size": 12, "color": INK_MUTED}},
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickvals": [0, 50, 100],
                    "tickwidth": 0,
                    "tickcolor": GRIDLINE,
                    "tickfont": {"color": INK_MUTED, "size": 10},
                },
                "bar": {"color": color, "thickness": 0.28},
                "bgcolor": "#f4f4f2",
                "borderwidth": 1,
                "bordercolor": GRIDLINE,
                "steps": [
                    {"range": [0, 50], "color": "rgba(208,59,59,0.08)"},
                    {"range": [50, 75], "color": "rgba(250,178,25,0.10)"},
                    {"range": [75, 100], "color": "rgba(12,163,12,0.10)"},
                ],
            },
        )
    )
    return polish_figure(fig, height=250)


def clean_bar_chart(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    title: str,
    y_title: str,
    colors: list[str],
    metric_mode: str | None = None,
    percent_labels: bool = False,
    height: int = 330,
) -> go.Figure:
    if df.empty:
        return empty_figure("No data available")

    labels = df[x_col].astype(str).tolist()
    values = pd.to_numeric(df[y_col], errors="coerce").fillna(0).astype(float).tolist()
    bar_colors = [colors[index % len(colors)] for index in range(len(labels))]
    text = [f"{value:.1%}" if percent_labels else format_number(value, metric_mode) for value in values]
    max_value = max(values) if values else 0

    fig = go.Figure(
        go.Bar(
            x=labels,
            y=values,
            marker=dict(color=bar_colors),
            text=text,
            textposition="outside",
            textfont=dict(color=INK_PRIMARY, size=11),
            width=0.5,
            hovertemplate="%{x}<br>%{text}<extra></extra>",
        )
    )
    fig.update_layout(
        title=title,
        showlegend=False,
        bargap=0.45,
        yaxis=dict(
            title=y_title,
            range=[0, max_value * 1.22 if max_value else 1],
            tickformat=".0%" if percent_labels else None,
        ),
    )
    return polish_figure(fig, height=height)


def make_heatmap(
    df: pd.DataFrame,
    x_col: str,
    y_col: str,
    z_col: str,
    title: str,
    metric_mode: str,
    height: int = 330,
) -> go.Figure:
    if df.empty:
        return empty_figure("No exposure data available")

    pivot = df.pivot_table(index=y_col, columns=x_col, values=z_col, aggfunc="sum", fill_value=0)
    pivot = pivot.reindex(sorted(pivot.columns, key=str), axis=1)

    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            x=pivot.columns.astype(str).tolist(),
            y=pivot.index.astype(str).tolist(),
            colorscale=SEQUENTIAL_BLUE,
            colorbar=dict(
                title=dict(text=metric_mode, font=dict(size=10, color=INK_MUTED)),
                tickfont=dict(size=10, color=INK_MUTED),
                thickness=12,
                len=0.8,
                outlinewidth=0,
            ),
            hovertemplate=f"%{{x}} · %{{y}}<br>Open {metric_mode}: %{{z:,.0f}}<extra></extra>",
            xgap=2,
            ygap=2,
        )
    )
    fig.update_layout(title=title)
    return polish_figure(fig, height=height)


def metric_card(title: str, value: str, subtitle: str, tone: str) -> html.Div:
    return html.Div(
        [
            html.Div(title, className="metric-title"),
            html.Div(value, className="metric-value"),
            html.Div(subtitle, className="metric-subtitle"),
        ],
        className=f"metric-card metric-{tone}",
    )


def panel(title: str, child: Any, class_name: str = "") -> html.Div:
    return html.Div(
        [
            html.Div(title, className="panel-title"),
            html.Div(child, className="panel-body"),
        ],
        className=f"panel {class_name}".strip(),
    )


def build_summary_table(report_data: dict[str, Any], metric_mode: str) -> list[dict[str, Any]]:
    cols = metric_columns(metric_mode)
    df = pd.DataFrame(report_data.get("coverage_summary", []))
    if df.empty:
        return []

    table = df[
        [
            "season",
            "requested_month",
            cols["total"],
            cols["covered"],
            cols["open"],
            cols["coverage_pct"],
            cols["open_pct"],
            "risk_level",
        ]
    ].copy()
    table = table.sort_values(["season", "requested_month"])
    table[cols["total"]] = table[cols["total"]].map(lambda value: format_number(value, metric_mode))
    table[cols["covered"]] = table[cols["covered"]].map(lambda value: format_number(value, metric_mode))
    table[cols["open"]] = table[cols["open"]].map(lambda value: format_number(value, metric_mode))
    table[cols["coverage_pct"]] = table[cols["coverage_pct"]].map(format_pct)
    table[cols["open_pct"]] = table[cols["open_pct"]].map(format_pct)
    table = table.rename(
        columns={
            "season": "Season",
            "requested_month": "Month",
            cols["total"]: f"Total {metric_mode}",
            cols["covered"]: f"Covered {metric_mode}",
            cols["open"]: f"Open {metric_mode}",
            cols["coverage_pct"]: "Coverage",
            cols["open_pct"]: "Open %",
            "risk_level": "Risk",
        }
    )
    return table.to_dict("records")


def classify_risk_level(coverage_percentage: float) -> str:
    if coverage_percentage >= 0.75:
        return "Low"
    if coverage_percentage >= 0.5:
        return "Medium"
    return "High"


def build_dimension_risk_context(
    df: pd.DataFrame,
    dimension: str,
    limit: int = 15,
) -> list[dict[str, Any]]:
    required_columns = {
        dimension,
        "status",
        "report_wholesale_value",
        "report_volume",
    }
    if df.empty or not required_columns.issubset(df.columns):
        return []

    included = df[df["is_included"]].copy() if "is_included" in df else df.copy()
    if included.empty:
        return []

    included[dimension] = included[dimension].fillna("Unclassified").astype(str)
    included["is_open_order"] = included["status"].astype(str).str.strip() == "Open Order"
    included["is_covered"] = included["status"].astype(str).str.strip().isin(
        ["Booked/Shipped", "Available"]
    )
    included["open_order_value"] = included["report_wholesale_value"].where(
        included["is_open_order"],
        0,
    )
    included["open_order_volume"] = included["report_volume"].where(
        included["is_open_order"],
        0,
    )
    included["covered_value"] = included["report_wholesale_value"].where(
        included["is_covered"],
        0,
    )
    included["covered_volume"] = included["report_volume"].where(
        included["is_covered"],
        0,
    )

    grouped = (
        included.groupby(dimension, as_index=False)
        .agg(
            total_value=("report_wholesale_value", "sum"),
            covered_value=("covered_value", "sum"),
            open_order_value=("open_order_value", "sum"),
            total_volume=("report_volume", "sum"),
            covered_volume=("covered_volume", "sum"),
            open_order_volume=("open_order_volume", "sum"),
            rows=("source_row_number", "count"),
        )
        .sort_values(["open_order_value", "open_order_volume"], ascending=False)
    )

    if grouped.empty:
        return []

    grouped["value_coverage_percentage"] = grouped.apply(
        lambda row: row["covered_value"] / row["total_value"]
        if row["total_value"]
        else 0,
        axis=1,
    )
    grouped["volume_coverage_percentage"] = grouped.apply(
        lambda row: row["covered_volume"] / row["total_volume"]
        if row["total_volume"]
        else 0,
        axis=1,
    )
    grouped["open_order_value_percentage"] = grouped.apply(
        lambda row: row["open_order_value"] / row["total_value"]
        if row["total_value"]
        else 0,
        axis=1,
    )
    grouped["risk_level"] = grouped["value_coverage_percentage"].map(classify_risk_level)

    output_columns = [
        dimension,
        "risk_level",
        "total_value",
        "covered_value",
        "open_order_value",
        "value_coverage_percentage",
        "open_order_value_percentage",
        "total_volume",
        "covered_volume",
        "open_order_volume",
        "volume_coverage_percentage",
        "rows",
    ]
    grouped = grouped[output_columns].head(limit).copy()

    for column in [
        "total_value",
        "covered_value",
        "open_order_value",
        "total_volume",
        "covered_volume",
        "open_order_volume",
    ]:
        grouped[column] = grouped[column].round(2)

    for column in [
        "value_coverage_percentage",
        "volume_coverage_percentage",
        "open_order_value_percentage",
    ]:
        grouped[column] = grouped[column].round(4)

    return grouped.to_dict("records")


def build_top_raw_open_order_rows(df: pd.DataFrame, limit: int = 10) -> list[dict[str, Any]]:
    if df.empty or "status" not in df:
        return []

    open_orders = df[df["status"].astype(str).str.strip() == "Open Order"].copy()
    if open_orders.empty:
        return []

    open_orders = open_orders.sort_values(
        ["report_wholesale_value", "report_volume"],
        ascending=[False, False],
    ).head(limit)

    columns = [
        "source_row_number",
        "season",
        "requested_month",
        "category",
        "sub_category",
        "gender",
        "age_division",
        "style_color",
        "style_name",
        "coverage_performance",
        "eta",
        "customer_request_date",
        "timing_bucket",
        "report_wholesale_value",
        "report_volume",
        "ship_to_name",
        "sold_to_name",
    ]
    available_columns = [column for column in columns if column in open_orders.columns]
    output = open_orders[available_columns].copy()

    for column in ["report_wholesale_value", "report_volume"]:
        if column in output:
            output[column] = pd.to_numeric(output[column], errors="coerce").fillna(0).round(2)

    return output.where(pd.notna(output), None).to_dict("records")


def build_insights(
    report_data: dict[str, Any],
    filtered_df: pd.DataFrame,
    metric_mode: str,
) -> list[str]:
    summary = report_data["executive_summary"]
    cols = metric_columns(metric_mode)
    metric_value = "report_wholesale_value" if metric_mode == "Value" else "report_volume"
    included = filtered_df[filtered_df["is_included"]].copy()
    open_orders = included[included["status"] == "Open Order"].copy()

    insights = [
        (
            f"{metric_mode} coverage is {format_pct(summary.get(cols['coverage_pct']))}; "
            f"open exposure remains {format_number(summary.get(cols['open']), metric_mode)}."
        ),
        (
            f"Risk level is {summary.get('risk_level', 'N/A')} across "
            f"{summary.get('included_rows', 0):,} included rows."
        ),
    ]

    if not open_orders.empty and "category" in open_orders:
        category = (
            open_orders.groupby("category", dropna=False)[metric_value]
            .sum()
            .sort_values(ascending=False)
            .head(1)
        )
        if not category.empty:
            insights.append(
                f"Largest open exposure category is {category.index[0]} at "
                f"{format_number(category.iloc[0], metric_mode)}."
            )

    timing = pd.DataFrame(report_data.get("timing_risk", []))
    if not timing.empty and cols["late_pct"] in timing:
        highest_late = timing.sort_values(cols["late_pct"], ascending=False).head(1)
        if not highest_late.empty:
            row = highest_late.iloc[0]
            insights.append(
                f"Highest late-risk period is {row['season']} / {row['requested_month']} "
                f"at {format_pct(row[cols['late_pct']])} of open orders."
            )

    return insights


def build_dashboard_content(
    metric_mode: str,
    selected_filters: dict[str, list[str]],
    refresh_token: int,
) -> tuple[
    list[Any],
    list[Any],
    go.Figure,
    go.Figure,
    go.Figure,
    go.Figure,
    go.Figure,
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any] | None,
]:
    base_df = load_base_dataframe(refresh_token)
    filtered_df = apply_dashboard_filters(base_df, selected_filters)

    if filtered_df.empty:
        empty = empty_figure("No rows match the selected filters")
        return [], [], empty, empty, empty, empty, empty, [], [], None

    report_data = build_coverage_report(filtered_df.to_dict("records"))
    category_risk_summary = build_dimension_risk_context(filtered_df, "category")
    sub_category_risk_summary = build_dimension_risk_context(filtered_df, "sub_category")
    report_data["category_risk_summary"] = category_risk_summary
    report_data["highest_category_risk"] = (
        category_risk_summary[0] if category_risk_summary else {}
    )
    report_data["sub_category_risk_summary"] = sub_category_risk_summary
    report_data["top_raw_open_order_rows"] = build_top_raw_open_order_rows(filtered_df)
    summary = report_data["executive_summary"]
    cols = metric_columns(metric_mode)

    open_pct = safe_ratio(summary.get(cols["open"]), summary.get(cols["total"]))
    validation = report_data.get("validation", {})
    validation_text = "PASS" if validation.get("passes_reconciliation") else "CHECK"
    validation_tone = "green" if validation_text == "PASS" else "red"

    cards = [
        metric_card("Total Demand", format_number(summary.get(cols["total"]), metric_mode), f"{summary.get('included_rows', 0):,} included rows", "blue"),
        metric_card("Covered", format_number(summary.get(cols["covered"]), metric_mode), "Booked/Shipped + Available", "green"),
        metric_card("Coverage", format_pct(summary.get(cols["coverage_pct"])), f"{metric_mode.lower()} basis", "violet"),
        metric_card("Open Exposure", format_number(summary.get(cols["open"]), metric_mode), f"{format_pct(open_pct)} of demand", "amber"),
        metric_card("Validation", validation_text, f"{summary.get('cancelled_rows', 0):,} cancelled rows excluded", validation_tone),
    ]

    insights = [
        html.Div(insight, className="insight-item")
        for insight in build_insights(report_data, filtered_df, metric_mode)
    ]

    status_df = pd.DataFrame(
        [
            ("Booked/Shipped", summary.get(cols["booked"], 0)),
            ("Available", summary.get(cols["available"], 0)),
            ("Open Order", summary.get(cols["open"], 0)),
        ],
        columns=["Status", metric_mode],
    )
    status_fig = clean_bar_chart(
        status_df,
        "Status",
        metric_mode,
        "Coverage Mix by Status",
        metric_mode,
        [STATUS_MIX_COLORS["Booked/Shipped"], STATUS_MIX_COLORS["Available"], STATUS_MIX_COLORS["Open Order"]],
        metric_mode=metric_mode,
    )

    gauge_fig = make_gauge(
        f"{metric_mode} Coverage",
        float(summary.get(cols["coverage_pct"], 0) or 0),
        RISK_COLORS.get(summary.get("risk_level", "N/A"), STATUS_COLORS["muted"]),
    )

    coverage_summary = pd.DataFrame(report_data.get("coverage_summary", []))
    if coverage_summary.empty:
        trend_fig = empty_figure("No trend data")
        season_fig = empty_figure("No season data")
    else:
        trend_df = (
            coverage_summary.groupby("requested_month", as_index=False)
            .agg(coverage_pct=(cols["coverage_pct"], "mean"), open_exposure=(cols["open"], "sum"))
            .sort_values("requested_month")
        )
        trend_fig = go.Figure()
        trend_fig.add_trace(
            go.Scatter(
                x=trend_df["requested_month"],
                y=trend_df["coverage_pct"],
                mode="lines+markers",
                name="Coverage",
                line=dict(color=CATEGORICAL_COLORS[0], width=2, shape="spline"),
                marker=dict(size=8, color=CATEGORICAL_COLORS[0], line=dict(color="#ffffff", width=2)),
                fill="tozeroy",
                fillcolor="rgba(42, 120, 214, 0.10)",
                hovertemplate="%{x}: %{y:.1%}<extra></extra>",
            )
        )
        trend_fig.update_layout(
            title=f"Monthly Coverage Trend ({metric_mode})",
            yaxis_tickformat=".0%",
            yaxis_title="Coverage",
            showlegend=False,
        )
        trend_fig = polish_figure(trend_fig, height=330)

        season_df = (
            coverage_summary.groupby(["season", "requested_month"], as_index=False)
            .agg(open_exposure=(cols["open"], "sum"))
            .sort_values("open_exposure", ascending=False)
        )
        season_fig = make_heatmap(
            season_df,
            "requested_month",
            "season",
            "open_exposure",
            f"Open Exposure by Season & Month ({metric_mode})",
            metric_mode,
        )

    timing = pd.DataFrame(report_data.get("timing_risk", []))
    if timing.empty:
        timing_fig = empty_figure("No open order timing risk")
    else:
        timing_cols = [
            ("Early/On Time", f"early_on_time_{cols['prefix']}"),
            ("+1 week", f"plus_1_week_{cols['prefix']}"),
            ("+2 weeks", f"plus_2_weeks_{cols['prefix']}"),
            ("+3 weeks", f"plus_3_weeks_{cols['prefix']}"),
            ("+4 weeks", f"plus_4_weeks_or_later_{cols['prefix']}"),
        ]
        timing_df = pd.DataFrame(
            [{"Bucket": label, metric_mode: timing.get(column, pd.Series(dtype=float)).sum()} for label, column in timing_cols]
        )
        timing_fig = clean_bar_chart(
            timing_df,
            "Bucket",
            metric_mode,
            f"Open Timing Exposure ({metric_mode})",
            metric_mode,
            TIMING_RAMP,
            metric_mode=metric_mode,
        )

    top_open_records = []
    open_df = filtered_df[filtered_df["status"] == "Open Order"].copy()
    if not open_df.empty:
        metric_field = "report_wholesale_value" if metric_mode == "Value" else "report_volume"
        group_cols = [column for column in ["category", "sub_category", "gender"] if column in open_df.columns]
        if group_cols:
            top_open = (
                open_df.groupby(group_cols, dropna=False)
                .agg(Open=(metric_field, "sum"), Rows=("source_row_number", "count"))
                .reset_index()
                .sort_values("Open", ascending=False)
                .head(10)
            )
            top_open["Open"] = top_open["Open"].map(lambda value: format_number(value, metric_mode))
            top_open_records = top_open.to_dict("records")

    return (
        cards,
        insights,
        status_fig,
        gauge_fig,
        trend_fig,
        season_fig,
        timing_fig,
        build_summary_table(report_data, metric_mode),
        top_open_records,
        report_data,
    )


filter_options = get_filter_options()

app = Dash(__name__, title="SC Coverage Executive Dashboard")
server = app.server


@server.route("/run-report", methods=["POST"])
def run_report_endpoint():
    payload = request.get_json(silent=True) or {}
    banner = str(payload.get("banner") or DEFAULT_BANNER)
    seasons = normalize_payload_list(payload.get("seasons")) or DEFAULT_SEASONS
    requested_months = normalize_payload_list(payload.get("requested_months"))
    order_type = str(payload.get("order_type") or DEFAULT_ORDER_TYPE)
    recipient_name = str(payload.get("recipient_name") or "")
    dashboard_url = str(payload.get("dashboard_url") or request.host_url.rstrip("/"))
    airtable_exceptions_url = str(payload.get("airtable_exceptions_url") or "").strip()
    exception_limit = int(payload.get("exception_limit") or 50)

    generated_at = datetime.now(timezone.utc).isoformat()

    records = load_orderbook_records(
        banner=banner,
        seasons=seasons,
        order_type=order_type,
    )
    base_df = records_to_filter_dataframe(records)
    filtered_df = apply_dashboard_filters(
        base_df,
        {"requested_month": requested_months},
    )

    if filtered_df.empty:
        return jsonify(
            {
                "status": "failed",
                "mode": "dashboard_link",
                "generated_at": generated_at,
                "report_run_id": generated_at,
                "dashboard_url": dashboard_url,
                "airtable_exceptions_url": airtable_exceptions_url,
                "banner": banner,
                "seasons": seasons,
                "requested_months": requested_months,
                "order_type": order_type,
                "error": "No records matched the report filters.",
                "email_subject": f"SC Coverage Report Failed - {banner}",
                "email_body": (
                    "The SC Coverage Report workflow ran, but no records matched "
                    "the selected banner, season, order type, and requested month filters."
                ),
            }
        ), 400

    report_data = build_coverage_report(filtered_df.to_dict(orient="records"))
    summary = report_data.get("executive_summary", {})
    validation = report_data.get("validation", {})
    coverage_exceptions = build_coverage_exceptions(
        filtered_df,
        report_run_id=generated_at,
        limit=exception_limit,
    )
    agent_observations, agent_observation_error = safe_generate_observations(report_data)

    season_text = ", ".join(str(season) for season in seasons)
    requested_month_text = ", ".join(requested_months) if requested_months else "All"
    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"

    risk_level_value = str(summary.get("risk_level", "N/A"))
    email_subject = (
        f"SC Coverage Dashboard Ready - {banner} - {season_text} - "
        f"Risk: {risk_level_value}"
    )
    email_body = f"""{greeting}

The SC Coverage dashboard is ready.

Dashboard:
{dashboard_url}
"""

    if airtable_exceptions_url:
        email_body += f"""
Coverage Exceptions Review:
{airtable_exceptions_url}
"""

    email_body += f"""

Report scope:
- Banner: {banner}
- Seasons: {season_text}
- Requested months: {requested_month_text}
- Order type: {order_type}

Executive summary:
- Value coverage: {format_pct(summary.get("value_coverage_percentage"))}
- Volume coverage: {format_pct(summary.get("volume_coverage_percentage"))}
- Open order value: {format_number(summary.get("open_order_value"), "Value")}
- Open order volume: {format_number(summary.get("open_order_volume"))}
- Included rows: {summary.get("included_rows", 0):,}
- Cancelled rows excluded: {summary.get("cancelled_rows", 0):,}
- Coverage exceptions exported: {len(coverage_exceptions):,}
- Risk level: {risk_level_value}

Agent observations:
{chr(10).join(f"- {observation}" for observation in agent_observations[:5])}

Open the dashboard link to view the current executive report with filters, value/volume views, timing risk, and open exceptions.

This message was generated automatically by the SC Coverage Report Agent.
"""

    return jsonify(
        {
            "status": "success",
            "mode": "dashboard_link",
            "generated_at": generated_at,
            "report_run_id": generated_at,
            "dashboard_url": dashboard_url,
            "airtable_exceptions_url": airtable_exceptions_url,
            "banner": banner,
            "seasons": seasons,
            "requested_months": requested_months,
            "order_type": order_type,
            "records_count": len(records),
            "filtered_records_count": len(filtered_df),
            "source_rows": summary.get("source_rows"),
            "included_rows": summary.get("included_rows"),
            "cancelled_rows": summary.get("cancelled_rows"),
            "total_value": summary.get("total_value"),
            "covered_value": summary.get("covered_value"),
            "open_order_value": summary.get("open_order_value"),
            "value_coverage_percentage": summary.get("value_coverage_percentage"),
            "total_volume": summary.get("total_volume"),
            "covered_volume": summary.get("covered_volume"),
            "open_order_volume": summary.get("open_order_volume"),
            "volume_coverage_percentage": summary.get("volume_coverage_percentage"),
            "risk_level": risk_level_value,
            "coverage_exceptions_count": len(coverage_exceptions),
            "coverage_exceptions": coverage_exceptions,
            "agent_observations": agent_observations,
            "agent_observation_error": agent_observation_error,
            "validation_passed": validation.get("passes_reconciliation"),
            "value_difference": validation.get("value_difference"),
            "volume_difference": validation.get("volume_difference"),
            "unexpected_statuses": validation.get("unexpected_statuses", []),
            "missing_required_values": validation.get("missing_required_values", {}),
            "email_subject": email_subject,
            "email_body": email_body,
        }
    )

app.index_string = """
<!DOCTYPE html>
<html>
  <head>
    {%metas%}
    <title>{%title%}</title>
    {%favicon%}
    {%css%}
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <style>
      :root {
        --page-bg: #f4f5f3;
        --surface: #ffffff;
        --surface-muted: #f7f7f5;
        --ink-primary: #0b0b0b;
        --ink-secondary: #52514e;
        --ink-muted: #898781;
        --border: rgba(11, 11, 11, 0.09);
        --gridline: #e5e4dd;
        --accent-blue: #2a78d6;
        --accent-green: #0ca30c;
        --accent-amber: #fab219;
        --accent-violet: #4a3aa7;
        --accent-red: #d03b3b;
        --shadow: 0 1px 2px rgba(11, 11, 11, 0.05), 0 1px 1px rgba(11, 11, 11, 0.03);
      }
      * { box-sizing: border-box; }
      body {
        margin: 0;
        background: var(--page-bg);
        color: var(--ink-primary);
        font-family: 'Inter', 'Segoe UI', system-ui, -apple-system, sans-serif;
      }
      .app-shell {
        max-width: 1900px;
        margin: 0 auto;
        padding: 20px 32px 32px;
      }
      .hero {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 16px;
        margin-bottom: 18px;
        border-bottom: 1px solid var(--border);
      }
      .hero-brand {
        display: flex;
        align-items: baseline;
        gap: 10px;
      }
      .hero-kicker {
        color: var(--accent-blue);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .hero-title {
        color: var(--ink-primary);
        font-size: 19px;
        font-weight: 600;
        letter-spacing: -0.01em;
      }
      .hero-subtitle {
        color: var(--ink-muted);
        font-size: 12px;
        text-align: right;
      }
      .layout-grid {
        display: grid;
        grid-template-columns: 260px minmax(0, 1fr);
        gap: 20px;
        align-items: start;
      }
      .sidebar, .panel, .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: 10px;
        box-shadow: var(--shadow);
      }
      .sidebar {
        grid-column: 1;
        padding: 16px;
        position: sticky;
        top: 20px;
      }
      .dashboard-main {
        grid-column: 2;
        min-width: 0;
      }
      .sidebar-title {
        color: var(--ink-primary);
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.04em;
        text-transform: uppercase;
        padding-bottom: 10px;
        margin-bottom: 12px;
        border-bottom: 1px solid var(--border);
      }
      .filter-label {
        font-size: 11px;
        font-weight: 600;
        color: var(--ink-muted);
        letter-spacing: 0.02em;
        text-transform: uppercase;
        margin: 12px 0 5px;
      }
      .metric-grid {
        display: grid;
        grid-template-columns: repeat(5, minmax(0, 1fr));
        gap: 12px;
      }
      .metric-card {
        min-height: 100px;
        padding: 14px 16px 12px;
        position: relative;
        border-top: 3px solid transparent;
      }
      .metric-blue   { border-top-color: var(--accent-blue); }
      .metric-green  { border-top-color: var(--accent-green); }
      .metric-violet { border-top-color: var(--accent-violet); }
      .metric-amber  { border-top-color: var(--accent-amber); }
      .metric-red    { border-top-color: var(--accent-red); }
      .metric-title {
        color: var(--ink-muted);
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.03em;
      }
      .metric-value {
        color: var(--ink-primary);
        font-size: 27px;
        font-weight: 600;
        letter-spacing: -0.01em;
        margin-top: 8px;
      }
      .metric-subtitle {
        color: var(--ink-muted);
        font-size: 11.5px;
        margin-top: 4px;
      }
      .insight-list {
        display: grid;
        grid-template-columns: repeat(2, minmax(0, 1fr));
        gap: 10px;
        margin-top: 12px;
      }
      .insight-item {
        background: var(--surface);
        border: 1px solid var(--border);
        border-left: 3px solid var(--accent-blue);
        border-radius: 8px;
        padding: 10px 12px;
        color: var(--ink-secondary);
        font-size: 12.5px;
        line-height: 1.4;
        box-shadow: var(--shadow);
      }
      .chart-grid {
        display: grid;
        grid-template-columns: 1fr 1fr 1.55fr;
        gap: 12px;
        margin-top: 14px;
      }
      .chart-grid .panel:nth-child(4) {
        grid-column: span 2;
      }
      .panel {
        overflow: hidden;
        min-height: 0;
      }
      .panel-title {
        color: var(--ink-secondary);
        font-size: 11.5px;
        font-weight: 700;
        letter-spacing: 0.03em;
        text-transform: uppercase;
        padding: 12px 14px 10px;
        border-bottom: 1px solid var(--border);
      }
      .panel-body {
        padding: 6px 8px 8px;
      }
      .tables-grid {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 12px;
        margin-top: 14px;
      }
      .sidebar-divider {
        height: 1px;
        background: var(--border);
        margin: 18px 0 12px;
      }
      .ai-chat-preview {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 8px;
        background: rgba(42, 120, 214, 0.06);
        border: 1px solid rgba(42, 120, 214, 0.30);
        border-left: 3px solid var(--accent-blue);
        border-radius: 8px;
        padding: 10px 12px;
        cursor: pointer;
        transition: background 0.15s ease, border-color 0.15s ease;
      }
      .ai-chat-preview:hover {
        background: rgba(42, 120, 214, 0.11);
        border-color: rgba(42, 120, 214, 0.45);
      }
      .ai-chat-preview-text {
        display: flex;
        flex-direction: column;
        gap: 2px;
        min-width: 0;
      }
      .ai-chat-title {
        color: var(--accent-blue);
        font-size: 12px;
        font-weight: 700;
      }
      .ai-chat-hint {
        color: var(--ink-muted);
        font-size: 10.5px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .ai-chat-icon {
        color: var(--accent-blue);
        font-size: 15px;
        flex: none;
      }
      .ai-chat.is-expanded .ai-chat-preview {
        display: none;
      }
      .ai-chat-overlay {
        display: flex;
        position: fixed;
        inset: 0;
        align-items: center;
        justify-content: center;
        z-index: 9000;
        isolation: isolate;
        transform: translateZ(0);
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
        transition: opacity 0.12s ease-out;
      }
      .ai-chat.is-expanded .ai-chat-overlay {
        opacity: 1;
        visibility: visible;
        pointer-events: auto;
      }
      .ai-chat-backdrop {
        position: absolute;
        inset: 0;
        background: rgba(11, 11, 11, 0.4);
        cursor: pointer;
      }
      .ai-chat-modal {
        position: relative;
        z-index: 1;
        width: 620px;
        max-width: 92vw;
        max-height: 82vh;
        overflow-y: auto;
        background: var(--surface);
        border-top: 4px solid var(--accent-blue);
        border-radius: 12px;
        box-shadow: 0 24px 48px rgba(11, 11, 11, 0.22), 0 4px 12px rgba(11, 11, 11, 0.10);
        padding: 18px 20px 20px;
        transform: scale(0.97);
        transition: transform 0.12s ease-out;
      }
      .ai-chat.is-expanded .ai-chat-modal {
        transform: scale(1);
      }
      .ai-chat-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
      }
      .ai-chat-header .ai-chat-title {
        font-size: 14px;
      }
      .ai-chat-icon-btn {
        width: 26px;
        height: 26px;
        padding: 0;
        margin: 0;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(42, 120, 214, 0.08);
        border: 1px solid rgba(42, 120, 214, 0.30);
        color: var(--accent-blue);
        border-radius: 6px;
        font-size: 13px;
        line-height: 1;
        cursor: pointer;
      }
      .ai-chat-icon-btn:hover {
        background: rgba(42, 120, 214, 0.16);
      }
      .ai-empty, .ai-answer {
        color: var(--ink-secondary);
        font-size: 13px;
        line-height: 1.55;
        padding: 10px 12px;
      }
      .ai-answer {
        background: var(--surface-muted);
        border: 1px solid var(--border);
        border-radius: 8px;
        margin-top: 12px;
        max-height: 360px;
        overflow-y: auto;
        white-space: pre-wrap;
      }
      .ai-question {
        width: 100%;
        min-height: 160px;
        box-sizing: border-box;
        resize: vertical;
        border: 1px solid var(--border);
        border-radius: 8px;
        padding: 10px 12px;
        color: var(--ink-primary);
        background: var(--surface);
        font-family: var(--font);
        font-size: 13px;
        line-height: 1.5;
      }
      .ai-question:focus {
        outline: 2px solid rgba(42, 120, 214, 0.18);
        border-color: var(--accent-blue);
      }
      .ai-ask-btn {
        background: var(--accent-blue) !important;
        color: #ffffff !important;
        border: 1px solid var(--accent-blue) !important;
      }
      .ai-ask-btn:hover {
        background: #2166ba !important;
      }
      button {
        background: var(--surface);
        color: var(--ink-primary);
        border: 1px solid var(--border);
        border-radius: 7px;
        font-weight: 600;
        font-size: 12px;
        padding: 9px 10px;
        width: 100%;
        margin-top: 16px;
        cursor: pointer;
        transition: background 0.15s ease;
      }
      button:hover {
        background: var(--surface-muted);
      }
      .Select-control {
        background: var(--surface) !important;
        color: var(--ink-primary) !important;
        border-color: var(--border) !important;
        font-size: 12px;
        border-radius: 6px !important;
      }
      .Select-menu-outer {
        background: var(--surface) !important;
        border-color: var(--border) !important;
      }
      .Select-value-label,
      .Select-option,
      .Select-placeholder {
        color: var(--ink-primary) !important;
        font-size: 12px;
      }
      .Select-option.is-focused {
        background: var(--surface-muted) !important;
      }
      label {
        color: var(--ink-secondary);
        font-size: 12px;
        margin-right: 10px;
      }
      @media (max-width: 1100px) {
        .layout-grid, .chart-grid, .tables-grid, .insight-list {
          grid-template-columns: 1fr;
        }
        .sidebar, .dashboard-main {
          grid-column: auto;
        }
        .metric-grid {
          grid-template-columns: repeat(2, minmax(0, 1fr));
        }
        .sidebar {
          position: static;
        }
      }
    </style>
  </head>
  <body>
    {%app_entry%}
    <footer>
      {%config%}
      {%scripts%}
      {%renderer%}
    </footer>
  </body>
</html>
"""


def dropdown(column: str, label: str) -> html.Div:
    return html.Div(
        [
            html.Div(label, className="filter-label"),
            dcc.Dropdown(
                id=f"filter-{column}",
                options=make_options(filter_options.get(column, [])),
                multi=True,
                placeholder=f"All {label.lower()}",
            ),
        ]
    )


app.layout = html.Div(
    [
        dcc.Store(id="report-context-store"),
        dcc.Store(id="rules-context-store"),
        html.Div(
            [
                html.Div(id="ai-chat-backdrop", className="ai-chat-backdrop", n_clicks=0),
                html.Div(
                    [
                        html.Div(
                            [
                                html.Span("Ask AI About This Report", className="ai-chat-title"),
                                html.Button(
                                    "⤡",
                                    id="ai-chat-minimize",
                                    className="ai-chat-icon-btn",
                                    n_clicks=0,
                                    title="Minimize",
                                ),
                            ],
                            className="ai-chat-header",
                        ),
                        dcc.Textarea(
                            id="ai-question",
                            className="ai-question",
                            placeholder="Ask about coverage logic, risk drivers, timing exposure, or what to review next.",
                        ),
                        html.Button("Ask AI", id="ask-ai", n_clicks=0, className="ai-ask-btn"),
                        html.Div(
                            "Ask a question to get a grounded answer based on the current report.",
                            id="ai-answer",
                            className="ai-empty",
                        ),
                    ],
                    className="ai-chat-modal",
                ),
            ],
            className="ai-chat-overlay",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div("SC Coverage", className="hero-kicker"),
                        html.Div("Supply Chain Coverage Scorecard", className="hero-title"),
                    ],
                    className="hero-brand",
                ),
                html.Div("Snipes / Nike-Jordan futures", className="hero-subtitle"),
            ],
            className="hero",
        ),
        html.Div(
            [
                html.Div(
                    [
                        html.Div("Report Controls", className="sidebar-title"),
                        html.Div("Metric View", className="filter-label"),
                        dcc.RadioItems(
                            id="metric-mode",
                            options=[
                                {"label": "Value", "value": "Value"},
                                {"label": "Volume", "value": "Volume"},
                            ],
                            value="Value",
                            inline=True,
                        ),
                        *[dropdown(column, label) for column, label in FILTER_CONFIG],
                        html.Button("Refresh Data", id="refresh-data", n_clicks=0),
                        html.Div(className="sidebar-divider"),
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.Span("Ask AI", className="ai-chat-title"),
                                        html.Span(
                                            "About this report — click to expand",
                                            className="ai-chat-hint",
                                        ),
                                    ],
                                    className="ai-chat-preview-text",
                                ),
                                html.Span("⤢", className="ai-chat-icon"),
                            ],
                            id="ai-chat-preview",
                            className="ai-chat-preview",
                            n_clicks=0,
                        ),
                    ],
                    className="sidebar",
                ),
                html.Div(
                    [
                        html.Div(id="metric-cards", className="metric-grid"),
                        html.Div(id="insights", className="insight-list"),
                        html.Div(
                            [
                                panel("Coverage Gauge", dcc.Graph(id="coverage-gauge")),
                                panel("Coverage Mix", dcc.Graph(id="status-mix")),
                                panel("Monthly Coverage Trend", dcc.Graph(id="coverage-trend")),
                                panel("Season Exposure", dcc.Graph(id="season-exposure")),
                                panel("Timing Risk", dcc.Graph(id="timing-risk")),
                            ],
                            className="chart-grid",
                        ),
                        html.Div(
                            [
                                panel(
                                    "Coverage Summary",
                                    dash_table.DataTable(
                                        id="coverage-table",
                                        page_size=10,
                                        sort_action="native",
                                        style_table={"overflowX": "auto"},
                                        style_header={
                                            "backgroundColor": "#f7f7f5",
                                            "color": "#52514e",
                                            "fontWeight": "700",
                                            "fontSize": "11px",
                                            "textTransform": "uppercase",
                                            "letterSpacing": "0.02em",
                                            "border": "none",
                                            "borderBottom": "1px solid #e5e4dd",
                                        },
                                        style_cell={
                                            "fontFamily": "'Inter', 'Segoe UI', system-ui, sans-serif",
                                            "fontSize": 12,
                                            "padding": "9px 10px",
                                            "border": "none",
                                            "borderBottom": "1px solid #f0efec",
                                            "backgroundColor": "#ffffff",
                                            "color": "#0b0b0b",
                                        },
                                        style_data_conditional=[
                                            {
                                                "if": {"row_index": "odd"},
                                                "backgroundColor": "#fafaf8",
                                            }
                                        ],
                                    ),
                                ),
                                panel(
                                    "Top Open Exceptions",
                                    dash_table.DataTable(
                                        id="exceptions-table",
                                        page_size=10,
                                        sort_action="native",
                                        style_table={"overflowX": "auto"},
                                        style_header={
                                            "backgroundColor": "#f7f7f5",
                                            "color": "#52514e",
                                            "fontWeight": "700",
                                            "fontSize": "11px",
                                            "textTransform": "uppercase",
                                            "letterSpacing": "0.02em",
                                            "border": "none",
                                            "borderBottom": "1px solid #e5e4dd",
                                        },
                                        style_cell={
                                            "fontFamily": "'Inter', 'Segoe UI', system-ui, sans-serif",
                                            "fontSize": 12,
                                            "padding": "9px 10px",
                                            "border": "none",
                                            "borderBottom": "1px solid #f0efec",
                                            "backgroundColor": "#ffffff",
                                            "color": "#0b0b0b",
                                        },
                                        style_data_conditional=[
                                            {
                                                "if": {"row_index": "odd"},
                                                "backgroundColor": "#fafaf8",
                                            }
                                        ],
                                    ),
                                ),
                            ],
                            className="tables-grid",
                        ),
                    ],
                    className="dashboard-main",
                ),
            ],
            className="layout-grid",
        ),
    ],
    id="ai-chat-panel",
    className="app-shell ai-chat is-collapsed",
)


@app.callback(
    Output("metric-cards", "children"),
    Output("insights", "children"),
    Output("status-mix", "figure"),
    Output("coverage-gauge", "figure"),
    Output("coverage-trend", "figure"),
    Output("season-exposure", "figure"),
    Output("timing-risk", "figure"),
    Output("coverage-table", "data"),
    Output("coverage-table", "columns"),
    Output("exceptions-table", "data"),
    Output("exceptions-table", "columns"),
    Output("report-context-store", "data"),
    Output("rules-context-store", "data"),
    Input("metric-mode", "value"),
    Input("filter-season", "value"),
    Input("filter-requested_month", "value"),
    Input("filter-brand", "value"),
    Input("filter-category", "value"),
    Input("filter-sub_category", "value"),
    Input("filter-gender", "value"),
    Input("filter-age_division", "value"),
    Input("filter-timing_bucket", "value"),
    Input("filter-status", "value"),
    Input("refresh-data", "n_clicks"),
)
def update_dashboard(
    metric_mode: str,
    season: list[str] | None,
    requested_month: list[str] | None,
    brand: list[str] | None,
    category: list[str] | None,
    sub_category: list[str] | None,
    gender: list[str] | None,
    age_division: list[str] | None,
    timing_bucket: list[str] | None,
    status: list[str] | None,
    refresh_data_clicks: int,
) -> tuple[Any, ...]:
    if refresh_data_clicks:
        load_base_dataframe.cache_clear()

    selected_filters = filter_values_to_dict(
        season=season,
        requested_month=requested_month,
        brand=brand,
        category=category,
        sub_category=sub_category,
        gender=gender,
        age_division=age_division,
        timing_bucket=timing_bucket,
        status=status,
    )

    (
        cards,
        insights,
        status_fig,
        gauge_fig,
        trend_fig,
        season_fig,
        timing_fig,
        summary_rows,
        exception_rows,
        report_data,
    ) = build_dashboard_content(metric_mode, selected_filters, refresh_data_clicks or 0)

    summary_columns = [{"name": column, "id": column} for column in (summary_rows[0].keys() if summary_rows else [])]
    exception_columns = [{"name": column, "id": column} for column in (exception_rows[0].keys() if exception_rows else [])]
    rules, _rules_error = get_pinecone_rules(report_data, selected_filters)

    return (
        cards,
        insights,
        status_fig,
        gauge_fig,
        trend_fig,
        season_fig,
        timing_fig,
        summary_rows,
        summary_columns,
        exception_rows,
        exception_columns,
        report_data or {},
        rules,
    )


@app.callback(
    Output("ai-answer", "children"),
    Output("ai-answer", "className"),
    Input("ask-ai", "n_clicks"),
    State("ai-question", "value"),
    State("report-context-store", "data"),
    State("rules-context-store", "data"),
    prevent_initial_call=True,
)
def update_ai_answer(
    n_clicks: int,
    question: str | None,
    report_data: dict[str, Any] | None,
    rules: list[dict[str, Any]] | None,
) -> tuple[str, str]:
    if not n_clicks:
        return (
            "Ask a question to get a grounded answer based on the current report.",
            "ai-empty",
        )

    answer = answer_report_question(question or "", report_data, rules or [])
    return answer, "ai-answer"


app.clientside_callback(
    """
    function(previewClicks, minimizeClicks, backdropClicks) {
        const ctx = dash_clientside.callback_context;
        if (!ctx.triggered.length) {
            return dash_clientside.no_update;
        }
        const triggeredId = ctx.triggered[0].prop_id.split(".")[0];
        if (triggeredId === "ai-chat-preview") {
            return "app-shell ai-chat is-expanded";
        }
        return "app-shell ai-chat is-collapsed";
    }
    """,
    Output("ai-chat-panel", "className"),
    Input("ai-chat-preview", "n_clicks"),
    Input("ai-chat-minimize", "n_clicks"),
    Input("ai-chat-backdrop", "n_clicks"),
    prevent_initial_call=True,
)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8050"))
    debug = os.getenv("DASH_DEBUG", "false").lower() == "true"
    app.run(debug=debug, host="0.0.0.0", port=port)
