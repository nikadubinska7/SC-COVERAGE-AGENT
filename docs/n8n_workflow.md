# n8n Workflow

## Purpose

n8n automates the business workflow around the SC Coverage dashboard:

- trigger report generation
- create an Airtable summary run
- send a Gmail notification
- create detailed Airtable coverage-exception records

## Final Node Order

```text
Manual Trigger
-> HTTP Request
-> Airtable: Create Report Run
-> Gmail: Send Message
-> Code: Split Coverage Exceptions
-> Airtable: Create Coverage Exceptions
```

Gmail is placed before the Code node so the workflow sends one email, not one email per exception.

## HTTP Request Node

Method:

```text
POST
```

URL:

```text
https://sc-coverage-dashboard.onrender.com/run-report
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
  "airtable_exceptions_url": "https://airtable.com/...",
  "recipient_name": "Nika",
  "exception_limit": 50
}
```

Recommended settings:

```text
Retry On Fail: enabled
Max Tries: 3
Wait Between Tries: 5000 ms
```

## Airtable: Report Runs

Create one record in:

```text
Base: SC Coverage Review
Table: Report runs
```

Key mappings:

```text
Run ID                  {{$json.report_run_id}}
Generated At            {{$json.generated_at}}
Banner                  {{$json.banner}}
Seasons                 {{$json.seasons}}
Order Type              {{[$json.order_type]}}
Value Coverage          {{$json.value_coverage_percentage}}
Volume Coverage         {{$json.volume_coverage_percentage}}
Open Order Value        {{$json.open_order_value}}
Open Order Volume       {{$json.open_order_volume}}
Risk Level              {{$json.risk_level}}
Dashboard URL           {{$json.dashboard_url}}
Workflow Status         {{$json.status}}
Included Rows           {{$json.included_rows}}
Cancelled Rows          {{$json.cancelled_rows}}
```

Enable Airtable typecast when select options may be created automatically.

## Gmail Node

Use the HTTP Request node output for subject and body:

```text
Subject:
{{$node["HTTP Request"].json.email_subject}}

Message:
{{$node["HTTP Request"].json.email_body}}
```

This email includes:

- dashboard link
- Airtable coverage-exceptions review link
- executive KPI summary
- ReAct agent observations

## Code Node

Purpose:

Convert one HTTP response containing a `coverage_exceptions` array into many n8n items.

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
const exceptions = $('HTTP Request').first().json.coverage_exceptions || [];
const reportRunRecordId = $('Create a record').first().json.id;

return exceptions.map(exception => ({
  json: {
    ...exception,
    report_run_record_id: reportRunRecordId,
  },
}));
```

## Airtable: Coverage Exceptions

Create records in:

```text
Base: SC Coverage Review
Table: Coverage Exceptions
```

Key mappings:

```text
Exception ID             {{$json.exception_id}}
Report Run               {{[$json.report_run_record_id]}}
Division                 {{$json.division}}
Category                 {{$json.category}}
Sub Category             {{$json.sub_category}}
Gender                   {{$json.gender}}
Age Division             {{$json.age_division}}
Season                   {{$json.season}}
Requested Month          {{$json.requested_month}}
ETA                      {{$json.eta}}
Customer Request Date    {{$json.customer_request_date}}
Timing Bucket            {{$json.timing_bucket}}
Open Order Value         {{$json.open_order_value}}
Open Order Volume        {{$json.open_order_volume}}
Coverage Performance     {{$json.coverage_performance}}
Owner                    {{$json.owner}}
Review Status            {{$json.review_status}}
Comment                  {{$json.comment}}
```

`Report Run` is a linked-record field and must receive an array.

## Expected Run Result

For `exception_limit = 50`:

```text
HTTP Request                    1 item
Airtable Report runs            1 item
Gmail                           1 item
Code                            50 items
Airtable Coverage Exceptions    50 items
```

## Known Limitation

Repeated test runs create new Airtable records. For a production version, add cleanup/upsert logic to avoid duplicate exception records for the same report run.
