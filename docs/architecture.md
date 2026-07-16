 Architecture

## MVP workflow

```text
N8N Trigger
  ↓
Python Agent Runner
  ↓
LangGraph Workflow
  ↓
Retrieve Rules from Pinecone
  ↓
Extract Data from Supabase
  ↓
Calculate Coverage in Python
  ↓
Validate Report
  ↓
Generate Report Commentary
  ↓
Publish Google Sheet
  ↓
Send Gmail Notification
Main components
Component	Role
N8N	External workflow trigger and orchestration
Python	Main backend runtime
LangGraph	Agent workflow, state and routing
LangChain	Tool wrapping
ReAct agent	Reasoning and tool selection
Pinecone	RAG store for reporting rules
Supabase	Mock orderbook database
Google Sheets API	Report publishing
Gmail API	Email notification
OpenAI	LLM reasoning and commentary
LangGraph nodes

The planned nodes are:

validate_input
retrieve_rules
run_react_agent
extract_data
transform_data
validate_report
generate_commentary
publish_google_sheet
send_email
handle_failure
State object

The workflow passes a state object containing:

banner
seasons
order_type
reporting_date
recipient_email
rules
raw_records
report_data
validation_results
observations
report_url
errors
status
Design principle

The LLM controls reasoning and tool selection, but deterministic Python controls all financial calculations and validations.