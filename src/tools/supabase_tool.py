import os
from typing import Any

from dotenv import load_dotenv
from supabase import create_client


TABLE_NAME = "orderbook"
PAGE_SIZE = 1000


def get_supabase_client():
    load_dotenv()

    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")

    if not url or not key:
        raise ValueError("Missing SUPABASE_URL or SUPABASE_KEY in .env")

    return create_client(url, key)


def query_orderbook(
    banner: str,
    seasons: list[str],
    order_type: str,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """
    Query orderbook records from Supabase with pagination.

    Args:
        banner: Retail account name, e.g. Snipes.
        seasons: Seasons to include, e.g. ["HO2026", "SP2027"].
        order_type: Order type filter.
        limit: Optional max number of rows.

    Returns:
        List of orderbook records.
    """
    if not banner:
        raise ValueError("banner is required")

    if not seasons:
        raise ValueError("seasons must contain at least one season")

    if not order_type:
        raise ValueError("order_type is required")

    supabase = get_supabase_client()

    all_records: list[dict[str, Any]] = []
    offset = 0

    while True:
        current_page_size = PAGE_SIZE

        if limit is not None:
            remaining = limit - len(all_records)
            if remaining <= 0:
                break
            current_page_size = min(PAGE_SIZE, remaining)

        response = (
            supabase.table(TABLE_NAME)
            .select("*")
            .eq("banner", banner)
            .in_("season", seasons)
            .eq("order_type", order_type)
            .range(offset, offset + current_page_size - 1)
            .execute()
        )

        page = response.data or []
        all_records.extend(page)

        if len(page) < current_page_size:
            break

        offset += current_page_size

    return all_records


if __name__ == "__main__":
    records = query_orderbook(
        banner="Snipes",
        seasons=["HO2026", "SP2027"],
        order_type="Standard Order - Futures",
    )

    print(f"Records returned: {len(records)}")

    if records:
        print("First record keys:")
        print(sorted(records[0].keys()))

        print("")
        print("First record sample:")
        for key in [
            "banner",
            "season",
            "status",
            "order_type",
            "requested_month",
            "confirmed_wholesale",
            "available_wholesale",
            "report_wholesale_value",
        ]:
            print(f"{key}: {records[0].get(key)}")