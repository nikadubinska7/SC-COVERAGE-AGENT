# Google Sheets Workflow

## Purpose

This workflow exports the full filtered orderbook to Google Sheets for pivot-table analysis.

## Recommended Design

Use a Google Sheets file with a raw-data tab and a summary tab with pre-created pivot tables.

Tabs:

```text
Raw OB
Coverage Summary
```

n8n updates only `Raw OB`.
The `Coverage Summary` pivots remain in the sheet and refresh from the raw-data tab.

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
agent_observations ReAct agent observations
```

## n8n Node Order

Use this structure:

```text
Manual Trigger
-> HTTP Request: /export-orderbook
-> Google Sheets: clear Raw OB
-> Code: prepare rows with representative column names
-> Google Sheets: append Raw OB rows
-> Code: prepare one email payload
-> Gmail: send Sheet + dashboard links
```

Do not add a separate header-row append node. The Google Sheets append node creates headers from the JSON keys. A separate header node creates duplicate header rows.

## Code Node: Prepare Rows

Use this to convert each raw object into one n8n item with readable column names:

```javascript
const rows = $('HTTP Request').first().json.rows || [];

function titleCase(value) {
  const special = {
    eta: 'ETA',
    crd: 'CRD',
    id: 'ID',
    usd: 'USD',
    msrp: 'MSRP',
    ob: 'OB'
  };

  return value
    .split('_')
    .map(part => {
      const lower = part.toLowerCase();
      if (special[lower]) return special[lower];
      return lower.charAt(0).toUpperCase() + lower.slice(1);
    })
    .join(' ');
}

return rows.map(row => {
  const output = {};

  for (const [key, value] of Object.entries(row)) {
    output[titleCase(key)] = value;
  }

  return { json: output };
});
```

## Pivot Tables

Create pivots manually once in `Coverage Summary`.

Useful pivots:

1. Coverage by Season
   - Rows: `Season`, `Requested Month`
   - Columns: `Status`
   - Values: `Report Wholesale Value`, `Report Volume`

2. Category Risk
   - Rows: `Age Division`, `Sub Category`
   - Columns: `Status`, `Coverage Performance`
   - Values: `Report Wholesale Value`, `Report Volume`

3. Timing Risk
   - Rows: `Requested Month`
   - Columns: `Timing Bucket`
   - Values: `Report Wholesale Value`, `Report Volume`

4. Open Orders
   - Filter: `Status = Open Order`
   - Rows: `Category`, `Sub Category`, `Style Name`
   - Values: `Report Wholesale Value`, `Report Volume`

## Gmail Notification

Send one email after the append node. Add a final code node first:

```javascript
return [
  {
    json: $('HTTP Request').first().json
  }
];
```

This prevents Gmail from receiving one item per spreadsheet row.

The email should include:

- dashboard link
- Google Sheets link
- rows and columns exported
- ReAct agent observations from `agent_observations`

## Known Note

Google Sheets is suitable here because the current export is around 2,000 rows and 70+ columns. The full export is far below the standard Google Sheets 10 million cell limit.
