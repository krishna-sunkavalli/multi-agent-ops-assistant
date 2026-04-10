// Ops Assistant — Infrastructure Orchestrator (AVM Edition)
// All resources use Azure Verified Modules where available.
// Default: public access (no VNet). Set USE_PRIVATE_ENDPOINTS=true for private networking.
// Run: azd up

targetScope = 'resourceGroup'

// ═══════════════════════════════════════════════════════
//  Parameters
// ═══════════════════════════════════════════════════════

@description('Base project name used for resource naming')
param projectName string

@description('Azure region for all resources (Sweden Central recommended for Foundry Agent Service)')
param location string = 'swedencentral'

@description('Object ID of the user or service principal running the deployment')
param deployerPrincipalId string

@description('Display name of the deployer (for SQL Entra admin)')
param deployerDisplayName string = 'Deployment Admin'

@description('Custom hostname for the App Gateway (e.g., myapp.example.com)')
param customHostname string = ''

@description('GPT-4o model capacity in thousands of TPM (default 70)')
param modelCapacity int = 70

@description('Deploy private endpoints and VNet integration (default: false = public access)')
param usePrivateEndpoints bool = false

// ═══════════════════════════════════════════════════════
//  Variables
// ═══════════════════════════════════════════════════════

var nameSuffix = uniqueString(resourceGroup().id)
var useAppGateway = usePrivateEndpoints
var useVNet = usePrivateEndpoints
var publicNetworkAccess = usePrivateEndpoints ? 'Disabled' : 'Enabled'
var tags = {
  project: 'multi-agent-ops-assistant'
  environment: 'demo'
}

// Resource naming
var identityName = 'id-${projectName}-${nameSuffix}'
var storageAccountName = take('st${replace(projectName, '-', '')}${nameSuffix}', 24)
var registryName = 'acr${replace(projectName, '-', '')}${nameSuffix}'
var vaultName = take('kv-${replace(projectName, '-', '')}${nameSuffix}', 24)
var searchServiceName = 'srch-${projectName}-${nameSuffix}'
var sqlServerName = 'sql-${projectName}-${nameSuffix}'
var sqlDatabaseName = 'ops-assistant-db'
var foundryAccountName = 'ai-${projectName}-${nameSuffix}'
var foundryProjectName = '${projectName}-project'
var managedEnvName = 'cae-${projectName}-${nameSuffix}'
var containerAppName = 'ca-${projectName}'

// Constructed values
var searchEndpoint = 'https://${searchServiceName}.search.windows.net'
var sqlConnectionString = 'Server=${sql.outputs.fullyQualifiedDomainName};Database=${sqlDatabaseName};Authentication=ActiveDirectoryDefault;Encrypt=True;TrustServerCertificate=False;'

// ═══════════════════════════════════════════════════════
//  1. User-Assigned Managed Identity (AVM)
// ═══════════════════════════════════════════════════════

module acaIdentity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'aca-identity'
  params: {
    name: identityName
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  2. Virtual Network + Subnets (custom module, only when needed)
// ═══════════════════════════════════════════════════════

module network 'modules/network.bicep' = if (useVNet) {
  name: 'network'
  params: {
    projectName: projectName
    nameSuffix: nameSuffix
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  3. AI Foundry — Cognitive Services Account + GPT-4o (AVM)
// ═══════════════════════════════════════════════════════

module foundry 'br/public:avm/res/cognitive-services/account:0.14.2' = {
  name: 'foundry'
  params: {
    name: foundryAccountName
    kind: 'AIServices'
    customSubDomainName: foundryAccountName
    location: location
    allowProjectManagement: true
    publicNetworkAccess: publicNetworkAccess
    managedIdentities: {
      systemAssigned: true
    }
    deployments: [
      {
        name: 'gpt-4o'
        model: {
          format: 'OpenAI'
          name: 'gpt-4o'
        }
        sku: {
          name: 'Standard'
          capacity: modelCapacity
        }
      }
      {
        name: 'gpt-4o-mini'
        model: {
          format: 'OpenAI'
          name: 'gpt-4o-mini'
        }
        sku: {
          name: 'GlobalStandard'
          capacity: modelCapacity
        }
      }
    ]
    roleAssignments: [
      // Deployer → Cognitive Services OpenAI User
      {
        principalId: deployerPrincipalId
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        principalType: 'User'
      }
      // Deployer → Azure AI Developer
      {
        principalId: deployerPrincipalId
        roleDefinitionIdOrName: 'Azure AI Developer'
        principalType: 'User'
      }
      // App MI → Cognitive Services OpenAI User
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Cognitive Services OpenAI User'
        principalType: 'ServicePrincipal'
      }
      // App MI → Cognitive Services User
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Cognitive Services User'
        principalType: 'ServicePrincipal'
      }
      // App MI → Azure AI Developer
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Azure AI Developer'
        principalType: 'ServicePrincipal'
      }
    ]
    tags: tags
  }
}

