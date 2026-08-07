# n8n Workflow

## Purpose

n8n automates the final SC Coverage workflow:

- trigger the deployed Render endpoint
- refresh the Google Sheets `Raw OB` tab with the full filtered orderbook
- keep pivot tables available in `Coverage Summary`
- send one Gmail notification with dashboard, Google Sheets, export summary, and ReAct agent observations

## Final Node Order

```text
Manual Trigger
-> HTTP Request
-> Google Sheets: Clear Raw OB
-> Code: Prepare Raw OB Rows
-> Google Sheets: Append Raw OB Rows
-> Code: Prepare Email Payload
-> Gmail: Send Message
```

The `Prepare Email Payload` node is required because the append step processes 2,000+ rows. Without this node, Gmail receives one item per exported row and attempts to send thousands of emails.

## HTTP Request Node

Method:

```text
POST
```

URL:

```text
https://sc-coverage-dashboard.onrender.com/export-orderbook
```

Body content type:

```text
JSON
```

Example body:

```json
{
  "banner": "Snipes",
  "seasons": ["HO2026", "SP2027"],
  "order_type": "Standard Order - Futures",
  "dashboard_url": "https://sc-coverage-dashboard.onrender.com",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/1rmjLAi2xwU7akxceoyH3RpycpfauFBg__cyAo0Vv4BY/edit"
}
```

Recommended settings:

```text
Retry On Fail: enabled
Max Tries: 3
Wait Between Tries: 5000-10000 ms
```

The endpoint response includes:

```text
rows_count
columns_count
rows
summary
agent_observations
agent_observation_error
```

## Google Sheets: Clear Raw OB

Use:

```text
Resource: Sheet Within Document
Operation: Clear
Document: By ID
Sheet: Raw OB
Clear: Whole Sheet
Keep First Row: Off
```

This guarantees each run replaces the previous export instead of appending duplicate rows.

## Code: Prepare Raw OB Rows

Mode:

```text
Run Once for All Items
```

Language:

```text
JavaScript
```

Code:

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

This converts raw keys such as `source_row_number` into representative sheet headers such as `Source Row Number`.

## Google Sheets: Append Raw OB Rows

Use:

```text
Resource: Sheet Within Document
Operation: Append Row
Document: By ID
Sheet: Raw OB
Mapping Column Mode: Map Automatically
```

Expected item count:

```text
2041 items
```

The exact row count can change with filters or source data.

## Code: Prepare Email Payload

Mode:

```text
Run Once for All Items
```

Language:

```text
JavaScript
```

Code:

```javascript
return [
  {
    json: $('HTTP Request').first().json
  }
];
```

Expected item count:

```text
1 item
```

## Gmail Node

Use the `HTTP Request` output for dynamic content.

Subject:

```text
SC Coverage Dashboard + Sheets Ready
```

Message:

```text
Hi Nika,

The SC Coverage Google Sheets export is ready.

Google Sheet:
{{ $('HTTP Request').item.json.google_sheet_url }}

Dashboard:
{{ $('HTTP Request').item.json.dashboard_url }}

Report scope:
- Banner: {{ $('HTTP Request').item.json.banner }}
- Seasons: {{ $('HTTP Request').item.json.seasons.join(", ") }}
- Order type: {{ $('HTTP Request').item.json.order_type }}

Export summary:
- Rows exported: {{ $('HTTP Request').item.json.rows_count }}
- Columns exported: {{ $('HTTP Request').item.json.columns_count }}

Agent observations:
{{ $('HTTP Request').item.json.agent_observations.join("\n") }}

This message was generated automatically by the SC Coverage workflow.
```

Recommended settings:

```text
Retry On Fail: enabled
Max Tries: 3
Wait Between Tries: 5000-10000 ms
```

## Expected Run Result

For the current Snipes sample scope:

```text
HTTP Request                       1 item
Google Sheets Clear Raw OB         1 item
Prepare Raw OB Rows                about 2041 items
Google Sheets Append Raw OB Rows   about 2041 items
Prepare Email Payload              1 item
Gmail                              1 item
```

## Known Notes

Google/Gmail may temporarily rate-limit test runs. This is why the Gmail node should use retry settings and receive only the single prepared email payload.

Repeated runs replace the `Raw OB` tab, while the `Coverage Summary` pivot tables remain available for analysis.
