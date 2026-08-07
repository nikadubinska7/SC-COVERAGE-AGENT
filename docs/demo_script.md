# Demo Script

## 1. Business Problem

Supply-chain teams need to understand whether future Nike/Snipes demand is covered by booked, shipped, or available stock, and where open-order delivery risk remains.

The project automates a manual workflow that would normally require database extracts, Excel pivots, coverage calculations, validation checks, report formatting, and email follow-up.

## 2. Data Layer

Supabase stores the cleaned orderbook data and acts as the source of truth.

The reporting logic filters by:

- banner
- season
- order type
- requested month
- product/category dimensions
- order status and timing risk

## 3. Deterministic Reporting Layer

Python calculates:

- total demand value and volume
- booked/shipped value and volume
- available value and volume
- open-order exposure
- coverage percentage by value and volume
- timing buckets
- cancelled-row exclusion
- reconciliation and validation status

The LLM does not calculate financial metrics. It only explains and interprets validated Python outputs.

## 4. Agent Layer

LangGraph defines the agent workflow:

```text
validate input
-> retrieve Pinecone rules
-> extract Supabase data
-> calculate report
-> validate report
-> generate ReAct observations
```

The ReAct agent uses tools to reason over:

- executive summary
- risk level
- validation status

The `/export-orderbook` endpoint includes these ReAct observations in the JSON response and Gmail body.

## 5. RAG Layer

Pinecone stores reporting rules, validation rules, and data-dictionary knowledge.

The dashboard exposes RAG through:

- `Pinecone Business Rules` panel
- `Ask AI About This Report` chat

The chat answers questions using the current report context and retrieved Pinecone rules.

## 6. Dashboard Layer

The Dash/Plotly dashboard is deployed on Render.

It shows:

- KPI cards
- coverage mix
- coverage gauge
- monthly coverage trend
- season exposure heatmap
- timing risk chart
- coverage summary table
- top open exceptions
- Pinecone-backed rule explanations
- AI report chat

## 7. Automation Layer

n8n runs the autonomous workflow:

```text
Manual Trigger
-> HTTP Request to Render /export-orderbook
-> Google Sheets clears Raw OB
-> Code node prepares representative column labels
-> Google Sheets appends the full filtered orderbook
-> Code node prepares one email payload
-> Gmail notification
```

Gmail sends one email with:

- dashboard link
- Google Sheets link
- export summary
- executive summary
- ReAct agent observations

## 8. Google Sheets Analysis Layer

Google Sheets is used for full-data business analysis and pivot-table exploration.

The n8n workflow refreshes the `Raw OB` tab with the current filtered orderbook export.

`Coverage Summary` contains pivot tables for season, category, timing, value, and volume review.

## 9. Final Value

The final system is an autonomous supply-chain coverage reporting agent that combines:

- reliable deterministic calculations
- LangGraph/ReAct agent observations
- Pinecone RAG explanations
- executive dashboarding
- n8n automation
- Google Sheets pivot-table analysis
- Gmail notification