// ── 3b. Foundry Project (native Bicep — AVM doesn't support projects sub-resource) ──

resource foundryAccountRef 'Microsoft.CognitiveServices/accounts@2025-04-01-preview' existing = {
  name: foundryAccountName
}

resource foundryProject 'Microsoft.CognitiveServices/accounts/projects@2025-04-01-preview' = {
  parent: foundryAccountRef
  name: foundryProjectName
  location: location
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    description: 'Ops Assistant Foundry project'
    displayName: 'Ops Assistant'
  }
  tags: tags
  dependsOn: [foundry]
}

// ═══════════════════════════════════════════════════════
//  3c. Application Insights + Log Analytics (custom module)
// ═══════════════════════════════════════════════════════

module appInsights 'modules/app-insights.bicep' = {
  name: 'app-insights'
  params: {
    projectName: projectName
    nameSuffix: nameSuffix
    location: location
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  4. Azure AI Search (AVM)
// ═══════════════════════════════════════════════════════

module search 'br/public:avm/res/search/search-service:0.12.0' = {
  name: 'search'
  params: {
    name: searchServiceName
    location: location
    sku: 'basic'
    replicaCount: 1
    partitionCount: 1
    hostingMode: 'Default'
    publicNetworkAccess: usePrivateEndpoints ? 'Disabled' : 'Enabled'
    networkRuleSet: usePrivateEndpoints ? {
      bypass: 'None'
      ipRules: []
    } : null
    disableLocalAuth: false
    authOptions: {
      aadOrApiKey: {
        aadAuthFailureMode: 'http401WithBearerChallenge'
      }
    }
    managedIdentities: {
      systemAssigned: true
    }
    roleAssignments: [
      // Deployer → Search Service Contributor
      {
        principalId: deployerPrincipalId
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
        principalType: 'User'
      }
      // App MI → Search Index Data Reader
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: '1407120a-92aa-4202-b7e9-c0e197c71c8f'
        principalType: 'ServicePrincipal'
      }
      // App MI → Search Service Contributor
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
        principalType: 'ServicePrincipal'
      }
    ]
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  5. Storage Account (AVM)
// ═══════════════════════════════════════════════════════

module storage 'br/public:avm/res/storage/storage-account:0.32.0' = {
  name: 'storage'
  params: {
    name: storageAccountName
    location: location
    kind: 'StorageV2'
    skuName: 'Standard_LRS'
    allowBlobPublicAccess: false
    publicNetworkAccess: publicNetworkAccess
    networkAcls: publicNetworkAccess == 'Enabled' ? {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    } : {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
    blobServices: {
      containers: [
        {
          name: 'operational-docs'
          publicAccess: 'None'
        }
      ]
    }
    roleAssignments: [
      // Deployer → Storage Blob Data Contributor
      {
        principalId: deployerPrincipalId
        roleDefinitionIdOrName: 'Storage Blob Data Contributor'
        principalType: 'User'
      }
      // App MI → Storage Blob Data Reader
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: 'Storage Blob Data Reader'
        principalType: 'ServicePrincipal'
      }
    ]
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  6. Azure SQL Server + Database (AVM)
// ═══════════════════════════════════════════════════════

module sql 'br/public:avm/res/sql/server:0.21.1' = {
  name: 'sql'
  params: {
    name: sqlServerName
    location: location
    minimalTlsVersion: '1.2'
    publicNetworkAccess: publicNetworkAccess
    administrators: {
      azureADOnlyAuthentication: true
      login: deployerDisplayName
      principalType: 'User'
      sid: deployerPrincipalId
      tenantId: tenant().tenantId
    }
    databases: [
      {
        name: sqlDatabaseName
        sku: {
          name: 'Basic'
          tier: 'Basic'
        }
        maxSizeBytes: 2147483648
        availabilityZone: -1
        zoneRedundant: false
      }
    ]
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  7. Azure Container Registry (AVM)
// ═══════════════════════════════════════════════════════

module acr 'br/public:avm/res/container-registry/registry:0.12.0' = {
  name: 'acr'
  params: {
    name: registryName
    location: location
    acrSku: 'Premium'
    publicNetworkAccess: publicNetworkAccess
    networkRuleBypassOptions: 'AzureServices'
    networkRuleSetDefaultAction: usePrivateEndpoints ? 'Deny' : 'Allow'
    exportPolicyStatus: 'enabled'
    roleAssignments: [
      // App MI → AcrPull
      {
        principalId: acaIdentity.outputs.principalId
        roleDefinitionIdOrName: '7f951dda-4ed3-4680-a7ca-43fe172d538d'
        principalType: 'ServicePrincipal'
      }
    ]
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  8. Key Vault (AVM) + Secrets (native Bicep)
// ═══════════════════════════════════════════════════════

module keyvault 'br/public:avm/res/key-vault/vault:0.13.3' = {
  name: 'keyvault'
  params: {
    name: vaultName
    location: location
    enableRbacAuthorization: true
    enableSoftDelete: true
    publicNetworkAccess: publicNetworkAccess
    networkAcls: publicNetworkAccess == 'Enabled' ? {
      defaultAction: 'Allow'
      bypass: 'AzureServices'
    } : {
      defaultAction: 'Deny'
      bypass: 'AzureServices'
    }
    roleAssignments: [
      // Deployer → Key Vault Secrets Officer
      {
        principalId: deployerPrincipalId
        roleDefinitionIdOrName: 'Key Vault Secrets Officer'
        principalType: 'User'
      }
      // Deployer → Key Vault Administrator
      {
        principalId: deployerPrincipalId
        roleDefinitionIdOrName: 'Key Vault Administrator'
        principalType: 'User'
      }
    ]
    tags: tags
  }
}

// Key Vault secrets (native Bicep — created after AVM provisions the vault)
resource kvRef 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: vaultName
  dependsOn: [keyvault]
}

resource sqlSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kvRef
  name: 'sql-connection-string'
  properties: {
    value: sqlConnectionString
  }
}

resource searchSecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kvRef
  name: 'search-endpoint'
  properties: {
    value: searchEndpoint
  }
}

resource foundrySecret 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: kvRef
  name: 'foundry-endpoint'
  properties: {
    value: foundryProject.properties.endpoints['AI Foundry API']
  }
}

// ═══════════════════════════════════════════════════════
//  8b. Foundry MI → cross-service role assignments
//  (standalone Bicep — system-assigned MI principalId is runtime-only,
//   so it can't be passed as an AVM roleAssignment parameter)
// ═══════════════════════════════════════════════════════

resource searchRef 'Microsoft.Search/searchServices@2024-06-01-preview' existing = {
  name: searchServiceName
}

resource foundrySearchRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchRef.id, 'foundry-mi', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
  scope: searchRef
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '1407120a-92aa-4202-b7e9-c0e197c71c8f')
    principalId: foundry.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
  dependsOn: [search]
}

resource storageRef 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

resource foundryStorageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storageRef.id, 'foundry-mi', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
  scope: storageRef
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'ba92f5b4-2d11-453d-a403-e96b0029c9fe')
    principalId: foundry.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
  dependsOn: [storage]
}

