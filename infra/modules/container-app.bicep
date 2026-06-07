// ==============================================================================
// Container App Module
// ==============================================================================

param name string
param location string
param tags object
param environmentId string
param containerRegistryId string
param containerRegistryName string
param containerRegistryLoginServer string
param imageName string
param imageTag string
param cpu string = '1.0'
param memory string = '2.0Gi'
param minReplicas int = 1
param maxReplicas int = 3
param targetPort int = 8000
param environmentVariables array = []
param secretEnvironmentVariables array = []

resource app 'Microsoft.App/containerApps@2024-03-01' = {
  name: name
  location: location
  tags: tags
  properties: {
    managedEnvironmentId: environmentId
    configuration: {
      ingress: {
        external: true
        targetPort: targetPort
        transport: 'http'
        allowInsecure: false
      }
      registries: [
        {
          server: containerRegistryLoginServer
          identity: 'system'
        }
      ]
      secrets: [
        {
          name: 'openai-api-key'
          value: ''  // Set via GitHub Actions
        }
        {
          name: 'perplexity-api-key'
          value: ''
        }
        {
          name: 'gamma-api-key'
          value: ''
        }
        {
          name: 'api-key-secret'
          value: ''
        }
      ]
      activeRevisionsMode: 'Single'
    }
    template: {
      containers: [
        {
          name: 'api'
          image: '${containerRegistryLoginServer}/${imageName}:${imageTag}'
          env: concat(environmentVariables, [
            { name: 'OPENAI_API_KEY', secretRef: 'openai-api-key' }
            { name: 'PERPLEXITY_API_KEY', secretRef: 'perplexity-api-key' }
            { name: 'GAMMA_API_KEY', secretRef: 'gamma-api-key' }
            { name: 'API_KEY_SECRET', secretRef: 'api-key-secret' }
          ])
          resources: {
            cpu: json(cpu)
            memory: memory
          }
          probes: [
            {
              type: 'Liveness'
              httpGet: {
                path: '/api/v1/health'
                port: targetPort
              }
              periodSeconds: 30
              initialDelaySeconds: 10
            }
          ]
        }
      ]
      scale: {
        minReplicas: minReplicas
        maxReplicas: maxReplicas
        rules: [
          {
            name: 'http-requests'
            http: {
              metadata: {
                concurrentRequests: '100'
              }
            }
          }
          {
            name: 'cpu-scaling'
            custom: {
              type: 'cpu'
              metadata: {
                type: 'Utilization'
                value: '70'
              }
            }
          }
        ]
      }
    }
  }
}

output appId string = app.id
output name string = app.name
output fqdn string = app.properties.configuration.ingress.fqdn