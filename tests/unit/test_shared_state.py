"""
Unit tests for shared_state.py — thread-safe last interaction storage.
"""
import json
import threading
import pytest


class TestSharedState:
    """Thread-safe shared state for cross-agent communication."""

    def test_update_and_retrieve(self):
        from shared_state import update_last_interaction, get_last_interaction

        update_last_interaction(
            query="How are we doing?",
            response="All stations nominal.",
            agent="Operations Agent",
        )
        last = json.loads(get_last_interaction())

        assert last["query"] == "How are we doing?"
        assert last["response"] == "All stations nominal."
        assert last["agent"] == "Operations Agent"

    def test_tool_calls_stored(self):
        from shared_state import update_last_interaction, get_last_interaction

        update_last_interaction(
            query="test",
            response="result",
            agent="ops",
            tool_calls=[{"name": "run_sql_query", "args": {"sql": "SELECT 1"}}],
            tool_definitions=[{"name": "run_sql_query"}],
        )
        last = json.loads(get_last_interaction())

        assert len(last["tool_calls"]) == 1
        assert last["tool_calls"][0]["name"] == "run_sql_query"
        assert len(last["tool_definitions"]) == 1

    def test_defaults_to_empty(self):
        from shared_state import update_last_interaction, get_last_interaction

        update_last_interaction(query="q", response="r", agent="a")
        last = json.loads(get_last_interaction())

        assert last["tool_calls"] == []
        assert last["tool_definitions"] == []

    def test_overwrite_previous(self):
        from shared_state import update_last_interaction, get_last_interaction

        update_last_interaction(query="first", response="r1", agent="a1")
        update_last_interaction(query="second", response="r2", agent="a2")
        last = json.loads(get_last_interaction())

        assert last["query"] == "second"
        assert last["agent"] == "a2"

    def test_thread_safety(self):
        """Concurrent writes should not corrupt state."""
        from shared_state import update_last_interaction, get_last_interaction

        errors = []

        def writer(idx):
            try:
                for _ in range(100):
                    update_last_interaction(
                        query=f"q-{idx}",
                        response=f"r-{idx}",
                        agent=f"agent-{idx}",
                    )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        last = json.loads(get_last_interaction())
        assert "query" in last
        assert "response" in last
