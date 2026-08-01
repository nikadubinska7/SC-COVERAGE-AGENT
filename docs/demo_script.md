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

The `/run-report` endpoint includes these ReAct observations in the JSON response and Gmail body.

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
-> HTTP Request to Render /run-report
-> Airtable Report runs record
-> Gmail notification
-> Code node splits coverage exceptions
-> Airtable Coverage Exceptions records
```

Gmail sends one email with:

- dashboard link
- Airtable exception-review link
- executive summary
- ReAct agent observations

## 8. Airtable Review Layer

Airtable is used for business follow-up, not as the raw database.

`Report runs` tracks each generated report.

`Coverage Exceptions` stores the top open-order risks for review, filtering, grouping, ownership, comments, and status tracking.

## 9. Final Value

The final system is an autonomous supply-chain coverage reporting agent that combines:

- reliable deterministic calculations
- LangGraph/ReAct agent observations
- Pinecone RAG explanations
- executive dashboarding
- n8n automation
- Airtable operational review
- Gmail notification
