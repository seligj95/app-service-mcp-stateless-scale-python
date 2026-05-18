param name string
param location string = resourceGroup().location
param tags object = {}

param appServicePlanId string
param pythonVersion string = '3.11'
param applicationInsightsConnectionString string

var commonAppSettings = [
  {
    name: 'WEBSITES_PORT'
    value: '8000'
  }
  {
    name: 'ENABLE_ORYX_BUILD'
    value: 'true'
  }
  {
    name: 'SCM_DO_BUILD_DURING_DEPLOYMENT'
    value: 'true'
  }
  {
    name: 'PYTHONPATH'
    value: '/home/site/wwwroot'
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: applicationInsightsConnectionString
  }
  {
    name: 'ApplicationInsightsAgent_EXTENSION_VERSION'
    value: '~3'
  }
  {
    name: 'XDT_MicrosoftApplicationInsights_Mode'
    value: 'recommended'
  }
]

var commonSiteConfig = {
  linuxFxVersion: 'PYTHON|${pythonVersion}'
  alwaysOn: true
  ftpsState: 'FtpsOnly'
  appCommandLine: 'python -m uvicorn main:app --host 0.0.0.0 --port 8000'
  http20Enabled: true
  minTlsVersion: '1.2'
  cors: {
    allowedOrigins: ['*']
    supportCredentials: false
  }
  healthCheckPath: '/health'
}

resource web 'Microsoft.Web/sites@2024-04-01' = {
  name: name
  location: location
  tags: union(tags, {
    'azd-service-name': 'web'
  })
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlanId
    reserved: true
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: union(commonSiteConfig, {
      appSettings: commonAppSettings
    })
  }
}

resource staging 'Microsoft.Web/sites/slots@2024-04-01' = {
  parent: web
  name: 'staging'
  location: location
  tags: tags
  kind: 'app,linux'
  properties: {
    serverFarmId: appServicePlanId
    reserved: true
    httpsOnly: true
    clientAffinityEnabled: false
    siteConfig: union(commonSiteConfig, {
      appSettings: commonAppSettings
    })
  }
}

output id string = web.id
output name string = web.name
output uri string = 'https://${web.properties.defaultHostName}'
output stagingUri string = 'https://${staging.properties.defaultHostName}'
