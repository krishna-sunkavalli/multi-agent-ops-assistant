// Private DNS zone for internal Container Apps Environment
// Required so App Gateway and other VNet resources can resolve internal Container App FQDNs.
// Uses Azure Verified Modules (AVM)

@description('Default domain of the Container Apps Environment (e.g., braverock-xxx.northcentralus.azurecontainerapps.io)')
param defaultDomain string

@description('Static IP of the Container Apps Environment')
param staticIp string

@description('VNet resource ID to link the DNS zone to')
param vnetId string

@description('Tags to apply to all resources')
param tags object = {}

module dnsZone 'br/public:avm/res/network/private-dns-zone:0.7.0' = {
  name: 'dns-zone-cae'
  params: {
    name: defaultDomain
    virtualNetworkLinks: [
      {
        name: 'vnet-link-cae'
        virtualNetworkResourceId: vnetId
        registrationEnabled: false
      }
    ]
    a: [
      {
        name: '*'
        ttl: 300
        aRecords: [
          {
            ipv4Address: staticIp
          }
        ]
      }
    ]
    tags: tags
  }
}
