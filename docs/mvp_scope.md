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
git status
git add docs/mvp_scope.md docs/coverage_rules.md docs/data_dictionary.md docs/architecture.md
git commit -m "Document MVP scope and coverage rules"

ls docs
ls docs

