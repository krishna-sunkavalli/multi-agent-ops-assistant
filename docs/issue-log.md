# MULTI-AGENT OPS ASSISTANT — Issue Log & Resolutions

> Comprehensive log of every issue encountered during development, deployment,
> and hardening of the MULTI-AGENT OPS ASSISTANT multi-agent system.
> Each entry includes: symptom, root cause, fix, and affected files.

---

## Issue #1 — Dockerfile Build Failures

| Field | Detail |
|---|---|
| **Symptom** | Multiple ACR build iterations failed with missing dependencies and incorrect paths. |
| **Root Cause** | Original Dockerfile didn't match the restructured project layout (OSS SA pattern). Missing `requirements.txt` copy, wrong `WORKDIR`, and missing system packages for `pyodbc`. |
| **Fix** | Rewrote Dockerfile with correct `COPY` ordering, added `unixodbc-dev` and ODBC driver install, set proper `WORKDIR /app`. |
| **Files** | `Dockerfile` |

---

## Issue #2 — GPT-4o Model Quota Exhausted

| Field | Detail |
|---|---|
| **Symptom** | Agent calls returned 429 errors — "Requests to the ChatCompletions_Create Operation have exceeded token rate limit." |
| **Root Cause** | Default GPT-4o deployment in `northcentralus` had insufficient TPM quota for the multi-agent workload (triage + 5 specialists). |
| **Fix** | Increased GPT-4o TPM quota via Azure Portal. Added the triage agent on a separate `gpt-4o-mini` deployment to reduce quota pressure on the main model. |
| **Files** | `infra/modules/foundry.bicep`, `src/agents/registry.py` |

---

## Issue #3 — Application Insights Auth Type Error

| Field | Detail |
|---|---|
| **Symptom** | Bicep deployment failed with Application Insights configuration error. |
| **Root Cause** | The `authType` property was set incorrectly for the workspace-based Application Insights resource. |
| **Fix** | Corrected the Application Insights Bicep module to use the proper auth configuration for workspace-based mode. |
| **Files** | `infra/main.bicep` |

---

## Issue #4 — App Gateway Custom Hostname Mismatch

| Field | Detail |
|---|---|
| **Symptom** | HTTPS requests to `shiftiq.azdemohub.com` returned 502 Bad Gateway or TLS errors. |
| **Root Cause** | App Gateway backend health probe and hostname configuration didn't match the Container App's FQDN. |
| **Fix** | Fixed App Gateway hostname settings, backend pool, and health probe to correctly route to the Container App FQDN. |
| **Files** | `infra/main.bicep` |

---

## Issue #5 — SQL Admin SID Configuration

| Field | Detail |
|---|---|
| **Symptom** | Azure SQL Server deployment failed or app couldn't authenticate with Entra ID. |
| **Root Cause** | The SQL admin SID (Security Identifier) was hardcoded or missing, preventing Entra ID authentication setup. |
| **Fix** | Parameterized the SQL admin SID in Bicep and injected the deployer's object ID from the preprovision hook. |
| **Files** | `infra/modules/sql.bicep`, `hooks/preprovision.ps1`, `hooks/preprovision.sh` |

---

## Issue #6 — Agent Framework SDK Version Incompatibility

| Field | Detail |
|---|---|
| **Symptom** | Import errors and API mismatches at container startup — `Agent`, `ChatOptions`, and `AzureAIClient` signatures didn't match the installed SDK. |
| **Root Cause** | Initial code was written for a newer (unreleased) version of the Agent Framework SDK. The `rc2` release had different API surface. |
| **Fix** | Downgraded to `agent-framework-core==1.0.0rc2` and `agent-framework-azure-ai==1.0.0rc2`. Updated all code to match rc2 APIs. |
| **Files** | `requirements.txt`, `src/agents/registry.py`, `src/orchestrator.py` |

---

## Issue #7 — azure-ai-projects Version Conflict

| Field | Detail |
|---|---|
| **Symptom** | `ImportError` or `AttributeError` at startup when importing from `azure.ai.projects`. |
| **Root Cause** | The `azure-ai-projects` package version was incompatible with the agent framework SDK. |
| **Fix** | Pinned `azure-ai-projects==2.0.0b3` which is compatible with the rc2 agent framework. |
| **Files** | `requirements.txt` |

---

## Issue #8 — ChatOptions Dict Access Pattern

