// ==============================================================================
// main.bicep - Infrastructure Azure pour Cabinet Agent Entretien
// ==============================================================================
// Usage:
//   az deployment sub create \
//     --location <location> \
//     --template-file infra/main.bicep \
//     --parameters environmentName=dev \
//                  location=eastus2
// ==============================================================================

targetScope = 'subscription'

@description('Nom de l\'environnement (dev, staging, prod)')
param environmentName string = 'dev'

@description('Région Azure pour les ressources')
param location string = resourceGroup().location

@description('Préfixe pour le nommage des ressources')
param prefix string = 'cabinet-agent'

// ==============================================================================
// Variables
// ==============================================================================

var tags = {
  Environment: environmentName
  Project: 'Cabinet-Agent-Entretien'
  ManagedBy: 'Bicep'
  CostCenter: 'AI-Infrastructure'
}

var resourceToken = uniqueString(subscription().id, environmentName, location)

var names = {
  resourceGroup: '${prefix}-${environmentName}-rg'
  containerRegistry: 'acr${resourceToken}'
  containerAppEnv: '${prefix}-${environmentName}-env'
  containerApp: '${prefix}-${environmentName}-api'
  logAnalytics: '${prefix}-${environmentName}-logs'
  postgresServer: '${prefix}-${environmentName}-pg'
  redisCache: '${prefix}-${environmentToken}-redis'
  storageAccount: 'st${replace(resourceToken, '-', '')}'
}

// ==============================================================================
// Resource Group
// ==============================================================================

resource rg 'Microsoft.Resources/resourceGroups@2024-03-01' = {
  name: names.resourceGroup
  location: location
  tags: tags
}

// ==============================================================================
// Log Analytics Workspace
// ==============================================================================

module logAnalytics 'modules/log-analytics.bicep' = {
  scope: rg
  name: 'logAnalytics'
  params: {
    name: names.logAnalytics
    location: location
    tags: tags
    retentionInDays: (environmentName == 'prod') ? 90 : 30
  }
}

// ==============================================================================
// Azure Container Registry
// ==============================================================================

module containerRegistry 'modules/container-registry.bicep' = {
  scope: rg
  name: 'containerRegistry'
  params: {
    name: names.containerRegistry
    location: location
    tags: tags
    sku: (environmentName == 'prod') ? 'Premium' : 'Standard'
    adminUserEnabled: true
  }
}

// ==============================================================================
// PostgreSQL Flexible Server
// ==============================================================================

module postgres 'modules/postgres.bicep' = {
  scope: rg
  name: 'postgres'
  params: {
    name: names.postgresServer
    location: location
    tags: tags
    administratorLogin: 'cabinet_admin'
    administratorLoginPassword: postgresPassword
    skuName: (environmentName == 'prod') ? 'Standard_D2s_v3' : 'Standard_B1ms'
    storageSizeGB: (environmentName == 'prod') ? 128 : 32
    version: '16'
  }
}

@secure()
param postgresPassword string

// ==============================================================================
// Redis Cache
// ==============================================================================

module redis 'modules/redis.bicep' = {
  scope: rg
  name: 'redis'
  params: {
    name: names.redisCache
    location: location
    tags: tags
    sku: (environmentName == 'prod') ? 'Premium' : 'Basic'
    family: (environmentName == 'prod') ? 'P' : 'C'
    capacity: (environmentName == 'prod') ? 1 : 0
  }
}

// ==============================================================================
// Container Apps Environment
// ==============================================================================

module containerAppEnv 'modules/container-app-environment.bicep' = {
  scope: rg
  name: 'containerAppEnv'
  params: {
    name: names.containerAppEnv
    location: location
    tags: tags
    logAnalyticsWorkspaceId: logAnalytics.outputs.workspaceId
  }
}

// ==============================================================================
// Container App
// ==============================================================================

module containerApp 'modules/container-app.bicep' = {
  scope: rg
  name: 'containerApp'
  params: {
    name: names.containerApp
    location: location
    tags: tags
    environmentId: containerAppEnv.outputs.environmentId
    containerRegistryId: containerRegistry.outputs.registryId
    containerRegistryName: containerRegistry.outputs.name
    containerRegistryLoginServer: containerRegistry.outputs.loginServer
    imageName: 'cabinet-agent-entretien'
    imageTag: 'latest'
    cpu: (environmentName == 'prod') ? 2.0 : 1.0
    memory: (environmentName == 'prod') ? '4.0Gi' : '2.0Gi'
    minReplicas: (environmentName == 'prod') ? 2 : 1
    maxReplicas: (environmentName == 'prod') ? 10 : 3
    targetPort: 8000
    environmentVariables: [
      { name: 'DATABASE_URL', value: 'postgresql+asyncpg://cabinet_admin:${postgresPassword}@${postgres.outputs.fqdn}:5432/rdv_bilan' }
      { name: 'REDIS_URL', value: '${redis.outputs.hostName}:6379' }
      { name: 'LLM_MODEL', value: 'gpt-4o' }
    ]
    secretEnvironmentVariables: [
      { name: 'OPENAI_API_KEY', keyVaultUrl: '' }  // Set via GitHub secrets
      { name: 'PERPLEXITY_API_KEY', keyVaultUrl: '' }
      { name: 'GAMMA_API_KEY', keyVaultUrl: '' }
      { name: 'API_KEY_SECRET', keyVaultUrl: '' }
    ]
  }
  dependsOn: [
    postgres
    redis
  ]
}

// ==============================================================================
// Outputs
// ==============================================================================

output resourceGroupName string = rg.name
output containerRegistryName string = containerRegistry.outputs.name
output containerRegistryLoginServer string = containerRegistry.outputs.loginServer
output containerAppName string = containerApp.outputs.name
output containerAppFqdn string = containerApp.outputs.fqdn
output containerAppUrl string = 'https://${containerApp.outputs.fqdn}'
output postgresFqdn string = postgres.outputs.fqdn
output redisHostName string = redis.outputs.hostName