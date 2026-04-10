## Ops Assistant Solution Accelerator: Responsible AI FAQ

- ### What is Ops Assistant?
    This solution accelerator is an open-source GitHub Repository that demonstrates a multi-agent AI assistant for retail shift managers. Built on the Microsoft Agent Framework with triage-based orchestration, it uses specialized AI agents to answer real-time operational questions by querying live store data and grounding responses in operational knowledge bases (SOPs, playbooks, KPI definitions).

- ### What can Ops Assistant do?
    This is a conversational AI assistant that helps shift managers make data-driven decisions during their shift.

    **Key Capabilities:**
    - Provide real-time store status summaries (wait times, order volumes, station utilization)
    - Diagnose operational bottlenecks and recommend staffing changes
    - Forecast upcoming demand based on historical patterns and mobile order pipelines
    - Execute staff reassignments and project their operational impact
    - Ground all recommendations in organization-specific SOPs and playbooks via Foundry IQ knowledge base

- ### What is/are Ops Assistant's intended use(s)?
    This repository is to be used only as a solution accelerator following the open-source license terms listed in the GitHub repository. The example scenario's intended purpose is to demonstrate how AI agents can assist retail shift managers with operational decision-making by querying real-time data and providing actionable, SOP-grounded recommendations — helping them perform their work more efficiently.

- ### How was Ops Assistant evaluated? What metrics are used to measure performance?
    The solution includes a built-in Quality Agent that evaluates responses using Microsoft Foundry evaluators for groundedness, relevance, coherence, and fluency. Additionally, integration tests validate core workflows including dashboard APIs, agent routing, staff move persistence, and safety metadata. Content safety is enforced through Azure AI Content Safety integration.

- ### What are the limitations of Ops Assistant? How can users minimize the impact of Ops Assistant's limitations when using the system?
    This solution accelerator can only be used as a sample to accelerate the creation of an AI assistant for shift management. The repository showcases a sample scenario of a coffee shop shift manager. Users should review the system prompts provided and update them as per their organizational guidance. Users should run their own evaluation flow either using the guidance provided in the GitHub repository or their choice of evaluation methods. AI-generated content may be inaccurate and should be manually reviewed. Currently, the sample repo is available in English only.

- ### What operational factors and settings allow for effective and responsible use of Ops Assistant?
    Users can customize the following to tailor the system to their needs:
    - **Agent YAML configurations** (`src/agents/configs/`) — modify agent instructions, tool assignments, and knowledge base flags
    - **Operational documents** (`operational-docs/`) — replace with your organization's SOPs, playbooks, and KPI definitions
    - **Database schema and seed data** (`database/`) — adapt to your store's operational data model
    - **Content safety thresholds** — configure via Azure AI Content Safety settings
    - **Model selection** — adjust GPT model deployments and token quotas based on usage patterns

    Please note that these parameters are only provided as guidance to start the configuration but not as a complete available list to adjust the system behavior. Please always refer to the latest product documentation for these details or reach out to your Microsoft account team if you need assistance.
