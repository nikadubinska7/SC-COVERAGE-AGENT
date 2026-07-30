import importlib.util
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUNNER_PATH = PROJECT_ROOT / "scripts" / "run_report_for_n8n.py"
WORKFLOW_PATH = PROJECT_ROOT / "workflows" / "sc_coverage_report_gmail_workflow.json"


def load_runner_module():
    spec = importlib.util.spec_from_file_location("run_report_for_n8n", RUNNER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_n8n_success_payload_contains_dashboard_email_content():
    runner = load_runner_module()

    report_data = {
        "executive_summary": {
            "source_rows": 2,
            "included_rows": 2,
            "total_value": 1500,
            "covered_value": 1000,
            "open_order_value": 500,
            "value_coverage_percentage": 0.6667,
            "total_volume": 150,
            "covered_volume": 100,
            "open_order_volume": 50,
            "volume_coverage_percentage": 0.6667,
            "risk_level": "Medium",
        },
        "validation": {
            "passes_reconciliation": True,
            "value_difference": 0,
            "volume_difference": 0,
            "unexpected_statuses": [],
            "missing_required_values": {},
        },
    }

    payload = runner.build_success_payload(
        banner="Snipes",
        seasons=["HO2026", "SP2027"],
        requested_months=None,
        order_type="Standard Order - Futures",
        dashboard_url="https://example.streamlit.app",
        records_count=2,
        filtered_records_count=2,
        report_data=report_data,
        observations=["Coverage is stable."],
        rag_rules=[],
        recipient_name="Nika",
    )

    assert payload["status"] == "success"
    assert payload["validation_passed"] is True
    assert payload["dashboard_url"] == "https://example.streamlit.app"
    assert "https://example.streamlit.app" in payload["email_body"]
    assert "Coverage is stable." in payload["email_body"]


def test_n8n_workflow_has_required_nodes():
    workflow = json.loads(WORKFLOW_PATH.read_text(encoding="utf-8"))
    node_names = {node["name"] for node in workflow["nodes"]}

    assert "Manual Trigger" in node_names
    assert "Weekly Schedule" in node_names
    assert "Run Report Agent" in node_names
    assert "Parse Report JSON" in node_names
    assert "Report Successful?" in node_names
    assert "Send Gmail - Report Ready" in node_names
    assert "Send Gmail - Failure" in node_names
