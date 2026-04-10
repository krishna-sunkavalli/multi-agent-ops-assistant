# Azure Infrastructure Standards
# Applies to all customer-facing demo and reference architecture repos

---

## Module Strategy

- Always use Azure Verified Modules (AVM) before authoring raw Bicep resources
- Before writing any resource, check https://aka.ms/avm for an existing module
- If no AVM module exists, follow AVM parameter naming conventions for consistency
- Do not wrap AVM modules in unnecessary abstraction layers — call them directly
- Pin AVM module versions explicitly — never use floating references

---

## Networking

### Topology
- Support both hub-spoke (Azure Firewall + UDR) and vWAN topologies — ask which applies if not clear from context
- Never create standalone VNets without peering or connectivity to a hub unless explicitly building an isolated sandbox
- Do not hardcode address spaces — always parameterize CIDR ranges

### Subnets & NSGs
- Every subnet must have an NSG associated — no exceptions
- NSG rules must follow least-privilege: deny all inbound by default, allow only required ports explicitly
- Use Application Security Groups (ASGs) for workload-to-workload rules instead of IP-based rules where possible
- AzureBastionSubnet, GatewaySubnet, and RouteServerSubnet are exempt from custom NSGs (platform requirement)

### Routing
- All spoke traffic must route through Azure Firewall via UDR — do not allow direct internet egress from spoke subnets
- Default route (0.0.0.0/0) must point to the Firewall private IP or vWAN hub

### Ingress
- All inbound HTTP/HTTPS traffic must route through an existing Application Gateway
- Do not create new public IPs for workloads — use the shared Application Gateway frontend
- Application Gateway must have WAF policy attached (Prevention mode for production, Detection for demos unless stated otherwise)
- Do not use Azure Load Balancer as an internet-facing ingress point

### Private DNS
- Use Azure Private DNS Zones for all Private Endpoint resolution
- Link Private DNS Zones to the hub VNet — not to spoke VNets directly
- Do not enable public DNS resolution for services that have a Private Endpoint configured
- Naming pattern: `privatelink.<service>.core.windows.net` — follow Microsoft standard zone names exactly

---

## Identity & RBAC

### Managed Identity
- All Azure services must use Managed Identity (system-assigned by default)
- Use user-assigned Managed Identity when the identity is shared across multiple resources or needs to survive resource recreation
- Never use service principals with client secrets for service-to-service authentication where Managed Identity is supported
- Never use storage account keys, connection strings, or SAS tokens where Managed Identity + RBAC is available

### Role Assignments
- Always assign the minimum required role — do not assign Contributor or Owner to workload identities
- Preferred roles by service:
  - Storage: `Storage Blob Data Reader` / `Storage Blob Data Contributor`
  - Key Vault: `Key Vault Secrets User` / `Key Vault Crypto User`
  - Service Bus: `Azure Service Bus Data Sender` / `Azure Service Bus Data Receiver`
  - Azure AI services: `Cognitive Services User`
- Scope role assignments to the resource level, not subscription or resource group, unless explicitly required
- Do not use `az role assignment create` with `--role Owner` in demo scripts — flag this as a security concern

### Key Vault
- Every deployment must have a Key Vault for secrets and certificates
- Key Vault must have soft-delete and purge protection enabled
- Access model: use RBAC, not Access Policies
- Key Vault must be deployed with a Private Endpoint — no public network access

---

## PaaS Security

### Private Endpoints
- All PaaS services must have a Private Endpoint configured — this is non-negotiable
- Services this applies to (minimum): Storage Accounts, Key Vault, Azure SQL, Cosmos DB, Service Bus, Event Hub, ACR, Azure AI services, Azure OpenAI, AI Search, App Configuration
- After creating a Private Endpoint, set `publicNetworkAccess: 'Disabled'` on the resource
- Do not leave `publicNetworkAccess` at default — always set it explicitly

### Customer-Managed Keys (CMK)
- Enable CMK for Storage Accounts and Azure AI services in any architecture presented as production-grade
- CMK key must be stored in Key Vault with auto-rotation configured
- The resource's Managed Identity must have `Key Vault Crypto User` on the CMK key

### Network Access Controls
- Storage Accounts: default action `Deny`, allowlist only required subnet service endpoints or Private Endpoints
- Key Vault: default action `Deny`
- ACR: disable admin user, use Managed Identity pull, set `publicNetworkAccess: 'Disabled'`
- Azure AI / OpenAI: set `publicNetworkAccess: 'Disabled'`, use Private Endpoint for all model inference traffic

---

## Naming & Tagging (CAF)

### Naming Convention
Follow CAF abbreviation standards: `<abbreviation>-<workload>-<environment>-<region>-<instance>`

| Resource | Abbreviation |
|---|---|
| Resource Group | `rg` |
| Virtual Network | `vnet` |
| Subnet | `snet` |
| Network Security Group | `nsg` |
| Application Gateway | `agw` |
| Azure Firewall | `afw` |
| Key Vault | `kv` |
| Storage Account | `st` (no hyphens, max 24 chars) |
| Log Analytics Workspace | `log` |
| App Service Plan | `asp` |
| App Service | `app` |
| Container App | `ca` |
| Container App Environment | `cae` |
| Azure OpenAI | `oai` |
| AI Search | `srch` |
| Cosmos DB Account | `cosmos` |
| Service Bus Namespace | `sb` |

- Environment values: `dev`, `test`, `uat`, `prod`
- Region shortcodes: `eus` (East US), `eus2` (East US 2), `cus` (Central US), `wus2` (West US 2)
- Example: `kv-blazefitness-prod-eus2-001`

### Required Tags
Every resource and resource group must include:

```bicep
tags: {
  Environment: environment          // dev | test | uat | prod
  WorkloadName: workloadName        // e.g. 'BlazeFitness'
  Owner: owner                      // team or individual
  CostCenter: costCenter            // billing code
  DeployedBy: 'Bicep/AVM'
}
```

---

## Monitoring & Diagnostics

### Log Analytics
- Every deployment must include a Log Analytics Workspace
- All resources must send diagnostic logs to the shared Log Analytics Workspace
- Do not create per-resource Log Analytics Workspaces — use the centralized workspace

### Diagnostic Settings
- Enable diagnostic settings on every resource that supports it
- Minimum log categories to enable: audit logs, sign-in logs, resource-specific operational logs
- Always enable metrics collection alongside logs
- Retention: minimum 30 days for demos, 90 days for production-aligned architectures

### Alerts
- Include at least one Azure Monitor Alert Rule per critical resource (Key Vault, App Gateway, Firewall)
- Alert rules must have an Action Group configured — do not create alerts without notification targets

### Application Insights
- Any compute workload (App Service, Container Apps, Functions, AKS) must have Application Insights connected
- Use workspace-based Application Insights linked to the central Log Analytics Workspace
- Never create classic (non-workspace-based) Application Insights resources

---

## General Bicep Standards

- Parameters over hardcoded values — every environment-specific value must be a parameter
- No secrets in `.bicep` or `.bicepparam` files — use Key Vault references via `existing` resource
- Every module must expose outputs for resource IDs, names, and any values needed downstream
- Use `@description()` decorators on all parameters and outputs
- Prefer `targetScope = 'resourceGroup'` unless subscription or management group scope is explicitly required
- Always set `location` from a parameter — never hardcode region strings

## CI/CD
- GitHub Actions workflows are in `.github/workflows/`
- Bicep deployments use `az deployment group create` — do not suggest Terraform or ARM JSON
- Always validate Bicep with `az bicep build` before suggesting a deployment step