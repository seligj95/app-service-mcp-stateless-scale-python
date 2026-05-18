targetScope = 'resourceGroup'

@minLength(1)
@maxLength(64)
@description('Name of the environment that can be used as part of naming resource convention')
param environmentName string

@minLength(1)
@description('Primary location for all resources')
param location string

@description('Id of the user or app to assign application roles')
param principalId string = ''

@description('Python runtime version on App Service')
param pythonVersion string = '3.11'

@description('Number of App Service instances to run in parallel (the unit of horizontal scale)')
@minValue(1)
@maxValue(10)
param instanceCount int = 3

@description('SKU of the App Service plan (must be Premium for staging slots + Always On)')
param appServicePlanSkuName string = 'P0v3'

@description('Optional override for the App Service Plan name')
param appServicePlanName string = ''

var abbrs = loadJsonContent('./abbreviations.json')
var resourceToken = toLower(uniqueString(subscription().id, environmentName, location))
var tags = {
  'azd-env-name': environmentName
}

module monitoring './shared/monitoring.bicep' = {
  name: 'monitoring'
  params: {
    logAnalyticsName: '${abbrs.operationalInsightsWorkspaces}${resourceToken}'
    applicationInsightsName: '${abbrs.insightsComponents}${resourceToken}'
    location: location
    tags: tags
  }
}

module appServicePlan './shared/app-service-plan.bicep' = {
  name: 'app-service-plan'
  params: {
    name: !empty(appServicePlanName) ? appServicePlanName : '${abbrs.webServerFarms}${resourceToken}'
    location: location
    tags: tags
    skuName: appServicePlanSkuName
    instanceCount: instanceCount
    reserved: true
  }
}

module web './app/web.bicep' = {
  name: 'web'
  params: {
    name: '${abbrs.webSitesAppService}web-${resourceToken}'
    location: location
    tags: tags
    appServicePlanId: appServicePlan.outputs.id
    pythonVersion: pythonVersion
    applicationInsightsConnectionString: monitoring.outputs.applicationInsightsConnectionString
  }
}

output AZURE_LOCATION string = location
output AZURE_TENANT_ID string = tenant().tenantId
output WEB_URI string = web.outputs.uri
output WEB_STAGING_URI string = web.outputs.stagingUri
output APPLICATIONINSIGHTS_CONNECTION_STRING string = monitoring.outputs.applicationInsightsConnectionString
output APP_INSTANCE_COUNT int = instanceCount
