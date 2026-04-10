"""
Ops Assistant — configuration loaded from environment / .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of src/)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

# ── Microsoft Foundry ──
AZURE_AI_PROJECT_ENDPOINT = os.environ.get(
    "AZURE_AI_PROJECT_ENDPOINT",
    os.environ.get(
        "AZURE_AI_FOUNDRY_ENDPOINT",
        "https://<your-resource>.services.ai.azure.com/api/projects/<your-project>",
    ),
)
MODEL_DEPLOYMENT_NAME = os.environ.get("AZURE_AI_MODEL_DEPLOYMENT", "gpt-4o")
TRIAGE_MODEL_DEPLOYMENT = os.environ.get("TRIAGE_MODEL_DEPLOYMENT", "gpt-4o-mini")

# ── Azure AI Search (Foundry IQ) ──
SEARCH_ENDPOINT = os.environ.get(
    "AZURE_SEARCH_ENDPOINT",
    "https://<your-search>.search.windows.net",
)
KNOWLEDGE_BASE_NAME = os.environ.get("KNOWLEDGE_BASE_NAME", "ops-assistant-kb")
SEARCH_INDEX_NAME = os.environ.get("SEARCH_INDEX_NAME", "ops-assistant-kb")

# ── SQL Database ──
SQL_SERVER_FQDN = os.environ.get(
    "SQL_SERVER_FQDN", "<your-server>.database.windows.net"
)
SQL_DATABASE_NAME = os.environ.get("SQL_DATABASE_NAME", "ops-assistant-db")

# ── Azure AI Content Safety (guardrails) ──
# Derive from the AI resource name in the project endpoint if not set
_resource_name = ""
if AZURE_AI_PROJECT_ENDPOINT and "//" in AZURE_AI_PROJECT_ENDPOINT:
    _resource_name = AZURE_AI_PROJECT_ENDPOINT.split("//")[1].split(".")[0]

CONTENT_SAFETY_ENDPOINT = os.environ.get(
    "CONTENT_SAFETY_ENDPOINT",
    f"https://{_resource_name}.cognitiveservices.azure.com/" if _resource_name else "",
)

# ── Azure OpenAI endpoint (for Foundry evaluators) ──
AZURE_OPENAI_ENDPOINT = os.environ.get(
    "AZURE_OPENAI_ENDPOINT",
    f"https://{_resource_name}.openai.azure.com/" if _resource_name else "",
)

# ── Azure project context (for logging evaluations to Foundry portal) ──
# Extract project name from endpoint: .../api/projects/<project-name>
_project_name = ""
if AZURE_AI_PROJECT_ENDPOINT and "/projects/" in AZURE_AI_PROJECT_ENDPOINT:
    _project_name = AZURE_AI_PROJECT_ENDPOINT.rstrip("/").rsplit("/", 1)[-1]

AZURE_SUBSCRIPTION_ID = os.environ.get(
    "AZURE_SUBSCRIPTION_ID", ""
)
AZURE_RESOURCE_GROUP = os.environ.get(
    "AZURE_RESOURCE_GROUP", ""
)
AZURE_PROJECT_NAME = os.environ.get(
    "AZURE_PROJECT_NAME", _project_name or ""
)

# ── Store context ──
DEFAULT_STORE_ID = os.environ.get("DEFAULT_STORE_ID", "STORE-001")

# ── Foundry Tracing (OpenTelemetry → Application Insights) ──
ENABLE_FOUNDRY_TRACING = os.environ.get(
    "ENABLE_FOUNDRY_TRACING", "true"
).lower() in ("true", "1", "yes")

# ── Traffic Simulator ──
ENABLE_TRAFFIC_SIMULATOR = os.environ.get(
    "ENABLE_TRAFFIC_SIMULATOR", "false"
).lower() in ("true", "1", "yes")
TRAFFIC_SIMULATOR_INTERVAL_SECS = int(
    os.environ.get("TRAFFIC_SIMULATOR_INTERVAL_SECS", "60")
)