| Field | Detail |
|---|---|
| **Symptom** | `TypeError: 'ChatOptions' object is not subscriptable` at runtime when setting agent options. |
| **Root Cause** | Code used attribute access (`options.temperature`) but `ChatOptions` in rc2 is a `TypedDict` requiring bracket notation. |
| **Fix** | Changed all `ChatOptions` construction to use dict-style: `ChatOptions(store=True, temperature=0.0, tool_choice="required")`. |
| **Files** | `src/agents/registry.py` |

---

## Issue #9 — Wrong Foundry Project Endpoint

| Field | Detail |
|---|---|
| **Symptom** | All agent calls returned 404 — "Project not found." |
| **Root Cause** | The `AZURE_AI_PROJECT_ENDPOINT` environment variable pointed to the Foundry account endpoint instead of the project endpoint (missing `/projects/shiftcopilot-project` path). |
| **Fix** | Updated the Bicep output and Container App env var to use the full project endpoint: `https://ai-shiftcopilot-ouk4fynffbcy4.services.ai.azure.com/api/projects/shiftcopilot-project`. |
| **Files** | `infra/main.bicep`, `infra/modules/containerapp.bicep` |

---

## Issue #10 — Misleading Error Messages on Agent Failure

| Field | Detail |
|---|---|
| **Symptom** | When an agent call failed, the user saw a generic "An error occurred" message with no diagnostic context. |
| **Root Cause** | Exception handling in the orchestrator caught all exceptions but didn't surface the actual error type or Foundry API error details. |
| **Fix** | Added structured error handling that logs the full exception, returns the error category (rate limit, auth, not found), and includes retry-after headers for 429s. |
| **Files** | `src/orchestrator.py` |

---

## Issue #11 — 400 Invalid Payload (`store=False`)

| Field | Detail |
|---|---|
| **Symptom** | Agent calls returned `400 invalid_payload` from the Responses API after the first tool call in a conversation. |
| **Root Cause** | `store=False` in `ChatOptions` caused the SDK to rebuild the full message payload on each turn instead of using `previous_response_id`. The rebuilt payload had schema mismatches with the Responses API's expected format for tool-result submissions. |
| **Fix** | Changed to `store=True` — lets the Responses API manage conversation state server-side, using `previous_response_id` for seamless multi-turn tool calling. |
| **Files** | `src/agents/registry.py` |

---

## Issue #12 — Staff Move Returns Wrong Data

| Field | Detail |
|---|---|
| **Symptom** | The `move_staff_to_station` tool reported success but the staff member wasn't actually moved — subsequent queries showed them at the old station. |
| **Root Cause** | The SQL UPDATE query had a logic error in the WHERE clause, and the function returned stale cached data instead of re-querying after the update. |
| **Fix** | Fixed the SQL UPDATE query and added a post-update verification query to return fresh data confirming the move. |
| **Files** | `src/tools/staffing_tools.py` |

---

## Issue #13 — Non-Idempotent Database Schema

| Field | Detail |
|---|---|
| **Symptom** | Re-running `azd provision` failed at the database seeding step because `CREATE TABLE` statements threw "object already exists" errors. |
| **Root Cause** | `database/schema.sql` used plain `CREATE TABLE` without existence checks. |
| **Fix** | Wrapped all DDL in `IF NOT EXISTS` / `IF OBJECT_ID(...) IS NULL` guards so the schema is fully idempotent on re-runs. |
| **Files** | `database/schema.sql` |

---

## Issue #14 — App Gateway Not Conditional

| Field | Detail |
|---|---|
| **Symptom** | Deployments to subscriptions without an existing App Gateway and custom domain failed because the Bicep assumed the gateway resources existed. |
| **Root Cause** | App Gateway, public IP, and related resources were always deployed even when `customDomainHostname` was empty. |
| **Fix** | Added a `deployAppGateway` boolean condition gated on whether `customDomainHostname` is provided. All App Gateway resources are conditional. |
| **Files** | `infra/main.bicep` |

---

## Issue #15 — ACR Locked During Deploy

| Field | Detail |
|---|---|
| **Symptom** | `azd deploy` (container image push) failed with "denied: client IP not allowed" because ACR's public access was disabled. |
| **Root Cause** | The ACR was locked down (network rules default Deny) for security, but the deploy step needs public access to push images from the ACR build agent. |
| **Fix** | Added `preprovision` hook to temporarily enable ACR public access, and `postdeploy` hook to re-disable it after the image is pushed. |
| **Files** | `hooks/preprovision.ps1`, `hooks/preprovision.sh`, `hooks/postdeploy.ps1`, `hooks/postdeploy.sh` |

---

## Issue #16 — Hardcoded Azure Region

