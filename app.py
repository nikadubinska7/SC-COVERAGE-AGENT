from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd
import plotly.express as px
import streamlit as st

from src.services.dashboard_data import (
    DEFAULT_BANNER,
    DEFAULT_ORDER_TYPE,
    DEFAULT_SEASONS,
    FILTER_COLUMNS,
    build_dashboard_payload,
    build_filter_options,
    load_orderbook_records,
    records_to_filter_dataframe,
)


st.set_page_config(
    page_title="SC Coverage Report",
    page_icon="SC",
    layout="wide",
    initial_sidebar_state="expanded",
)


STATUS_COLORS = {
    "Booked/Shipped": "#16A34A",
    "Available": "#2563EB",
    "Open Order": "#DC2626",
    "Early/On Time": "#16A34A",
    "+1 week": "#F59E0B",
    "+2 weeks": "#F59E0B",
    "+3 weeks": "#DC2626",
    "+4 weeks or later": "#991B1B",
    "Unclassified Open Order": "#6B7280",
}

RISK_COLORS = {
    "Low": "#16A34A",
    "Medium": "#F59E0B",
    "High": "#DC2626",
}


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: #f6f7f9;
            color: #111827;
        }
        [data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e5e7eb;
        }
        .block-container {
            padding-top: 1.6rem;
            padding-bottom: 2.5rem;
        }
        .hero {
            background: linear-gradient(135deg, #111827 0%, #1f2937 58%, #0f766e 100%);
            color: #ffffff;
            padding: 26px 30px;
            border-radius: 8px;
            margin-bottom: 18px;
        }
        .hero-title {
            font-size: 34px;
            font-weight: 760;
            margin-bottom: 4px;
            letter-spacing: 0;
        }
        .hero-subtitle {
            font-size: 15px;
            color: #d1d5db;
            margin-bottom: 14px;
        }
        .hero-meta {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            font-size: 13px;
            color: #f3f4f6;
        }
        .meta-pill {
            background: rgba(255,255,255,0.12);
            border: 1px solid rgba(255,255,255,0.18);
            border-radius: 999px;
            padding: 6px 11px;
        }
        .kpi-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 18px 18px 16px;
            min-height: 128px;
            box-shadow: 0 8px 22px rgba(17,24,39,0.06);
        }
        .kpi-label {
            color: #6b7280;
            font-size: 12px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0;
            margin-bottom: 8px;
        }
        .kpi-value {
            color: #111827;
            font-size: 28px;
            font-weight: 760;
            line-height: 1.1;
            margin-bottom: 8px;
            overflow-wrap: anywhere;
        }
        .kpi-note {
            color: #4b5563;
            font-size: 13px;
            line-height: 1.35;
        }
        .badge {
            display: inline-block;
            border-radius: 999px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 760;
            padding: 6px 12px;
        }
        .section-card {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 18px;
            margin-bottom: 16px;
            box-shadow: 0 8px 22px rgba(17,24,39,0.04);
        }
        .observation-card {
            background: #ffffff;
            border-left: 4px solid #0f766e;
            border-radius: 8px;
            padding: 13px 15px;
            margin-bottom: 10px;
            color: #111827;
            box-shadow: 0 4px 14px rgba(17,24,39,0.04);
        }
        div[data-testid="stMetric"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def fmt_number(value: Any, metric_mode: str | None = None) -> str:
    if value is None:
        return "0"

    number = float(value)
    if metric_mode == "Value":
        return f"{number:,.0f}"
    return f"{number:,.0f}"


def fmt_pct(value: Any) -> str:
    if value is None:
        return "0.0%"
    return f"{float(value):.1%}"


def metric_prefix(metric_mode: str) -> str:
    return "value" if metric_mode == "Value" else "volume"


def metric_label(metric_mode: str) -> str:
    return "Value" if metric_mode == "Value" else "Volume"


def selected_metric_columns(metric_mode: str) -> dict[str, str]:
    prefix = metric_prefix(metric_mode)
    label = metric_label(metric_mode)
    return {
        "total": f"total_{prefix}",
        "booked": f"booked_shipped_{prefix}",
        "available": f"available_{prefix}",
        "open": f"open_order_{prefix}",
        "covered": f"covered_{prefix}",
        "coverage_pct": f"{prefix}_coverage_percentage",
        "open_pct": f"open_order_{prefix}_percentage",
        "total_label": f"Total {label}",
        "booked_label": f"Booked/Shipped {label}",
        "available_label": f"Available {label}",
        "open_label": f"Open Order {label}",
        "covered_label": f"Covered {label}",
    }


def status_badge(text: str, color: str) -> str:
    return f'<span class="badge" style="background:{color};">{text}</span>'


@st.cache_data(show_spinner=False)
def cached_load_records(refresh_token: int) -> list[dict[str, Any]]:
    return load_orderbook_records(
        banner=DEFAULT_BANNER,
        seasons=DEFAULT_SEASONS,
        order_type=DEFAULT_ORDER_TYPE,
    )


def render_header(metric_mode: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    st.markdown(
        f"""
        <div class="hero">
          <div class="hero-title">SC Coverage Report</div>
          <div class="hero-subtitle">Snipes / Nike-Jordan Order Coverage</div>
          <div class="hero-meta">
            <span class="meta-pill">Last refresh: {timestamp}</span>
            <span class="meta-pill">Metric mode: {metric_mode}</span>
            <span class="meta-pill">Source: Supabase orderbook</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class="kpi-card">
          <div class="kpi-label">{label}</div>
          <div class="kpi-value">{value}</div>
          <div class="kpi-note">{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpis(summary: dict[str, Any], metric_mode: str) -> None:
    columns = selected_metric_columns(metric_mode)
    risk = summary.get("risk_level", "N/A")
    risk_color = RISK_COLORS.get(risk, "#6B7280")

    col1, col2, col3, col4, col5 = st.columns([1.2, 1.2, 1, 1.2, 1])

    with col1:
        render_kpi_card(
            columns["total_label"],
            fmt_number(summary.get(columns["total"]), metric_mode),
            "Total included demand",
        )

    with col2:
        render_kpi_card(
            columns["covered_label"],
            fmt_number(summary.get(columns["covered"]), metric_mode),
            "Booked/Shipped plus Available",
        )

    with col3:
        render_kpi_card(
            "Coverage %",
            fmt_pct(summary.get(columns["coverage_pct"])),
            f"{metric_mode.lower()} basis",
        )

    with col4:
        render_kpi_card(
            columns["open_label"],
            fmt_number(summary.get(columns["open"]), metric_mode),
            "Remaining exposure",
        )

    with col5:
        st.markdown(
            f"""
            <div class="kpi-card">
              <div class="kpi-label">Risk Level</div>
              <div class="kpi-value">{status_badge(str(risk), risk_color)}</div>
              <div class="kpi-note">Based on value coverage</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def make_status_mix(summary: dict[str, Any], metric_mode: str) -> pd.DataFrame:
    columns = selected_metric_columns(metric_mode)
    return pd.DataFrame(
        [
            ("Booked/Shipped", summary.get(columns["booked"], 0)),
            ("Available", summary.get(columns["available"], 0)),
            ("Open Order", summary.get(columns["open"], 0)),
        ],
        columns=["Status", metric_label(metric_mode)],
    )


def render_coverage_overview(
    report_data: dict[str, Any],
    metric_mode: str,
    key_prefix: str,
) -> None:
    summary = report_data["executive_summary"]
    coverage_summary = pd.DataFrame(report_data["coverage_summary"])
    columns = selected_metric_columns(metric_mode)
    metric_name = metric_label(metric_mode)

    st.subheader("Coverage Overview")

    col1, col2 = st.columns(2)
    with col1:
        mix_df = make_status_mix(summary, metric_mode)
        fig = px.bar(
            mix_df,
            x="Status",
            y=metric_name,
            color="Status",
            color_discrete_map=STATUS_COLORS,
            text=metric_name,
            title="Coverage Mix by Status",
        )
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig.update_layout(showlegend=False, yaxis_title=metric_name, xaxis_title="")
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"{key_prefix}_coverage_mix_{metric_prefix(metric_mode)}",
        )

    with col2:
        if coverage_summary.empty:
            st.info("No coverage summary available.")
        else:
            season_df = (
                coverage_summary.groupby("season", as_index=False)
                .agg(
                    coverage_pct=(columns["coverage_pct"], "mean"),
                    open_exposure=(columns["open"], "sum"),
                )
            )
            fig = px.bar(
                season_df,
                x="season",
                y="coverage_pct",
                color="season",
                title=f"Coverage % by Season ({metric_name})",
                text="coverage_pct",
            )
            fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
            fig.update_layout(
                showlegend=False,
                yaxis_tickformat=".0%",
                yaxis_title="Coverage %",
                xaxis_title="Season",
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"{key_prefix}_coverage_by_season_{metric_prefix(metric_mode)}",
            )

    col3, col4 = st.columns(2)
    with col3:
        if coverage_summary.empty:
            st.info("No season exposure available.")
        else:
            exposure_df = (
                coverage_summary.groupby("season", as_index=False)
                .agg(open_exposure=(columns["open"], "sum"))
            )
            fig = px.bar(
                exposure_df,
                x="season",
                y="open_exposure",
                color="season",
                title=f"Open Order Exposure by Season ({metric_name})",
                text="open_exposure",
            )
            fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
            fig.update_layout(showlegend=False, yaxis_title=metric_name, xaxis_title="Season")
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"{key_prefix}_open_exposure_by_season_{metric_prefix(metric_mode)}",
            )

    with col4:
        if coverage_summary.empty:
            st.info("No monthly trend available.")
        else:
            month_df = (
                coverage_summary.groupby("requested_month", as_index=False)
                .agg(coverage_pct=(columns["coverage_pct"], "mean"))
                .sort_values("requested_month")
            )
            fig = px.line(
                month_df,
                x="requested_month",
                y="coverage_pct",
                markers=True,
                title=f"Monthly Coverage Trend ({metric_name})",
            )
            fig.update_layout(
                yaxis_tickformat=".0%",
                yaxis_title="Coverage %",
                xaxis_title="Requested Month",
            )
            st.plotly_chart(
                fig,
                use_container_width=True,
                key=f"{key_prefix}_monthly_trend_{metric_prefix(metric_mode)}",
            )


def render_timing_risk(
    report_data: dict[str, Any],
    metric_mode: str,
    key_prefix: str,
) -> None:
    timing = pd.DataFrame(report_data["timing_risk"])
    metric = metric_prefix(metric_mode)
    metric_name = metric_label(metric_mode)

    st.subheader("Timing Risk")

    if timing.empty:
        st.info("No open order timing risk found for the selected filters.")
        return

    bucket_columns = [
        ("Early/On Time", f"early_on_time_{metric}"),
        ("+1 week", f"plus_1_week_{metric}"),
        ("+2 weeks", f"plus_2_weeks_{metric}"),
        ("+3 weeks", f"plus_3_weeks_{metric}"),
        ("+4 weeks or later", f"plus_4_weeks_or_later_{metric}"),
    ]

    bucket_df = pd.DataFrame(
        [
            {"Timing Bucket": label, metric_name: timing.get(column, pd.Series(dtype=float)).sum()}
            for label, column in bucket_columns
        ]
    )

    col1, col2 = st.columns(2)

    with col1:
        fig = px.bar(
            bucket_df,
            x="Timing Bucket",
            y=metric_name,
            color="Timing Bucket",
            color_discrete_map=STATUS_COLORS,
            text=metric_name,
            title=f"Open Order Timing Bucket Exposure ({metric_name})",
        )
        fig.update_traces(texttemplate="%{text:,.0f}", textposition="outside")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title=metric_name)
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"{key_prefix}_timing_bucket_{metric}",
        )

    with col2:
        heatmap_df = timing.copy()
        heatmap_df["Period"] = (
            heatmap_df["season"].astype(str)
            + " | "
            + heatmap_df["requested_month"].astype(str)
        )
        heatmap_df["Late Exposure %"] = heatmap_df[f"late_open_order_{metric}_percentage"]
        fig = px.bar(
            heatmap_df,
            x="Period",
            y="Late Exposure %",
            color="season",
            text="Late Exposure %",
            title=f"Timing Risk by Season and Requested Month ({metric_name})",
        )
        fig.update_traces(texttemplate="%{text:.1%}", textposition="outside")
        fig.update_layout(
            yaxis_tickformat=".0%",
            xaxis_title="Season / Requested Month",
            yaxis_title="Late Open Order %",
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"{key_prefix}_timing_by_period_{metric}",
        )


