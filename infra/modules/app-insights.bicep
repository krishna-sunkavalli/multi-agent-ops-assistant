// Application Insights + Log Analytics workspace for Foundry distributed tracing
// Uses Azure Verified Modules (AVM)

@description('Base name for resource naming')
param projectName string

@description('Unique suffix for globally unique names')
param nameSuffix string

@description('Azure region for all resources')
param location string

@description('Tags to apply to all resources')
param tags object = {}

var logAnalyticsName = 'log-${projectName}-${nameSuffix}'
var appInsightsName = 'appi-${projectName}-${nameSuffix}'

// Log Analytics workspace (backing store for Application Insights)
module logAnalytics 'br/public:avm/res/operational-insights/workspace:0.10.0' = {
  name: 'log-analytics'
  params: {
    name: logAnalyticsName
    location: location
    skuName: 'PerGB2018'
    dataRetention: 30
    tags: tags
  }
}

// Application Insights (workspace-based)
module appInsightsComponent 'br/public:avm/res/insights/component:0.6.0' = {
  name: 'app-insights-component'
  params: {
    name: appInsightsName
    location: location
    workspaceResourceId: logAnalytics.outputs.resourceId
    applicationType: 'web'
    kind: 'web'
    tags: tags
  }
}

@description('Application Insights connection string')
output connectionString string = appInsightsComponent.outputs.connectionString

@description('Application Insights instrumentation key')
output instrumentationKey string = appInsightsComponent.outputs.instrumentationKey

@description('Application Insights resource ID')
output resourceId string = appInsightsComponent.outputs.resourceId

@description('Application Insights name')
output name string = appInsightsName

@description('Log Analytics workspace resource ID')
output logAnalyticsWorkspaceResourceId string = logAnalytics.outputs.resourceId
