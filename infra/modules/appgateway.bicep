// Application Gateway WAF_v2 — HTTPS entry point for MULTI-AGENT OPS ASSISTANT (secure mode)
// Uses Azure Verified Modules (AVM) where available.
// Raw resources: Public IP (runtime outputs needed), WAF Policy (no AVM module), KV role assignment (scoped).
//
// Deployed only in secure mode (usePrivateEndpoints=true).
//
// Two modes:
//   Custom domain: Client → App GW (HTTPS + SSL cert from Key Vault) → Container App (internal, port 443)
//                  HTTP (port 80) redirects to HTTPS.
//   No domain:     Client → App GW (HTTP + WAF) → Container App (internal, port 443)
//                  Uses Azure-assigned DNS label (agw-<project>-<suffix>.<region>.cloudapp.azure.com)

@description('Base name for resource naming')
param projectName string

@description('Unique suffix for globally unique names')
param nameSuffix string

@description('Azure region for all resources')
param location string

@description('App Gateway subnet resource ID')
param subnetId string

@description('Backend FQDN of the internal Container App')
param backendFqdn string

@description('Custom domain hostname — leave empty to use Azure-assigned DNS label with HTTP + WAF (no cert required)')
param hostname string = ''

@description('Key Vault resource ID (always provided; SSL cert used only when hostname is set)')
param keyVaultResourceId string

@description('Name of the SSL certificate in Key Vault (used only when hostname is provided)')
param sslCertName string = 'appgw-ssl-cert'

@description('Tags to apply to all resources')
param tags object = {}

var appGwName = 'agw-${projectName}-${nameSuffix}'
var pipName = 'pip-agw-${projectName}-${nameSuffix}'
var identityName = 'id-agw-${projectName}-${nameSuffix}'
var wafPolicyName = 'waf-${projectName}-${nameSuffix}'
var useCustomDomain = !empty(hostname)

// ── User-Assigned Managed Identity (AVM) ──
module identity 'br/public:avm/res/managed-identity/user-assigned-identity:0.5.0' = {
  name: 'agw-identity'
  params: {
    name: identityName
    location: location
    tags: tags
  }
}

// ── Grant the identity Key Vault Secrets User role ──
var keyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
resource keyVault 'Microsoft.KeyVault/vaults@2023-07-01' existing = {
  name: last(split(keyVaultResourceId, '/'))
}

resource kvRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(keyVaultResourceId, identityName, keyVaultSecretsUser)
  scope: keyVault
  properties: {
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', keyVaultSecretsUser)
    principalId: identity.outputs.principalId
    principalType: 'ServicePrincipal'
  }
}

// ── Public IP address (raw — runtime properties needed for outputs) ──
resource publicIp 'Microsoft.Network/publicIPAddresses@2024-01-01' = {
  name: pipName
  location: location
  sku: {
    name: 'Standard'
    tier: 'Regional'
  }
  properties: {
    publicIPAllocationMethod: 'Static'
    dnsSettings: {
      domainNameLabel: 'agw-${projectName}-${nameSuffix}'
    }
  }
  tags: tags
}

// ── WAF Policy (raw — no AVM module available, required by AVM App GW for WAF_v2) ──
resource wafPolicy 'Microsoft.Network/ApplicationGatewayWebApplicationFirewallPolicies@2024-01-01' = {
  name: wafPolicyName
  location: location
  properties: {
    policySettings: {
      requestBodyCheck: true
      maxRequestBodySizeInKb: 128
      fileUploadLimitInMb: 100
      state: 'Enabled'
      mode: 'Prevention'
    }
    managedRules: {
      managedRuleSets: [
        {
          ruleSetType: 'OWASP'
          ruleSetVersion: '3.2'
        }
      ]
    }
  }
  tags: tags
}

