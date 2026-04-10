// Private Endpoints and Private DNS Zones for all backend services
// Uses Azure Verified Modules (AVM)

@description('Azure region for all resources')
param location string

@description('VNet resource ID for DNS zone links')
param vnetId string

@description('Subnet ID for private endpoints')
param privateEndpointSubnetId string

@description('SQL Server resource ID')
param sqlServerResourceId string

@description('AI Search service resource ID')
param searchResourceId string

@description('Storage account resource ID')
param storageResourceId string

@description('Key Vault resource ID')
param keyVaultResourceId string

@description('Cognitive Services (Foundry) account resource ID')
param foundryResourceId string

@description('Container Registry resource ID')
param acrResourceId string

@description('Tags to apply to all resources')
param tags object = {}

// ── Private DNS Zone names ──
var dnsZoneNames = {
  sql: 'privatelink${environment().suffixes.sqlServerHostname}'
  search: 'privatelink.search.windows.net'
  blob: 'privatelink.blob.${environment().suffixes.storage}'
  keyVault: 'privatelink.vaultcore.azure.net'
  cognitiveServices: 'privatelink.cognitiveservices.azure.com'
  openai: 'privatelink.openai.azure.com'
  aiServices: 'privatelink.services.ai.azure.com'
  acr: 'privatelink.azurecr.io'
}

// ── VNet link config (shared by all DNS zones) ──
var vnetLinks = [
  {
    virtualNetworkResourceId: vnetId
    registrationEnabled: false
  }
]

// ── Private DNS Zones (AVM) ──────────────────────────────────────────────

module dnsZoneSql 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-sql'
  params: {
    name: dnsZoneNames.sql
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneSearch 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-search'
  params: {
    name: dnsZoneNames.search
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneBlob 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-blob'
  params: {
    name: dnsZoneNames.blob
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneKeyVault 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-keyvault'
  params: {
    name: dnsZoneNames.keyVault
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneCognitiveServices 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-cogsvcs'
  params: {
    name: dnsZoneNames.cognitiveServices
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneOpenai 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-openai'
  params: {
    name: dnsZoneNames.openai
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneAiServices 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-aiservices'
  params: {
    name: dnsZoneNames.aiServices
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

module dnsZoneAcr 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-acr'
  params: {
    name: dnsZoneNames.acr
    virtualNetworkLinks: vnetLinks
    tags: tags
  }
}

// ── Private Endpoints (AVM) ──────────────────────────────────────────────

module peSql 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: 'pe-sql'
  params: {
    name: 'pe-sql'
    location: location
    subnetResourceId: privateEndpointSubnetId
    privateLinkServiceConnections: [
      {
        name: 'pe-sql-conn'
        properties: {
          privateLinkServiceId: sqlServerResourceId
          groupIds: [ 'sqlServer' ]
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          privateDnsZoneResourceId: dnsZoneSql.outputs.resourceId
        }
      ]
    }
    tags: tags
  }
}

module peSearch 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: 'pe-search'
  params: {
    name: 'pe-search'
    location: location
    subnetResourceId: privateEndpointSubnetId
    privateLinkServiceConnections: [
      {
        name: 'pe-search-conn'
        properties: {
          privateLinkServiceId: searchResourceId
          groupIds: [ 'searchService' ]
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          privateDnsZoneResourceId: dnsZoneSearch.outputs.resourceId
        }
      ]
    }
    tags: tags
  }
}

module peBlob 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: 'pe-blob'
  params: {
    name: 'pe-blob'
    location: location
    subnetResourceId: privateEndpointSubnetId
    privateLinkServiceConnections: [
      {
        name: 'pe-blob-conn'
        properties: {
          privateLinkServiceId: storageResourceId
          groupIds: [ 'blob' ]
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          privateDnsZoneResourceId: dnsZoneBlob.outputs.resourceId
        }
      ]
    }
    tags: tags
  }
}

module peKeyVault 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: 'pe-keyvault'
  params: {
    name: 'pe-keyvault'
    location: location
    subnetResourceId: privateEndpointSubnetId
    privateLinkServiceConnections: [
      {
        name: 'pe-keyvault-conn'
        properties: {
          privateLinkServiceId: keyVaultResourceId
          groupIds: [ 'vault' ]
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          privateDnsZoneResourceId: dnsZoneKeyVault.outputs.resourceId
        }
      ]
    }
    tags: tags
  }
}

module peCognitiveServices 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: 'pe-cogsvcs'
  params: {
    name: 'pe-cogsvcs'
    location: location
    subnetResourceId: privateEndpointSubnetId
    privateLinkServiceConnections: [
      {
        name: 'pe-cogsvcs-conn'
        properties: {
          privateLinkServiceId: foundryResourceId
          groupIds: [ 'account' ]
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          privateDnsZoneResourceId: dnsZoneCognitiveServices.outputs.resourceId
        }
        {
          privateDnsZoneResourceId: dnsZoneOpenai.outputs.resourceId
        }
        {
          privateDnsZoneResourceId: dnsZoneAiServices.outputs.resourceId
        }
      ]
    }
    tags: tags
  }
}

module peAcr 'br/public:avm/res/network/private-endpoint:0.12.0' = {
  name: 'pe-acr'
  params: {
    name: 'pe-acr'
    location: location
    subnetResourceId: privateEndpointSubnetId
    privateLinkServiceConnections: [
      {
        name: 'pe-acr-conn'
        properties: {
          privateLinkServiceId: acrResourceId
          groupIds: [ 'registry' ]
        }
      }
    ]
    privateDnsZoneGroup: {
      privateDnsZoneGroupConfigs: [
        {
          privateDnsZoneResourceId: dnsZoneAcr.outputs.resourceId
        }
      ]
    }
    tags: tags
  }
}
