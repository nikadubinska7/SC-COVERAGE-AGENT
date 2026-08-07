# Architecture

## Final System Diagram

```mermaid
flowchart LR
    A[Raw orderbook Excel] --> B[Cleaned CSV]
    B --> C[Supabase orderbook table]

    C --> D[Dash / Plotly Dashboard on Render]
    D --> E[/export-orderbook HTTP endpoint]

    F[n8n Manual Trigger] --> G[HTTP Request to /export-orderbook]
    G --> H[Google Sheets: clear Raw OB]
    H --> I[Code: prepare representative row keys]
    I --> J[Google Sheets: append Raw OB rows]
    J --> K[Code: prepare one email payload]
    K --> T[Gmail: dashboard + Google Sheets links]

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
3. n8n triggers the Render `/export-orderbook` endpoint through an HTTP Request node.
4. `/export-orderbook` calculates report KPIs, validation results, and ReAct agent observations, then returns the filtered raw orderbook rows.
5. n8n clears the Google Sheets `Raw OB` tab.
6. n8n converts raw snake_case fields into representative Google Sheets column labels.
7. n8n appends the full filtered orderbook to Google Sheets.
8. Gmail sends one email containing the dashboard link, Google Sheets link, export summary, and ReAct agent observations.

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

The production `/export-orderbook` endpoint reuses the same deterministic calculation services and calls the ReAct observation generator with fallback behavior. This makes the agent reasoning visible in the automated email/report payload while keeping the deployed dashboard fast and stable.

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
- Google Sheets n8n connector for full orderbook pivot-table export.
- Gmail n8n connector for notifications.
- Render-hosted HTTP endpoint for workflow triggering.

## Design Decision

The original brief planned Google Sheets as the report destination. During execution, the final design kept Google Sheets for analysis and added a professional dashboard and agent layer:

```text
Dash/Plotly dashboard + Google Sheets pivot workflow
```

Reason:

- Dash gives a more professional executive interface.
- Google Sheets supports familiar pivot-table exploration for the full filtered orderbook.
- Supabase remains the source of truth for the full orderbook.
- n8n refreshes Google Sheets automatically and sends the shareable links by Gmail.

Google Sheets is the analyst layer. The n8n workflow calls `/export-orderbook`, refreshes the `Raw OB` tab, and relies on manually created pivots in `Coverage Summary` for Excel-like analysis.
