# ==============================================================================
# Guide de Déploiement - Cabinet Agent Entretien
# ==============================================================================

## Vue d'ensemble

Ce projet est maintenant configuré pour un déploiement complet sur Azure :

```
GitHub Actions CI/CD → Azure Container Registry → Azure Container Apps
                                              ↓
                                    Microsoft Copilot Studio (Frontend)
```

## Fichiers créés

### 1. Containerisation
- `/Dockerfile` - Image Docker multi-stage (Python 3.11, FastAPI, spaCy)
- `/.dockerignore` - Optimisation du build

### 2. CI/CD Pipeline
- `/.github/workflows/deploy-azure.yml` - Pipeline complet :
  - Test + Lint
  - Build & Push vers ACR
  - Déploiement vers ACA
  - Health check automatique

### 3. Infrastructure as Code (Bicep)
- `/infra/main.bicep` - Template principal
- `/infra/modules/` - Modules réutilisables :
  - `log-analytics.bicep` - Monitoring
  - `container-registry.bicep` - ACR
  - `postgres.bicep` - Base de données
  - `redis.bicep` - Cache
  - `container-app-environment.bicep` - Env ACA
  - `container-app.bicep` - Application

### 4. Azure Developer CLI
- `/azure.yaml` - Configuration azd pour déploiement simplifié

### 5. Intégration Frontend
- `/docs/COPILOT_STUDIO_INTEGRATION.md` - Guide complet Copilot Studio

---

## Déploiement rapide

### Option A : Via GitHub Actions (Recommandé)

1. **Configurer les secrets GitHub** dans votre repo :
   ```
   AZURE_CREDENTIALS      → JSON du Service Principal
   AZURE_SUBSCRIPTION_ID  → Votre subscription ID
   AZURE_RESOURCE_GROUP   → Nom du resource group
   ACR_NAME               → Nom du Container Registry (ex: acrentreprise)
   ACA_NAME               → Nom du Container App (ex: cabinet-agent-api)
   ACA_ENVIRONMENT        → Environment name (ex: cabinet-agent-env)
   OPENAI_API_KEY         → Clé OpenAI
   PERPLEXITY_API_KEY     → Clé Perplexity
   GAMMA_API_KEY          → Clé Gamma
   API_KEY_SECRET         → Secret pour l'API
   DATABASE_URL           → URL PostgreSQL
   REDIS_URL              → URL Redis
   ```

2. **Créer le Service Principal Azure** :
   ```bash
   az ad sp create-for-rbac \
     --name "cabinet-agent-github-actions" \
     --role contributor \
     --scopes /subscriptions/<SUBSCRIPTION_ID> \
     --json-auth
   ```

3. **Push sur main** :
   ```bash
   git add .
   git commit -m "Add Azure deployment infrastructure"
   git push origin main
   ```

4. Le pipeline se déclenche automatiquement.

### Option B : Via Azure Developer CLI (azd)

```bash
# Installation
brew install azd  # macOS
# ou
winget install Microsoft.AzureDeveloperCLI  # Windows

# Authentification
azd auth login

# Initialisation
cd Cabinet_Agent_Entretien
azd init

# Créer un environnement
azd env new dev

# Provisionner l'infrastructure
azd provision

# Déployer l'application
azd deploy
```

### Option C : Via Azure CLI manuel

```bash
# 1. Créer le groupe de ressources
az group create --name cabinet-agent-rg --location eastus2

# 2. Créer l'ACR
az acr create \
  --name cabinetagentacr \
  --resource-group cabinet-agent-rg \
  --sku Standard --admin-enabled true

# 3. Builder et pousser l'image
az acr build \
  --registry cabinetagentacr \
  --image cabinet-agent-entretien:latest \
  .

# 4. Créer l'environnement Container Apps
az containerapp env create \
  --name cabinet-agent-env \
  --resource-group cabinet-agent-rg \
  --location eastus2

# 5. Créer le Container App
az containerapp create \
  --name cabinet-agent-api \
  --resource-group cabinet-agent-rg \
  --environment cabinet-agent-env \
  --image cabinetagentacr.azurecr.io/cabinet-agent-entretien:latest \
  --registry-server cabinetagentacr.azurecr.io \
  --target-port 8000 \
  --ingress external \
  --env-vars "OPENAI_API_KEY=xxx" "PERPLEXITY_API_KEY=xxx"
```

