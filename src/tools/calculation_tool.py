from pprint import pprint

from src.services.transformations import build_coverage_report
from src.tools.supabase_tool import query_orderbook


def calculate_coverage_report(
    banner: str,
    seasons: list[str],
    order_type: str,
) -> dict:
    records = query_orderbook(
        banner=banner,
        seasons=seasons,
        order_type=order_type,
    )

    if not records:
        raise ValueError("No records returned from Supabase.")

    return build_coverage_report(records)


if __name__ == "__main__":
    report = calculate_coverage_report(
        banner="Snipes",
        seasons=["HO2026", "SP2027"],
        order_type="Standard Order - Futures",
    )

    print("Executive summary:")
    pprint(report["executive_summary"])

    print("")
    print("Validation:")
    pprint(report["validation"])

    print("")
    print("First 5 coverage rows:")
    print(report["coverage_by_season"][:5])