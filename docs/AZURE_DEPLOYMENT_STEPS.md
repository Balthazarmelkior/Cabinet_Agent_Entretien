# ==============================================================================
# Guide de Déploiement Azure - Cabinet Agent Entretien
# ==============================================================================
# Ce guide décrit les étapes exactes pour déployer sur Azure Container Apps.
# ==============================================================================

## Prérequis

- Compte Azure avec subscription active
- GitHub repository : https://github.com/Balthazarmelkior/Cabinet_Agent_Entretien
- Azure CLI installé : https://docs.microsoft.com/cli/azure/install-azure-cli
- Clés API : OpenAI, Perplexity (optionnel), Gamma (optionnel)

---

## Étape 1 : Créer les ressources Azure

```bash
# 1. Connexion à Azure
az login

# 2. Définir la subscription (si plusieurs)
az account set --subscription "<votre-subscription-id>"

# 3. Définir les variables
LOCATION="eastus2"  # ou "francecentral" pour l'Europe
RG_NAME="cabinet-agent-dev-rg"
ACR_NAME="cabinetagentacr$(openssl rand -hex 4)"  # nom globalement unique
ACA_ENV="cabinet-agent-dev-env"
ACA_NAME="cabinet-agent-dev-api"

# 4. Créer le Resource Group
az group create --name $RG_NAME --location $LOCATION

# 5. Créer l'Azure Container Registry
az acr create \
  --resource-group $RG_NAME \
  --name $ACR_NAME \
  --sku Standard \
  --admin-enabled true

# 6. Créer l'environnement Container Apps
az containerapp env create \
  --resource-group $RG_NAME \
  --name $ACA_ENV \
  --location $LOCATION

# 7. Récupérer l'ACR login server
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
echo "ACR Login Server: $ACR_LOGIN_SERVER"
```

---

## Étape 2 : Créer un Service Principal pour GitHub Actions

```bash
# 1. Créer le Service Principal
SUBSCRIPTION_ID=$(az account show --query id --output tsv)
SP_NAME="cabinet-agent-deployer"

az ad sp create-for-rbac \
  --name $SP_NAME \
  --role Contributor \
  --scopes /subscriptions/$SUBSCRIPTION_ID/resourceGroups/$RG_NAME \
  --json-auth

# 2. Copier la sortie JSON complète (elle ressemble à ça) :
# {
#   "clientId": "...",
#   "clientSecret": "...",
#   "subscriptionId": "...",
#   "tenantId": "...",
#   "activeDirectoryEndpointUrl": "...",
#   ...
# }
```

---

## Étape 3 : Configurer les secrets GitHub

Aller sur GitHub : https://github.com/Balthazarmelkior/Cabinet_Agent_Entretien/settings/secrets/actions

Cliquer **New repository secret** pour chaque secret :

| Secret Name | Valeur |
|-------------|--------|
| `AZURE_CREDENTIALS` | Sortie JSON complète de `az ad sp create-for-rbac` |
| `AZURE_SUBSCRIPTION_ID` | Votre subscription ID (ex: `12345678-1234-1234-1234-123456789012`) |
| `AZURE_RESOURCE_GROUP` | `cabinet-agent-dev-rg` |
| `ACR_NAME` | `cabinetagentacrxxxx` (sans .azurecr.io) |
| `ACA_NAME` | `cabinet-agent-dev-api` |
| `ACA_ENVIRONMENT` | `cabinet-agent-dev-env` |
| `OPENAI_API_KEY` | `sk-...` (votre clé OpenAI) |
| `PERPLEXITY_API_KEY` | `pplx-...` (optionnel) |
| `GAMMA_API_KEY` | Votre clé Gamma (optionnel) |
| `API_KEY_SECRET` | Une clé secrète pour sécuriser l'API (ex: un UUID) |

---

## Étape 4 : Pousser le code sur GitHub

Depuis votre machine locale (pas depuis ce terminal) :

```bash
# Cloner le repo si pas déjà fait
git clone https://github.com/Balthazarmelkior/Cabinet_Agent_Entretien.git
cd Cabinet_Agent_Entretien

# Copier les fichiers créés (Dockerfile, .github/workflows, infra/, azure.yaml, docs/)
# Si vous avez accès aux fichiers créés ici :
# - Copier tout le contenu de /opt/data/Cabinet_Agent_Entretien/

# Ajouter les fichiers
git add .
git commit -m "Add Azure deployment infrastructure: Dockerfile, CI/CD, Bicep, Copilot Studio docs"
git push origin main
```

---

## Étape 5 : Déclencher le déploiement

Option A : Automatique (push sur main)

Le pipeline se déclenche automatiquement quand vous poussez sur `main` ou `master`.

Option B : Manuel

Aller sur : https://github.com/Balthazarmelkior/Cabinet_Agent_Entretien/actions

1. Sélectionner le workflow **Deploy to Azure Container Apps**
2. Cliquer **Run workflow**
3. Choisir l'environnement : `dev`
4. Cliquer **Run workflow**

