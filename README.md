# SC Coverage Agent

Streamlit is the primary reporting interface for the SC Coverage Report Agent.

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

Required local environment variables are loaded from `.env` and are not committed:

- `SUPABASE_URL`
- `SUPABASE_KEY`
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_INDEX_NAME`
