# SC Coverage Agent

Streamlit and Dash reporting interfaces are available for the SC Coverage Report Agent.

The Dash app is the executive-style dashboard. The Streamlit app remains available as the original reporting interface.

## Run the executive Dash dashboard

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the Dash app:

```bash
python dash_app.py
```

Open:

```text
http://localhost:8050
```

## Run the dashboard

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
streamlit run app.py
```

The dashboard loads orderbook records from Supabase, applies sidebar filters, rebuilds deterministic coverage metrics, shows Value/Volume views, displays agent observations, and exposes the reporting rules retrieved from Pinecone when available.

## N8N Gmail workflow

Import the workflow at:

```text
workflows/sc_coverage_report_gmail_workflow.json
```

Setup instructions are in:

```text
docs/n8n_workflow.md
```

The workflow runs the local report agent, validates the report payload, and sends the Streamlit dashboard link to Gmail.

Required local environment variables are loaded from `.env` and are not committed:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
- `STREAMLIT_DASHBOARD_URL`
- `N8N_SC_REPORT_RECIPIENT_EMAIL`
- `N8N_SC_REPORT_RECIPIENT_NAME`
