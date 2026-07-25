from __future__ import annotations

from langgraph.graph import END, StateGraph

from src.agent import run_react_analysis
from src.services.report_builder import export_report_to_excel
from src.services.transformations import build_coverage_report
from src.state import CoverageState
from src.tools.pinecone_tool import retrieve_reporting_rules
from src.tools.supabase_tool import query_orderbook


def add_error(state: CoverageState, message: str) -> CoverageState:
    errors = state.get("errors", [])
    errors.append(message)
    state["errors"] = errors
    state["status"] = "failed"
    return state


def validate_input_node(state: CoverageState) -> CoverageState:
    required_fields = ["banner", "seasons", "order_type", "reporting_date"]

    missing = []
    for field in required_fields:
        value = state.get(field)
        if value is None or value == "" or value == []:
            missing.append(field)

    if missing:
        return add_error(state, f"Missing required input fields: {missing}")

    state["status"] = "input_validated"
    state["errors"] = state.get("errors", [])
    return state


def retrieve_rules_node(state: CoverageState) -> CoverageState:
    try:
        query = state.get(
            "rules_query",
            "How is SC coverage calculated, which statuses are included, and how are value and volume validated?",
        )
        state["reporting_rules"] = retrieve_reporting_rules(query=query, top_k=3)
        state["status"] = "rules_retrieved"
        return state
    except Exception as exc:
        return add_error(state, f"Failed to retrieve reporting rules: {exc}")


def extract_data_node(state: CoverageState) -> CoverageState:
    try:
        records = query_orderbook(
            banner=state["banner"],
            seasons=state["seasons"],
            order_type=state["order_type"],
        )

        if not records:
            return add_error(state, "No records returned from Supabase.")

        state["raw_records"] = records
        state["status"] = "data_extracted"
        return state
    except Exception as exc:
        return add_error(state, f"Failed to extract Supabase data: {exc}")


def calculate_report_node(state: CoverageState) -> CoverageState:
    try:
        report = build_coverage_report(state["raw_records"])
        state["report_data"] = report
        state["validation_results"] = report["validation"]
        state["status"] = "report_calculated"
        return state
    except Exception as exc:
        return add_error(state, f"Failed to calculate coverage report: {exc}")


def validate_report_node(state: CoverageState) -> CoverageState:
    validation = state.get("validation_results", {})

    if not validation.get("passes_reconciliation"):
        return add_error(
            state,
            f"Report failed reconciliation: {validation}",
        )

    state["status"] = "validated"
    return state


def generate_observations_node(state: CoverageState) -> CoverageState:
    try:
        observations = run_react_analysis(state["report_data"])
        state["observations"] = observations
        state["status"] = "observations_generated"
        return state
    except Exception as exc:
        summary = state["report_data"]["executive_summary"]

        value_coverage_pct = summary["value_coverage_percentage"] * 100
        volume_coverage_pct = summary["volume_coverage_percentage"] * 100

        state["observations"] = [
            f"Total report value is {summary['total_value']:,.0f}.",
            f"Total report volume is {summary['total_volume']:,.0f}.",
            f"Value coverage is {value_coverage_pct:.1f}% based on Booked/Shipped plus Available value.",
            f"Volume coverage is {volume_coverage_pct:.1f}% based on Booked/Shipped plus Available volume.",
            f"Open order exposure is {summary['open_order_value']:,.0f} value and {summary['open_order_volume']:,.0f} units.",
            f"Included seasons: {', '.join(summary['seasons'])}.",
            f"ReAct observation generation failed; fallback deterministic observations used. Error: {exc}",
        ]
        state["status"] = "observations_generated"
        return state


def export_local_report_node(state: CoverageState) -> CoverageState:
    try:
        output_path = export_report_to_excel(
            report_data=state["report_data"],
            observations=state.get("observations", []),
        )
        state["report_url"] = str(output_path)
        state["status"] = "completed_local"
        return state
    except Exception as exc:
        return add_error(state, f"Failed to export local report: {exc}")


def should_continue(state: CoverageState) -> str:
    if state.get("status") == "failed":
        return "failed"
    return "continue"


def build_graph():
    graph = StateGraph(CoverageState)

    graph.add_node("validate_input", validate_input_node)
    graph.add_node("retrieve_rules", retrieve_rules_node)
    graph.add_node("extract_data", extract_data_node)
    graph.add_node("calculate_report", calculate_report_node)
    graph.add_node("validate_report", validate_report_node)
    graph.add_node("generate_observations", generate_observations_node)
    graph.add_node("export_local_report", export_local_report_node)

    graph.set_entry_point("validate_input")

    graph.add_conditional_edges(
        "validate_input",
        should_continue,
        {
            "continue": "retrieve_rules",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "retrieve_rules",
        should_continue,
        {
            "continue": "extract_data",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "extract_data",
        should_continue,
        {
            "continue": "calculate_report",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "calculate_report",
        should_continue,
        {
            "continue": "validate_report",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "validate_report",
        should_continue,
        {
            "continue": "generate_observations",
            "failed": END,
        },
    )

    graph.add_conditional_edges(
        "generate_observations",
        should_continue,
        {
            "continue": "export_local_report",
            "failed": END,
        },
    )

    graph.add_edge("export_local_report", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()

    initial_state: CoverageState = {
        "banner": "Snipes",
        "seasons": ["HO2026", "SP2027"],
        "order_type": "Standard Order - Futures",
        "reporting_date": "2026-07-23",
        "recipient_email": "demo@example.com",
        "errors": [],
    }

    final_state = app.invoke(initial_state)

    print("Final status:")
    print(final_state.get("status"))

    print("")
    print("Errors:")
    print(final_state.get("errors"))

    print("")
    print("Executive summary:")
    print(final_state["report_data"]["executive_summary"])

    print("")
    print("Validation:")
    print(final_state["validation_results"])

    print("")
    print("Observations:")
    for observation in final_state.get("observations", []):
        print(f"- {observation}")

    print("")
    print("RAG sources:")
    for rule in final_state.get("reporting_rules", []):
        print(f"- {rule['title']} | {rule['source']} | score={rule['score']}")

    print("")
    print("Report file:")
    print(final_state.get("report_url"))