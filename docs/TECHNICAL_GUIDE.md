# Technical Guide

## Architecture Overview

Multi-Agent Ops Assistant is a **multi-agent AI assistant** for retail shift managers, built on **Microsoft Foundry** with the **Microsoft Agent Framework SDK**. It answers real-time operational questions by querying a live **Azure SQL** database and grounding responses with **Azure AI Search** (Foundry IQ) knowledge base.

### Solution Architecture

```
Store Manager (Chat UI — static/index.html)
        │
        ▼  WebSocket
┌─────────────────────────────────┐
│   FastAPI Server (api.py)        │
│   + Orchestrator                 │
└────────────┬────────────────────┘
             │
             ▼
┌─────────────────────────────────┐
│   Triage Agent (gpt-4o-mini)     │  ← Classifies intent, routes to specialist
└────┬───────┬────────┬───────┬───┘
     │       │        │       │
     ▼       ▼        ▼       ▼
┌────────┐ ┌──────────┐ ┌──────────┐ ┌─────────┐
│  Ops   │ │  Diag    │ │ Forecast │ │ Safety  │
│ Agent  │ │  Agent   │ │  Agent   │ │  Agent  │
└───┬────┘ └────┬─────┘ └────┬─────┘ └────┬────┘
    │           │             │            │
    ▼           ▼             ▼            ▼
┌──────────────────────────────────────────────┐
│           Custom Tools (Python)               │
│    Dynamic SQL │ Staff Moves │ Forecasting     │
└──────────────────────┬───────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    Azure SQL     Azure AI      Azure AI
    Database      Search/IQ     Content Safety
```

### Two-Layer Agent Architecture

| Layer | Technology | Role |
|-------|-----------|------|
| Foundry SDK (`azure-ai-projects`) | `agents.create_version()` with `PromptAgentDefinition` | Registers agents in the Foundry portal for visibility and management |
| Agent Framework (`agent-framework-azure-ai`) | `AzureAIClient.as_agent()` | Wraps Foundry agents for orchestration, tool execution, and session memory |

---

## Agent Design

Six agents defined declaratively in YAML configs at `src/agents/configs/`:

| Agent | Model | Tools | Knowledge | Purpose |
|-------|-------|-------|-----------|---------|
| **Triage** | gpt-4o-mini | `route_to_specialist` | No | Silent router — classifies intent and routes to specialist |
| **Operations** | gpt-4o | `run_sql_query` | Yes (Foundry IQ) | Real-time store performance via dynamic SQL |
| **Diagnostics** | gpt-4o | `run_sql_query`, `move_staff_to_station` | Yes (Foundry IQ) | Root cause analysis, staff moves, SOP-grounded recommendations |
| **Forecasting** | gpt-4o | `run_sql_query` | Yes (Foundry IQ) | Demand prediction: 40% historical, 40% run rate, 20% mobile pipeline |
| **Safety** | gpt-4o | `analyze_content_safety` | Yes (Foundry IQ) | On-demand content safety analysis |
| **Quality** | gpt-4o | `get_last_interaction`, `evaluate_response_quality`, `evaluate_agent_tools` | No | Evaluates prior response using Foundry evaluators |

### Routing Strategies (in priority order)

1. **Deterministic keyword regex** — fastest, no LLM call needed
2. **Mutable dict capture** from `route_to_specialist` tool call
3. **Parse tool call arguments** from `AgentResponse` messages
4. **Keyword scan** of response text (last resort)
5. **Default to "operations"** if all else fails

### Model Selection

- **Triage Agent** → GPT-4o-mini (cheaper, faster — only needs classification)
- **Specialist Agents** → GPT-4o (full reasoning for data analysis and recommendations)

---

## Data Layer

### Database: Azure SQL Database

- **Auth:** Entra ID-only (no SQL passwords)
- **TLS:** Minimum 1.2

### Schema (5 tables + 1 view)

| Table | Purpose |
|-------|---------|
| `LiveOrders` | Current in-progress and queued orders (type, station, status, wait time) |
| `StationMetrics` | Station performance (orders/hr, capacity %, staff count, avg wait) |
| `StaffAssignments` | Who is at which station (active assignments with shift times) |
| `HourlyTargets` | Expected order volume by hour and day of week |
| `MobileOrderQueue` | Pending mobile orders with scheduled pickup times |
| `vw_CurrentStoreStatus` | View joining StationMetrics + LiveOrders + MobileOrderQueue for real-time snapshot |

### Dynamic SQL