| Field | Detail |
|---|---|
| **Symptom** | Deploying to a different region than `northcentralus` failed because several resources had the region hardcoded. |
| **Root Cause** | Some Bicep modules used literal `'northcentralus'` instead of the `location` parameter. |
| **Fix** | Parameterized all region references through the `location` parameter flowing from `main.bicepparam`. |
| **Files** | `infra/main.bicep`, `infra/main.bicepparam`, various modules |

---

## Issue #17 — Knowledge Base Setup Was Manual

| Field | Detail |
|---|---|
| **Symptom** | After `azd up`, the AI Search index for Foundry IQ knowledge base didn't exist — agents with `use_knowledge: true` couldn't retrieve operational docs. |
| **Root Cause** | The Search index creation and document indexing was a manual step (`setup-foundry-iq.sh`) not integrated into the azd lifecycle. |
| **Fix** | Added automated Search index creation and document indexing to `postprovision.ps1`/`.sh` using the Azure AI Search REST API. Temporarily enables Search public access, creates index, indexes 5 operational docs, then re-disables public access. |
| **Files** | `hooks/postprovision.ps1`, `hooks/postprovision.sh` |

---

## Issue #18 — Stale `setup-foundry-iq.sh` Script

| Field | Detail |
|---|---|
| **Symptom** | Running the old manual setup script failed because it referenced outdated resource names and API versions. |
| **Root Cause** | The script wasn't updated after the infrastructure was restructured. |
| **Fix** | Updated the script to match current resource names, or deprecated it in favor of the automated postprovision hook. |
| **Files** | `infra/scripts/setup-foundry-iq.sh` |

---

## Issue #19 — All Routing Was Hardcoded (No LLM Triage)

| Field | Detail |
|---|---|
| **Symptom** | Every demo question was routed via regex keyword matching — the LLM triage agent was never actually invoked. Anyone inspecting the code would see "no autonomous logic, just hardcoded routing." |
| **Root Cause** | `_KEYWORD_OVERRIDES` in `orchestrator.py` contained 25 regex patterns that matched every standard question. The keyword check runs before the LLM triage, so the triage agent was completely bypassed. |
| **Fix** | Removed 24 of 25 keyword overrides, keeping only bare confirmations (`"yes"`, `"go ahead"`, `"proceed"`, etc.) that lack semantic context for the LLM. All real questions now route through the LLM triage agent (gpt-4o-mini). |
| **Files** | `src/orchestrator.py` |

---

## Issue #20 — Triage Agent Infinite Loop (40 Iterations)

| Field | Detail |
|---|---|
| **Symptom** | After removing keyword overrides, the triage agent took 60-80 seconds per request and hit "Maximum iterations reached (40)." Cascading timeouts caused downstream test failures. |
| **Root Cause** | `tool_choice: "required"` forced the model to call `route_to_specialist` on every iteration. The framework resets `tool_choice` to `auto` after iteration 1, but the triage instructions say "NEVER produce text output" — so the model kept calling the tool voluntarily. With the default `max_iterations=40`, this burned 40 API calls before the framework forced a final text response. |
| **Fix** | Added `function_invocation_configuration={"max_function_calls": 1, "max_iterations": 2}` to the triage agent's `AzureAIClient`. This caps the triage to exactly 1 tool call + 1 final response — the correct behavior for a router agent. |
| **Files** | `src/agents/registry.py` |

---

## Issue #21 — Safety and Quality Agents Misrouted

| Field | Detail |
|---|---|
| **Symptom** | "Can you analyze the content safety of this text" routed to Diagnostics instead of Safety. "Evaluate the quality of the previous response" also misrouted. |
| **Root Cause** | The triage agent's routing instructions didn't have strong enough signals for safety and quality patterns. The LLM defaulted to diagnostics (the catch-all for "analysis" type questions). |
| **Fix** | Enhanced `triage.yaml` with priority rules for safety and quality that are checked before the general routing table. Added explicit disambiguation examples: `"content safety" → safety`, `"evaluate" / "rate" / "score" → quality`. |
| **Files** | `src/agents/configs/triage.yaml` |

---

## Issue #22 — Streaming Overlap Optimization Incompatible with LLM Triage

| Field | Detail |
|---|---|
| **Symptom** | After removing keyword overrides, the performance optimization (overlapping safety check with specialist execution) no longer made sense — triage was no longer instant. |
| **Root Cause** | The v15 optimization assumed triage was instant (keyword match), so it overlapped the content safety API call with the specialist agent call. With LLM-based triage, this pattern was invalid because the specialist isn't known until triage completes. |
| **Fix** | Reverted `process_message_stream` to `asyncio.gather(safety_task, triage_task)` — runs content safety and LLM triage in parallel (both take ~200-500ms), then streams the specialist. |
| **Files** | `src/orchestrator.py` |

