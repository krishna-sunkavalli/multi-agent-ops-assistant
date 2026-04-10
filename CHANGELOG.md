# Changelog

All notable changes to the Multi-Agent Ops Assistant solution accelerator.

## [1.0.0] - 2025-04-10

### Added

- **Multi-agent orchestration** — Triage agent routes queries to 5 specialist agents (Operations, Forecasting, Safety, Quality, Diagnostics) via Microsoft Agent Framework
- **Foundry IQ knowledge base** — Operational documents indexed in Azure AI Search with automatic RAG retrieval
- **Real-time SQL analytics** — Dynamic read-only SQL generation against Azure SQL for live operational data (orders, staffing, stations)
- **Content safety guardrails** — Azure AI Content Safety integration with configurable severity thresholds
- **Foundry tracing** — OpenTelemetry distributed traces for every LLM call, tool execution, and agent run
- **Response evaluation** — Built-in evaluators for groundedness, relevance, coherence, and fluency
- **Traffic simulator** — Optional background order generator for realistic demo scenarios
- **One-click deployment** — `azd up` provisions all infrastructure, seeds database, creates knowledge base, and deploys the app
- **Infrastructure as Code** — Full Bicep templates using Azure Verified Modules (AVM)
- **Managed identity everywhere** — No passwords or connection strings; Entra ID authentication for all services
- **Private endpoint support** — Optional `USE_PRIVATE_ENDPOINTS` toggle for enterprise networking
- **GitHub Codespaces & Dev Containers** — Pre-configured development environments with all required tools