---

## Prochaines étapes

### 1. Infrastructure locale (Cluster K3s)

Un skill a été créé pour vous accompagner : `k3s-cluster-setup`

Pour l'utiliser :
```
Je veux configurer mon cluster K3s local
```

Le skill couvre :
- Installation K3s sur vos 2 Asus GX10
- Configuration GPU NVIDIA Grace Blackwell
- Déploiement Ollama + modèles
- Intégration avec HuggingFace

### 2. Déployer Copilot Studio

Suivre le guide : `/docs/COPILOT_STUDIO_INTEGRATION.md`

Étapes principales :
1. Créer le connecteur personnalisé
2. Importer la spec OpenAPI
3. Créer le bot avec dialogues Power Fx
4. Configurer l'upload de fichiers via Power Automate
5. Publier sur Teams/Web

### 3. Monitoring

L'infrastructure inclut Log Analytics. Pour voir les logs :
```bash
az monitor log-analytics query \
  --workspace <workspace-id> \
  --analytics-query "ContainerAppConsoleLogs | where ContainerAppName == 'cabinet-agent-api'"
```

---

## Coûts estimés (environment dev)

| Ressource | SKU | Coût mensuel estimé |
|-----------|-----|---------------------|
| Container Apps | 1 vCPU, 2GB | ~$50 |
| Container Registry | Standard | ~$5 |
| PostgreSQL | Burstable B1ms | ~$15 |
| Redis | Basic C0 | ~$15 |
| Log Analytics | PerGB | ~$5 |
| **Total** | | **~$90/mois** |

Pour la production, prévoir ~$300-500/mois avec :
- 2+ réplicas Container Apps
- PostgreSQL GeneralPurpose
- Redis Premium
- Plus de capacité GPU

---

## Architecture complète

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AZURE CLOUD                                  │
│                                                                      │
│  ┌─────────────────┐    ┌────────────────────────────────────────┐ │
│  │  Copilot Studio │    │         Azure Container Apps            │ │
│  │   (Frontend)    │───▶│  ┌────────────────────────────────┐    │ │
│  │                 │    │  │   Cabinet Agent Entretien       │    │ │
│  │  - Chat UI      │    │  │   - FastAPI                     │    │ │
│  │  - Power Fx     │    │  │   - LangGraph Workflow          │    │ │
│  │  - Teams        │    │  │   - Agents: Carla/Lucie/Gamma   │    │ │
│  └─────────────────┘    │  └────────────────────────────────┘    │ │
│                          │            │                            │ │
│                          │            ▼                            │ │
│                          │  ┌─────────────────┐                    │ │
│                          │  │  PostgreSQL     │                    │ │
│                          │  │  (State/Etat)   │                    │ │
│                          │  └─────────────────┘                    │ │
│                          │            │                            │ │
│                          │            ▼                            │ │
│                          │  ┌─────────────────┐                    │ │
│                          │  │  Redis Cache    │                    │ │
│                          │  └─────────────────┘                    │ │
│                          └────────────────────────────────────────┘ │
│                                      │                              │
│                                      ▼                              │
│                          ┌────────────────────────────────────────┐ │
│                          │       Azure Container Registry         │ │
│                          │       (Images Docker)                  │ │
│                          └────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                       LAB LOCAL (K3s)                                │
│                                                                      │
│  ┌──────────────────────┐       ┌──────────────────────┐           │
│  │  Node 1: GX10 Spark  │       │  Node 2: GX10 Spark  │           │
│  │  - K3s Agent         │◀────▶│  - K3s Server        │           │
│  │  - 128 GB RAM        │       │  - 128 GB RAM        │           │
│  │  - GB10 GPU          │       │  - GB10 GPU          │           │
│  └──────────────────────┘       └──────────────────────┘           │
│               │                            │                        │
│               ▼                            ▼                        │
│       ┌───────────────────────────────────────┐                     │
│       │  Ollama + HuggingFace Models          │                     │
│       │  (Inference locale, offline)          │                     │
│       └───────────────────────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Support

Pour toute question ou problème :
1. Consulter les logs Azure : `az containerapp logs show`
2. Vérifier les health checks : `curl https://<url>/api/v1/health`
3. Consulter ce README et les documents dans `/docs/`