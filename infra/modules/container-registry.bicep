// ==============================================================================
// Azure Container Registry Module
// ==============================================================================

param name string
param location string
param tags object
param sku string = 'Standard'
param adminUserEnabled bool = true

resource registry 'Microsoft.ContainerRegistry/registries@2023-07-01' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: sku
  }
  properties: {
    adminUserEnabled: adminUserEnabled
  }
}

output registryId string = registry.id
output name string = registry.name
output loginServer string = registry.properties.loginServer