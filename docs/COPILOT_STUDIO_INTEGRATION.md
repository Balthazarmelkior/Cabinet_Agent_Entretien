# ==============================================================================
# Intégration Microsoft Copilot Studio - Cabinet Agent Entretien
# ==============================================================================
# Ce document décrit comment intégrer le frontend Copilot Studio avec l'API
# Cabinet Agent Entretien déployée sur Azure Container Apps.
# ==============================================================================

## Architecture

```
┌─────────────────────┐          ┌──────────────────────────┐
│   Copilot Studio    │          │   Azure Container Apps   │
│   (Frontend)        │──────────│   (Backend API)          │
│                     │   HTTP   │                          │
│  - Conversation     │          │  - FastAPI               │
│  - Power Fx         │          │  - LangGraph Workflow    │
│  - Connecteurs      │          │  - Multi-agents          │
└─────────────────────┘          └──────────────────────────┘
          │                                  │
          │                                  │
          ▼                                  ▼
┌─────────────────────┐          ┌──────────────────────────┐
│   Power Platform    │          │   Azure Services         │
│   - Dataverse       │          │   - PostgreSQL           │
│   - Blob Storage    │          │   - Redis Cache          │
└─────────────────────┘          │   - Container Registry   │
                                 └──────────────────────────┘
```

## Étape 1 : Configurer l'API dans Azure

### 1.1 Récupérer l'URL de l'API

Après déploiement via CI/CD ou `azd deploy` :

```bash
# Via Azure CLI
az containerapp show \
  --name cabinet-agent-dev-api \
  --resource-group cabinet-agent-dev-rg \
  --query properties.configuration.ingress.fqdn \
  --output tsv

# Résultat : cabinet-agent-dev-api.xxx.azurecontainerapps.io
```

### 1.2 Configurer CORS pour Copilot Studio

Ajouter dans les variables d'environnement du Container App :

```bash
az containerapp update \
  --name cabinet-agent-dev-api \
  --resource-group cabinet-agent-dev-rg \
  --set-env-vars "CORS_ORIGINS=https://copilotstudio.microsoft.com,https://make.powerapps.com"
```

Ou dans le code FastAPI (`rdv_bilan_ia/app/main.py`) :

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://copilotstudio.microsoft.com",
        "https://make.powerapps.com",
        "https://*.powerapps.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Étape 2 : Créer un connecteur personnalisé

### 2.1 Dans Copilot Studio

1. Aller dans **Copilot Studio** → **Settings** → **Actions**
2. Cliquer **+ Add an action**
3. Choisir **Create a custom connector**

### 2.2 Importer la spec OpenAPI

L'API FastAPI expose automatiquement sa spec OpenAPI :

```
https://<your-aca-url>/openapi.json
```

1. Coller l'URL de la spec OpenAPI
2. Donner un nom au connecteur : `Cabinet Agent Entretien`
3. Configurer l'authentification :
   - Type : **API Key**
   - Parameter name : `X-API-Key`
   - Parameter location : `Header`

### 2.3 Définir les actions

Actions disponibles depuis l'API :

| Action | Endpoint | Description |
|--------|----------|-------------|
| Préparer entretien | `POST /api/v1/prepare-rdv` | Lance le workflow complet |
| Statut analyse | `GET /api/v1/status/{job_id}` | Polling du statut |
| Exporter livrables | `GET /api/v1/export/{job_id}` | Récupère les résultats |
| Health check | `GET /api/v1/health` | Vérifie la disponibilité |

## Étape 3 : Créer le bot Copilot

### 3.1 Créer un nouveau copilot

1. **Copilot Studio** → **Create** → **New copilot**
2. Nom : `Assistant Entretien Bilan`
3. Langue : Français

### 3.2 Configurer les dialogues

#### Dialogue principal

