# SC Coverage Agent

Autonomous supply-chain coverage reporting agent for Nike/Snipes future orderbook analysis.

The project combines deterministic reporting, a LangGraph/ReAct agent layer, Pinecone RAG, an executive Dash/Plotly dashboard, n8n automation, Airtable review tracking, and Gmail notification.

## Final Workflow

```text
Supabase orderbook data
  -> Dash/Plotly dashboard deployed on Render
  -> n8n HTTP Request calls /run-report
  -> Python calculates coverage metrics and validation
  -> ReAct agent generates report observations
  -> Pinecone provides business-rule context for dashboard explanations/chat
  -> Airtable stores report runs and coverage exceptions
  -> Gmail sends the dashboard and Airtable review links
```

## Main Components

- `dash_app.py` - Render-deployed Dash dashboard and `/run-report` endpoint.
- `src/graph.py` - LangGraph workflow for validation, RAG retrieval, Supabase extraction, calculation, validation, ReAct observations, and local export.
- `src/agent.py` - ReAct-style agent using tools for summary, risk, and validation reasoning.
- `src/tools/pinecone_tool.py` - Pinecone retrieval tool for reporting rules.
- `src/tools/supabase_tool.py` - Supabase orderbook extraction.
- `src/services/transformations.py` - deterministic coverage calculations and validation inputs.
- `scripts/ingest_pinecone.py` - ingests markdown reporting knowledge into Pinecone.
- `scripts/load_supabase.py` - loads processed orderbook data into Supabase.
- `docs/architecture.md` - final architecture diagram and workflow explanation.
- `docs/n8n_workflow.md` - n8n setup and field mapping notes.

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

- one Airtable `Report runs` record per workflow run
- prioritized Airtable `Coverage Exceptions` records for review/action
- one Gmail notification containing dashboard and Airtable review links

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

The n8n workflow uses:

```text
Manual Trigger
-> HTTP Request to Render /run-report
-> Airtable: create Report runs record
-> Gmail: send dashboard/review links
-> Code: split coverage_exceptions array
-> Airtable: create Coverage Exceptions records
```

The HTTP Request body includes:

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

## Design Decision

The original plan used Google Sheets as the main report output. During execution, the project evolved into a more business-ready workflow:

```text
Dash/Plotly = executive dashboard
Airtable = operational exception review
Gmail = notification
Supabase = source of truth
Pinecone + ReAct = agent reasoning/context layer
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
