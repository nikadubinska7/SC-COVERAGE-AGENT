# Google Sheets Workflow

## Purpose

This workflow is a second n8n workflow alongside the Airtable workflow.

Use Airtable for operational exception review.
Use Google Sheets for full database export and pivot-table analysis.

## Recommended Design

Use a Google Sheets template with pre-created pivot tables.

Tabs:

```text
Raw Orderbook
Pivot - Coverage by Season
Pivot - Category Risk
Pivot - Timing Risk
Pivot - Open Orders
README
```

n8n updates only `Raw Orderbook`.
The pivot tabs remain in the sheet and refresh from the raw-data tab.

## Backend Endpoint

The dashboard service exposes:

```text
POST /export-orderbook
```

Example URL:

```text
https://sc-coverage-dashboard.onrender.com/export-orderbook
```

Example body:

```json
{
  "banner": "Snipes",
  "seasons": ["HO2026", "SP2027"],
  "order_type": "Standard Order - Futures",
  "dashboard_url": "https://sc-coverage-dashboard.onrender.com",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/..."
}
```

Response includes:

```text
columns        ordered column names
header_row     same as columns
rows           row objects
values         row arrays matching columns
rows_count     number of exported rows
summary        report KPI summary
```

## n8n Node Order

Duplicate the Airtable workflow and use this structure:

```text
Manual Trigger
-> HTTP Request: /export-orderbook
-> Google Sheets: clear Raw Orderbook
-> Google Sheets: append header row
-> Code: split values into rows
-> Google Sheets: append raw rows
-> Gmail: send Sheet + dashboard links
```

## Code Node

Use this to convert the `values` array into one n8n item per spreadsheet row:

```javascript
const values = $('HTTP Request').first().json.values || [];

return values.map(row => ({
  json: {
    row,
  },
}));
```

The Google Sheets append node should append:

```text
{{$json.row}}
```

## Pivot Tables

Create pivots manually once in the template.

Useful pivots:

1. Coverage by Season
   - Rows: `season`, `requested_month`
   - Columns: `status`
   - Values: `report_wholesale_value`, `report_volume`

2. Category Risk
   - Rows: `category`, `sub_category`
   - Columns: `status`
   - Values: `report_wholesale_value`, `report_volume`

3. Timing Risk
   - Rows: `timing_bucket`
   - Columns: `season`
   - Values: `report_wholesale_value`, `report_volume`

4. Open Orders
   - Filter: `status = Open Order`
   - Rows: `category`, `sub_category`, `style_name`
   - Values: `report_wholesale_value`, `report_volume`

## Known Note

Google Sheets is suitable here because the current export is around 2,000 rows and 70+ columns. The full export is far below the standard Google Sheets 10 million cell limit.
