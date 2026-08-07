# Architecture

## Final System Diagram

```mermaid
flowchart LR
    A[Raw orderbook Excel] --> B[Cleaned CSV]
    B --> C[Supabase orderbook table]

    C --> D[Dash / Plotly Dashboard on Render]
    D --> E[/run-report HTTP endpoint]

    F[n8n Manual Trigger] --> G[HTTP Request to /run-report]
    G --> H[Airtable: Report runs]
    H --> I[Gmail: dashboard + review links]
    I --> J[Code: split coverage_exceptions]
    J --> K[Airtable: Coverage Exceptions]

    C --> L[LangGraph workflow]
    L --> M[Deterministic coverage calculations]
    L --> N[ReAct agent observations]

    O[Knowledge markdown files] --> P[Pinecone vector index]
    P --> Q[Pinecone Business Rules panel]
    P --> R[Ask AI chat]
    D --> Q
    D --> R
```

## Production Workflow

1. Cleaned orderbook data is loaded into Supabase.
2. The Dash dashboard on Render reads Supabase and builds the executive report.
3. n8n triggers the Render `/run-report` endpoint through an HTTP Request node.
4. `/run-report` calculates report KPIs, validation results, prioritized coverage exceptions, and ReAct agent observations.
5. n8n creates one Airtable `Report runs` record.
6. Gmail sends one email containing the dashboard link and Airtable exception-review link.
7. n8n splits the `coverage_exceptions` array into individual items.
8. n8n creates Airtable `Coverage Exceptions` records for business review and follow-up.

## Agent Layer

The agent layer is implemented in Python and consists of:

- `src/graph.py` - LangGraph orchestration.
- `src/agent.py` - ReAct-style reasoning over deterministic report outputs.
- `src/tools/pinecone_tool.py` - RAG retrieval from Pinecone.
- `src/tools/supabase_tool.py` - orderbook extraction from Supabase.
- `src/services/transformations.py` - deterministic calculations and validation.

LangGraph coordinates:

```text
validate_input
-> retrieve_rules
-> extract_data
-> calculate_report
-> validate_report
-> generate_observations
-> export_local_report
```

The production `/run-report` endpoint reuses the same deterministic calculation services and calls the ReAct observation generator with fallback behavior. This makes the agent reasoning visible in the automated email/report payload while keeping the deployed dashboard fast and stable.

## Pinecone RAG

Knowledge files in `data/knowledge/` are embedded into Pinecone with:

```text
Embedding model: text-embedding-3-small
Namespace: coverage_rules
Chunking: 900-character chunks with 150-character overlap
```

The dashboard uses Pinecone in two visible ways:

1. `Pinecone Business Rules` panel retrieves relevant reporting-rule snippets for the current report context.
2. `Ask AI About This Report` retrieves Pinecone rule snippets for each user question and combines them with current raw-data-derived report context.

The chat does not send the entire raw orderbook to the LLM. Python first derives compact, deterministic summaries from the currently filtered Supabase dataframe:

- highest-risk category by open-order exposure
- category and sub-category risk summaries
- top raw open-order rows
- coverage summary
- timing-risk summary
- validation results

The LLM receives these summaries plus Pinecone rule snippets. This makes answers data-grounded and rule-grounded without asking the model to calculate financial metrics.

## Deterministic Reporting Logic

Financial and operational calculations are not delegated to the LLM.

Python services calculate:

- total value and volume
- booked/shipped coverage
- available coverage
- open-order exposure
- value and volume coverage percentages
- timing buckets
- cancelled-row exclusion
- reconciliation and validation differences
- prioritized coverage exceptions

The LLM is used only for:

- concise report observations
- business interpretation
- Pinecone-grounded Q&A

## Tool/API Integrations

The project uses real APIs/connectors:

- Supabase API for orderbook data.
- Pinecone API for RAG retrieval.
- OpenAI API for embeddings and report chat/observations.
- Airtable n8n connector for review tables.
- Google Sheets n8n connector for full orderbook pivot-table export.
- Gmail n8n connector for notifications.
- Render-hosted HTTP endpoint for workflow triggering.

## Design Decision

The original brief planned Google Sheets as the report destination. During execution, the design moved to:

```text
Dash/Plotly dashboard + Airtable review workflow
```

Reason:

- Dash gives a more professional executive interface.
- Airtable supports filtering, grouping, ownership, comments, and review statuses.
- Supabase remains the source of truth for the full orderbook.
- Airtable receives only prioritized exceptions, avoiding duplicate raw-data storage.

Google Sheets is used as an optional analyst layer. A separate n8n workflow calls `/export-orderbook`, refreshes a `Raw Orderbook` tab, and relies on pre-created pivot-table tabs for Excel-like analysis.
