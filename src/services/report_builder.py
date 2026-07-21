from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


OUTPUT_DIR = Path("reports")


def build_summary_dataframe(summary: dict[str, Any], observations: list[str]) -> pd.DataFrame:
    rows = [
        ("Source rows", summary.get("source_rows")),
        ("Included rows", summary.get("included_rows")),
        ("Cancelled rows", summary.get("cancelled_rows")),
        ("Total report value", summary.get("total_value")),
        ("Booked/Shipped value", summary.get("booked_shipped_value")),
        ("Available value", summary.get("available_value")),
        ("Open order value", summary.get("open_order_value")),
        ("Covered value", summary.get("covered_value")),
        ("Coverage percentage", summary.get("coverage_percentage")),
        ("Seasons", ", ".join(summary.get("seasons", []))),
        ("Requested months", ", ".join(summary.get("requested_months", []))),
    ]

    df = pd.DataFrame(rows, columns=["Metric", "Value"])

    observation_rows = pd.DataFrame(
        [(f"Observation {idx}", observation) for idx, observation in enumerate(observations, start=1)],
        columns=["Metric", "Value"],
    )

    return pd.concat([df, observation_rows], ignore_index=True)


def build_validation_dataframe(validation: dict[str, Any]) -> pd.DataFrame:
    rows = []

    for key, value in validation.items():
        rows.append((key, str(value)))

    return pd.DataFrame(rows, columns=["Check", "Result"])


def export_report_to_excel(
    report_data: dict[str, Any],
    observations: list[str],
    output_path: str | Path | None = None,
) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if output_path is None:
        output_path = OUTPUT_DIR / "sc_coverage_report.xlsx"
    else:
        output_path = Path(output_path)

    summary_df = build_summary_dataframe(
        report_data["executive_summary"],
        observations,
    )

    coverage_df = pd.DataFrame(report_data["coverage_by_season"])
    validation_df = build_validation_dataframe(report_data["validation"])

    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="Executive Summary", index=False)
        coverage_df.to_excel(writer, sheet_name="Coverage by Season", index=False)
        validation_df.to_excel(writer, sheet_name="Validation", index=False)

        workbook = writer.book

        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]

            worksheet.freeze_panes = "A2"

            for cell in worksheet[1]:
                cell.style = "Headline 3"

            for column_cells in worksheet.columns:
                max_length = 0
                column_letter = column_cells[0].column_letter

                for cell in column_cells:
                    value = "" if cell.value is None else str(cell.value)
                    max_length = max(max_length, len(value))

                worksheet.column_dimensions[column_letter].width = min(max_length + 2, 45)

        summary_sheet = writer.sheets["Executive Summary"]

        for row in summary_sheet.iter_rows(min_row=2):
            metric = row[0].value
            value_cell = row[1]

            if metric == "Coverage percentage" and isinstance(value_cell.value, float):
                value_cell.number_format = "0.0%"

            if metric and "value" in str(metric).lower() and isinstance(value_cell.value, (int, float)):
                value_cell.number_format = '#,##0.00'

    return output_path