from __future__ import annotations

import argparse
import contextlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BANNER = "Snipes"
DEFAULT_SEASONS = ["HO2026", "SP2027"]
DEFAULT_ORDER_TYPE = "Standard Order - Futures"
DEFAULT_DASHBOARD_URL = "http://localhost:8501"


def load_environment() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except Exception:
        # The project may already load environment variables elsewhere.
        # Do not fail the N8N runner only because python-dotenv is unavailable.
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the SC Coverage Report Agent and emit clean JSON for N8N."
    )

    parser.add_argument(
        "--banner",
        default=DEFAULT_BANNER,
        help="Retail banner/account to report on.",
    )

    parser.add_argument(
        "--seasons",
        nargs="+",
        default=DEFAULT_SEASONS,
        help="One or more seasons to include.",
    )

    parser.add_argument(
        "--requested-months",
        nargs="*",
        default=None,
        help="Optional requested months to include, for example 202610 202611.",
    )

    parser.add_argument(
        "--order-type",
        default=DEFAULT_ORDER_TYPE,
        help="Order type to include.",
    )

    parser.add_argument(
        "--dashboard-url",
        default=os.getenv("STREAMLIT_DASHBOARD_URL", DEFAULT_DASHBOARD_URL),
        help="Dashboard URL to include in the N8N/Gmail notification.",
    )

    parser.add_argument(
        "--recipient-name",
        default="",
        help="Optional recipient name for the email body.",
    )

    parser.add_argument(
        "--skip-ai-observations",
        action="store_true",
        help="Use deterministic fallback observations instead of calling the OpenAI agent.",
    )

    parser.add_argument(
        "--skip-rag-rules",
        action="store_true",
        help="Skip Pinecone reporting-rule retrieval.",
    )

    parser.add_argument(
        "--strict-exit",
        action="store_true",
        help="Exit with code 1 when report generation fails. Default is JSON-only failure with exit code 0.",
    )

    return parser.parse_args()


def fmt_number(value: float | int | None) -> str:
    if value is None:
        return "0"
    return f"{float(value):,.0f}"


def fmt_currency(value: float | int | None) -> str:
    if value is None:
        return "$0"
    return f"${float(value):,.0f}"


def fmt_pct(value: float | int | None) -> str:
    if value is None:
        return "0.0%"
    return f"{float(value):.1%}"


def filter_records_by_requested_months(
    records: list[dict[str, Any]],
    requested_months: list[str] | None,
) -> list[dict[str, Any]]:
    if not requested_months:
        return records

    requested_month_set = {str(month).strip() for month in requested_months}

    return [
        record
        for record in records
        if str(record.get("requested_month", "")).strip() in requested_month_set
    ]


def query_orderbook_records(
    banner: str,
    seasons: list[str],
    order_type: str,
) -> list[dict[str, Any]]:
    from src.tools.supabase_tool import query_orderbook

    try:
        return query_orderbook(
            banner=banner,
            seasons=seasons,
            order_type=order_type,
        )
    except TypeError:
        # Fallback for older positional function signatures.
        return query_orderbook(banner, seasons, order_type)


def retrieve_rag_rules() -> list[dict[str, Any]]:
    from src.tools.pinecone_tool import retrieve_reporting_rules

    query_text = (
        "Supply chain coverage reporting rules, timing risk buckets, "
        "coverage validation, value and volume metrics."
    )

    try:
        results = retrieve_reporting_rules()
    except TypeError:
        results = retrieve_reporting_rules(query_text)

    if results is None:
        return []

    normalized: list[dict[str, Any]] = []

    for item in results:
        if isinstance(item, dict):
            normalized.append(
                {
                    "title": item.get("title")
                    or item.get("source")
                    or item.get("document")
                    or "reporting_rule",
                    "source": item.get("source") or item.get("path") or "",
                    "score": item.get("score"),
                    "content": item.get("content")
                    or item.get("text")
                    or item.get("page_content")
                    or "",
                }
            )
        else:
            normalized.append(
                {
                    "title": "reporting_rule",
                    "source": "",
                    "score": None,
                    "content": str(item),
                }
            )

    return normalized


