// Virtual Network with subnets for App Gateway, Container Apps, and Private Endpoints
// Uses Azure Verified Modules (AVM)

@description('Base name for resource naming')
param projectName string

@description('Unique suffix for globally unique names')
param nameSuffix string

@description('Azure region for all resources')
param location string

@description('Tags to apply to all resources')
param tags object = {}

var vnetName = 'vnet-${projectName}-${nameSuffix}'
var nsgAppGwName = 'nsg-appgw-${projectName}'
var nsgPeName = 'nsg-pe-${projectName}'

// ── NSG for App Gateway subnet (required ports for WAF_v2) ──
module nsgAppGw 'br/public:avm/res/network/network-security-group:0.5.0' = {
  name: 'nsg-appgw'
  params: {
    name: nsgAppGwName
    location: location
    securityRules: [
      {
        name: 'AllowHTTP'
        properties: {
          priority: 100
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '80'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowHTTPS'
        properties: {
          priority: 110
          direction: 'Inbound'
          access: 'Allow'
          protocol: 'Tcp'
          sourcePortRange: '*'
          destinationPortRange: '443'
          sourceAddressPrefix: 'Internet'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowGatewayManager'
        properties: {
          priority: 200
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '65200-65535'
          sourceAddressPrefix: 'GatewayManager'
          destinationAddressPrefix: '*'
        }
      }
      {
        name: 'AllowAzureLoadBalancer'
        properties: {
          priority: 210
          direction: 'Inbound'
          access: 'Allow'
          protocol: '*'
          sourcePortRange: '*'
          destinationPortRange: '*'
          sourceAddressPrefix: 'AzureLoadBalancer'
          destinationAddressPrefix: '*'
        }
      }
    ]
    tags: tags
  }
}

// ── NSG for Private Endpoints subnet ──
module nsgPe 'br/public:avm/res/network/network-security-group:0.5.0' = {
  name: 'nsg-pe'
  params: {
    name: nsgPeName
    location: location
    tags: tags
  }
}

// ── Virtual Network ──
module vnet 'br/public:avm/res/network/virtual-network:0.7.0' = {
  name: 'vnet'
  params: {
    name: vnetName
    location: location
    addressPrefixes: [
      '10.0.0.0/16'
    ]
    subnets: [
      {
        name: 'snet-appgw'
        addressPrefix: '10.0.0.0/24'
        networkSecurityGroupResourceId: nsgAppGw.outputs.resourceId
      }
      {
        name: 'snet-containerapp'
        addressPrefix: '10.0.2.0/23'
        delegation: 'Microsoft.App/environments'
      }
      {
        name: 'snet-privateendpoints'
        addressPrefix: '10.0.4.0/24'
        networkSecurityGroupResourceId: nsgPe.outputs.resourceId
      }
    ]
    tags: tags
  }
}

@description('VNet resource ID')
output vnetId string = vnet.outputs.resourceId

@description('VNet name')
output vnetName string = vnet.outputs.name

@description('App Gateway subnet ID')
output appGwSubnetId string = vnet.outputs.subnetResourceIds[0]

@description('Container Apps infrastructure subnet ID')
output containerAppSubnetId string = vnet.outputs.subnetResourceIds[1]

@description('Private Endpoints subnet ID')
output privateEndpointSubnetId string = vnet.outputs.subnetResourceIds[2]
