# ORDERBOOK Data Dictionary

## Source

The source is a mock Supabase table named `orderbook`.

The table was loaded from a simplified ORDERBOOK worksheet.

## Core fields

| Field | Meaning |
|---|---|
| banner | Retail account name |
| season | Product season, such as HO2026 or SP2027 |
| order_type | Order type, such as Standard Order - Futures |
| status | Order coverage status |
| requested_month | Customer requested month bucket |
| confirmed_wholesale | Confirmed wholesale order value |
| available_wholesale | Available wholesale value |
| report_wholesale_value | Value used for report aggregation |
| eta_vs_crd | ETA compared with customer request date |
| coverage_performance | Delivery timing classification |
| brand | Product brand |
| age_division | Product age/division segment |

## Required MVP fields

The MVP requires:

- banner
- season
- order_type
- status
- requested_month
- confirmed_wholesale
- available_wholesale
- report_wholesale_value

## Known MVP seasons

The current mock source contains:

- HO2026
- SP2027

## Known MVP account

The current mock source contains:

- Snipes

## Known MVP order type

The current mock source contains:

- Standard Order - Futures