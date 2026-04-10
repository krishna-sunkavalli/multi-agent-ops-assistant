"""
Unit tests for agent registry — route capture, config loading, YAML validation.
"""
import pytest


# ── Tests: route capture mechanism ───────────────────────────────────

class TestRouteCapture:
    """route_to_specialist, get/clear captured route."""

    def test_capture_and_retrieve(self):
        from agents.registry import route_to_specialist, get_captured_route, clear_captured_route

        clear_captured_route()
        route_to_specialist("operations")
        assert get_captured_route() == "operations"

    def test_clear_resets_to_none(self):
        from agents.registry import route_to_specialist, get_captured_route, clear_captured_route

        route_to_specialist("diagnostics")
        clear_captured_route()
        assert get_captured_route() is None

    def test_overwrite_with_new_route(self):
        from agents.registry import route_to_specialist, get_captured_route, clear_captured_route

        clear_captured_route()
        route_to_specialist("operations")
        route_to_specialist("forecasting")
        assert get_captured_route() == "forecasting"

    def test_case_normalization(self):
        from agents.registry import route_to_specialist, get_captured_route, clear_captured_route

        clear_captured_route()
        route_to_specialist("  Operations  ")
        assert get_captured_route() == "operations"

    def test_returns_confirmation_string(self):
        from agents.registry import route_to_specialist

        result = route_to_specialist("diagnostics")
        assert "diagnostics" in result.lower()


# ── Tests: valid routes ──────────────────────────────────────────────

class TestValidRoutes:
    """VALID_ROUTES should contain all expected specialist agents."""

    def test_contains_all_specialists(self):
        from agents.registry import VALID_ROUTES

        expected = {"operations", "diagnostics", "forecasting", "safety", "quality"}
        assert VALID_ROUTES == expected

    def test_no_triage_in_valid_routes(self):
        from agents.registry import VALID_ROUTES

        assert "triage" not in VALID_ROUTES


# ── Tests: AGENT_CONFIGS loaded from YAML ────────────────────────────

class TestAgentConfigs:
    """YAML configs loaded once at import time."""

    def test_all_agents_loaded(self):
        from agents.registry import AGENT_CONFIGS

        expected = {"triage", "operations", "diagnostics", "forecasting", "safety", "quality"}
        assert set(AGENT_CONFIGS.keys()) == expected

    def test_each_config_has_required_keys(self):
        from agents.registry import AGENT_CONFIGS

        for name, cfg in AGENT_CONFIGS.items():
            assert "instructions" in cfg, f"{name} missing instructions"
            assert "tools" in cfg, f"{name} missing tools"
            assert "use_knowledge" in cfg, f"{name} missing use_knowledge"
            assert isinstance(cfg["instructions"], str), f"{name} instructions not string"
            assert isinstance(cfg["tools"], list), f"{name} tools not list"

    def test_triage_has_route_tool(self):
        from agents.registry import AGENT_CONFIGS

        triage = AGENT_CONFIGS["triage"]
        tool_names = [t.__name__ for t in triage["tools"]]
        assert "route_to_specialist" in tool_names

    def test_operations_has_sql_tools(self):
        from agents.registry import AGENT_CONFIGS

        ops = AGENT_CONFIGS["operations"]
        tool_names = [t.__name__ for t in ops["tools"]]
        assert "run_sql_query" in tool_names

    def test_display_names_set(self):
        from agents.registry import AGENT_CONFIGS

        for name, cfg in AGENT_CONFIGS.items():
            assert "display_name" in cfg
            assert cfg["display_name"].startswith("OpsAssistant-")

    def test_tools_are_callable(self):
        from agents.registry import AGENT_CONFIGS

        for name, cfg in AGENT_CONFIGS.items():
            for tool_fn in cfg["tools"]:
                assert callable(tool_fn), f"{name} has non-callable tool: {tool_fn}"


# ── Tests: TOOL_REGISTRY ─────────────────────────────────────────────

class TestToolRegistry:
    """Global tool registry maps names to callables."""

    def test_all_entries_callable(self):
        from agents.registry import TOOL_REGISTRY

        for name, fn in TOOL_REGISTRY.items():
            assert callable(fn), f"TOOL_REGISTRY['{name}'] is not callable"

    def test_route_to_specialist_registered(self):
        from agents.registry import TOOL_REGISTRY

        assert "route_to_specialist" in TOOL_REGISTRY

    def test_core_tools_registered(self):
        from agents.registry import TOOL_REGISTRY

        expected = [
            "get_store_metrics", "get_order_mix",
            "get_station_throughput", "get_staffing_positions",
            "run_sql_query", "get_database_schema",
        ]
        for tool_name in expected:
            assert tool_name in TOOL_REGISTRY, f"Missing tool: {tool_name}"
