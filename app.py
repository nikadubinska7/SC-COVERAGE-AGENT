from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
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
    "Booked/Shipped": "#4C8F35",
    "Available": "#069DC3",
    "Open Order": "#E34A2C",
    "Early/On Time": "#4C8F35",
    "+1 week": "#C59A32",
    "+2 weeks": "#D97706",
    "+3 weeks": "#E34A2C",
    "+4 weeks or later": "#6D3A8B",
    "Unclassified Open Order": "#607080",
}

BRAND_COLORS = {
    "forest": "#315F37",
    "forest_2": "#2B6D2E",
    "sage": "#9FCB93",
    "sage_2": "#DCECCF",
    "navy": "#193B5C",
    "navy_2": "#0B5B7A",
    "blue": "#069DC3",
    "blue_2": "#8BD8EE",
    "teal": "#12A8A6",
    "green": "#4C8F35",
    "green_2": "#A7E44B",
    "gold": "#C59A32",
    "orange": "#E67E00",
    "red": "#B6172E",
    "plum": "#6D3A8B",
    "ink": "#172033",
    "muted": "#657285",
    "panel": "#FFFFFF",
    "line": "#E1E6DD",
}

RISK_COLORS = {
    "Low": "#4C8F35",
    "Medium": "#C59A32",
    "High": "#B6172E",
}

SEASON_COLOR_SCALE = [
    [0.0, "#C7F2FF"],
    [0.35, "#22C7E8"],
    [0.7, "#069DC3"],
    [1.0, "#193B5C"],
]

EXPOSURE_COLOR_SCALE = [
    [0.0, "#FFE0B8"],
    [0.4, "#F59E0B"],
    [0.75, "#E34A2C"],
    [1.0, "#6D3A8B"],
]

CUBE_PALETTE = [
    "#069DC3",
    "#8A36C8",
    "#E34A2C",
    "#4C8F35",
    "#C59A32",
    "#0B5B7A",
]


