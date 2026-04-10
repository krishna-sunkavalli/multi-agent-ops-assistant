# Multi-Agent Ops Assistant

A solution accelerator for building **AI-powered operations assistants** using [Microsoft Agent Framework](https://github.com/microsoft/agent-framework) and [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/). It demonstrates how specialized AI agents — each with distinct expertise — can collaborate through triage-based orchestration to answer real-time operational questions, diagnose bottlenecks, forecast demand, and execute staffing changes, all through natural language conversation.

This accelerator can be adapted to any industry where a frontline manager needs real-time, AI-driven operational insights — **retail store management, hotel operations, warehouse logistics, healthcare unit coordination**, and more. The included implementation showcases a **quick-service restaurant (QSR) shift manager copilot** branded as **ShiftIQ**.
<br/>

<div align="center">

[**SOLUTION OVERVIEW**](#solution-overview)  \| [**QUICK DEPLOY**](#quick-deploy)  \| [**BUSINESS SCENARIO**](#business-scenario)  \| [**SUPPORTING DOCUMENTATION**](#supporting-documentation)

</div>
<br/>

**Note:** With any AI solutions you create using these templates, you are responsible for assessing all associated risks and for complying with all applicable laws and safety standards. Learn more in the transparency documents for [Agent Service](https://learn.microsoft.com/en-us/azure/ai-foundry/responsible-ai/agents/transparency-note) and [Agent Framework](https://github.com/microsoft/agent-framework/blob/main/TRANSPARENCY_FAQ.md).
<br/>

> [!CAUTION]
> **Single-User Demo Accelerator** — This solution accelerator is designed as a **single-user demonstration** and is **not production-ready as-is**. Key limitations include:
> - **No conversation persistence** — Chat history is held in-memory and lost on refresh or disconnect.
> - **No user authentication** — Every WebSocket connection is anonymous; there is no user identity or session tracking.
> - **Shared global state** — The last interaction is stored in a single process-wide variable, not per-user.
> - **No multi-tenancy** — All connections share the same agent instances and store context.
>
> To move toward production, you would need to add user authentication (e.g., Microsoft Entra ID), per-user conversation storage (e.g., Azure Cosmos DB or Azure SQL), session management, and multi-tenant data isolation.
<br/>

<h2><img src="docs/images/readme/solution-overview.png" width="32" alt=""/> Solution overview </h2>

This solution accelerator provides a reference architecture for building multi-agent operations assistants on Azure. Multiple AI agents — each with distinct expertise — collaborate through a triage-based orchestrator to deliver real-time, data-driven answers and SOP-grounded recommendations via natural language conversation.

The accelerator is built with **Microsoft Agent Framework** for agent orchestration and **Microsoft Foundry** for model hosting, evaluation, and knowledge management. It is designed to be adapted to various operational domains by swapping the data model, agent configurations, and knowledge base.

**Included demo scenario:** A QSR shift manager copilot (**ShiftIQ**) that uses Microsoft Foundry, Azure AI Search (Foundry IQ), Azure SQL Database, and Azure Container Apps to help coffee shop managers monitor store performance, diagnose bottlenecks, forecast demand, and execute staffing moves. The sample data simulates a busy morning rush with a deliberate cold bar bottleneck. All data is synthetic and intended for demonstration purposes only.

### Solution architecture (QSR demo)

```
QSR Shift Manager (ShiftIQ Chat UI)
        │  WebSocket
        ▼
┌──────────────────────────────────────┐
│   FastAPI + Orchestrator              │  Azure Container Apps
│   (Triage-Based Routing)              │  (VNet-integrated)
└────────────┬─────────────────────────┘
             │                              Optional: App Gateway (WAF v2)
     ┌───────┼───────┬───────┬───────┐        when CUSTOM_HOSTNAME is set
     ▼       ▼       ▼       ▼       ▼
  Triage   Ops    Diag   Forecast  Safety   Quality
  (mini)  Agent   Agent   Agent    Agent    Agent
             │       │       │       │        │
             ▼       ▼       ▼       ▼        ▼
         Azure SQL   AI Search   Content   Guardrails
         Database    (Foundry IQ) Safety    + Evals
```

### Agentic architecture

All agents are GPT-4o (except Triage which uses GPT-4o-mini) and are defined via YAML configs in `src/agents/configs/`. The orchestrator uses a triage-based routing pattern — a lightweight classifier dispatches each user message to the appropriate specialist agent:

| Agent | Role | Tools |
|---|---|---|
| **Triage** (GPT-4o-mini) | Classifies intent, routes to specialist | `route_to_specialist` |
| **Operations** | Real-time store status, KPIs, order mix | `run_sql_query` |
| **Diagnostics** | Bottleneck analysis, staffing moves | `run_sql_query`, `move_staff_to_station` |
| **Forecasting** | Demand prediction, surge detection | `run_sql_query` |
| **Safety** | Content safety analysis, policy explanation | `analyze_content_safety` |
| **Quality** | Response + tool-use evaluation via Foundry evaluators | `evaluate_response_quality`, `evaluate_agent_tools` |

### Additional resources

[Microsoft Agent Framework](https://github.com/microsoft/agent-framework)

[Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/)

[Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/)

[Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/)

[Azure AI Search](https://learn.microsoft.com/en-us/azure/search/)

<br/>

### Key features
<details open>
  <summary>Click to learn more about the key features this solution enables</summary>

  - **Multi-Agent Orchestration** <br/>
  Demonstrates Microsoft Agent Framework with triage-based routing to coordinate specialist agents — each with their own tools, system prompts, and expertise domain.

  - **Adaptable to Any Operations Domain** <br/>
  Swap the SQL schema, agent YAML configs, and knowledge base documents to build an ops assistant for retail, hospitality, logistics, healthcare, or any frontline management scenario.

  - **Real-Time Operational Intelligence** (QSR demo) <br/>
  A shift manager asks "How are we doing?" and gets an instant summary of wait times, order volumes, station utilization, and staffing — all from live SQL data.

  - **Intelligent Bottleneck Diagnosis** (QSR demo) <br/>
  Automatically identifies which stations are overloaded, analyzes root causes, and recommends specific staffing changes grounded in the organization's SOPs.

  - **Demand Forecasting** (QSR demo) <br/>
  Predicts upcoming order volumes using a weighted blend of historical patterns (40%), current run rate (40%), and mobile order pipeline (20%) to stay ahead of surges.

  - **Knowledge-Grounded Recommendations** <br/>
  All recommendations are grounded in a Foundry IQ knowledge base containing SOPs, playbooks, and KPI definitions — ensuring consistency regardless of manager experience.

</details>

<br /><br />

<h2><img src="docs/images/readme/quick-deploy.png" width="32" alt=""/> Quick deploy </h2>

### How to install or deploy
Follow the quick deploy steps on the deployment guide to deploy this solution to your own Azure subscription.

> **Note:** This solution accelerator requires **Azure Developer CLI (azd) version 1.18.0 or higher**. Please ensure you have the latest version installed before proceeding with deployment. [Download azd here](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/install-azd).

[Click here to launch the deployment guide](./docs/DEPLOYMENT.md)
<br/><br/>

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/multi-agent-ops-assistant) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/multi-agent-ops-assistant) |
|---|---|

<br/>

> ⚠️ **Important: Check Azure OpenAI Quota Availability**
<br/>To ensure sufficient quota is available in your subscription, please follow the [quota check instructions guide](./docs/QuotaCheck.md) before you deploy the solution.

<br/>

### Prerequisites and costs

To deploy this solution accelerator, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the necessary permissions to create **resource groups, resources, and assign roles at the resource group level**. This should include Contributor role at the subscription level and Role Based Access Control (RBAC) permissions at the subscription and/or resource group level.

The following tools must be installed:

- [Azure CLI (`az`)](https://learn.microsoft.com/cli/azure/install-azure-cli) (v2.60+)
- [Azure Developer CLI (`azd`)](https://aka.ms/install-azd) (v1.18.0+)
- [sqlcmd (Go)](https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd) — required for database seeding during deployment
- [Python 3.11+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/downloads)

Check the [Azure Products by Region](https://azure.microsoft.com/en-us/explore/global-infrastructure/products-by-region/?products=all&regions=all) page and select a **region** where the following services are available.

Pricing varies per region and usage, so it isn't possible to predict exact costs for your usage. The majority of the Azure resources used in this infrastructure are on usage-based pricing tiers. However, Azure Container Registry has a fixed cost per registry per day.

Use the [Azure pricing calculator](https://azure.microsoft.com/en-us/pricing/calculator) to calculate the cost of this solution in your subscription.

_Note: This is not meant to outline all costs as selected SKUs, scaled use, customizations, and integrations into your own tenant can affect the total consumption of this sample solution._

| Product | Description | Cost |
|---|---|---|
| [Microsoft Foundry](https://learn.microsoft.com/en-us/azure/ai-foundry/) | Build generative AI applications on an enterprise-grade platform. Multi-agent orchestration with Microsoft Agent Framework. | [Pricing](https://azure.microsoft.com/pricing/details/ai-studio/) |
| [Azure OpenAI Service](https://learn.microsoft.com/en-us/azure/ai-services/openai/) | GPT-4o for specialist agent reasoning, GPT-4o-mini for triage routing. Pricing is based on token count. | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/) |
| [Azure SQL Database](https://learn.microsoft.com/en-us/azure/azure-sql/) | Basic tier. Real-time operational data — orders, stations, staffing assignments. | [Pricing](https://azure.microsoft.com/pricing/details/azure-sql-database/single/) |
| [Azure AI Search](https://learn.microsoft.com/en-us/azure/search/) | Foundry IQ knowledge base for SOPs, playbooks, and KPI definitions. | [Pricing](https://azure.microsoft.com/pricing/details/search/) |
| [Azure Container Apps](https://learn.microsoft.com/en-us/azure/container-apps/) | Serverless container hosting for the FastAPI application. | [Pricing](https://azure.microsoft.com/pricing/details/container-apps/) |
| [Azure Container Registry](https://learn.microsoft.com/en-us/azure/container-registry/) | Premium tier. Private container image registry. | [Pricing](https://azure.microsoft.com/pricing/details/container-registry/) |
| [Azure Key Vault](https://learn.microsoft.com/en-us/azure/key-vault/) | Secrets management for application configuration. | [Pricing](https://azure.microsoft.com/pricing/details/key-vault/) |
| [Azure Blob Storage](https://learn.microsoft.com/en-us/azure/storage/blobs/) | Standard tier, LRS. Operational document storage. | [Pricing](https://azure.microsoft.com/pricing/details/storage/blobs/) |
| [Azure AI Content Safety](https://learn.microsoft.com/en-us/azure/ai-services/content-safety/) | Content moderation for agent responses. | [Pricing](https://azure.microsoft.com/pricing/details/cognitive-services/content-safety/) |
| [Azure Application Gateway](https://learn.microsoft.com/en-us/azure/application-gateway/) | WAF v2 public entry point with web application firewall protection. | [Pricing](https://azure.microsoft.com/pricing/details/application-gateway/) |
| [Azure Virtual Network](https://learn.microsoft.com/en-us/azure/virtual-network/) | Network isolation with private endpoints for all backend services. | [Pricing](https://azure.microsoft.com/pricing/details/virtual-network/) |
| [Azure Monitor / Application Insights](https://learn.microsoft.com/en-us/azure/azure-monitor/) | Distributed tracing and observability via Foundry telemetry integration. | [Pricing](https://azure.microsoft.com/pricing/details/monitor/) |

<br/>

> ⚠️ **Important:** To avoid unnecessary costs, remember to take down your app if it's no longer in use, either by deleting the resource group in the Portal or running `azd down`.

<br /><br />

<h2><img src="docs/images/readme/business-scenario.png" width="32" alt=""/> Business Scenario </h2>

Frontline managers across industries face the same core challenge: making fast, data-driven decisions while juggling multiple information sources, SOPs, and staffing constraints. This accelerator provides the multi-agent foundation to build an AI-powered operations assistant for any such scenario.

**Included demo: QSR Shift Manager (ShiftIQ)**

Quick-service restaurant (QSR) shift managers face constant operational challenges — fluctuating customer demand, station bottlenecks, mobile order surges, and staffing decisions that need to happen in real time. Instead of monitoring multiple dashboards and manually cross-referencing POS data, a shift manager opens **ShiftIQ** and asks questions in natural language:

| Manager asks ShiftIQ | What happens behind the scenes |
|---|---|
| "How are we doing?" | Operations agent queries live SQL data, summarizes wait times, order load, and hourly pace across all stations |
| "Why are wait times climbing?" | Diagnostics agent pinpoints the bottleneck (e.g., cold bar at 125% capacity), recommends SOP-compliant staffing shift |
| "What's coming in the next 30 minutes?" | Forecasting agent detects a mobile order surge forming, advises batch prep per the surge playbook |
| "Move Sarah to cold bar" | Diagnostics agent confirms the move, updates the database, and projects impact on wait times |
| "Evaluate that last response" | Quality agent runs Foundry evaluators (coherence, relevance, groundedness) and logs results to the Foundry portal |

⚠️ The sample data used in this repository is synthetic. The data is intended for use as sample data only.

### Other use cases

This accelerator's architecture — triage routing, specialist agents, SQL-backed operational data, and SOP knowledge base — can be adapted to other domains:

| Use Case | Persona | What changes |
|---|---|---|
| **Retail store ops** | Store Manager | SQL schema → inventory, foot traffic, checkout queues; SOPs → loss prevention, planogram compliance |
| **Hotel operations** | Front Desk / Duty Manager | SQL schema → room status, housekeeping, guest requests; SOPs → check-in procedures, escalation protocols |
| **Warehouse logistics** | Shift Supervisor | SQL schema → pick rates, dock schedules, zone capacity; SOPs → safety protocols, priority routing |
| **Healthcare unit coordination** | Charge Nurse | SQL schema → bed status, patient flow, staffing ratios; SOPs → acuity-based assignment, rapid response triggers |

### Business value
<details>
  <summary>Click to learn more about what value this solution provides</summary>

  - **Faster decisions during the rush** <br/>
  Shift managers get instant, data-driven answers from ShiftIQ instead of manually checking POS dashboards, labor sheets, and order queues.

  - **Smarter staffing moves** <br/>
  AI-recommended staffing changes are grounded in the organization's SOPs and real-time utilization data — not gut feel.

  - **Stay ahead of surges** <br/>
  The forecasting agent detects incoming mobile order surges before they hit, enabling preemptive batch prep and station rebalancing.

  - **Consistent quality regardless of experience** <br/>
  New and veteran managers alike get the same SOP-grounded recommendations, ensuring operational consistency.

  - **Secure and responsible** <br/>
  Managed identities, Entra ID-only authentication, content safety guardrails, and built-in Foundry evaluators ensure responsible AI practices.

</details>

<br /><br />

<h2><img src="docs/images/readme/supporting-documentation.png" width="32" alt=""/> Supporting documentation </h2>

### Technical guide

For comprehensive technical documentation including architecture, agent orchestration, configuration, and development setup, see the [Technical Guide](./docs/TECHNICAL_GUIDE.md).

### Security guidelines

This template uses [Managed Identity](https://learn.microsoft.com/entra/identity/managed-identities-azure-resources/overview) for authentication between Azure services.

Azure SQL Database uses Entra ID-only authentication (no SQL passwords). Dynamic SQL is restricted to read-only `SELECT` statements with regex-based write operation blocking.

To ensure continued best practices in your own repository, we recommend that anyone creating solutions based on our templates ensure that the [Github secret scanning](https://docs.github.com/code-security/secret-scanning/about-secret-scanning) setting is enabled.

This deployment includes the following security features out of the box:

* **Virtual Network isolation** — All backend services (SQL, Search, Storage, Key Vault, Foundry, ACR) are connected via [private endpoints](https://learn.microsoft.com/azure/private-link/private-endpoint-overview) within a VNet.
* **Flexible ingress** — The deployment supports two modes. In **private mode** (`usePrivateEndpoints=true`), an [Azure Application Gateway](https://learn.microsoft.com/azure/application-gateway/overview) with WAF v2 is the sole public entry point and the Container App is internal-only. When a custom hostname and SSL cert are provided, the gateway uses HTTPS with SNI; otherwise it uses HTTP with WAF protection and an Azure-assigned DNS label. In **public mode** (default), the Container App is externally accessible via its managed FQDN.
* **Managed Identity everywhere** — No passwords or API keys are stored. All service-to-service auth uses system-assigned managed identities with least-privilege RBAC.
* **Entra ID-only SQL authentication** — Azure SQL Database has local SQL auth disabled.

You may want to consider additional security measures, such as:

* Enabling Microsoft Defender for Cloud to [secure your Azure resources](https://learn.microsoft.com/azure/defender-for-cloud).
* Adding [DDoS Protection](https://learn.microsoft.com/azure/ddos-protection/ddos-protection-overview) for the public-facing Application Gateway.

<br/>

### Cross references
Check out similar solution accelerators

| Solution Accelerator | Description |
|---|---|
| [Content&nbsp;generation](https://github.com/microsoft/content-generation-solution-accelerator) | Multi-agent content generation for marketing campaigns using Microsoft Agent Framework with HandoffBuilder orchestration. |
| [Customer&nbsp;chatbot](https://github.com/microsoft/customer-chatbot-solution-accelerator) | Intelligent customer service chatbot using Microsoft Foundry's Agent Framework with specialized agents for product lookup and knowledge management. |
| [Multi-Agent&nbsp;Automation](https://github.com/microsoft/Multi-Agent-Custom-Automation-Engine-Solution-Accelerator) | AI-driven multi-agent system for automating complex organizational tasks, powered by Microsoft Agent Framework and Azure Foundry. |
| [Chat&nbsp;with&nbsp;your&nbsp;data](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator) | Chat with your own data by combining Azure AI Search and Large Language Models (LLMs) to create a conversational search experience. |
| [Build&nbsp;your&nbsp;own&nbsp;copilot](https://github.com/microsoft/Build-your-own-copilot-Solution-Accelerator) | Helps client advisors save time and prepare relevant discussion topics with overviews, client profile views, and chatting with structured data. |

💡 Want to get familiar with Microsoft's AI and Data Engineering best practices? Check out our playbooks to learn more

| Playbook | Description |
|---|---|
| [AI&nbsp;playbook](https://github.com/microsoft/ai-playbook) | The Artificial Intelligence (AI) Playbook provides enterprise software engineers with solutions, capabilities, and code developed to solve real-world AI problems. |
| [Data&nbsp;playbook](https://github.com/microsoft/data-playbook) | The data playbook provides enterprise software engineers with solutions which contain code developed to solve real-world problems. Everything in the playbook is developed with, and validated by, some of Microsoft's largest and most influential customers and partners. |

<br/>

## Provide feedback

Have questions, find a bug, or want to request a feature? [Submit a new issue](https://github.com/microsoft/multi-agent-ops-assistant/issues) on this repo and we'll connect.

<br/>

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

<br/>

## Responsible AI Transparency FAQ
Please refer to [Transparency FAQ](./docs/TRANSPARENCY_FAQ.md) for responsible AI transparency details of this solution accelerator.

<br/>

## Disclaimers

This release is an artificial intelligence (AI) system that generates text based on user input. The text generated by this system may include ungrounded content, meaning that it is not verified by any reliable source or based on any factual data. The data included in this release is synthetic, meaning that it is artificially created by the system and may contain factual errors or inconsistencies. Users of this release are responsible for determining the accuracy, validity, and suitability of any content generated by the system for their intended purposes. Users should not rely on the system output as a source of truth or as a substitute for human judgment or expertise.

This release only supports English language input and output. Users should not attempt to use the system with any other language or format. The system output may not be compatible with any translation tools or services, and may lose its meaning or coherence if translated.

This release does not reflect the opinions, views, or values of Microsoft Corporation or any of its affiliates, subsidiaries, or partners. The system output is solely based on the system's own logic and algorithms, and does not represent any endorsement, recommendation, or advice from Microsoft or any other entity. Microsoft disclaims any liability or responsibility for any damages, losses, or harms arising from the use of this release or its output by any user or third party.

This release is intended as a proof of concept only, and is not a finished or polished product. It is not intended for commercial use or distribution, and is subject to change or discontinuation without notice. Any planned deployment of this release or its output should include comprehensive testing and evaluation to ensure it is fit for purpose and meets the user's requirements and expectations. Microsoft does not guarantee the quality, performance, reliability, or availability of this release or its output, and does not provide any warranty or support for it.

This Software requires the use of third-party components which are governed by separate proprietary or open-source licenses as identified below, and you must comply with the terms of each applicable license in order to use the Software. You acknowledge and agree that this license does not grant you a license or other right to use any such third-party proprietary or open-source components.

To the extent that the Software includes components or code used in or derived from Microsoft products or services, including without limitation Microsoft Azure Services (collectively, "Microsoft Products and Services"), you must also comply with the Product Terms applicable to such Microsoft Products and Services. You acknowledge and agree that the license governing the Software does not grant you a license or other right to use Microsoft Products and Services. Nothing in the license or this ReadMe file will serve to supersede, amend, terminate or modify any terms in the Product Terms for any Microsoft Products and Services.

You must also comply with all domestic and international export laws and regulations that apply to the Software, which include restrictions on destinations, end users, and end use. For further information on export restrictions, visit https://aka.ms/exporting.

You acknowledge that the Software and Microsoft Products and Services (1) are not designed, intended or made available as a medical device(s), and (2) are not designed or intended to be a substitute for professional medical advice, diagnosis, treatment, or judgment and should not be used to replace or as a substitute for professional medical advice, diagnosis, treatment, or judgment. Customer is solely responsible for displaying and/or obtaining appropriate consents, warnings, disclaimers, and acknowledgements to end users of Customer's implementation of the Online Services.

You acknowledge the Software is not subject to SOC 1 and SOC 2 compliance audits. No Microsoft technology, nor any of its component technologies, including the Software, is intended or made available as a substitute for the professional advice, opinion, or judgment of a certified financial services professional. Do not use the Software to replace, substitute, or provide professional financial advice or judgment.

BY ACCESSING OR USING THE SOFTWARE, YOU ACKNOWLEDGE THAT THE SOFTWARE IS NOT DESIGNED OR INTENDED TO SUPPORT ANY USE IN WHICH A SERVICE INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE COULD RESULT IN THE DEATH OR SERIOUS BODILY INJURY OF ANY PERSON OR IN PHYSICAL OR ENVIRONMENTAL DAMAGE (COLLECTIVELY, "HIGH-RISK USE"), AND THAT YOU WILL ENSURE THAT, IN THE EVENT OF ANY INTERRUPTION, DEFECT, ERROR, OR OTHER FAILURE OF THE SOFTWARE, THE SAFETY OF PEOPLE, PROPERTY, AND THE ENVIRONMENT ARE NOT REDUCED BELOW A LEVEL THAT IS REASONABLY, APPROPRIATE, AND LEGAL, WHETHER IN GENERAL OR IN A SPECIFIC INDUSTRY. BY ACCESSING THE SOFTWARE, YOU FURTHER ACKNOWLEDGE THAT YOUR HIGH-RISK USE OF THE SOFTWARE IS AT YOUR OWN RISK.
