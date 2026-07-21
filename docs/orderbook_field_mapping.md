# ORDERBOOK Field Mapping

This document maps the original Excel ORDERBOOK columns to normalized Supabase-ready fields.

Source workbook: `data/raw/EXT_ORDERBOOK_SOURCE.xlsx`
Clean CSV: `data/processed/orderbook_clean.csv`

## Source profile

- Source rows: 2041
- Source columns: 71
- Cleaned columns: 73

## Column mapping

| Original Excel column | Clean field name |
|---|---|
| `BANNER` | `banner` |
| `STATUS` | `status` |
| `ETA` | `eta` |
| `ETA vs CRD` | `eta_vs_crd` |
| `COVERAGE PERFORMANCE` | `coverage_performance` |
| `W/C` | `week_commencing` |
| `AGE + DIVISION` | `age_division` |
| `NIKE?` | `brand` |
| `CONFIRMED WHLS $` | `confirmed_wholesale` |
| `AVAILABLE WHLS $` | `available_wholesale` |
| `Sold-to Name` | `sold_to_name` |
| `Sold-to Code` | `sold_to_code` |
| `Ship-to Name` | `ship_to_name` |
| `Ship-to Code` | `ship_to_code` |
| `Order Entry Date` | `order_entry_date` |
| `Customer Request Date (CRD)` | `customer_request_date` |
| `Customer Requested Date YYYYMM (CRD)` | `requested_month` |
| `Customer Confirmed Date (CCD)` | `customer_confirmed_date` |
| `Season` | `season` |
| `Order Type` | `order_type` |
| `Always Available Product Indicator` | `always_available_product_indicator` |
| `Distribution Method (DC/DRS)` | `distribution_method` |
| `Shipment Type` | `shipment_type` |
| `Sales Order Number` | `sales_order_number` |
| `Sales Order Line Item Number` | `sales_order_line_item_number` |
| `PO Number` | `po_number` |
| `Contact Name` | `contact_name` |
| `Gender` | `gender` |
| `Category` | `category` |
| `Sub Category` | `sub_category` |
| `Division` | `division` |
| `Style/Color` | `style_color` |
| `Style Name` | `style_name` |
| `Color Description` | `color_description` |
| `Replica Indicator` | `replica_indicator` |
| `Launch Date` | `launch_date` |
| `Launch Code` | `launch_code` |
| `Campaign` | `campaign` |
| `Order Status` | `order_status` |
| `Ordered Quantity` | `ordered_quantity` |
| `Confirmed Quantity` | `confirmed_quantity` |
| `Remaining To Ship Quantity` | `remaining_to_ship_quantity` |
| `Remaining To Ship Percentage` | `remaining_to_ship_percentage` |
| `Available Quantity` | `available_quantity` |
| `Percentage Available Of Order` | `percentage_available_of_order` |
| `Not Available Quantity` | `not_available_quantity` |
| `Total Booked Quantity` | `total_booked_quantity` |
| `Not Covered Quantity` | `not_covered_quantity` |
| `Rejected Quantity` | `rejected_quantity` |
| `Rejected Date` | `rejected_date` |
| `Rejection Reason` | `rejection_reason` |
| `Nike ETA` | `nike_eta` |
| `Planned Delivery Date` | `planned_delivery_date` |
| `First Possible Delivery Date (DRS Method Only)` | `first_possible_delivery_date_drs_method_only` |
| `Planned Goods Issue Date` | `planned_goods_issue_date` |
| `Container Number` | `container_number` |
| `Packlist(DC) & Shipment ID(DRS)` | `packlist_dc_shipment_id_drs` |
| `Shipped Carton Quantity` | `shipped_carton_quantity` |
| `Remaining To Ship Estimated DC Carton Quantity` | `remaining_to_ship_estimated_dc_carton_quantity` |
| `Unshippable Order Reason` | `unshippable_order_reason` |
| `Delivery Schedule Block Description` | `delivery_schedule_block_description` |
| `Wholesale Price (Transaction Currency)` | `wholesale_price_transaction_currency` |
| `Net Price (Transaction Currency)` | `net_price_transaction_currency` |
| `Transaction Currency` | `transaction_currency` |
| `Wholesale Price (USD)` | `wholesale_price_usd` |
| `Net Price (USD)` | `net_price_usd` |
| `MSRP` | `msrp` |
| `Discount Percentage` | `discount_percentage` |
| `Harmonized Tax Code` | `harmonized_tax_code` |
| `WHOLESALE US CONFIRMED` | `wholesale_us_confirmed` |
| `WHOLESALE US AVAILABLE` | `wholesale_us_available` |

## Added fields

| Field | Purpose |
|---|---|
| `source_row_number` | Original Excel row number for traceability |
| `report_wholesale_value` | Value used in report aggregation |