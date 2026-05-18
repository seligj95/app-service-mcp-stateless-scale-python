param name string
param location string = resourceGroup().location
param tags object = {}

@description('SKU name. Premium v3 is required for staging slots and Always On at this scale.')
param skuName string = 'P0v3'

@description('Number of instances to run in parallel')
@minValue(1)
@maxValue(10)
param instanceCount int = 3

param reserved bool = true

resource appServicePlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    capacity: instanceCount
  }
  properties: {
    reserved: reserved
  }
}

output id string = appServicePlan.id
output name string = appServicePlan.name
output instanceCount int = instanceCount
