from __future__ import annotations

import argparse
import contextlib
import json
import sys
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_report_for_n8n import (  # noqa: E402
    DEFAULT_BANNER,
    DEFAULT_DASHBOARD_URL,
    DEFAULT_ORDER_TYPE,
    DEFAULT_SEASONS,
    build_failure_payload,
    load_environment,
    run_report,
)


def build_dashboard_link_payload(args: argparse.Namespace) -> dict[str, Any]:
    season_text = ", ".join(args.seasons)
    greeting = f"Hi {args.recipient_name}," if args.recipient_name else "Hi,"

    email_subject = f"SC Coverage Dashboard Ready - {args.banner} - {season_text}"
    email_body = f"""{greeting}

The SC Coverage dashboard is ready.

Dashboard:
{args.dashboard_url}

Report scope:
- Banner: {args.banner}
- Seasons: {season_text}
- Order type: {args.order_type}

Open the dashboard link to view the current report with season filters and value/volume views.

This message was generated automatically by the SC Coverage Report Agent.
"""

    return {
        "status": "success",
        "mode": "dashboard_link",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dashboard_url": args.dashboard_url,
        "banner": args.banner,
        "seasons": args.seasons,
        "requested_months": args.requested_months or [],
        "order_type": args.order_type,
        "email_subject": email_subject,
        "email_body": email_body,
    }


def _as_list(value: Any, default: list[str]) -> list[str]:
    if value is None:
        return default

    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    return default


def build_report_args(payload: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        banner=str(payload.get("banner") or DEFAULT_BANNER),
        seasons=_as_list(payload.get("seasons"), DEFAULT_SEASONS),
        requested_months=_as_list(payload.get("requested_months"), [])
        or None,
        order_type=str(payload.get("order_type") or DEFAULT_ORDER_TYPE),
        dashboard_url=str(payload.get("dashboard_url") or DEFAULT_DASHBOARD_URL),
        recipient_name=str(payload.get("recipient_name") or ""),
        skip_ai_observations=bool(payload.get("skip_ai_observations", True)),
        skip_rag_rules=bool(payload.get("skip_rag_rules", True)),
        strict_exit=False,
    )


class ReportRequestHandler(BaseHTTPRequestHandler):
    server_version = "SCCoverageReportAPI/1.0"

    def do_GET(self) -> None:
        if self.path == "/health":
            self._send_json({"status": "ok"})
            return

        self._send_json(
            {"status": "failed", "error": "Use POST /run-report."},
            status=HTTPStatus.NOT_FOUND,
        )

    def do_POST(self) -> None:
        if self.path != "/run-report":
            self._send_json(
                {"status": "failed", "error": "Unknown endpoint."},
                status=HTTPStatus.NOT_FOUND,
            )
            return

        payload = self._read_json_body()

        try:
            report_args = build_report_args(payload)

            if payload.get("generate_summary", False):
                with contextlib.redirect_stdout(sys.stderr):
                    result = run_report(report_args)
            else:
                result = build_dashboard_link_payload(report_args)

            self._send_json(result)

        except Exception as exc:
            report_args = build_report_args(payload)
            result = build_failure_payload(
                error=str(exc),
                banner=report_args.banner,
                seasons=report_args.seasons,
                requested_months=report_args.requested_months,
                order_type=report_args.order_type,
                dashboard_url=report_args.dashboard_url,
            )
            self._send_json(result, status=HTTPStatus.OK)

    def _read_json_body(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0") or "0")

        if content_length == 0:
            return {}

        raw_body = self.rfile.read(content_length)

        try:
            data = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON request body: {exc}") from exc

        if not isinstance(data, dict):
            raise ValueError("JSON request body must be an object.")

        return data

    def _send_json(
        self,
        payload: dict[str, Any],
        status: HTTPStatus = HTTPStatus.OK,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(
            "%s - - [%s] %s\n"
            % (self.address_string(), self.log_date_time_string(), format % args)
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Serve the SC Coverage Report runner over local HTTP for n8n."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    return parser.parse_args()


def main() -> int:
    load_environment()
    args = parse_args()
    server = ThreadingHTTPServer((args.host, args.port), ReportRequestHandler)

    print(f"SC Coverage Report API listening on http://{args.host}:{args.port}")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping SC Coverage Report API.")
    finally:
        server.server_close()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
