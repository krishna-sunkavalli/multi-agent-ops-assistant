"""
Unit tests for config/settings.py — environment variable parsing and defaults.
"""
import os
import pytest


class TestDefaultValues:
    """Settings module provides sensible defaults."""

    def test_default_store_id(self):
        from config.settings import DEFAULT_STORE_ID
        assert DEFAULT_STORE_ID == os.environ.get("DEFAULT_STORE_ID", "STORE-001")

    def test_default_model_deployment(self):
        from config.settings import MODEL_DEPLOYMENT_NAME
        assert MODEL_DEPLOYMENT_NAME == os.environ.get("AZURE_AI_MODEL_DEPLOYMENT", "gpt-4o")

    def test_default_triage_model(self):
        from config.settings import TRIAGE_MODEL_DEPLOYMENT
        assert TRIAGE_MODEL_DEPLOYMENT == os.environ.get("TRIAGE_MODEL_DEPLOYMENT", "gpt-4o-mini")

    def test_default_knowledge_base_name(self):
        from config.settings import KNOWLEDGE_BASE_NAME
        assert KNOWLEDGE_BASE_NAME == os.environ.get("KNOWLEDGE_BASE_NAME", "ops-assistant-kb")

    def test_default_search_index(self):
        from config.settings import SEARCH_INDEX_NAME
        assert SEARCH_INDEX_NAME == os.environ.get("SEARCH_INDEX_NAME", "ops-assistant-kb")

    def test_default_database_name(self):
        from config.settings import SQL_DATABASE_NAME
        assert SQL_DATABASE_NAME == os.environ.get("SQL_DATABASE_NAME", "ops-assistant-db")


class TestContentSafetyEndpointDerivation:
    """Content safety endpoint derived from AI project endpoint."""

    def test_endpoint_derived_from_project(self):
        from config.settings import AZURE_AI_PROJECT_ENDPOINT, CONTENT_SAFETY_ENDPOINT

        if AZURE_AI_PROJECT_ENDPOINT and "//" in AZURE_AI_PROJECT_ENDPOINT:
            resource = AZURE_AI_PROJECT_ENDPOINT.split("//")[1].split(".")[0]
            if resource and not os.environ.get("CONTENT_SAFETY_ENDPOINT"):
                assert resource in CONTENT_SAFETY_ENDPOINT


class TestTracingConfig:
    """Tracing and simulator boolean parsing."""

    def test_tracing_defaults_true(self):
        from config.settings import ENABLE_FOUNDRY_TRACING
        env_val = os.environ.get("ENABLE_FOUNDRY_TRACING", "true").lower()
        expected = env_val in ("true", "1", "yes")
        assert ENABLE_FOUNDRY_TRACING == expected

    def test_simulator_defaults_false(self):
        from config.settings import ENABLE_TRAFFIC_SIMULATOR
        env_val = os.environ.get("ENABLE_TRAFFIC_SIMULATOR", "false").lower()
        expected = env_val in ("true", "1", "yes")
        assert ENABLE_TRAFFIC_SIMULATOR == expected

    def test_simulator_interval_is_int(self):
        from config.settings import TRAFFIC_SIMULATOR_INTERVAL_SECS
        assert isinstance(TRAFFIC_SIMULATOR_INTERVAL_SECS, int)
        assert TRAFFIC_SIMULATOR_INTERVAL_SECS > 0