resource acrRef 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = {
  name: registryName
}

resource foundryAcrRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(acrRef.id, 'foundry-mi', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
  scope: acrRef
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
    principalId: foundry.outputs.systemAssignedMIPrincipalId!
    principalType: 'ServicePrincipal'
  }
  dependsOn: [acr]
}

// ═══════════════════════════════════════════════════════
//  9. Private Endpoints (custom module, only when usePrivateEndpoints)
// ═══════════════════════════════════════════════════════

module privateEndpoints 'modules/private-endpoints.bicep' = if (usePrivateEndpoints) {
  name: 'private-endpoints'
  params: {
    location: location
    vnetId: network!.outputs.vnetId
    privateEndpointSubnetId: network!.outputs.privateEndpointSubnetId
    sqlServerResourceId: sql.outputs.resourceId
    searchResourceId: search.outputs.resourceId
    storageResourceId: storage.outputs.resourceId
    keyVaultResourceId: keyvault.outputs.resourceId
    foundryResourceId: foundry.outputs.resourceId
    acrResourceId: acr.outputs.resourceId
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  10. Container Apps Environment (AVM)
// ═══════════════════════════════════════════════════════

module managedEnv 'br/public:avm/res/app/managed-environment:0.13.1' = {
  name: 'managed-environment'
  params: {
    name: managedEnvName
    location: location
    zoneRedundant: false
    internal: usePrivateEndpoints
    publicNetworkAccess: publicNetworkAccess
    infrastructureSubnetResourceId: useVNet ? network!.outputs.containerAppSubnetId : null
    appInsightsConnectionString: appInsights.outputs.connectionString
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsWorkspaceResourceId: appInsights.outputs.logAnalyticsWorkspaceResourceId
    }
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  11. Container App (AVM)
// ═══════════════════════════════════════════════════════

module containerApp 'br/public:avm/res/app/container-app:0.22.0' = {
  name: 'containerapp'
  params: {
    name: containerAppName
    environmentResourceId: managedEnv.outputs.resourceId
    location: location
    managedIdentities: {
      userAssignedResourceIds: [
        acaIdentity.outputs.resourceId
      ]
    }
    registries: [
      {
        server: '${registryName}.azurecr.io'
        identity: acaIdentity.outputs.resourceId
      }
    ]
    ingressExternal: !usePrivateEndpoints
    ingressTargetPort: 8000
    ingressTransport: 'auto'
    ingressAllowInsecure: false
    containers: [
      {
        name: 'ops-assistant'
        image: 'mcr.microsoft.com/k8se/quickstart:latest'
        resources: {
          cpu: json('1.0')
          memory: '2Gi'
        }
        env: [
          { name: 'AZURE_CLIENT_ID', value: acaIdentity.outputs.clientId }
          { name: 'AZURE_AI_PROJECT_ENDPOINT', value: foundryProject.properties.endpoints['AI Foundry API'] }
          { name: 'AZURE_AI_MODEL_DEPLOYMENT', value: 'gpt-4o' }
          { name: 'AZURE_SEARCH_ENDPOINT', value: searchEndpoint }
          { name: 'KNOWLEDGE_BASE_NAME', value: 'ops-assistant-kb' }
          { name: 'SQL_SERVER_FQDN', value: sql.outputs.fullyQualifiedDomainName }
          { name: 'SQL_DATABASE_NAME', value: sqlDatabaseName }
          { name: 'DEFAULT_STORE_ID', value: 'STORE-001' }
          { name: 'TRIAGE_MODEL_DEPLOYMENT', value: 'gpt-4o-mini' }
          { name: 'AZURE_SUBSCRIPTION_ID', value: subscription().subscriptionId }
          { name: 'AZURE_RESOURCE_GROUP', value: resourceGroup().name }
          { name: 'ENABLE_TRAFFIC_SIMULATOR', value: 'true' }
          { name: 'ENABLE_FOUNDRY_TRACING', value: 'true' }
          { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.outputs.connectionString }
        ]
      }
    ]
    scaleSettings: {
      minReplicas: 1
      maxReplicas: 3
      rules: [
        {
          name: 'http-rule'
          http: {
            metadata: {
              concurrentRequests: '50'
            }
          }
        }
      ]
    }
    tags: union(tags, { 'azd-service-name': 'opsassistant' })
  }
}

// ═══════════════════════════════════════════════════════
//  12. Private DNS zone for internal Container Apps (custom module)
// ═══════════════════════════════════════════════════════

module containerappDns 'modules/containerapp-dns.bicep' = if (usePrivateEndpoints) {
  name: 'containerapp-dns'
  params: {
    defaultDomain: managedEnv.outputs.defaultDomain
    staticIp: managedEnv.outputs.staticIp
    vnetId: network!.outputs.vnetId
    tags: tags
  }
}

// ═══════════════════════════════════════════════════════
//  13. Link Application Insights to Foundry (enables SDK tracing)
// ═══════════════════════════════════════════════════════

resource appInsightsConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: foundryAccountRef
  name: 'appinsights'
  properties: {
    category: 'AppInsights'
    target: appInsights.outputs.resourceId
    authType: 'ApiKey'
    isSharedToAll: true
    credentials: {
      key: appInsights.outputs.instrumentationKey
    }
    metadata: {
      ApiType: 'Azure'
      ResourceId: appInsights.outputs.resourceId
    }
  }
  dependsOn: [foundry]
}

// ═══════════════════════════════════════════════════════
//  14. Link Azure AI Search to Foundry (enables KB discovery)
// ═══════════════════════════════════════════════════════

resource searchConnection 'Microsoft.CognitiveServices/accounts/connections@2025-04-01-preview' = {
  parent: foundryAccountRef
  name: 'cognitive-search'
  properties: {
    category: 'CognitiveSearch'
    target: searchEndpoint
    authType: 'AAD'
    isSharedToAll: true
    metadata: {
      ApiType: 'Azure'
      ResourceId: search.outputs.resourceId
    }
  }
  dependsOn: [foundry]
}

// ═══════════════════════════════════════════════════════
//  15. Application Gateway (secure mode: HTTPS frontend → internal Container App)
// ═══════════════════════════════════════════════════════

module appgateway 'modules/appgateway.bicep' = if (useAppGateway) {
  name: 'appgateway'
  params: {
    projectName: projectName
    nameSuffix: nameSuffix
    location: location
    subnetId: network!.outputs.appGwSubnetId
    backendFqdn: containerApp.outputs.fqdn
    hostname: customHostname
    keyVaultResourceId: keyvault.outputs.resourceId
    tags: tags
  }
  dependsOn: [privateEndpoints, containerappDns]
}

// ═══════════════════════════════════════════════════════
//  Outputs (azd-compatible)
// ═══════════════════════════════════════════════════════

@description('Foundry project endpoint (for AIProjectClient / Agents API)')
output AZURE_AI_PROJECT_ENDPOINT string = foundryProject.properties.endpoints['AI Foundry API']

@description('Foundry project name')
output AZURE_PROJECT_NAME string = foundryProjectName

@description('Azure AI Search endpoint')
output AZURE_SEARCH_ENDPOINT string = searchEndpoint

@description('Azure AI Search service name')
output AZURE_SEARCH_SERVICE_NAME string = search.outputs.name

@description('SQL Server FQDN')
output SQL_SERVER_FQDN string = sql.outputs.fullyQualifiedDomainName

@description('SQL Server name')
output SQL_SERVER_NAME string = sql.outputs.name

@description('SQL database name')
output SQL_DATABASE_NAME string = sqlDatabaseName

@description('SQL connection string (Entra ID auth)')
output SQL_CONNECTION_STRING string = sqlConnectionString

@description('ACR login server')
output AZURE_CONTAINER_REGISTRY_ENDPOINT string = acr.outputs.loginServer

@description('ACR registry name')
output AZURE_CONTAINER_REGISTRY_NAME string = acr.outputs.name

@description('Key Vault URI')
output AZURE_KEY_VAULT_URI string = keyvault.outputs.uri

@description('Key Vault name')
output AZURE_KEY_VAULT_NAME string = keyvault.outputs.name

@description('Storage account name')
output AZURE_STORAGE_ACCOUNT_NAME string = storage.outputs.name

@description('Storage blob endpoint')
output AZURE_STORAGE_BLOB_ENDPOINT string = storage.outputs.primaryBlobEndpoint

@description('Container App internal FQDN')
output SERVICE_OPSASSISTANT_FQDN string = containerApp.outputs.fqdn

@description('Container App name')
output SERVICE_OPSASSISTANT_NAME string = containerApp.outputs.name

@description('Container App managed identity principal ID')
output SERVICE_OPSASSISTANT_PRINCIPAL_ID string = acaIdentity.outputs.principalId

@description('Container App managed identity client ID (used for SQL SID)')
output SERVICE_OPSASSISTANT_CLIENT_ID string = acaIdentity.outputs.clientId

@description('Application Gateway public IP (empty when App Gateway is not deployed)')
output APP_GATEWAY_IP string = useAppGateway ? appgateway!.outputs.publicIpAddress : ''

@description('Application Gateway FQDN (empty when App Gateway is not deployed)')
output APP_GATEWAY_FQDN string = useAppGateway ? appgateway!.outputs.fqdn : ''

@description('Application Gateway name (empty when App Gateway is not deployed)')
output APP_GATEWAY_NAME string = useAppGateway ? appgateway!.outputs.appGwName : ''

@description('Public URL (App Gateway HTTPS in secure mode with custom domain, HTTP with Azure DNS label, or direct Container App in public mode)')
output SERVICE_OPSASSISTANT_URL string = useAppGateway
  ? (!empty(customHostname) ? 'https://${customHostname}' : 'http://${appgateway!.outputs.fqdn}')
  : 'https://${containerApp.outputs.fqdn}'

@description('Foundry account name (for postprovision KB setup)')
output AZURE_AI_ACCOUNT_NAME string = foundryAccountName

@description('Resource group name (for hooks)')
output AZURE_RESOURCE_GROUP_NAME string = resourceGroup().name

@description('VNet name (empty when VNet is not deployed)')
output VNET_NAME string = useVNet ? network!.outputs.vnetName : ''

@description('Whether private endpoints are enabled (for postprovision hook)')
output USE_PRIVATE_ENDPOINTS string = usePrivateEndpoints ? 'true' : 'false'

@description('Application Insights connection string')
output APPLICATIONINSIGHTS_CONNECTION_STRING string = appInsights.outputs.connectionString

@description('Application Insights name')
output APPLICATIONINSIGHTS_NAME string = appInsights.outputs.name