---

## Étape 6 : Vérifier le déploiement

```bash
# 1. Vérifier le statut du Container App
az containerapp show \
  --resource-group $RG_NAME \
  --name $ACA_NAME \
  --query properties.runningStatus

# 2. Récupérer l'URL
az containerapp show \
  --resource-group $RG_NAME \
  --name $ACA_NAME \
  --query properties.configuration.ingress.fqdn \
  --output tsv

# 3. Tester l'API
curl https://<votre-url>/api/v1/health
# Attendu : {"status": "healthy"}
```

---

## Étape 7 : Déployer l'infrastructure (facultatif avec Bicep)

Si vous voulez créer automatiquement toute l'infrastructure (PostgreSQL, Redis, etc.) :

```bash
# Définir un mot de passe pour PostgreSQL
POSTGRES_PASSWORD="VotreMotDePasseSecurise123!"

# Déployer avec Bicep
az deployment sub create \
  --location $LOCATION \
  --template-file infra/main.bicep \
  --parameters environmentName=dev \
               location=$LOCATION \
               postgresPassword=$POSTGRES_PASSWORD
```

---

## Architecture déployée

```
Azure Resource Group: cabinet-agent-dev-rg
│
├── Azure Container Registry (ACR)
│   └── cabinet-agent-entretien:latest
│
├── Container Apps Environment
│   └── Container App: cabinet-agent-dev-api
│       └── FastAPI (Uvicorn)
│           ├── LangGraph Workflow
│           ├── Agent CARLA (Perplexity)
│           └── Health endpoint
│
├── (Optionnel) PostgreSQL Flexible Server
│   └── Database: rdv_bilan
│
├── (Optionnel) Redis Cache
│
└── (Optionnel) Log Analytics Workspace
```

---

## URLs

| Environnement | API URL |
|---------------|---------|
| Dev | `https://cabinet-agent-dev-api.<region>.azurecontainerapps.io` |
| Staging | `https://cabinet-agent-staging-api.<region>.azurecontainerapps.io` |
| Prod | `https://cabinet-agent-prod-api.<region>.azurecontainerapps.io` |

---

## Endpoints API disponibles

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `GET` | `/api/v1/health` | Health check |
| `POST` | `/api/v1/prepare-rdv` | Lancer l'analyse |
| `GET` | `/api/v1/status/{job_id}` | Statut du job |
| `GET` | `/api/v1/export/{job_id}` | Récupérer les résultats |
| `GET` | `/docs` | Documentation OpenAPI |

---

## Coûts estimés (région East US 2)

| Ressource | SKU | Estimation/mois |
|-----------|-----|-----------------|
| Container Apps (1 vCPU, 2GB) | Consumption | ~$50 avec trafic |
| Container Registry | Standard | ~$5 |
| PostgreSQL Flexible | B1ms | ~$15 |
| Redis Cache | Basic | ~$16 |
| **Total estimé** | | **~$86/mois** |

---

## Dépannage

### Le pipeline échoue à l'étape "Build & Push"

```bash
# Vérifier que l'ACR existe
az acr show --name $ACR_NAME

# Vérifier les permissions du Service Principal
az role assignment list --assignee <clientId-du-SP>
```

### Le Container App ne démarre pas

```bash
# Voir les logs
az containerapp logs show \
  --resource-group $RG_NAME \
  --name $ACA_NAME \
  --tail 100

# Vérifier les variables d'environnement
az containerapp show \
  --resource-group $RG_NAME \
  --name $ACA_NAME \
  --query properties.template.containers[0].env
```

### L'endpoint health retourne une erreur

```bash
# Vérifier que l'API a accès aux clés
az containerapp exec \
  --resource-group $RG_NAME \
  --name $ACA_NAME \
  --command "env | grep -E 'OPENAI|PERPLEXITY|GAMMA'"
```

---

## Commandes utiles

```bash
# Voir tous les Container Apps
az containerapp list --resource-group $RG_NAME --output table

# Scaler manuellement
az containerapp update \
  --resource-group $RG_NAME \
  --name $ACA_NAME \
  --min-replicas 2 \
  --max-replicas 5

# Redémarrer le container
az containerapp revision restart \
  --resource-group $RG_NAME \
  --name $ACA_NAME

# Supprimer tout (attention !)
az group delete --name $RG_NAME --yes --no-wait
```

---

## Prochaines étapes après déploiement

1. **Intégration Copilot Studio** → Voir `docs/COPILOT_STUDIO_INTEGRATION.md`
2. **Configuration du domaine personnalisé** → Ajouter votre domaine
3. **Monitoring** → Configurer les alertes Azure Monitor
4. **Environnements multiples** → Ajouter staging et prod

---

## Support

- Azure Container Apps docs : https://learn.microsoft.com/azure/container-apps/
- GitHub Actions docs : https://docs.github.com/actions
- FastAPI docs : https://fastapi.tiangolo.com/