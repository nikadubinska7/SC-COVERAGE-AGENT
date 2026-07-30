# SC Coverage Report Agent — MVP Scope

## Business objective

Automatically analyze Snipes coverage on Nike/Jordan orders by season and requested month, publish the result to Google Sheets, and send the report link by email.

The workflow replaces the manual process of extracting orderbook data, building coverage pivots, checking delivery risk buckets, formatting the report, and notifying stakeholders.

## Selected use case

Supply-chain coverage reporting for a retail account.

Client/account: Snipes  
Brand scope: Nike and Jordan  
Source type: Mock orderbook database  
Database target: Supabase PostgreSQL  

## Trigger inputs

The MVP workflow accepts the following input:

- `banner`: Snipes
- `seasons`: list of selected seasons
- `order_type`: Standard Order - Futures
- `reporting_date`: ISO date
- `recipient_email`: valid email address

Example:

```json
{
  "banner": "Snipes",
  "seasons": ["SP2026", "SU2026", "FA2026", "HO2026"],
  "order_type": "Standard Order - Futures",
  "reporting_date": "2026-07-16",
  "recipient_email": "user@example.com"
}


Source data

Supabase table:

orderbook

The table is populated with mock data derived from the ORDERBOOK worksheet in the source Excel workbook.

Included statuses

The MVP includes the following statuses in coverage calculations:

Booked/Shipped
Available
Open Order

Cancelled records are excluded from coverage calculations but counted in the validation tab.

Report dimensions

The report groups and filters data by:

Banner
Season
Requested month
Status
Coverage timing bucket
Brand
Age/division
Report metrics

The MVP calculates:

Confirmed wholesale value
Available wholesale value
Booked/Shipped value
Open-order value
Total value
Percentage of total by status
Coverage percentage
Reconciliation difference

Wholesale value is the mandatory MVP metric. Quantity-based reporting is optional and will be added only after confirming the exact quantity field in the source workbook.

Coverage timing buckets

Open orders are grouped into:

Early/On Time
+1 week
+2 weeks
+3 weeks
+4 weeks or later

The exact mapping will be implemented after validating the source workbook field used for ETA versus customer request date.

Google Sheets output

The MVP creates one Google Sheets file with three tabs:

Executive Summary
Coverage by Season
Validation
Success criteria

The MVP is successful when:

N8N triggers the workflow.
The Python LangGraph agent runs without manual intervention.
Supabase data is extracted successfully.
Pinecone reporting rules are retrieved.
Coverage calculations are completed.
Report totals reconcile to source totals.
Monetary reconciliation difference is no more than 0.01.
Google Sheet is created successfully.
Email notification contains a working report URL.
Failures are logged and returned to N8N.
Out of scope for MVP

The following are excluded from the MVP:

Multiple clients
PDF export
Advanced dashboard
Scheduled weekly automation
Historical availability snapshots
All Excel tabs from the original workbook
Manual business comments
Real-time monitoring
Full MCP server deployment
Multi-company comparison
Human approval before email