def build_summary_table(report_data: dict[str, Any], metric_mode: str) -> pd.DataFrame:
    coverage_summary = pd.DataFrame(report_data["coverage_summary"])
    columns = selected_metric_columns(metric_mode)

    if coverage_summary.empty:
        return pd.DataFrame()

    output = coverage_summary[
        [
            "season",
            "requested_month",
            columns["total"],
            columns["booked"],
            columns["available"],
            columns["open"],
            columns["covered"],
            columns["coverage_pct"],
            columns["open_pct"],
            "risk_level",
        ]
    ].copy()

    output = output.rename(
        columns={
            "season": "Season",
            "requested_month": "Requested Month",
            columns["total"]: columns["total_label"],
            columns["booked"]: columns["booked_label"],
            columns["available"]: columns["available_label"],
            columns["open"]: columns["open_label"],
            columns["covered"]: columns["covered_label"],
            columns["coverage_pct"]: "Coverage %",
            columns["open_pct"]: "Open Order %",
            "risk_level": "Risk Level",
        }
    )

    return output.sort_values(["Season", "Requested Month"])


def render_summary_table(
    report_data: dict[str, Any],
    metric_mode: str,
    key_prefix: str,
) -> None:
    st.subheader("Coverage Summary")
    summary_table = build_summary_table(report_data, metric_mode)

    if summary_table.empty:
        st.info("No summary rows available.")
        return

    display_table = summary_table.copy()
    display_table["Coverage %"] = display_table["Coverage %"] * 100
    display_table["Open Order %"] = display_table["Open Order %"] * 100

    st.dataframe(
        display_table,
        use_container_width=True,
        hide_index=True,
        key=f"{key_prefix}_coverage_summary_table_{metric_prefix(metric_mode)}",
        column_config={
            "Coverage %": st.column_config.ProgressColumn(
                "Coverage %",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
            "Open Order %": st.column_config.ProgressColumn(
                "Open Order %",
                format="%.1f%%",
                min_value=0,
                max_value=100,
            ),
        },
    )


def render_observations(observations: list[str], observation_error: str | None) -> None:
    st.subheader("Agent Observations")

    if observation_error:
        st.warning(
            "OpenAI observations were unavailable, so deterministic fallback observations are shown."
        )

    if not observations:
        st.info("No observations available for the current selection.")
        return

    for observation in observations:
        st.markdown(
            f'<div class="observation-card">{observation}</div>',
            unsafe_allow_html=True,
        )


def render_validation(validation: dict[str, Any], key_prefix: str) -> None:
    st.subheader("Validation")
    passed = bool(validation.get("passes_reconciliation"))
    badge = status_badge("PASS" if passed else "FAIL", "#16A34A" if passed else "#DC2626")
    st.markdown(badge, unsafe_allow_html=True)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Source rows", fmt_number(validation.get("source_rows")))
    col2.metric("Included rows", fmt_number(validation.get("included_rows")))
    col3.metric("Value difference", fmt_number(validation.get("value_difference"), "Value"))
    col4.metric("Volume difference", fmt_number(validation.get("volume_difference"), "Volume"))

    validation_rows = [
        ("Source total value", fmt_number(validation.get("source_total_value"), "Value")),
        ("Report total value", fmt_number(validation.get("report_total_value"), "Value")),
        ("Source total volume", fmt_number(validation.get("source_total_volume"), "Volume")),
        ("Report total volume", fmt_number(validation.get("report_total_volume"), "Volume")),
        ("Unexpected statuses", ", ".join(validation.get("unexpected_statuses", [])) or "None"),
        ("Missing required values", str(validation.get("missing_required_values", {}))),
    ]
    st.dataframe(
        pd.DataFrame(validation_rows, columns=["Check", "Result"]),
        use_container_width=True,
        hide_index=True,
        key=f"{key_prefix}_validation_table",
    )


def render_reporting_rules(rules: list[dict[str, Any]], rules_error: str | None) -> None:
    with st.expander("Reporting rules used by agent", expanded=False):
        if rules_error:
            st.warning(f"RAG rules could not be retrieved: {rules_error}")

        if not rules:
            st.info("No reporting rules available.")
            return

        for rule in rules:
            st.markdown(f"**{rule.get('title', 'Rule')}**")
            st.caption(
                f"{rule.get('source', 'unknown source')} | score={rule.get('score')}"
            )
            st.write(rule.get("text", ""))


def render_sidebar(records: list[dict[str, Any]]) -> tuple[str, dict[str, list[str]]]:
    filter_options = build_filter_options(records_to_filter_dataframe(records))

    st.sidebar.header("Report Controls")
    metric_mode = st.sidebar.radio(
        "Metric view",
        options=["Value", "Volume"],
        horizontal=True,
    )

    selected_filters: dict[str, list[str]] = {}
    for column in FILTER_COLUMNS:
        options = filter_options.get(column, [])
        selected_filters[column] = st.sidebar.multiselect(
            column.replace("_", " ").title(),
            options=options,
            default=[],
        )

    return metric_mode, selected_filters


def main() -> None:
    inject_css()

    if "refresh_token" not in st.session_state:
        st.session_state.refresh_token = 0

    if st.sidebar.button("Refresh data", use_container_width=True):
        st.cache_data.clear()
        st.session_state.refresh_token += 1

    try:
        records = cached_load_records(st.session_state.refresh_token)
    except Exception as exc:
        render_header("Value")
        st.error(f"Could not load orderbook data from Supabase: {exc}")
        st.stop()

    if not records:
        render_header("Value")
        st.warning("Supabase returned no orderbook records.")
        st.stop()

    metric_mode, selected_filters = render_sidebar(records)
    payload = build_dashboard_payload(records, selected_filters)

    render_header(metric_mode)

    if payload["dataframe"].empty or not payload["report_data"]:
        st.warning("No records match the selected filters. Clear filters or refresh data.")
        st.stop()

    report_data = payload["report_data"]
    summary = report_data["executive_summary"]

    tabs = st.tabs(
        [
            "Dashboard",
            "Coverage Summary",
            "Timing Risk",
            "Raw Coverage Data",
            "Validation",
            "RAG Rules",
        ]
    )

    with tabs[0]:
        render_kpis(summary, metric_mode)
        st.divider()
        render_coverage_overview(report_data, metric_mode, key_prefix="dashboard")
        st.divider()
        render_timing_risk(report_data, metric_mode, key_prefix="dashboard")
        st.divider()
        render_summary_table(report_data, metric_mode, key_prefix="dashboard")
        st.divider()
        render_observations(payload["observations"], payload["observation_error"])
        st.divider()
        render_validation(report_data["validation"], key_prefix="dashboard")
        render_reporting_rules(payload["reporting_rules"], payload["rules_error"])

    with tabs[1]:
        render_summary_table(report_data, metric_mode, key_prefix="summary_tab")
        st.dataframe(
            pd.DataFrame(report_data["coverage_summary"]),
            use_container_width=True,
            hide_index=True,
            key="summary_tab_raw_coverage_summary",
        )

    with tabs[2]:
        render_timing_risk(report_data, metric_mode, key_prefix="timing_tab")
        st.dataframe(
            pd.DataFrame(report_data["timing_risk"]),
            use_container_width=True,
            hide_index=True,
            key="timing_tab_raw_timing_risk",
        )

    with tabs[3]:
        st.dataframe(
            pd.DataFrame(report_data["coverage_by_season"]),
            use_container_width=True,
            hide_index=True,
            key="raw_coverage_data_table",
        )

    with tabs[4]:
        render_validation(report_data["validation"], key_prefix="validation_tab")

    with tabs[5]:
        render_reporting_rules(payload["reporting_rules"], payload["rules_error"])


if __name__ == "__main__":
    main()