def generate_observations(report_data: dict[str, Any]) -> list[str]:
    try:
        from src.agent import run_react_analysis

        observations = run_react_analysis(report_data)

        if isinstance(observations, list):
            return [str(item).strip() for item in observations if str(item).strip()]

        if isinstance(observations, str):
            return [
                line.strip("-• ").strip()
                for line in observations.splitlines()
                if line.strip()
            ]

    except Exception as exc:
        return build_fallback_observations(report_data, error=str(exc))

    return build_fallback_observations(report_data)


def build_fallback_observations(
    report_data: dict[str, Any],
    error: str | None = None,
) -> list[str]:
    summary = report_data.get("executive_summary", {})
    validation = report_data.get("validation", {})

    observations = [
        (
            f"Coverage is {fmt_pct(summary.get('value_coverage_percentage'))} by value "
            f"and {fmt_pct(summary.get('volume_coverage_percentage'))} by volume."
        ),
        (
            f"Open order exposure is {fmt_currency(summary.get('open_order_value'))} "
            f"and {fmt_number(summary.get('open_order_volume'))} units."
        ),
        (
            f"Risk level is {summary.get('risk_level', 'N/A')} based on current "
            "coverage percentage."
        ),
        (
            "Validation passed."
            if validation.get("passes_reconciliation")
            else "Validation failed and requires review."
        ),
    ]

    if error:
        observations.append(
            f"OpenAI/ReAct observation generation was unavailable, so fallback observations were used. Error: {error}"
        )

    return observations


def build_email_subject(
    banner: str,
    seasons: list[str],
    risk_level: str,
) -> str:
    season_text = ", ".join(seasons)
    return f"SC Coverage Report Ready — {banner} — {season_text} — Risk: {risk_level}"


def build_email_body(
    recipient_name: str,
    dashboard_url: str,
    banner: str,
    seasons: list[str],
    order_type: str,
    report_data: dict[str, Any],
    observations: list[str],
) -> str:
    summary = report_data.get("executive_summary", {})
    validation = report_data.get("validation", {})

    greeting = f"Hi {recipient_name}," if recipient_name else "Hi,"

    observation_lines = "\n".join(
        [f"- {observation}" for observation in observations[:5]]
    )

    validation_text = (
        "PASS" if validation.get("passes_reconciliation") else "FAIL"
    )

    return f"""{greeting}

The SC Coverage Report is ready.

Dashboard:
{dashboard_url}

Report scope:
- Banner: {banner}
- Seasons: {", ".join(seasons)}
- Order type: {order_type}

Executive summary:
- Total value: {fmt_currency(summary.get("total_value"))}
- Covered value: {fmt_currency(summary.get("covered_value"))}
- Value coverage: {fmt_pct(summary.get("value_coverage_percentage"))}
- Open order value: {fmt_currency(summary.get("open_order_value"))}
- Total volume: {fmt_number(summary.get("total_volume"))}
- Covered volume: {fmt_number(summary.get("covered_volume"))}
- Volume coverage: {fmt_pct(summary.get("volume_coverage_percentage"))}
- Open order volume: {fmt_number(summary.get("open_order_volume"))}
- Risk level: {summary.get("risk_level", "N/A")}
- Validation: {validation_text}

Agent observations:
{observation_lines}

This message was generated automatically by the SC Coverage Report Agent.
"""