def inject_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                linear-gradient(135deg, rgba(76,143,53,0.16) 0%, rgba(255,255,255,0.42) 34%, rgba(6,157,195,0.10) 68%, rgba(230,126,0,0.10) 100%),
                repeating-linear-gradient(135deg, rgba(49,95,55,0.040) 0 1px, transparent 1px 34px),
                #f3f5ef;
            color: #172033;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #ffffff 0%, #f7faf3 100%);
            border-right: 1px solid #dfe8d7;
        }
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3 {
            color: #315f37;
        }
        .block-container {
            padding-top: 1.1rem;
            padding-bottom: 2.5rem;
            max-width: 1440px;
        }
        .hero {
            background: linear-gradient(180deg, #4f8f3f 0%, #315f37 48%, #214627 100%);
            color: #ffffff;
            padding: 16px 22px 18px;
            border-radius: 8px;
            margin-bottom: 18px;
            box-shadow:
                0 18px 34px rgba(49,95,55,0.18),
                inset 0 1px 0 rgba(255,255,255,0.30);
            border: 1px solid rgba(255,255,255,0.16);
            position: relative;
            overflow: hidden;
        }
        .hero:before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                linear-gradient(120deg, rgba(255,255,255,0.18), rgba(255,255,255,0) 42%),
                repeating-linear-gradient(90deg, rgba(255,255,255,0.05) 0 1px, transparent 1px 78px);
            pointer-events: none;
        }
        .hero-inner {
            position: relative;
            z-index: 1;
        }
        .hero-kicker {
            color: #f4e3a5;
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0;
            margin-bottom: 5px;
        }
        .hero-title {
            font-size: 30px;
            font-weight: 800;
            margin-bottom: 4px;
            letter-spacing: 0;
        }
        .hero-subtitle {
            font-size: 15px;
            color: #eef6ea;
            margin-bottom: 12px;
        }
        .hero-meta {
            display: flex;
            gap: 12px;
            flex-wrap: wrap;
            font-size: 13px;
            color: #f7faf3;
        }
        .meta-pill {
            background: rgba(255,255,255,0.16);
            border: 1px solid rgba(255,255,255,0.25);
            border-radius: 6px;
            padding: 6px 10px;
        }
        .kpi-card {
            background:
                linear-gradient(180deg, rgba(255,255,255,0.98) 0%, rgba(246,248,242,0.98) 100%);
            border: 1px solid #dfe8d7;
            border-radius: 8px;
            padding: 15px 15px 13px;
            min-height: 118px;
            box-shadow:
                0 14px 24px rgba(49,95,55,0.10),
                inset 0 1px 0 rgba(255,255,255,0.92);
            position: relative;
            overflow: hidden;
        }
        .kpi-card:before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 7px;
            background: linear-gradient(180deg, #5f8e57 0%, #315f37 100%);
        }
        .kpi-rose {
            background: linear-gradient(180deg, #fff6f7 0%, #f3cad1 100%);
        }
        .kpi-rose:before {
            background: linear-gradient(180deg, #d02a42 0%, #9e1730 100%);
        }
        .kpi-amber {
            background: linear-gradient(180deg, #fff5e4 0%, #f1dfc9 100%);
        }
        .kpi-amber:before {
            background: linear-gradient(180deg, #d7a94c 0%, #9b6d23 100%);
        }
        .kpi-lavender {
            background: linear-gradient(180deg, #f7f1ff 0%, #dbcfeb 100%);
        }
        .kpi-lavender:before {
            background: linear-gradient(180deg, #7b4fa0 0%, #4b2c69 100%);
        }
        .kpi-blue {
            background: linear-gradient(180deg, #effaff 0%, #cce4f3 100%);
        }
        .kpi-blue:before {
            background: linear-gradient(180deg, #0b7da7 0%, #064a6b 100%);
        }
        .kpi-sage {
            background: linear-gradient(180deg, #f4ffe9 0%, #d8edc5 100%);
        }
        .kpi-sage:before {
            background: linear-gradient(180deg, #6c9f43 0%, #315f37 100%);
        }
        .kpi-label {
            color: #738094;
            font-size: 12px;
            font-weight: 800;
            text-transform: uppercase;
            letter-spacing: 0;
            margin-bottom: 8px;
        }
        .kpi-value {
            color: #223047;
            font-size: 27px;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 8px;
            overflow-wrap: anywhere;
        }
        .kpi-note {
            color: #738094;
            font-size: 13px;
            line-height: 1.35;
        }
        .badge {
            display: inline-block;
            border-radius: 6px;
            color: #ffffff;
            font-size: 13px;
            font-weight: 800;
            padding: 6px 12px;
        }
        .panel-heading {
            background: linear-gradient(180deg, #4f8f3f 0%, #315f37 52%, #214627 100%);
            color: #ffffff;
            border-radius: 8px 8px 0 0;
            padding: 9px 13px;
            font-size: 14px;
            font-weight: 800;
            margin-top: 8px;
            border: 1px solid #4f7f4f;
            border-bottom: 0;
            box-shadow: 0 10px 18px rgba(49,95,55,0.12);
        }
        .panel-caption {
            background: linear-gradient(180deg, #ffffff 0%, #f7faf3 100%);
            border: 1px solid #dfe8d7;
            border-top: 0;
            color: #738094;
            padding: 0 13px 10px;
            margin-bottom: 4px;
            font-size: 12px;
        }
        .section-card {
            background: #ffffff;
            border: 1px solid #dfe8d7;
            border-radius: 8px;
            padding: 18px;
            margin-bottom: 16px;
            box-shadow: 0 10px 22px rgba(49,95,55,0.06);
        }
        .observation-card {
            background: linear-gradient(180deg, #ffffff 0%, #f7faf3 100%);
            border-left: 5px solid #76aec4;
            border-radius: 8px;
            padding: 13px 15px;
            margin-bottom: 10px;
            color: #223047;
            box-shadow:
                0 10px 18px rgba(49,95,55,0.07),
                inset 0 1px 0 rgba(255,255,255,0.94);
        }
        div[data-testid="stMetric"] {
            background: linear-gradient(180deg, #ffffff 0%, #f7faf3 100%);
            border: 1px solid #dfe8d7;
            border-radius: 8px;
            padding: 14px;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 6px;
        }
        .stTabs [data-baseweb="tab"] {
            background: rgba(255,255,255,0.82);
            border: 1px solid #dfe8d7;
            border-radius: 7px 7px 0 0;
            padding: 8px 12px;
            color: #223047;
            font-weight: 700;
        }
        .stTabs [aria-selected="true"] {
            background: linear-gradient(180deg, #5f8e57 0%, #315f37 100%);
            color: #ffffff;
            border-color: #4f7f4f;
        }
        h2, h3 {
            color: #315f37;
            letter-spacing: 0;
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
        return f"${number:,.0f}"
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
    return f'<span class="badge" style="background:{color};">{escape(text)}</span>'


def panel_heading(title: str, caption: str | None = None) -> None:
    st.markdown(
        f'<div class="panel-heading">{escape(title)}</div>',
        unsafe_allow_html=True,
    )
    if caption:
        st.markdown(
            f'<div class="panel-caption">{escape(caption)}</div>',
            unsafe_allow_html=True,
        )


def style_plotly_chart(fig: go.Figure, height: int = 315) -> go.Figure:
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=28, r=18, t=38, b=40),
        paper_bgcolor="#FFFFFF",
        plot_bgcolor="#FBFCF7",
        font=dict(color=BRAND_COLORS["ink"], family="Arial, sans-serif", size=12),
        title=dict(font=dict(size=14, color=BRAND_COLORS["forest"]), x=0.02, xanchor="left"),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1,
            font=dict(size=11),
        ),
    )
    fig.update_xaxes(showgrid=False, linecolor=BRAND_COLORS["line"])
    fig.update_yaxes(gridcolor="#EEF1E8", linecolor=BRAND_COLORS["line"])
    return fig


def add_raised_bar_style(fig: go.Figure) -> go.Figure:
    fig.update_traces(
        marker_line_color="rgba(49, 95, 55, 0.24)",
        marker_line_width=0.9,
        opacity=0.88,
        selector={"type": "bar"},
    )
    return fig


def hex_to_rgb(color: str) -> tuple[int, int, int]:
    value = color.lstrip("#")
    return tuple(int(value[index : index + 2], 16) for index in (0, 2, 4))


def shade_hex(color: str, factor: float) -> str:
    red, green, blue = hex_to_rgb(color)
    return (
        f"#{max(0, min(255, int(red * factor))):02x}"
        f"{max(0, min(255, int(green * factor))):02x}"
        f"{max(0, min(255, int(blue * factor))):02x}"
    )


def make_3d_block_chart(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    title: str,
    y_title: str,
    text_format: str = "number",
    colors: list[str] | None = None,
    y_tickformat: str | None = None,
    height: int = 315,
) -> go.Figure:
    if df.empty:
        return go.Figure()

    values = [float(value or 0) for value in df[y_column].tolist()]
    labels = [str(value) for value in df[x_column].tolist()]
    max_value = max(values) if values else 0
    y_padding = max_value * 0.22 if max_value else 1
    y_max = max_value + y_padding
    dx = 0.11
    dy = y_max * 0.055
    bar_width = 0.58
    palette = colors or CUBE_PALETTE

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=list(range(len(labels))),
            y=[0 for _ in labels],
            mode="markers",
            marker=dict(opacity=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    for index, (label, value) in enumerate(zip(labels, values)):
        color = palette[index % len(palette)]
        left = index - bar_width / 2
        right = index + bar_width / 2
        top = value

        fig.add_shape(
            type="rect",
            x0=left,
            x1=right,
            y0=0,
            y1=top,
            fillcolor=color,
            line=dict(color=shade_hex(color, 0.72), width=1.0),
            layer="below",
        )
        fig.add_shape(
            type="path",
            path=(
                f"M {left},{top} "
                f"L {left + dx},{top + dy} "
                f"L {right + dx},{top + dy} "
                f"L {right},{top} Z"
            ),
            fillcolor=shade_hex(color, 1.28),
            line=dict(color=shade_hex(color, 0.82), width=0.8),
            layer="below",
        )
        fig.add_shape(
            type="path",
            path=(
                f"M {right},{0} "
                f"L {right + dx},{dy} "
                f"L {right + dx},{top + dy} "
                f"L {right},{top} Z"
            ),
            fillcolor=shade_hex(color, 0.70),
            line=dict(color=shade_hex(color, 0.60), width=0.8),
            layer="below",
        )

        if text_format == "percent":
            label_text = f"{value:.1%}" if value <= 1 else f"{value:.1f}%"
        else:
            label_text = f"{value:,.0f}"

        fig.add_annotation(
            x=index + dx / 2,
            y=top * 0.56 if top else y_max * 0.03,
            text=label_text,
            showarrow=False,
            font=dict(size=12, color="#111827", family="Arial, sans-serif"),
        )

    fig.update_layout(
        title=title,
        xaxis=dict(
            tickmode="array",
            tickvals=list(range(len(labels))),
            ticktext=labels,
            range=[-0.65, len(labels) - 0.25],
        ),
        yaxis=dict(range=[0, y_max], title=y_title, tickformat=y_tickformat),
        showlegend=False,
    )

    return style_plotly_chart(fig, height=height)


def make_gauge(
    title: str,
    value: float,
    color: str,
    suffix: str = "%",
) -> go.Figure:
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=max(0, min(value * 100, 100)),
            number={"suffix": suffix, "font": {"size": 28, "color": BRAND_COLORS["ink"]}},
            title={"text": title, "font": {"size": 14, "color": BRAND_COLORS["forest"]}},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 0, "tickcolor": "#FFFFFF"},
                "bar": {"color": color, "thickness": 0.24},
                "bgcolor": "#FBFCF7",
                "borderwidth": 1,
                "bordercolor": BRAND_COLORS["line"],
                "steps": [
                    {"range": [0, 50], "color": "#F8E7E2"},
                    {"range": [50, 75], "color": "#F7ECCC"},
                    {"range": [75, 100], "color": "#EAF4E3"},
                ],
            },
        )
    )
    return style_plotly_chart(fig, height=235)


def safe_ratio(numerator: Any, denominator: Any) -> float:
    denominator_value = float(denominator or 0)
    if denominator_value == 0:
        return 0.0
    return float(numerator or 0) / denominator_value


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
          <div class="hero-inner">
            <div class="hero-kicker">Supply Chain Management Dashboard</div>
            <div class="hero-title">SC Coverage Report</div>
            <div class="hero-subtitle">Snipes / Nike-Jordan order coverage, timing exposure, and reconciliation control</div>
            <div class="hero-meta">
              <span class="meta-pill">Last refresh: {escape(timestamp)}</span>
              <span class="meta-pill">Metric mode: {escape(metric_mode)}</span>
              <span class="meta-pill">Source: Supabase orderbook</span>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_card(
    label: str,
    value: str,
    note: str,
    tone: str = "sage",
) -> None:
    st.markdown(
        f"""
        <div class="kpi-card kpi-{escape(tone)}">
          <div class="kpi-label">{escape(label)}</div>
          <div class="kpi-value">{escape(value)}</div>
          <div class="kpi-note">{escape(note)}</div>
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
            "rose",
        )

    with col2:
        render_kpi_card(
            columns["covered_label"],
            fmt_number(summary.get(columns["covered"]), metric_mode),
            "Booked/Shipped plus Available",
            "amber",
        )

    with col3:
        render_kpi_card(
            "Coverage %",
            fmt_pct(summary.get(columns["coverage_pct"])),
            f"{metric_mode.lower()} basis",
            "lavender",
        )

    with col4:
        render_kpi_card(
            columns["open_label"],
            fmt_number(summary.get(columns["open"]), metric_mode),
            "Remaining exposure",
            "blue",
        )

    with col5:
        st.markdown(
            f"""
            <div class="kpi-card kpi-sage">
              <div class="kpi-label">Risk Level</div>
              <div class="kpi-value">{status_badge(str(risk), risk_color)}</div>
              <div class="kpi-note">Based on value coverage</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_scorecard(
    summary: dict[str, Any],
    metric_mode: str,
    key_prefix: str,
) -> None:
    columns = selected_metric_columns(metric_mode)
    metric_name = metric_label(metric_mode)
    coverage_pct = float(summary.get(columns["coverage_pct"], 0) or 0)
    open_pct = safe_ratio(summary.get(columns["open"]), summary.get(columns["total"]))
    mix_df = make_status_mix(summary, metric_mode)

    col1, col2, col3 = st.columns([1, 1, 1.25])

    with col1:
        fig = make_gauge(
            title=f"{metric_name} Coverage",
            value=coverage_pct,
            color=(
                BRAND_COLORS["green"]
                if coverage_pct >= 0.75
                else BRAND_COLORS["gold"]
            ),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"{key_prefix}_coverage_gauge_{metric_prefix(metric_mode)}",
        )

    with col2:
        fig = make_gauge(
            title=f"Open {metric_name}",
            value=open_pct,
            color=(
                BRAND_COLORS["plum"]
                if open_pct >= 0.25
                else BRAND_COLORS["orange"]
            ),
        )
        st.plotly_chart(
            fig,
            use_container_width=True,
            key=f"{key_prefix}_open_gauge_{metric_prefix(metric_mode)}",
        )

    with col3:
        fig = px.pie(
            mix_df,
            names="Status",
            values=metric_name,
            hole=0.58,
            color="Status",
            color_discrete_map=STATUS_COLORS,
            title=f"{metric_name} Mix",
        )
        fig.update_traces(
            textposition="inside",
            texttemplate="%{percent:.1%}",
            pull=[0.02, 0.02, 0.04],
            marker=dict(line=dict(color="#FFFFFF", width=2)),
        )
        fig.update_layout(showlegend=True)
        st.plotly_chart(
            style_plotly_chart(fig, height=235),
            use_container_width=True,
            key=f"{key_prefix}_mix_donut_{metric_prefix(metric_mode)}",
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

    panel_heading(
        "Coverage Overview",
        "Status mix, seasonal coverage, open exposure, and monthly coverage movement.",
    )

    col1, col2 = st.columns(2)
    with col1:
        mix_df = make_status_mix(summary, metric_mode)
        fig = make_3d_block_chart(
            mix_df,
            x_column="Status",
            y_column=metric_name,
            title="Coverage Mix by Status",
            y_title=metric_name,
            colors=[
                STATUS_COLORS["Booked/Shipped"],
                STATUS_COLORS["Available"],
                STATUS_COLORS["Open Order"],
            ],
        )
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
            fig = make_3d_block_chart(
                season_df,
                x_column="season",
                y_column="coverage_pct",
                title=f"Coverage % by Season ({metric_name})",
                y_title="Coverage %",
                text_format="percent",
                colors=[
                    BRAND_COLORS["green"],
                    BRAND_COLORS["blue"],
                    BRAND_COLORS["plum"],
                ],
                y_tickformat=".0%",
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
            fig = make_3d_block_chart(
                exposure_df,
                x_column="season",
                y_column="open_exposure",
                title=f"Open Order Exposure by Season ({metric_name})",
                y_title=metric_name,
                colors=[
                    BRAND_COLORS["red"],
                    BRAND_COLORS["orange"],
                    BRAND_COLORS["plum"],
                ],
            )
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
            fig.update_traces(
                line=dict(color=BRAND_COLORS["blue"], width=3),
                marker=dict(
                    color=BRAND_COLORS["green_2"],
                    size=9,
                    line=dict(color=BRAND_COLORS["navy"], width=1.2),
                ),
                fill="tozeroy",
                fillcolor="rgba(100, 177, 200, 0.18)",
            )
            fig.update_layout(
                yaxis_tickformat=".0%",
                yaxis_title="Coverage %",
                xaxis_title="Requested Month",
            )
            st.plotly_chart(
                style_plotly_chart(fig),
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

    panel_heading(
        "Timing Risk",
        "Open order exposure split by delivery timing buckets and requested month.",
    )

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
        fig = make_3d_block_chart(
            bucket_df,
            x_column="Timing Bucket",
            y_column=metric_name,
            title=f"Open Order Timing Bucket Exposure ({metric_name})",
            y_title=metric_name,
            colors=[
                STATUS_COLORS["Early/On Time"],
                STATUS_COLORS["+1 week"],
                STATUS_COLORS["+2 weeks"],
                STATUS_COLORS["+3 weeks"],
                STATUS_COLORS["+4 weeks or later"],
            ],
        )
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
        fig = make_3d_block_chart(
            heatmap_df,
            x_column="Period",
            y_column="Late Exposure %",
            title=f"Timing Risk by Season and Requested Month ({metric_name})",
            y_title="Late Open Order %",
            text_format="percent",
            colors=[
                BRAND_COLORS["green"],
                BRAND_COLORS["gold"],
                BRAND_COLORS["red"],
                BRAND_COLORS["plum"],
            ],
            y_tickformat=".0%",
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
    panel_heading(
        "Coverage Summary",
        "Detailed season and requested-month coverage by the selected metric view.",
    )
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
    panel_heading(
        "Agent Observations",
        "Business-readable interpretation of coverage, exposure, and validation status.",
    )

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
    panel_heading(
        "Validation",
        "Reconciliation checks between source rows and report output.",
    )
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
        render_scorecard(summary, metric_mode, key_prefix="dashboard")
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
