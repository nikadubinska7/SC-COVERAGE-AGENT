from pathlib import Path
import re
import pandas as pd

SOURCE_PATH = Path("data/raw/EXT_ORDERBOOK_SOURCE.xlsx")
OUTPUT_DIR = Path("data/processed")
OUTPUT_CSV = OUTPUT_DIR / "orderbook_clean.csv"
MAPPING_PATH = Path("docs/orderbook_field_mapping.md")


COLUMN_MAP = {
    "BANNER": "banner",
    "STATUS": "status",
    "ETA": "eta",
    "ETA  vs CRD": "eta_vs_crd",
    "COVERAGE PERFORMANCE": "coverage_performance",
    "W/C": "week_commencing",
    "AGE + DIVISION": "age_division",
    "NIKE?": "brand",
    "CONFIRMED WHLS $": "confirmed_wholesale",
    "AVAILABLE WHLS $": "available_wholesale",
    "Sold-to Name": "sold_to_name",
    "Sold-to Code": "sold_to_code",
    "Ship-to Name": "ship_to_name",
    "Ship-to Code": "ship_to_code",
    "Order Entry Date": "order_entry_date",
    "Customer Request Date (CRD)": "customer_request_date",
    "Customer Requested Date YYYYMM (CRD)": "requested_month",
    "Customer Confirmed Date (CCD)": "customer_confirmed_date",
    "Season": "season",
    "Order Type": "order_type",
    "Always Available Product Indicator": "always_available_product_indicator",
    "Distribution Method (DC/DRS)": "distribution_method",
    "Shipment Type": "shipment_type",
    "Sales Order Number": "sales_order_number",
    "Sales Order Line Item Number": "sales_order_line_item_number",
    "PO Number": "po_number",
}


DATE_COLUMNS = [
    "eta",
    "week_commencing",
    "order_entry_date",
    "customer_request_date",
    "customer_confirmed_date",
]


NUMERIC_COLUMNS = [
    "confirmed_wholesale",
    "available_wholesale",
]


def normalize_fallback_column_name(name: str) -> str:
    """Normalize columns not explicitly mapped."""
    name = str(name).strip().lower()
    name = name.replace("$", "value")
    name = name.replace("%", "pct")
    name = re.sub(r"[^a-z0-9]+", "_", name)
    name = re.sub(r"_+", "_", name)
    return name.strip("_")


def clean_money_series(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace(",", "", regex=False)
        .str.replace("$", "", regex=False)
        .str.replace("€", "", regex=False)
        .str.replace(" ", "", regex=False)
        .replace({"nan": None, "None": None, "": None})
    )
    return pd.to_numeric(cleaned, errors="coerce").fillna(0)


def main():
    if not SOURCE_PATH.exists():
        raise FileNotFoundError(f"Source workbook not found: {SOURCE_PATH}")

    df = pd.read_excel(SOURCE_PATH, sheet_name="ORDERBOOK")

    original_columns = list(df.columns)

    rename_map = {}
    for col in df.columns:
        if col in COLUMN_MAP:
            rename_map[col] = COLUMN_MAP[col]
        else:
            rename_map[col] = normalize_fallback_column_name(col)

    df = df.rename(columns=rename_map)

    # Remove completely empty rows.
    df = df.dropna(how="all").copy()

    # Add stable source row number for traceability.
    df.insert(0, "source_row_number", range(2, len(df) + 2))

    # Normalize text columns.
    for col in df.columns:
        if col not in NUMERIC_COLUMNS and col not in DATE_COLUMNS:
            df[col] = df[col].astype("string").str.strip()

    # Normalize financial fields.
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = clean_money_series(df[col])

    # Normalize dates.
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce").dt.date

    # Standardize requested month as text.
    if "requested_month" in df.columns:
        df["requested_month"] = df["requested_month"].astype("string").str.replace(".0", "", regex=False)

    # Add report value for easier aggregation.
    def report_value(row):
        status = str(row.get("status", "")).strip().lower()
        if status == "available":
            return row.get("available_wholesale", 0)
        return row.get("confirmed_wholesale", 0)

    df["report_wholesale_value"] = df.apply(report_value, axis=1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False)

    mapping_lines = []
    mapping_lines.append("# ORDERBOOK Field Mapping")
    mapping_lines.append("")
    mapping_lines.append("This document maps the original Excel ORDERBOOK columns to normalized Supabase-ready fields.")
    mapping_lines.append("")
    mapping_lines.append(f"Source workbook: `{SOURCE_PATH}`")
    mapping_lines.append(f"Clean CSV: `{OUTPUT_CSV}`")
    mapping_lines.append("")
    mapping_lines.append("## Source profile")
    mapping_lines.append("")
    mapping_lines.append(f"- Source rows: {len(df)}")
    mapping_lines.append(f"- Source columns: {len(original_columns)}")
    mapping_lines.append(f"- Cleaned columns: {len(df.columns)}")
    mapping_lines.append("")
    mapping_lines.append("## Column mapping")
    mapping_lines.append("")
    mapping_lines.append("| Original Excel column | Clean field name |")
    mapping_lines.append("|---|---|")

    for original in original_columns:
        mapping_lines.append(f"| `{original}` | `{rename_map[original]}` |")

    mapping_lines.append("")
    mapping_lines.append("## Added fields")
    mapping_lines.append("")
    mapping_lines.append("| Field | Purpose |")
    mapping_lines.append("|---|---|")
    mapping_lines.append("| `source_row_number` | Original Excel row number for traceability |")
    mapping_lines.append("| `report_wholesale_value` | Value used in report aggregation |")

    MAPPING_PATH.write_text("\n".join(mapping_lines), encoding="utf-8")

    print(f"Clean CSV created: {OUTPUT_CSV}")
    print(f"Rows: {df.shape[0]}")
    print(f"Columns: {df.shape[1]}")
    print(f"Mapping created: {MAPPING_PATH}")
    print("")
    print("Preview:")
    print(df.head(5).to_string())


if __name__ == "__main__":
    main()