```powerfx
// Trigger: "Préparer un entretien bilan"
// User inputs: fichier_comptes, code_naf, nom_client

// 1. Lancer l'analyse
Set(job_response, CabinetAgentEntretien.PrepareRDV({
    secteur: UserInput.secteur,
    seuil_ca: UserInput.seuil_ca,
    fichier_comptes: UserInput.fichier_base64,
    format_fichier: "txt"
}));

Set(job_id, job_response.job_id);

// 2. Informer l'utilisateur
Say("Analyse en cours... Durée estimée : " & job_response.estimated_duration_seconds & " secondes");

// 3. Polling du statut
Set(attempts, 0);
Set(max_attempts, 60);
Set(status, "PENDING");

While(status <> "COMPLETED" And status <> "FAILED" And attempts < max_attempts,
    Wait(10);
    Set(status_response, CabinetAgentEntretien.GetStatus({job_id: job_id}));
    Set(status, status_response.status);
    Set(attempts, attempts + 1);
    
    If(status = "RUNNING",
        Say("Progression : " & status_response.progress_pct & "%")
    )
);

// 4. Récupérer les résultats
If(status = "COMPLETED",
    Set(export_response, CabinetAgentEntretien.Export({job_id: job_id}));
    
    Say("Analyse terminée !");
    Say("📊 Note sectorielle : " & export_response.livrables.note_sectorielle_md);
    Say("📈 SWOT disponible");
    Say("🎯 Questions RDV : " & export_response.livrables.questions_rdv);
    
    // Afficher le lien vers les slides
    AdaptiveCard({
        "type": "AdaptiveCard",
        "body": [{
            "type": "Action.OpenUrl",
            "title": "Voir les slides",
            "url": export_response.livrables.slides_gamma_url
        }]
    });
,
    Say("❌ L'analyse a échoué. Veuillez réessayer.")
);
```

### 3.3 Gérer l'upload de fichiers

Copilot Studio ne supporte pas directement l'upload de fichiers volumineux.
Utiliser **Power Automate** comme intermédiaire :

```yaml
# Power Automate Flow
Trigger: Copilot appelle un flux
Action 1: Demander à l'utilisateur de télécharger le fichier (OneDrive/SharePoint)
Action 2: Convertir le fichier en Base64
Action 3: Appeler l'API Cabinet Agent
Action 4: Retourner le job_id à Copilot
```

## Étape 4 : Sécurité

### 4.1 Gestion des clés API

1. Dans **Azure Key Vault**, stocker la clé API :
   ```bash
   az keyvault secret set \
     --vault-name cabinet-agent-kv \
     --name api-key-secret \
     --value "votre-cle-secrète"
   ```

2. Référencer le Key Vault dans Copilot Studio

### 4.2 Environnements

| Environnement | URL Copilot | URL API |
|---------------|-------------|---------|
| Dev | `https://copilotstudio.microsoft.com/environments/dev-xxx` | `cabinet-agent-dev-api.xxx.azurecontainerapps.io` |
| Staging | `https://copilotstudio.microsoft.com/environments/staging-xxx` | `cabinet-agent-staging-api.xxx.azurecontainerapps.io` |
| Prod | `https://copilotstudio.microsoft.com/environments/prod-xxx` | `cabinet-agent-prod-api.xxx.azurecontainerapps.io` |

## Étape 5 : Tests

### 5.1 Tester le connecteur

Dans Copilot Studio → **Test your connector** :

```json
{
  "secteur": "magasins optique",
  "seuil_ca": 1000000,
  "fichier_comptes": "BASE64_ENCODED_FEC_FILE",
  "format_fichier": "txt"
}
```

### 5.2 Tester le bot

Utiliser le panneau **Test your copilot** dans Copilot Studio.

Dialogue de test :
```
User: Je veux préparer un entretien bilan
Bot: Très bien ! Quel est le secteur d'activité ?
User: Magasin optique
Bot: Quel est le code NAF ?
User: 4778B
Bot: [upload request for FEC file]
...
```

## Étape 6 : Publication

### 6.1 Publier le copilot

1. **Publish** → **Publish to channels**
2. Canaux disponibles :
   - Microsoft Teams
   - Web chat (embed sur site web)
   - Mobile app
   - API (pour intégration directe)

### 6.2 Intégration Teams

Pour utiliser dans Microsoft Teams :

1. **Settings** → **Channels**
2. Ajouter **Microsoft Teams**
3. Publier
4. L'agent sera disponible dans Teams pour les utilisateurs autorisés

## Ressources

- [Documentation Copilot Studio](https://learn.microsoft.com/en-us/microsoft-copilot-studio/)
- [Connecteurs personnalisés](https://learn.microsoft.com/en-us/connectors/custom-connectors/)
- [Power Fx Reference](https://learn.microsoft.com/en-us/power-platform/power-fx/)
- [Intégration Teams](https://learn.microsoft.com/en-us/microsoft-copilot-studio/publish-gcc-teams)