---

## Issue #23 — E2E Test Recv Timeout Too Short

| Field | Detail |
|---|---|
| **Symptom** | E2E test turns 5 and 9 failed with "No [DONE] received" — the test timed out waiting for the agent response. |
| **Root Cause** | The per-message WebSocket `recv()` timeout was 60 seconds, which was insufficient for LLM-based triage (~500ms) + specialist agent with tool calls (~10-30s) + streaming. Some turns with complex tool chains exceeded 60s total. |
| **Fix** | Increased the `asyncio.wait_for(ws.recv(), timeout=...)` from 60 to 120 seconds. |
| **Files** | `tests/e2e_agent_test.py` |

---

## Issue #24 — Role Assignment Conflicts on Re-deployment

| Field | Detail |
|---|---|
| **Symptom** | `azd up` failed with `RoleAssignmentExists` errors for 3 role assignments (Search Service Contributor, Cognitive Services User, Azure AI Developer). All other resources provisioned successfully. |
| **Root Cause** | Three role assignments for the Container App managed identity had been created earlier (via `az` CLI or a previous Bicep run with different GUID seeds). The existing assignments had different GUID names (`519e3b09...`, `9767f2c9...`, `1e23d288...`) than what the current Bicep `guid()` function computes (`084e28f7...`, `604c6775...`, `24790f86...`). ARM rejects duplicate role+principal+scope combinations even when the assignment names differ. |
| **Fix** | Deleted the 3 stale role assignments using `az role assignment delete --assignee <principalId> --role <roleName> --scope <resourceId>`. After deletion, `azd up` created the assignments with correct Bicep-computed GUIDs. |
| **Files** | No code changes — operational fix. To prevent recurrence, role assignments use deterministic `guid(resourceId, principalId, roleDefinitionId)` names so Bicep deployments are idempotent. |

---

## Issue #25 — ACR Firewall Propagation Delay

| Field | Detail |
|---|---|
| **Symptom** | `az acr build` failed with "client IP not allowed" immediately after running `az acr update --default-action Allow`. |
| **Root Cause** | Azure ACR network rule changes take 10-30 seconds to propagate. Running the build immediately after the firewall update hits the old (Deny) rules. |
| **Fix** | Retry the build after a short delay. In the azd hooks, the preprovision script runs the ACR update early enough that propagation completes before the deploy step begins. |
| **Files** | No code changes — operational awareness. |

---

## Issue #26 — Container App 1012 (Service Restart) During Tests

| Field | Detail |
|---|---|
| **Symptom** | WebSocket connections dropped with error code 1012 during e2e tests immediately after a new Container App revision was deployed. |
| **Root Cause** | When a new Container App revision activates, the old revision's containers are terminated. Active WebSocket connections on the old revision receive a 1012 (Service Restart) close frame. This is a transient infrastructure event, not a code bug. |
| **Fix** | No code fix needed. Tests are re-run after a few seconds. The 1012 only occurs during the ~5 second window when the revision switches. |
| **Files** | No changes |

---

## Issue #27 — Docker Desktop Required for `azd up`

| Field | Detail |
|---|---|
| **Symptom** | `azd up` failed at the Package step with "Docker is not running" even though `AZURE_CONTAINER_REGISTRY_BUILD=true` was set for remote ACR builds. |
| **Root Cause** | azd 1.23.7 requires Docker Desktop to be running locally for the packaging step (tagging the image) even when the actual build happens remotely in ACR. |
| **Fix** | Start Docker Desktop before running `azd up`. The packaging step only tags locally; the actual build runs in ACR. |
| **Files** | No code changes — prerequisite documented. |

---

## Summary

| Category | Count |
|---|---|
| Infrastructure / Bicep | 7 (#1, #3, #4, #5, #14, #16, #24) |
| SDK / Dependencies | 4 (#6, #7, #8, #11) |
| Agent Logic | 4 (#10, #19, #20, #21) |
| Orchestrator | 3 (#10, #22, #19) |
| Data / SQL | 2 (#12, #13) |
| Automation / Hooks | 3 (#15, #17, #18) |
| Testing | 2 (#23, #26) |
| Operational | 3 (#25, #26, #27) |
| **Total Issues** | **27** |
| **Total Resolved** | **27** |