def build_success_payload(
    banner: str,
    seasons: list[str],
    requested_months: list[str] | None,
    order_type: str,
    dashboard_url: str,
    records_count: int,
    filtered_records_count: int,
    report_data: dict[str, Any],
    observations: list[str],
    rag_rules: list[dict[str, Any]],
    recipient_name: str,
) -> dict[str, Any]:
    summary = report_data.get("executive_summary", {})
    validation = report_data.get("validation", {})

    email_subject = build_email_subject(
        banner=banner,
        seasons=seasons,
        risk_level=str(summary.get("risk_level", "N/A")),
    )

    email_body = build_email_body(
        recipient_name=recipient_name,
        dashboard_url=dashboard_url,
        banner=banner,
        seasons=seasons,
        order_type=order_type,
        report_data=report_data,
        observations=observations,
    )

    return {
        "status": "success",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_url": dashboard_url,
        "banner": banner,
        "seasons": seasons,
        "requested_months": requested_months or [],
        "order_type": order_type,
        "records_count": records_count,
        "filtered_records_count": filtered_records_count,
        "source_rows": summary.get("source_rows"),
        "included_rows": summary.get("included_rows"),
        "total_value": summary.get("total_value"),
        "booked_shipped_value": summary.get("booked_shipped_value"),
        "available_value": summary.get("available_value"),
        "open_order_value": summary.get("open_order_value"),
        "covered_value": summary.get("covered_value"),
        "value_coverage_percentage": summary.get("value_coverage_percentage"),
        "total_volume": summary.get("total_volume"),
        "booked_shipped_volume": summary.get("booked_shipped_volume"),
        "available_volume": summary.get("available_volume"),
        "open_order_volume": summary.get("open_order_volume"),
        "covered_volume": summary.get("covered_volume"),
        "volume_coverage_percentage": summary.get("volume_coverage_percentage"),
        "risk_level": summary.get("risk_level"),
        "validation_passed": validation.get("passes_reconciliation"),
        "value_difference": validation.get("value_difference"),
        "volume_difference": validation.get("volume_difference"),
        "unexpected_statuses": validation.get("unexpected_statuses", []),
        "missing_required_values": validation.get("missing_required_values", {}),
        "observations": observations,
        "rag_rules_used": rag_rules[:5],
        "email_subject": email_subject,
        "email_body": email_body,
    }


def build_failure_payload(
    error: str,
    banner: str,
    seasons: list[str],
    requested_months: list[str] | None,
    order_type: str,
    dashboard_url: str,
) -> dict[str, Any]:
    return {
        "status": "failed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_url": dashboard_url,
        "banner": banner,
        "seasons": seasons,
        "requested_months": requested_months or [],
        "order_type": order_type,
        "error": error,
        "email_subject": f"SC Coverage Report Failed — {banner}",
        "email_body": (
            "The SC Coverage Report workflow failed.\n\n"
            f"Error:\n{error}\n\n"
            "Please review the N8N execution log and Python report runner output."
        ),
    }


def run_report(args: argparse.Namespace) -> dict[str, Any]:
    from src.services.transformations import build_coverage_report

    records = query_orderbook_records(
        banner=args.banner,
        seasons=args.seasons,
        order_type=args.order_type,
    )

    records_count = len(records)

    filtered_records = filter_records_by_requested_months(
        records=records,
        requested_months=args.requested_months,
    )

    filtered_records_count = len(filtered_records)

    if filtered_records_count == 0:
        raise ValueError(
            "No orderbook records found for the selected report scope."
        )

    report_data = build_coverage_report(filtered_records)
    observations = (
        build_fallback_observations(report_data)
        if getattr(args, "skip_ai_observations", False)
        else generate_observations(report_data)
    )
    rag_rules = (
        []
        if getattr(args, "skip_rag_rules", False)
        else retrieve_rag_rules()
    )

    return build_success_payload(
        banner=args.banner,
        seasons=args.seasons,
        requested_months=args.requested_months,
        order_type=args.order_type,
        dashboard_url=args.dashboard_url,
        records_count=records_count,
        filtered_records_count=filtered_records_count,
        report_data=report_data,
        observations=observations,
        rag_rules=rag_rules,
        recipient_name=args.recipient_name,
    )


def main() -> int:
    load_environment()
    args = parse_args()

    try:
        # Keep stdout clean for N8N JSON parsing.
        # Any noisy prints from internal tools go to stderr.
        with contextlib.redirect_stdout(sys.stderr):
            payload = run_report(args)

        print(json.dumps(payload, ensure_ascii=False))
        return 0

    except Exception as exc:
        payload = build_failure_payload(
            error=str(exc),
            banner=args.banner,
            seasons=args.seasons,
            requested_months=args.requested_months,
            order_type=args.order_type,
            dashboard_url=args.dashboard_url,
        )

        print(json.dumps(payload, ensure_ascii=False))

        if args.strict_exit:
            return 1

        return 0


if __name__ == "__main__":
    raise SystemExit(main())
