from pathlib import Path
import os
import math
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

CSV_PATH = Path("data/processed/orderbook_clean.csv")
TABLE_NAME = "orderbook"
BATCH_SIZE = 250

DATE_COLUMNS = [
    "eta",
    "week_commencing",
    "order_entry_date",
    "customer_request_date",
    "customer_confirmed_date",
    "rejected_date",
    "eta_possible_delivery_date_drs_method_only",
    "planned_goods_issue_date",
]


def clean_value(value):
    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if pd.isna(value):
        return None

    return value


def clean_record(record: dict) -> dict:
    return {key: clean_value(value) for key, value in record.items()}


def normalize_date_series(series: pd.Series) -> pd.Series:
    numeric_values = pd.to_numeric(series, errors="coerce")
    excel_serial_mask = numeric_values.between(20000, 60000)

    parsed = pd.to_datetime(series, errors="coerce")

    if excel_serial_mask.any():
        parsed_excel = pd.to_datetime(
            numeric_values.where(excel_serial_mask),
            unit="D",
            origin="1899-12-30",
            errors="coerce",
        )
        parsed = parsed.where(~excel_serial_mask, parsed_excel)

    return parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), None)


def normalize_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = normalize_date_series(df[col])

    return df


def main():
    print("Starting Supabase load script...")

    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    print(f"CSV path: {CSV_PATH}")
    print(f"CSV exists: {CSV_PATH.exists()}")
    print(f"Supabase URL set: {bool(url)}")
    print(f"Supabase key set: {bool(key)}")

    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    if not CSV_PATH.exists():
        raise FileNotFoundError(f"CSV not found: {CSV_PATH}")

    supabase = create_client(url, key)

    df = pd.read_csv(CSV_PATH)
    df = normalize_dates(df)

    print(f"CSV rows found: {len(df)}")
    print(f"CSV columns found: {len(df.columns)}")

    if df.empty:
        raise ValueError("CSV has zero rows. Nothing to load.")

    records = [clean_record(row) for row in df.to_dict(orient="records")]

    print(f"Loading {len(records)} records into table: {TABLE_NAME}")

    for start in range(0, len(records), BATCH_SIZE):
        batch = records[start:start + BATCH_SIZE]
        supabase.table(TABLE_NAME).insert(batch).execute()
        print(f"Inserted rows {start + 1} to {start + len(batch)}")

    print("Supabase load complete.")


if __name__ == "__main__":
    main()