Agents write their own SQL queries based on the injected schema. This gives agents maximum flexibility to answer any data question.

**Safety guardrails:**
- Regex blocks all write operations (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, `EXEC`, `xp_`, etc.)
- Queries must start with `SELECT`
- 50-row result cap
- 30-second query timeout
- Only `move_staff_to_station` can write (via a dedicated tool, not dynamic SQL)

### Connection Management

- Entra ID token auth via `DefaultAzureCredential` — tokens pre-packed into ODBC struct format
- Token cache with 45-min lifetime (15-min buffer before expiry)
- ODBC connection pooling enabled
- `managed_connection()` context manager ensures cleanup

---

## Project Structure

```
multi-agent-ops-assistant/
├── .devcontainer/           # Dev container configuration
├── .github/                 # GitHub templates and CI/CD workflows
├── database/                # SQL schema and seed data
│   ├── schema.sql           # Table definitions and view
│   └── seed-data.sql        # Demo scenario (cold bar bottleneck)
├── docs/                    # Documentation
│   ├── DEPLOYMENT.md        # Step-by-step deployment guide
│   ├── TECHNICAL_GUIDE.md   # This file — architecture and design
│   └── TRANSPARENCY_FAQ.md  # Responsible AI FAQ
├── hooks/                   # azd lifecycle hooks
│   ├── preprovision.*       # Pre-provision scripts
│   └── postprovision.*      # Post-provision scripts (DB seed, KB upload)
├── infra/                   # Azure infrastructure (Bicep)
│   ├── main.bicep           # Main infrastructure template
│   └── modules/             # Modular Bicep components
├── operational-docs/        # Knowledge base documents (SOPs, playbooks)
├── src/                     # Application source code
│   ├── api.py               # FastAPI server + WebSocket endpoint
│   ├── orchestrator.py      # Agent orchestration logic
│   ├── agents/              # Agent definitions and configs
│   │   ├── configs/         # YAML agent configurations
│   │   ├── knowledge.py     # Foundry IQ knowledge base integration
│   │   └── registry.py      # Tool registry (YAML name → Python callable)
│   ├── config/              # Application settings (env var loading)
│   ├── evals/               # Response quality evaluation
│   ├── guardrails/          # Content safety integration
│   └── tools/               # Agent tools (SQL, staffing, forecasting, etc.)
├── static/                  # Frontend chat UI
├── tests/                   # Integration and performance tests
├── azure.yaml               # Azure Developer CLI configuration
├── Dockerfile               # Container image definition
└── requirements.txt         # Python dependencies
```

---

## Configuration

All configuration is managed through environment variables. See `.env.sample` for a complete list.

### Key Settings

| Variable | Description |
|----------|-------------|
| `AZURE_AI_PROJECT_ENDPOINT` | Microsoft Foundry project endpoint |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | GPT model deployment name (default: `gpt-4o`) |
| `AZURE_AI_SEARCH_ENDPOINT` | Azure AI Search endpoint for Foundry IQ |
| `KNOWLEDGE_BASE_NAME` | Name of the Foundry IQ knowledge base index |
| `SQL_CONNECTION_STRING` | ODBC connection string for Azure SQL |
| `CONTENT_SAFETY_ENDPOINT` | Azure AI Content Safety endpoint |
| `DEFAULT_STORE_ID` | Store identifier for multi-store scenarios |

---

## Local Development

### Prerequisites

