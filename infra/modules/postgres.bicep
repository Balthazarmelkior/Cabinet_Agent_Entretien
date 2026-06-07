// ==============================================================================
// PostgreSQL Flexible Server Module
// ==============================================================================

param name string
param location string
param tags object
param administratorLogin string
@secure()
param administratorLoginPassword string
param skuName string = 'Standard_B1ms'
param storageSizeGB int = 32
param version string = '16'
param databaseName string = 'rdv_bilan'

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-12-01-preview' = {
  name: name
  location: location
  tags: tags
  sku: {
    name: skuName
    tier: contains(skuName, 'Standard_D') ? 'GeneralPurpose' : 'Burstable'
  }
  properties: {
    version: version
    administratorLogin: administratorLogin
    administratorLoginPassword: administratorLoginPassword
    storage: {
      storageSizeGB: storageSizeGB
      autoGrow: 'Enabled'
    }
    backup: {
      backupRetentionDays: 7
      geoRedundantBackup: 'Disabled'
    }
  }
}

resource database 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-12-01-preview' = {
  parent: postgres
  name: databaseName
  properties: {
    charset: 'UTF8'
    collation: 'en_US.utf8'
  }
}

resource firewallRuleAllowAll 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-12-01-preview' = {
  parent: postgres
  name: 'AllowAllAzureServices'
  properties: {
    startIpAddress: '0.0.0.0'
    endIpAddress: '0.0.0.0'
  }
}

output serverId string = postgres.id
output fqdn string = postgres.properties.fullyQualifiedDomainName
output databaseName string = database.name