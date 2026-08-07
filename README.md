# SC Coverage Agent

Autonomous supply-chain coverage reporting agent for Nike/Snipes future orderbook analysis.

The project combines deterministic reporting, a LangGraph/ReAct agent layer, Pinecone RAG, an executive Dash/Plotly dashboard, n8n automation, Google Sheets pivot analysis, and Gmail notification.

## Final Workflow

```text
Supabase orderbook data
  -> Dash/Plotly dashboard deployed on Render
  -> n8n calls /export-orderbook for Google Sheets pivot analysis
  -> Python calculates coverage metrics and validation
  -> LangGraph/ReAct generates report observations
  -> Pinecone provides business-rule context for dashboard explanations/chat
  -> Google Sheets stores the full filtered orderbook for pivots
  -> Gmail sends dashboard and Google Sheets links with agent observations
```

## Main Components

- `dash_app.py` - Render-deployed Dash dashboard, `/run-report`, and `/export-orderbook` endpoints.
- `src/graph.py` - LangGraph workflow for validation, RAG retrieval, Supabase extraction, calculation, validation, ReAct observations, and local export.
- `src/agent.py` - ReAct-style agent using tools for summary, risk, and validation reasoning.
- `src/tools/pinecone_tool.py` - Pinecone retrieval tool for reporting rules.
- `src/tools/supabase_tool.py` - Supabase orderbook extraction.
- `src/services/transformations.py` - deterministic coverage calculations and validation inputs.
- `scripts/ingest_pinecone.py` - ingests markdown reporting knowledge into Pinecone.
- `scripts/load_supabase.py` - loads processed orderbook data into Supabase.
- `docs/architecture.md` - final architecture diagram and workflow explanation.
- `docs/n8n_workflow.md` - n8n setup and field mapping notes.
- `docs/google_sheets_workflow.md` - Google Sheets export and pivot-table workflow.

## Core Deliverables

- Supabase data layer: cleaned orderbook stored and queried as the source of truth.
- LangGraph orchestration: graph-based agent workflow for input validation, retrieval, extraction, calculation, validation, and observations.
- ReAct agent reasoning: tool-based observations included in report payloads and Gmail notifications.
- Pinecone RAG: reporting rules and validation knowledge retrieved for dashboard explanations and AI chat.
- Dash/Plotly dashboard: executive report deployed on Render.
- n8n automation: report/export workflow that refreshes Google Sheets and sends Gmail notification.
- Google Sheets analysis layer: full filtered orderbook export with reusable pivot tables.

## Business Outputs

The dashboard reports:

- value coverage and volume coverage
- booked/shipped, available, and open-order exposure
- timing risk by requested month
- season/category/sub-category filters
- validation and reconciliation status
- top open-order exceptions
- Pinecone-backed business rule explanations
- AI chat grounded in current filtered orderbook summaries and retrieved Pinecone rules

n8n creates:

- a refreshed Google Sheets `Raw OB` export for the selected report scope
- reusable pivot tables in `Coverage Summary`
- one Gmail notification containing dashboard and Google Sheets links
- ReAct agent observations in the Gmail body

## Environment Variables

Required locally and on Render:

```text
SUPABASE_URL
SUPABASE_KEY
OPENAI_API_KEY
PINECONE_API_KEY
PINECONE_INDEX_NAME
```

Optional:

```text
OPENAI_CHAT_MODEL=gpt-4o-mini
```

## Run Locally

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the Dash dashboard:

```bash
python dash_app.py
```

Open:

```text
http://localhost:8050
```

## Load Data

Prepare/load the processed orderbook into Supabase:

```bash
python scripts/load_supabase.py
```

Ingest reporting rules into Pinecone:

```bash
python scripts/ingest_pinecone.py
```

## n8n Automation

The Google Sheets analyst workflow uses:

```text
Manual Trigger
-> HTTP Request to Render /export-orderbook
-> Google Sheets: clear Raw OB
-> Code: convert raw row keys into representative column labels
-> Google Sheets: append Raw OB rows
-> Code: prepare one email payload
-> Gmail: send dashboard/Google Sheets links and agent observations
```

The Google Sheets workflow writes the full filtered orderbook to the `Raw OB` tab. The `Coverage Summary` tab contains manually created pivot tables for season/category/timing analysis.

The HTTP Request body includes:

```json
{
  "banner": "Snipes",
  "seasons": ["HO2026", "SP2027"],
  "order_type": "Standard Order - Futures",
  "dashboard_url": "https://sc-coverage-dashboard.onrender.com",
  "google_sheet_url": "https://docs.google.com/spreadsheets/d/..."
}
```

## Validation

Run tests:

```bash
python -m pytest
```

Current test coverage validates:

- transformation logic
- coverage percentages
- cancelled-row exclusion
- reconciliation checks
- dashboard data helpers
- n8n payload behavior
- Google Sheets export payload and agent observations

## Design Decision

The original plan used Google Sheets as the main report output. During execution, the project evolved into a more business-ready workflow:

```text
Dash/Plotly = executive dashboard
Google Sheets = full-data pivot analysis
Gmail = notification
Supabase = source of truth
Pinecone + LangGraph/ReAct = agent reasoning/context layer
```

This keeps calculations deterministic while using AI for rule-grounded explanations and observations.

## AI Chat Grounding

The dashboard chat does not ask the LLM to scan the full raw database directly. Instead, Python derives compact summaries from the currently filtered Supabase/orderbook dataframe:

- highest-risk category by open-order value
- category risk summary
- sub-category risk summary
- top raw open-order rows by exposure
- coverage, timing, and validation summaries

For each user question, the app retrieves relevant Pinecone rule chunks and sends both the raw-data-derived context and the retrieved rules to the LLM. This keeps answers tied to actual data while satisfying the Pinecone RAG requirement.
