# Deployment Guide

## Prerequisites

To deploy this solution, ensure you have access to an [Azure subscription](https://azure.microsoft.com/free/) with the following permissions:

- **Contributor** role at the subscription level (to create resource groups and resources)
- **User Access Administrator** or **Role Based Access Control Administrator** role at the subscription level (to assign RBAC roles to managed identities)

### Required Tools

| Tool | Min Version | Purpose |
|------|-------------|---------|
| [Azure CLI (`az`)](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) | 2.60+ | Azure resource management |
| [Azure Developer CLI (`azd`)](https://aka.ms/install-azd) | 1.15.0+ | Infrastructure-as-code deployment |
| [sqlcmd (Go)](https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd) | latest | Database seeding (postprovision) |
| [Python](https://www.python.org/downloads/) | 3.11+ | Local development |
| [Git](https://git-scm.com/downloads) | latest | Source control |

> **Note:** GitHub Codespaces and Dev Containers include all tools automatically (including sqlcmd).

### Quota Pre-Flight Check

Before deploying, verify you have sufficient quota for the following resources in your target region:

| Resource | Required Quota | How to Check |
|----------|---------------|--------------|
| **GPT-4o (GlobalStandard)** | 80k TPM (default) | [Azure AI Foundry portal](https://ai.azure.com) → Settings → Quotas |
| **GPT-4o-mini (GlobalStandard)** | 30k TPM | Same as above |
| **vCPU (Container Apps)** | 2+ vCPUs | Azure Portal → Subscription → Usage + quotas |

> **⚠️ Insufficient GPT-4o quota is the #1 cause of deployment failures.** Request additional quota via the Azure portal *before* deploying.

### Recommended Regions

Not all Azure regions support every service required by this solution. The following regions are verified to work:

| Region | Notes |
|--------|-------|
| **East US** | Full service availability |
| **East US 2** | Full service availability |
| **Sweden Central** | Full service availability |
| **North Central US** | Full service availability |

### Important Note for PowerShell Users

If you encounter issues running PowerShell scripts due to the policy of not being digitally signed, you can temporarily adjust the `ExecutionPolicy` by running the following command in an elevated PowerShell session:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

This will allow the scripts to run for the current session without permanently changing your system's policy.

---

## Deployment Options & Steps

Pick from the options below to see step-by-step instructions for GitHub Codespaces, VS Code Dev Containers, or Local Environments.

| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/multi-agent-ops-assistant) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/multi-agent-ops-assistant) |
|---|---|

<details>
  <summary><b>Deploy in GitHub Codespaces</b></summary>

### GitHub Codespaces

You can run this solution using GitHub Codespaces. The button will open a web-based VS Code instance in your browser:

1. Open the solution accelerator (this may take several minutes):

    [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/microsoft/multi-agent-ops-assistant)

2. Accept the default values on the create Codespaces page.
3. Open a terminal window if it is not already open.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in VS Code Dev Containers</b></summary>

### VS Code Dev Containers

You can run this solution in VS Code Dev Containers, which will open the project in your local VS Code using the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers):

1. Start Docker Desktop (install it if not already installed).
2. Open the project:

    [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/microsoft/multi-agent-ops-assistant)

3. In the VS Code window that opens, once the project files show up (this may take several minutes), open a terminal window.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<details>
  <summary><b>Deploy in your local Environment</b></summary>

### Local Environment

If you're not using one of the above options for opening the project, then you'll need to:

1. Make sure the following tools are installed:

    - [Azure CLI (`az`)](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) <small>(v2.60+)</small>
    - [Azure Developer CLI (`azd`)](https://aka.ms/install-azd) <small>(v1.15.0+)</small>
    - [sqlcmd (Go)](https://learn.microsoft.com/sql/tools/sqlcmd/go-sqlcmd) <small>(required for database seeding)</small>
    - [Python 3.11+](https://www.python.org/downloads/)
    - [Git](https://git-scm.com/downloads)

2. Clone the repository or download the project code via command-line:

    ```shell
    azd init -t microsoft/multi-agent-ops-assistant
    ```

3. Open the project folder in your terminal or editor.
4. Continue with the [deploying steps](#deploying-with-azd).

</details>

<br/>

<details>
  <summary><b>Configurable Deployment Settings</b></summary>

When you start the deployment, most parameters will have **default values**, but you can update the following settings:

| **Setting** | **Description** | **Default value** |
|---|---|---|
| **Azure Region** | The region where resources will be created. | *(empty)* |
| **Environment Name** | A **3–20 character alphanumeric value** used to generate a unique ID to prefix the resources. | env_name |
| **GPT Model** | Choose from **gpt-4o, gpt-4o-mini**. | gpt-4o |
| **GPT Model Deployment Capacity** | Configure capacity for **GPT models** (in thousands of tokens per minute). | 80k |

</details>

<details>
  <summary><b>[Optional] Quota Recommendations</b></summary>

By default, the **GPT-4o model capacity** in deployment is set to **80k tokens per minute**, so we recommend verifying you have sufficient quota:

> **For GPT-4o** — increase the capacity post-deployment for optimal performance if your usage requires it.

Depending on your subscription quota and capacity, you can adjust quota settings to better meet your specific needs.

**⚠️ Warning:** Insufficient quota can cause deployment errors. Please ensure you have the recommended capacity or request additional capacity before deploying this solution.

</details>

---

## Deploying with AZD

Once you've opened the project in [Codespaces](#github-codespaces), [Dev Containers](#vs-code-dev-containers), or [locally](#local-environment), you can deploy it to Azure.

### Deploy

```bash
# 1. Log in to Azure (both CLIs)
az login
azd auth login

# 2. Deploy everything (infrastructure + container + database + knowledge base)
azd up
```

> **Note:** No Docker Desktop is required. Container images are built remotely on Azure Container Registry.

### What happens automatically

| Step | Phase | What it does |
|------|-------|-------------|
| 1 | **Pre-provision** | Captures your Entra identity, enables remote ACR builds |
| 2 | **Provision** | Deploys AI Foundry, AI Search, SQL Database, ACR, Key Vault, Storage, Container Apps, RBAC |
| 3 | **Post-provision** | Enables SQL/Storage public access temporarily, seeds database, uploads docs, grants SQL access, locks down SQL/Storage/Key Vault |
| 4 | **Deploy** | Builds container image on ACR (remote) and deploys to Container Apps |
| 5 | **Post-deploy** | Locks down ACR (disables public network access) |

---

## Post Deployment Steps

1. **Verify the application** — Navigate to the Container App URL output by `azd up` and confirm the chat UI loads.

2. **Reset demo data** — If you need to reset the database to the default bottleneck scenario:
   ```bash
   curl -X POST https://<your-app-url>/reset
   ```

3. **Deleting Resources After a Failed Deployment**
   - If your deployment fails and/or you need to clean up the resources, run:
   ```bash
   azd down
   ```

---

## Troubleshooting

<details>
  <summary><b>Common Issues and Solutions</b></summary>

### 429 Rate Limit Errors

**Symptom**: Agent responses fail intermittently with rate limit errors.

**Cause**: Insufficient GPT-4o token quota.

**Solution**: Increase model deployment capacity in Microsoft Foundry portal, or reduce concurrent usage.

### Database Connection Failures

**Symptom**: SQL queries return connection errors.

**Cause**: Entra ID token expiry or firewall issues.

**Solution**:
1. Verify the Container App managed identity has SQL access
2. Check SQL Server firewall allows Azure services
3. Restart the Container App to refresh Entra tokens

### Container App Not Starting

**Symptom**: Container App shows "Failed" revision status.

**Cause**: Missing environment variables or ACR pull permission.

**Solution**:
1. Verify all required environment variables are set in Container App configuration
2. Ensure the Container App managed identity has `AcrPull` role on the ACR
3. Check container logs: `az containerapp logs show -n <app-name> -g <resource-group>`

</details>

---

## Architecture Overview

The solution consists of:

- **Backend**: Python 3.11 + FastAPI + Uvicorn running in Azure Container Apps
- **AI Services**:
  - Microsoft Foundry (multi-agent orchestration with Microsoft Agent Framework)
  - Azure OpenAI GPT-4o (specialist agent reasoning)
  - Azure AI Search / Foundry IQ (operational knowledge base)
- **Data Services**:
  - Azure SQL Database (real-time operational data — orders, stations, staffing)
  - Azure Blob Storage (operational documents)
- **Networking**:
  - Azure Container Apps with managed ingress
  - Azure Container Registry (Premium, private)
  - Azure Key Vault for secrets management

---

## Security Considerations

1. **Managed Identity**: The solution uses system-assigned managed identity for authentication between all Azure services — no passwords or connection strings stored.
2. **Entra ID Authentication**: Azure SQL Database uses Entra ID-only authentication (no SQL passwords).
3. **RBAC**: Principle of least privilege — only necessary roles are assigned to each identity.
4. **No Secrets in Code**: All credentials managed through Azure managed identity and Key Vault.
5. **SQL Injection Prevention**: Dynamic SQL is restricted to read-only `SELECT` statements with regex-based write operation blocking.
