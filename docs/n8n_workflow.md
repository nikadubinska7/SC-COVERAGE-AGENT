# N8N Workflow: Streamlit Report Link by Gmail

This project uses Streamlit as the primary SC Coverage Report interface. The n8n workflow validates/generates the current report payload, then emails the Streamlit dashboard link through Gmail.

## Files

- Workflow import: `workflows/sc_coverage_report_gmail_workflow.json`
- Python runner for n8n: `scripts/run_report_for_n8n.py`
- Dashboard app: `app.py`

## How it works

1. Manual Trigger or Weekly Schedule starts the workflow.
2. Report Config sets the report scope and dashboard link.
3. Execute Command runs:

```bash
venv/bin/python scripts/run_report_for_n8n.py
```

4. The runner queries Supabase, rebuilds deterministic coverage metrics, retrieves RAG rules when available, generates observations with fallback behavior, and prints one clean JSON object.
5. n8n parses the JSON.
6. If report status is `success` and validation passed, Gmail sends the report-ready email.
7. Otherwise Gmail sends a failure email.

## Required setup

Start the dashboard first:

```bash
streamlit run app.py
```

Set these environment variables in the shell or service that runs n8n:

```bash
export STREAMLIT_DASHBOARD_URL="http://localhost:8501"
export N8N_SC_REPORT_RECIPIENT_EMAIL="your.email@gmail.com"
export N8N_SC_REPORT_RECIPIENT_NAME="Your Name"
```

If the email should open on another device, use a deployed/public Streamlit URL instead of `localhost`.

## Import into n8n

1. Open n8n.
2. Import `workflows/sc_coverage_report_gmail_workflow.json`.
3. Open both Gmail nodes.
4. Select or create your Gmail OAuth2 credential.
5. Check the Report Config node:
   - `projectPath`
   - `banner`
   - `seasons`
   - `orderType`
   - `dashboardUrl`
   - `recipientEmail`
6. Run Manual Trigger once.
7. If the test email is correct, activate the Weekly Schedule trigger.

## Important local/cloud note

This workflow uses the n8n Execute Command node. It works when n8n runs locally or on a server that can access this project directory.

If you use n8n Cloud, Execute Command is not available. In that case, deploy the Python runner behind an HTTP endpoint or run n8n self-hosted for this workflow.

## Validate the runner manually

From the project root:

```bash
venv/bin/python scripts/run_report_for_n8n.py \
  --dashboard-url "$STREAMLIT_DASHBOARD_URL" \
  --recipient-name "$N8N_SC_REPORT_RECIPIENT_NAME"
```

Expected output is one JSON object with:

- `status`
- `dashboard_url`
- `email_subject`
- `email_body`
- `validation_passed`
- value and volume metrics
- observations
- RAG rules used when available