// ── Application Gateway (AVM, WAF_v2) ──
module appGw 'br/public:avm/res/network/application-gateway:0.8.0' = {
  name: 'appgw'
  params: {
    name: appGwName
    location: location
    sku: 'WAF_v2'
    autoscaleMinCapacity: 1
    autoscaleMaxCapacity: 3
    availabilityZones: []
    firewallPolicyResourceId: wafPolicy.id
    managedIdentities: {
      userAssignedResourceIds: [ identity.outputs.resourceId ]
    }
    gatewayIPConfigurations: [
      {
        name: 'appGwIpConfig'
        properties: {
          subnet: { id: subnetId }
        }
      }
    ]
    frontendIPConfigurations: [
      {
        name: 'appGwFrontendIp'
        properties: {
          publicIPAddress: { id: publicIp.id }
        }
      }
    ]
    frontendPorts: [
      { name: 'port-443', properties: { port: 443 } }
      { name: 'port-80', properties: { port: 80 } }
    ]
    sslCertificates: useCustomDomain ? [
      {
        name: 'kv-ssl-cert'
        properties: {
          keyVaultSecretId: '${keyVault.properties.vaultUri}secrets/${sslCertName}'
        }
      }
    ] : []
    backendAddressPools: [
      {
        name: 'containerapp-backend'
        properties: {
          backendAddresses: [ { fqdn: backendFqdn } ]
        }
      }
    ]
    backendHttpSettingsCollection: [
      {
        name: 'https-settings'
        properties: {
          port: 443
          protocol: 'Https'
          cookieBasedAffinity: 'Disabled'
          requestTimeout: 120
          pickHostNameFromBackendAddress: true
          probe: {
            id: resourceId('Microsoft.Network/applicationGateways/probes', appGwName, 'health-probe')
          }
        }
      }
    ]
    httpListeners: useCustomDomain ? [
      {
        name: 'https-listener'
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appGwName, 'appGwFrontendIp')
          }
          frontendPort: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGwName, 'port-443')
          }
          protocol: 'Https'
          sslCertificate: {
            id: resourceId('Microsoft.Network/applicationGateways/sslCertificates', appGwName, 'kv-ssl-cert')
          }
          hostNames: [ hostname ]
          requireServerNameIndication: true
        }
      }
      {
        name: 'http-listener'
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appGwName, 'appGwFrontendIp')
          }
          frontendPort: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGwName, 'port-80')
          }
          protocol: 'Http'
          hostNames: [ hostname ]
        }
      }
    ] : [
      {
        name: 'http-listener'
        properties: {
          frontendIPConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendIPConfigurations', appGwName, 'appGwFrontendIp')
          }
          frontendPort: {
            id: resourceId('Microsoft.Network/applicationGateways/frontendPorts', appGwName, 'port-80')
          }
          protocol: 'Http'
        }
      }
    ]
    requestRoutingRules: useCustomDomain ? [
      {
        name: 'https-rule'
        properties: {
          priority: 100
          ruleType: 'Basic'
          httpListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appGwName, 'https-listener')
          }
          backendAddressPool: {
            id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGwName, 'containerapp-backend')
          }
          backendHttpSettings: {
            id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGwName, 'https-settings')
          }
        }
      }
      {
        name: 'http-to-https-redirect'
        properties: {
          priority: 200
          ruleType: 'Basic'
          httpListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appGwName, 'http-listener')
          }
          redirectConfiguration: {
            id: resourceId('Microsoft.Network/applicationGateways/redirectConfigurations', appGwName, 'redirect-http-to-https')
          }
        }
      }
    ] : [
      {
        name: 'http-rule'
        properties: {
          priority: 100
          ruleType: 'Basic'
          httpListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appGwName, 'http-listener')
          }
          backendAddressPool: {
            id: resourceId('Microsoft.Network/applicationGateways/backendAddressPools', appGwName, 'containerapp-backend')
          }
          backendHttpSettings: {
            id: resourceId('Microsoft.Network/applicationGateways/backendHttpSettingsCollection', appGwName, 'https-settings')
          }
        }
      }
    ]
    redirectConfigurations: useCustomDomain ? [
      {
        name: 'redirect-http-to-https'
        properties: {
          redirectType: 'Permanent'
          targetListener: {
            id: resourceId('Microsoft.Network/applicationGateways/httpListeners', appGwName, 'https-listener')
          }
          includePath: true
          includeQueryString: true
        }
      }
    ] : []
    probes: [
      {
        name: 'health-probe'
        properties: {
          protocol: 'Https'
          path: '/'
          interval: 30
          timeout: 30
          unhealthyThreshold: 3
          pickHostNameFromBackendHttpSettings: true
          minServers: 0
          match: { statusCodes: [ '200-399' ] }
        }
      }
    ]
    tags: tags
  }
  dependsOn: [ kvRoleAssignment ]
}

@description('Application Gateway public IP address')
output publicIpAddress string = publicIp.properties.ipAddress

@description('Application Gateway FQDN (Azure-assigned)')
output fqdn string = publicIp.properties.dnsSettings.fqdn

@description('Application Gateway name')
output appGwName string = appGw.outputs.name
