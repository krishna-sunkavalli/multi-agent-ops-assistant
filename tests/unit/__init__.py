"""
Unit test package for Multi-Agent Ops Assistant.

Pre-mocks heavy Azure SDK dependencies that aren't available in local
test environments (no ODBC drivers, no agent framework SDK match, etc.).
This runs before any test module in this package is imported.
"""
import sys
from unittest.mock import MagicMock

# Mock native/C-extension modules not available locally
for mod_name in [
    "pyodbc",
    "agent_framework_azure_ai",
    "azure.ai.projects",
    "azure.ai.projects.models",
]:
    sys.modules.setdefault(mod_name, MagicMock())