from __future__ import annotations

from langgraph.graph import END, StateGraph

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
            "How is SC coverage calculated, which statuses are included, and how is validation performed?",
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
    summary = state["report_data"]["executive_summary"]

    coverage_pct = summary["coverage_percentage"] * 100

    observations = [
        f"Total report value is {summary['total_value']:,.2f}.",
        f"Coverage is {coverage_pct:.1f}% based on Booked/Shipped plus Available value.",
        f"Open order exposure is {summary['open_order_value']:,.2f}.",
        f"Included seasons: {', '.join(summary['seasons'])}.",
    ]

    state["observations"] = observations
    state["status"] = "completed_local"
    return state


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

    graph.add_edge("generate_observations", END)

    return graph.compile()


if __name__ == "__main__":
    app = build_graph()

    initial_state: CoverageState = {
        "banner": "Snipes",
        "seasons": ["HO2026", "SP2027"],
        "order_type": "Standard Order - Futures",
        "reporting_date": "2026-07-21",
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
    for observation in final_state["observations"]:
        print(f"- {observation}")

    print("")
    print("RAG sources:")
    for rule in final_state["reporting_rules"]:
        print(f"- {rule['title']} | {rule['source']} | score={rule['score']}")