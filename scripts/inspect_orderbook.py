from pathlib import Path
import pandas as pd

WORKBOOK_PATH = Path("data/raw/EXT_ORDERBOOK_SOURCE.xlsx")
OUTPUT_PATH = Path("data/profiles/orderbook_profile.txt")


def main():
    if not WORKBOOK_PATH.exists():
        raise FileNotFoundError(f"Workbook not found: {WORKBOOK_PATH}")

    excel = pd.ExcelFile(WORKBOOK_PATH)

    lines = []
    lines.append("SC Coverage Source Workbook Profile")
    lines.append("=" * 80)
    lines.append("")
    lines.append("Workbook path:")
    lines.append(str(WORKBOOK_PATH))
    lines.append("")
    lines.append("Sheets:")
    for sheet in excel.sheet_names:
        lines.append(f"- {sheet}")

    if "ORDERBOOK" not in excel.sheet_names:
        raise ValueError("Expected sheet named ORDERBOOK, but it was not found.")

    df = pd.read_excel(WORKBOOK_PATH, sheet_name="ORDERBOOK")

    lines.append("")
    lines.append("ORDERBOOK shape:")
    lines.append(f"Rows: {df.shape[0]}")
    lines.append(f"Columns: {df.shape[1]}")

    lines.append("")
    lines.append("ORDERBOOK columns:")
    for idx, col in enumerate(df.columns, start=1):
        lines.append(f"{idx}. {col}")

    lines.append("")
    lines.append("Column data types:")
    for col, dtype in df.dtypes.items():
        lines.append(f"- {col}: {dtype}")

    lines.append("")
    lines.append("Missing values by column:")
    missing = df.isna().sum().sort_values(ascending=False)
    for col, count in missing.items():
        lines.append(f"- {col}: {count}")

    lines.append("")
    lines.append("First 5 rows preview:")
    lines.append(df.head(5).to_string())

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    print("\n".join(lines))
    print("")
    print(f"Profile saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