- Python 3.11+
- [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
- [ODBC Driver 18 for SQL Server](https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server)

### Setup

```bash
# Clone the repository
git clone https://github.com/microsoft/multi-agent-ops-assistant.git
cd multi-agent-ops-assistant

# Create virtual environment
python -m venv .venv
source .venv/bin/activate        # Linux/macOS
# .venv\Scripts\activate         # Windows

# Install dependencies
pip install --pre -r requirements.txt

# Copy and configure environment variables
cp .env.sample .env
# Edit .env with your Azure resource values

# Login to Azure (for DefaultAzureCredential)
az login

# Run the application
cd src
uvicorn api:app --host 0.0.0.0 --port 8000
```

Then open `http://localhost:8000` in your browser.

---

## Testing

### Integration Tests

```bash
# Run integration tests against deployed instance
python -m pytest tests/ -v
```

The test suite covers:
- Dashboard API endpoints
- Data reset functionality
- Agent routing (operations, diagnostics, forecasting)
- Staff move persistence
- Safety metadata
- Follow-up suggestions

---

## Seed Data Strategy

The seed data creates a deliberate **cold bar bottleneck scenario**: cold bar at 125% capacity with 310-second wait, plus 8 incoming mobile cold orders. This makes the demo narrative immediately compelling — the manager walks into an active problem.

---

## Retry Strategy

Exponential backoff on 429 rate limits — up to 3 retries with 2/4/8 second delays.

---

## Post-Deployment

### Foundry IQ Knowledge Base (Automated)

The knowledge base is created automatically during deployment by the `postprovision` hooks (Step 6: create search index, Step 8: index documents via Azure AI Search REST API). No manual action is required.

### Verify Deployment

```bash
# Check the Container App is running
azd show

# Get the app URL
azd env get-value SERVICE_OPSASSISTANT_URL
```

### Test

```bash
# Open the chat UI in your browser — chat uses WebSocket (/ws)
start $(azd env get-value SERVICE_OPSASSISTANT_URL)

# Or check the dashboard API
curl -s "$(azd env get-value SERVICE_OPSASSISTANT_URL)/api/dashboard"
```

> **Note:** Chat is WebSocket-based (`/ws`), not a REST endpoint. Open the URL in a browser to use the chat UI.

### Tear Down

```bash
azd down --purge --force
```

---

## Test Scenarios

With the demo seed data loaded (cold bar bottleneck + mobile surge scenario):

| Test | Input | Routed To | Expected Response |
|------|-------|-----------|-------------------|
| Status check | "How are we doing?" | Operations Agent | Metrics summary: ~107% pace, cold bar at 125% capacity, 5.2 min avg wait on cold bar, hot bar comfortable at 60% |
| Bottleneck diagnosis | "Why are wait times climbing?" | Diagnostics Agent | Identifies cold bar as bottleneck at 125%, recommends moving Sarah from hot bar (60% capacity) to cold bar, references cold bar surge playbook |
| Demand forecast | "What's coming in the next 30 minutes?" | Forecasting Agent | Reports 8 pending mobile orders (mostly cold drinks), flags surge risk, recommends batch prep and pre-staging |
| Greeting | "Hey, good morning" | Triage (stays) | Warm greeting, offers to help with shift management |
| Follow-up action | "Move Sarah to cold bar" | Diagnostics Agent | Confirms recommendation, projects ~30-40% wait time reduction based on playbook |
| Order mix | "What's the order mix look like?" | Operations Agent | Breakdown of hot/cold/food percentages and in-store/mobile split |

---

## Tech Stack

| Component | Technology |
|---|---|
| Agent Orchestration | Microsoft Agent Framework (Python) |
| Orchestration Pattern | Triage-based routing (custom keyword + LLM classification) |
| Agent Configuration | YAML-driven agent definitions (`src/agents/configs/`) |
| Knowledge Layer | Foundry IQ (Knowledge Bases) |
| Agent Runtime | Azure Container Apps (agents run in-process) |
| Streaming | Real token-by-token streaming via `Agent.run(stream=True)` over WebSocket |
| Models | GPT-4o (specialist agents), GPT-4o-mini (triage) — deployed in Foundry |
| Data Layer | Azure SQL Database (Entra ID-only auth) |
| Guardrails | Azure AI Content Safety (input/output filtering) |
| Evaluation | 9-metric response quality evaluation via `azure-ai-evaluation` |
| Observability | Application Insights via Foundry telemetry (OpenTelemetry) |
| Networking | VNet with private endpoints, Application Gateway (WAF v2) |
| Deployment | Azure Developer CLI (`azd`) with Bicep |

---

## Key References

| Resource | URL |
|---|---|
| Microsoft Agent Framework | https://github.com/microsoft/agent-framework |
| Agent Framework Samples | https://github.com/microsoft/Agent-Framework-Samples |
| Microsoft Foundry | https://learn.microsoft.com/en-us/azure/ai-foundry/ |
| Foundry IQ Overview | https://learn.microsoft.com/en-us/azure/ai-foundry/agents/concepts/what-is-foundry-iq |
| Azure AI Content Safety | https://learn.microsoft.com/en-us/azure/ai-services/content-safety/ |
| Azure Developer CLI (azd) | https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/ |

---

## Notes

- **Preview Status:** Microsoft Agent Framework and Foundry IQ are in preview. APIs may change.
- **Region:** North Central US is recommended for full feature availability.
- **Cost:** Each query invokes the triage agent (GPT-4o-mini) plus one specialist agent (GPT-4o). The triage agent uses GPT-4o-mini to minimize costs.
