// ==============================================================================
// Redis Cache Module
// ==============================================================================

param name string
param location string
param tags object
param sku string = 'Basic'
param family string = 'C'
param capacity int = 0

resource redis 'Microsoft.Cache/redis@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    sku: {
      name: sku
      family: family
      capacity: capacity
    }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

output redisId string = redis.id
output hostName string = redis.properties.hostName
output sslPort int = redis.properties.sslPort