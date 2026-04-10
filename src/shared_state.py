"""
Shared state for cross-agent communication in Ops Assistant.

Stores the last interaction (query + response + agent name + tool calls)
so the Quality Agent can evaluate previous responses on demand.

⚠️  SINGLE-USER DEMO ONLY
    This module uses a single process-wide global dict — one slot shared
    by ALL connections.  It is intentionally simple for demo purposes.

    FOR PRODUCTION you would need to:
    - Store conversation history per user/session (e.g., Azure Cosmos DB).
    - Authenticate users (Microsoft Entra ID) and isolate state by user ID.
    - Replace this global dict with a proper session store.
"""

import json
import threading

_lock = threading.Lock()
_last: dict = {
    "query": "",
    "response": "",
    "agent": "",
    "tool_calls": [],
    "tool_definitions": [],
}


def update_last_interaction(
    query: str,
    response: str,
    agent: str,
    tool_calls: list | None = None,
    tool_definitions: list | None = None,
):
    """Store the most recent query-response pair (called by orchestrator).

    Now also stores tool_calls and tool_definitions so the built-in
    Foundry agent evaluators (ToolCallAccuracy, ToolCallSuccess, etc.)
    can assess tool usage quality.
    """
    with _lock:
        _last.update(
            query=query,
            response=response,
            agent=agent,
            tool_calls=tool_calls or [],
            tool_definitions=tool_definitions or [],
        )


def get_last_interaction() -> str:
    """
    Retrieve the last query-response pair from the conversation.
    Used by the Quality Agent to evaluate previous responses.
    Returns the query, response text, which agent handled it,
    and any tool calls / tool definitions captured.
    """
    with _lock:
        if not _last["query"]:
            return json.dumps({"message": "No previous interaction to evaluate yet. Ask a question first, then come back to evaluate it."})
        return json.dumps(_last)
