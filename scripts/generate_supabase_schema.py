from pathlib import Path
import pandas as pd

CSV_PATH = Path("data/processed/orderbook_clean.csv")
OUTPUT_PATH = Path("docs/supabase_orderbook_schema.sql")
TABLE_NAME = "orderbook"


FORCED_TEXT_COLUMNS = [
    "eta_vs_crd",
]

FORCED_NUMERIC_COLUMNS = [
    "report_wholesale_value",
    "report_volume",
    "source_row_number",
    "sales_order_line_item_number",
]

DATE_HINTS = [
    "date",
    "week_commencing",
]

NUMERIC_HINTS = [
    "wholesale",
    "quantity",
    "percentage",
    "price",
    "value",
    "amount",
    "carton",
    "volume",
]


def infer_sql_type(column: str, series: pd.Series) -> str:
    col = column.lower()

    if column == "id":
        return "bigserial primary key"

    if col in FORCED_TEXT_COLUMNS:
        return "text"

    if col in FORCED_NUMERIC_COLUMNS:
        return "numeric"

    if any(hint in col for hint in DATE_HINTS):
        parsed = pd.to_datetime(series, errors="coerce")
        if parsed.notna().sum() > 0:
            return "date"

    if any(hint in col for hint in NUMERIC_HINTS):
        numeric = pd.to_numeric(series, errors="coerce")
        if numeric.notna().sum() > 0:
            return "numeric"

    return "text"


def main():
    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    df = pd.read_csv(CSV_PATH)

    lines = []
    lines.append("drop table if exists orderbook;")
    lines.append("")
    lines.append("create table orderbook (")
    lines.append("    id bigserial primary key,")

    column_defs = []
    for col in df.columns:
        if col == "id":
            continue
        sql_type = infer_sql_type(col, df[col])
        column_defs.append(f"    {col} {sql_type}")

    lines.append(",\n".join(column_defs))
    lines.append(");")
    lines.append("")
    lines.append("create index idx_orderbook_banner on orderbook (banner);")
    lines.append("create index idx_orderbook_season on orderbook (season);")
    lines.append("create index idx_orderbook_status on orderbook (status);")
    lines.append("create index idx_orderbook_order_type on orderbook (order_type);")
    lines.append("create index idx_orderbook_requested_month on orderbook (requested_month);")
    lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print(f"Schema SQL generated: {OUTPUT_PATH}")
    print("")
    print("\n".join(lines[:40]))
    print("...")


if __name__ == "__main__":
    main()
