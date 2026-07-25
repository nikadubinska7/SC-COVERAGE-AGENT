from __future__ import annotations

import os
from typing import Any

from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent


@tool
def summarize_coverage_result(executive_summary: dict[str, Any]) -> str:
    """
    Summarize the executive summary of the coverage report.
    """
    total_value = executive_summary.get("total_value", 0)
    total_volume = executive_summary.get("total_volume", 0)

    value_coverage_percentage = executive_summary.get(
        "value_coverage_percentage", 0
    ) * 100
    volume_coverage_percentage = executive_summary.get(
        "volume_coverage_percentage", 0
    ) * 100

    open_order_value = executive_summary.get("open_order_value", 0)
    open_order_volume = executive_summary.get("open_order_volume", 0)

    seasons = executive_summary.get("seasons", [])

    return (
        f"Total report value: {total_value:,.0f}. "
        f"Total report volume: {total_volume:,.0f}. "
        f"Value coverage percentage: {value_coverage_percentage:.1f}%. "
        f"Volume coverage percentage: {volume_coverage_percentage:.1f}%. "
        f"Open order value exposure: {open_order_value:,.0f}. "
        f"Open order volume exposure: {open_order_volume:,.0f}. "
        f"Included seasons: {', '.join(seasons)}."
    )


@tool
def evaluate_coverage_risk(executive_summary: dict[str, Any]) -> str:
    """
    Evaluate supply-chain coverage risk based on value and volume coverage.
    """
    value_coverage_percentage = executive_summary.get("value_coverage_percentage", 0)
    volume_coverage_percentage = executive_summary.get("volume_coverage_percentage", 0)
    open_order_value = executive_summary.get("open_order_value", 0)
    open_order_volume = executive_summary.get("open_order_volume", 0)

    risk_level = executive_summary.get("risk_level")

    if not risk_level:
        if value_coverage_percentage >= 0.75:
            risk_level = "Low"
        elif value_coverage_percentage >= 0.5:
            risk_level = "Medium"
        else:
            risk_level = "High"

    return (
        f"Risk level: {risk_level}. "
        f"Value coverage is {value_coverage_percentage * 100:.1f}%. "
        f"Volume coverage is {volume_coverage_percentage * 100:.1f}%. "
        f"Open order value exposure is {open_order_value:,.0f}. "
        f"Open order volume exposure is {open_order_volume:,.0f}."
    )


@tool
def check_validation_status(validation_results: dict[str, Any]) -> str:
    """
    Check whether the report passed value and volume validation and reconciliation.
    """
    passes = validation_results.get("passes_reconciliation")
    value_difference = validation_results.get("value_difference")
    volume_difference = validation_results.get("volume_difference")
    unexpected_statuses = validation_results.get("unexpected_statuses", [])

    if passes and not unexpected_statuses:
        return (
            "Validation passed. "
            f"Value reconciliation difference is {value_difference}. "
            f"Volume reconciliation difference is {volume_difference}."
        )

    return (
        "Validation issue detected. "
        f"Passes reconciliation: {passes}. "
        f"Value difference: {value_difference}. "
        f"Volume difference: {volume_difference}. "
        f"Unexpected statuses: {unexpected_statuses}."
    )


def build_react_agent():
    load_dotenv()

    if not os.getenv("OPENAI_API_KEY"):
        raise ValueError("Missing OPENAI_API_KEY in .env")

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

    tools = [
        summarize_coverage_result,
        evaluate_coverage_risk,
        check_validation_status,
    ]

    return create_agent(model=llm, tools=tools)


def run_react_analysis(report_data: dict[str, Any]) -> list[str]:
    """
    Run a ReAct agent over the completed deterministic report.

    The agent may call tools to inspect the executive summary and validation result.
    It returns concise business observations.
    """
    agent = build_react_agent()

    executive_summary = report_data["executive_summary"]
    validation_results = report_data["validation"]

    prompt = f"""
You are an autonomous supply-chain coverage reporting agent.

Analyze this coverage report and produce 4 concise observations for a business user.

Rules:
- Use the available tools before writing the final answer.
- Do not calculate totals yourself.
- Do not invent data.
- Discuss both value and volume.
- Focus on coverage, open-order risk, season scope, and validation status.
- Return only the observations as short bullet points.
- Do not return empty bullets.

Executive summary:
{executive_summary}

Validation results:
{validation_results}
"""

    result = agent.invoke(
        {
            "messages": [
                ("user", prompt),
            ]
        }
    )

    final_message = result["messages"][-1].content

    observations = []
    for line in final_message.splitlines():
        clean_line = line.strip().strip("-").strip()
        if clean_line:
            observations.append(clean_line)

    return observations


if __name__ == "__main__":
    sample_report = {
        "executive_summary": {
            "total_value": 149347764.66,
            "booked_shipped_value": 40125114.35,
            "available_value": 19203944.9,
            "open_order_value": 90018705.41,
            "covered_value": 59329059.25,
            "value_coverage_percentage": 0.3973,
            "total_volume": 2869524,
            "booked_shipped_volume": 790388,
            "available_volume": 375151,
            "open_order_volume": 1703985,
            "covered_volume": 1165539,
            "volume_coverage_percentage": 0.4062,
            "risk_level": "High",
            "seasons": ["HO2026", "SP2027"],
        },
        "validation": {
            "passes_reconciliation": True,
            "value_difference": 0.0,
            "volume_difference": 0.0,
            "unexpected_statuses": [],
        },
    }

    for observation in run_react_analysis(sample_report):
        print(f"- {observation}")