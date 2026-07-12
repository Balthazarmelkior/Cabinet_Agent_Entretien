# Agent Entretien Bilan — Cabinet Comptable

Deux modes d'utilisation complémentaires pour préparer les rendez-vous bilan :

- **UI Streamlit** — analyse FEC/PDF, benchmark sectoriel, analyse stratégique, fiche entretien Word (usage immédiat)
- **API FastAPI** — workflow multi-agents Carla/Lucie/Gamma, RGPD-compliant, human-in-the-loop (usage production)

---

## Fonctionnalités

- **Parsing automatique** FEC (CSV tabulé, norme DGFiP) et bilan PDF
- **Anonymisation RGPD** des données avant envoi aux agents IA (spaCy + Presidio + SIREN/SIRET)
- **Calcul de ratios** : rentabilité, liquidité, solvabilité, activité + trésorerie (BFR, FRNG, trésorerie nette, cycle de conversion)
- **Benchmarking sectoriel** : Banque de France → INSEE → LLM (fallback automatique)
- **Détection de signaux** : moteur déterministe multi-niveaux (ratios, montants agrégés, **moteur FEC compte-fin**) + enrichissement LLM qualitatif — **84/90 codes du référentiel couverts sans LLM**
- **Matching de missions** : **100 % déterministe** — intersection des `codes_signaux` actifs avec le catalogue TYLS (79 missions), scoré et trié par priorité (plus de LLM/RAG)
- **Agent CARLA** : analyse sectorielle stratégique via Perplexity (ReAct loop avec validation de sources), SWOT sectoriel, analyse micro-économique, questions stratégiques RDV
- **Analyse de trésorerie** : KPIs (BFR, FRNG, trésorerie nette), waterfall BFR, cycle de conversion, jauge trésorerie nette
- **Fiche d'entretien** enrichie avec toutes les données (sectoriel, trésorerie, benchmark, signaux) exportable en Word (.docx)
- **Présentation 10 slides** générée automatiquement via Gamma API v1.0

---

## Architecture

### Mode Streamlit (`app/`)

Pipeline LangGraph synchrone avec agent CARLA intégré :

```
extract_financial_data
    ├─→ detect_signals ──────────┐
    ├─→ benchmark_sectoriel ─────┤
    └─→ analyse_sectorielle ─────┤  (Agent CARLA : Perplexity + SWOT + micro + questions)
                                  ▼
                        match_missions → generate_interview_plan → generate_slides → END
```

L'agent CARLA (`agents/carla/`) est un ReAct agent autonome :
1. Recherche Perplexity (modèle `sonar-pro`) sur plusieurs thématiques
2. Validation des sources (domaines officiels : INSEE, BdF, CCI, BPI)
3. Production d'une note sectorielle + SWOT + analyse micro + 5 questions RDV

Le node `generate_slides` utilise l'API Gamma v1.0 pour générer une présentation 10 slides à partir de toutes les données collectées.

### Mode FastAPI (`rdv_bilan_ia/`)

Workflow LangGraph asynchrone avec multi-agents, PostgreSQL et human-in-the-loop :

```
anonymize → (ok: carla [Perplexity] | fail: END)
carla → (ok: lucie [GPT-4o] | warn: validate)
lucie → gamma [Gamma API] → validate [checkpoint humain]
validate → (ok: export | retry: lucie | abort: END)
```

---

## Détection de signaux & matching (moteur déterministe)

Le cœur métier repose sur un **référentiel de 90 signaux** et un **catalogue de 79
missions TYLS**, reliés par des codes. Tout est déterministe : le LLM n'intervient
qu'en enrichissement qualitatif optionnel.

### Référentiel & catalogue

| Fichier | Rôle | Env |
|---------|------|-----|
| `data/seuils_signaux.json` | 90 signaux indexés par code (catégorie, `comptes_fec`, seuil, période, `parametrable`) | `SEUILS_PATH` |
| `data/catalogue_missions_tyls.json` | 79 missions (`codes_signaux`, priorité, honoraires…) | `CATALOGUE_PATH` |

### Chaîne de détection (`nodes/detect_signals.py`)

Quatre niveaux, du plus simple au plus fin, tous alignés sur les codes du référentiel :

| Niveau | Module | Entrée | Exemples de codes |
|--------|--------|--------|-------------------|
| 1. Ratios | `analysis/rules.py::detect_signals_from_rules` | `Ratios` | `EBE_NEGATIF`, `LIQUIDITE_CRITIQUE`, `DELAI_CLIENTS_ELEVE` |
| 2. Montants agrégés | `analysis/rules.py::detect_signals_from_donnees` | `DonneesFinancieres` | `TRESORERIE_EXCEDENTAIRE`, `MASSE_SALARIALE_ELEVEE`, `DEPASSEMENT_SEUILS_CAC` |
| 3. Moteur FEC | `analysis/fec_signals.py::detect_signals_from_fec` | `IndicateursFEC` | `REMUNERATION_DIRIGEANT_ELEVEE`, `DECOUVERT_RECURRENT`, `SAISONNALITE_FORTE` |
| 4. Enrichissement LLM | `detect_signals.py` (GPT-4o) | contexte | signaux sectoriels/gouvernance qualitatifs |

Le **moteur FEC** (`analysis/fec_features.py` + `fec_signals.py`) calcule des
indicateurs fins depuis le FEC brut (ΣDébit/ΣCrédit par compte, N et N-1, comptages
de tiers/comptes/journaux distincts, **sommes mensuelles par compte**) puis applique :

- **Tables génériques** — `GENERIC_SIGNALS` (opérateurs `seuil_eur` / `presence` /
  `absence` / `mouvement`), `COUNT_SIGNALS` (métriques distinctes), `PARAM_SIGNALS`
  (composites paramétrables : Δ N/N-1, marge, DSO, coefficient de variation).
- **Détecteurs explicites** — ratios, composites même-année, variations N/N-1,
  signaux mensuels (découvert récurrent, saisonnalité), nouvelles activités.

**Couverture : 84/90 codes en déterministe.** Les 6 restants nécessitent une donnée
hors périmètre FEC (N-2, dates d'échéance, montant d'origine d'emprunt) ou relèvent
d'une détection qualitative (LLM) / d'une saisie manuelle.

### Seuils paramétrables (UI)

Les signaux marqués `parametrable: true` exposent leur seuil dans l'expander
**« Seuils de détection (avancé) »** de l'UI Streamlit (`seuils_parametrables()` +
`titre_signal()`). Les valeurs modifiées sont passées au pipeline via
`seuils_overrides` et priment sur les défauts du référentiel.

### Matching (`matching/mission_matcher.py` + `nodes/match_missions.py`)

`MissionMatcher` charge catalogue + référentiel et déclenche chaque mission dont les
`codes_signaux` **intersectent** les signaux actifs. Score = nombre de signaux
déclencheurs ; tri `(priorité, score)`. Les missions **priorité 1** sont toujours
proposées. `_verifier_coherence` garantit que tout code référencé par une mission
existe dans le référentiel.

> Les anciens matchers LLM/RAG (`matching/llm_matcher.py`, `matching/rag_matcher.py`,
> `RAG_THRESHOLD`) restent sur disque mais **ne sont plus branchés** dans le pipeline.

---

## Installation

### Prérequis

```bash
python -m venv .venv
source .venv/Scripts/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
# ou avec Poetry (mode FastAPI) :
pip install poetry && poetry install
```

### Variables d'environnement

```bash
cp .env.example .env
```

#### Mode Streamlit

```env
OPENAI_API_KEY=sk-...          # requis — GPT-4o pour LLM
INSEE_API_KEY=...              # optionnel — benchmark INSEE Esane
PERPLEXITY_API_KEY=pplx-...    # optionnel — analyse sectorielle CARLA (fallback: GPT-4o)
GAMMA_API_KEY=...              # optionnel — génération slides (fallback: Markdown seul)
LLM_MODEL=gpt-4o               # optionnel — modèle LLM (défaut gpt-4o)
CATALOGUE_PATH=data/catalogue_missions_tyls.json  # optionnel — catalogue missions
SEUILS_PATH=data/seuils_signaux.json              # optionnel — référentiel signaux
```

#### Mode FastAPI (complet)

```env
OPENAI_API_KEY=sk-...
PERPLEXITY_API_KEY=pplx-...
GAMMA_API_KEY=...
API_KEY_SECRET=change-me-in-production

DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/rdv_bilan
REDIS_URL=redis://localhost:6379/0
```

---

## Lancement

### UI Streamlit

```bash
streamlit run app/main.py
# Ouvrir http://localhost:8501
```

### API FastAPI

```bash
# 1. Infrastructure (PostgreSQL + Redis)
docker run -d -p 5432:5432 -e POSTGRES_PASSWORD=password postgres:16-alpine
docker run -d -p 6379:6379 redis:7-alpine

# 2. Modèle spaCy français (anonymisation)
python -m spacy download fr_core_news_md

# 3. Migrations base de données
alembic upgrade head

# 4. Lancer l'API
uvicorn rdv_bilan_ia.app.main:app --reload
# Docs interactives : http://localhost:8000/docs
```

---

## Déploiement Azure (production)

L'app tourne en production sur **Azure Container Apps**, déployée automatiquement
à chaque push sur `main` via GitHub Actions (`.github/workflows/deploy-azure.yml`).

### Accéder à l'app

Ouvre simplement l'URL dans un navigateur (aucune installation requise) :

```
https://aca-entretienbilan-ia.salmonocean-5796c2ca.westeurope.azurecontainerapps.io
```

C'est la même UI Streamlit que le mode local (`streamlit run app/main.py`) — les
7 onglets (Benchmark, Analyse sectorielle, Trésorerie, Évolution N/N-1, Signaux,
Missions, Fiche entretien, Slides Gamma) sont identiques. Voir
[Utilisation — Streamlit](#utilisation--streamlit) ci-dessous.

### Mettre à jour la version en production

Rien à faire manuellement : un `git push` sur `main` déclenche le pipeline
(tests → build de l'image Docker → push sur Azure Container Registry → déploiement
sur Container Apps → health check). Suivre l'avancement :

```bash
gh run list -R Balthazarmelkior/Cabinet_Agent_Entretien -L 5
gh run watch <run-id> -R Balthazarmelkior/Cabinet_Agent_Entretien
```

Ou directement dans l'onglet **Actions** du repo GitHub.

### Ressources Azure (groupe de ressources `rg-entretienbilan-ia`, West Europe)

| Ressource | Nom | Rôle |
|-----------|-----|------|
| Container App | `aca-entretienbilan-ia` | Héberge l'app Streamlit (port 8000, ingress externe) |
| Container Apps Environment | `aca-env-entretienbilan-ia` | Environnement d'exécution + logs |
| Container Registry | `acrentretienbilania` | Stocke les images Docker buildées par la CI |

### Authentification CI/CD

Le workflow s'authentifie à Azure en **OIDC** (federated identity, pas de secret
client stocké) via l'App Azure AD `3aa682e8-dc10-4e29-a5c2-a953fc848aca`, avec
Contributor sur le groupe de ressources et AcrPush sur le registre. Secrets GitHub
requis : voir l'en-tête de `.github/workflows/deploy-azure.yml`.

### Debug / logs production

```bash
az containerapp logs show --name aca-entretienbilan-ia -g rg-entretienbilan-ia --tail 100
az containerapp revision list --name aca-entretienbilan-ia -g rg-entretienbilan-ia -o table
```

---

## Utilisation — Streamlit

1. Déposer le fichier FEC (`.txt` / `.csv`) ou bilan PDF
2. Optionnel : déposer le FEC N-1 pour les comparaisons
3. Saisir le code NAF à 5 caractères (ex: `4711F`) — visible sur le Kbis
4. Renseigner le nom du client
5. Cocher **Anonymiser les données** (activé par défaut)
6. Cliquer **Lancer l'analyse**
7. Explorer les 7 onglets du dashboard :

| Onglet | Contenu |
|--------|---------|
| **Benchmark sectoriel** | Radar + détail des ratios vs médianes sectorielles |
| **Analyse sectorielle** | Note CARLA (Perplexity), SWOT, analyse micro, questions RDV |
| **Trésorerie** | KPIs (BFR, FRNG, tréso nette), waterfall, cycle conversion, jauge |
| **Évolution N/N-1** | Tableau comparatif (si FEC N-1 fourni) |
| **Signaux** | Risques, opportunités, optimisations, conformité |
| **Missions** | Recommandations scorées avec argumentaires |
| **Fiche entretien** | Synthèse, plan d'entretien, export Word |
| **Slides Gamma** | Présentation 10 slides (lien + iframe) |

---

## Utilisation — API FastAPI

### Endpoints

| Méthode | Route | Description | Auth |
|---------|-------|-------------|------|
| `POST` | `/api/v1/prepare-rdv` | Lancer le workflow complet | `X-API-Key` |
| `GET` | `/api/v1/status/{job_id}` | Polling du statut | `X-API-Key` |
| `GET` | `/api/v1/export/{job_id}` | Récupérer les livrables | `X-API-Key` |
| `GET` | `/api/v1/health` | Health check | Public |

### Exemple d'appel

```bash
# Lancer une analyse
curl -X POST http://localhost:8000/api/v1/prepare-rdv \
  -H "X-API-Key: change-me-in-production" \
  -H "Content-Type: application/json" \
  -d '{
    "secteur": "magasins optique",
    "seuil_ca": 1000000,
    "fichier_comptes": "<base64>",
    "format_fichier": "txt"
  }'
# → {"job_id": "uuid", "status": "PENDING", "estimated_duration_seconds": 420}

# Suivre le statut
curl http://localhost:8000/api/v1/status/{job_id} \
  -H "X-API-Key: change-me-in-production"
# → {"status": "RUNNING", "current_node": "carla", "progress_pct": 30}

# Récupérer les livrables
curl http://localhost:8000/api/v1/export/{job_id} \
  -H "X-API-Key: change-me-in-production"
# → {"livrables": {"note_sectorielle_md": "...", "swot_json": {...}, "slides_gamma_url": "..."}}
```

---

## Structure du projet

```
├── agents/carla/           # Agent CARLA autonome (Streamlit)
│   ├── agent.py            # ReAct agent avec create_react_agent
│   └── tools.py            # Tools: perplexity_search, source_validator
├── analysis/
│   ├── ratios.py           # Calcul des ratios (rentabilité, trésorerie, activité)
│   ├── rules.py            # Signaux niveaux 1-2 (ratios + montants agrégés)
│   ├── fec_features.py     # IndicateursFEC : ΣD/ΣC par compte, comptages, mensuel
│   └── fec_signals.py      # Moteur FEC (GENERIC/COUNT/PARAM + détecteurs explicites)
├── app/
│   ├── main.py             # UI Streamlit (formulaire + dashboard)
│   └── components/
│       ├── cards.py        # Cartes signaux + missions
│       ├── charts.py       # Radar benchmark + barres signaux
│       ├── download.py     # Export Word
│       └── treasury.py     # Graphiques trésorerie (waterfall, cycle, jauge)
├── benchmark/              # Orchestrateur multi-sources (BdF, INSEE, LLM)
├── matching/
│   ├── mission_matcher.py  # Matcher déterministe (codes_signaux ∩ signaux)
│   ├── llm_matcher.py      # ⚠️ legacy — plus branché
│   └── rag_matcher.py      # ⚠️ legacy — plus branché
├── data/
│   ├── catalogue_missions_tyls.json  # 79 missions TYLS
│   └── seuils_signaux.json           # 90 signaux (référentiel)
├── nodes/                  # Nodes LangGraph (pipeline Streamlit)
│   ├── analyse_sectorielle.py  # Agent CARLA → note + SWOT + micro + questions
│   ├── benchmark_sectoriel.py  # BdF → INSEE → LLM fallback
│   ├── detect_signals.py       # Niveaux 1-4 (ratios + montants + FEC + LLM)
│   ├── extract_financial_data.py   # Parsing + IndicateursFEC
│   ├── generate_interview_plan.py  # Fiche entretien (toutes données)
│   ├── generate_slides.py     # Gamma API v1.0
│   └── match_missions.py       # Appelle MissionMatcher (déterministe)
├── shared/
│   └── slide_builder.py    # Builder Markdown partagé (Streamlit + FastAPI)
├── utils/
│   └── async_helper.py     # Bridge sync→async safe
├── rdv_bilan_ia/           # Pipeline FastAPI (multi-agents, RGPD, HIL)
├── graph.py                # StateGraph principal (Streamlit)
├── models.py               # Modèles Pydantic
└── tests/
```

---

## Anonymisation des données

Activée par défaut dans les deux modes. Masque les données identifiantes **avant** tout envoi aux LLM.

### Mode Streamlit (`parsers/anonymizer.py`)

| Donnée | Traitement |
|--------|-----------|
| `EcritureLib` (FEC) | Remplacé par `****` |
| Comptes tiers 401x/411x/421x/455x | Tronqué à `xxx000` |
| SIREN/SIRET (PDF) | Remplacé par `[SIREN]` |
| Formes juridiques + nom | Remplacé par `[SOCIÉTÉ]` |

### Mode FastAPI (`core/security/anonymisation.py`)

Utilise **spaCy** (`fr_core_news_md`) + **Microsoft Presidio** :
- Entités NER : `PERSON`, `LOCATION`, `ORGANIZATION`, `PHONE_NUMBER`, `EMAIL_ADDRESS`, `IBAN_CODE`
- Reconnaisseurs personnalisés : `SIREN` (9 chiffres), `SIRET` (14 chiffres)
- Score de confiance minimum configurable (`ANONYMISATION_SCORE_MIN=0.95`)
- Si score insuffisant → workflow interrompu avec erreur `422`

---

## Format FEC attendu

Norme DGFiP (Article A47 A-1 du LPF) :
- Séparateur : tabulation
- Encodage : latin-1 (ISO-8859-1)
- Colonnes clés : `JournalCode`, `EcritureDate`, `CompteNum`, `CompAuxNum`
- Montants : soit `Debit` + `Credit`, soit `Montant` + `Sens` — les deux formats
  sont gérés par `analysis/fec_features.py` (le moteur FEC ne calcule les
  indicateurs mensuels que si `EcritureDate` est présente)

---

## Catalogue de missions (`data/catalogue_missions_tyls.json`)

```json
{
  "id": "MISSION_TRESORERIE",
  "titre": "Tableau de bord trésorerie",
  "description": "Mise en place d'un suivi mensuel prévisionnel",
  "benefice_client": "Anticiper les tensions et éviter les découverts",
  "codes_signaux": ["LIQUIDITE_CRITIQUE", "DELAI_CLIENTS_ELEVE"],
  "honoraires_indicatifs": "800-1500€/an",
  "priorite_proposition": 1
}
```

`priorite_proposition` : `1` = toujours proposer, `2` = selon contexte, `3` = rarement

---

## Ajouter un signal déterministe

**1. Déclarer le code** dans `data/seuils_signaux.json` (catégorie, `comptes_fec`,
seuil, période, `parametrable`). Le matcher exige que tout code référencé par une
mission existe dans le référentiel.

**2. Choisir le niveau de détection** selon la donnée disponible :

- **Ratio** (`analysis/rules.py::detect_signals_from_rules`) :

```python
if ratios.mon_ratio < seuil:
    signals.append(Signal(type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
        code="MON_CODE_SIGNAL", titre="Titre court",
        description="Description chiffrée.", levier="Ce que le cabinet propose"))
```

- **Montant agrégé** (`detect_signals_from_donnees`) : même patron, à partir de
  `DonneesFinancieres` (postes N/N-1).

- **Signal FEC compte-fin** (`analysis/fec_signals.py`) — le plus courant :
  - montant/présence/absence/mouvement simple → ajouter une entrée à `GENERIC_SIGNALS` ;
  - comptage de comptes/tiers/journaux distincts → `COUNT_SIGNALS` ;
  - composite paramétrable (Δ N/N-1, ratio, DSO…) → `PARAM_SIGNALS` (`fn(feat, seuil)`) ;
  - logique ad hoc → détecteur explicite ajouté à `_EXPLICIT_DETECTORS`.

  Les accesseurs de `IndicateursFEC` (`solde`, `mouvement`, `variation_pct`,
  `ratio_pct`, `nb_comptes`/`nb_tiers`/`nb_ecritures`, `solde_mensuel`/
  `solde_mensuel_cumule`) couvrent la plupart des cas.

**3. Câbler une mission** : ajouter le code dans les `codes_signaux` d'une mission
du catalogue — le matching se fait automatiquement.

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Orchestration | LangGraph (StateGraph) |
| Détection signaux | Moteur déterministe (référentiel 90 codes) + GPT-4o (enrichissement) |
| Matching missions | Déterministe (`codes_signaux` ∩ signaux) |
| LLM | OpenAI GPT-4o |
| Analyse sectorielle | Agent CARLA — Perplexity (`sonar-pro`) + ReAct loop |
| Présentation | Gamma API v1.0 (`public-api.gamma.app`) |
| Anonymisation | spaCy `fr_core_news_md` + Microsoft Presidio |
| API | FastAPI + Uvicorn |
| Base de données | PostgreSQL (SQLAlchemy async) |
| Queue / Cache | Redis |
| Parsing FEC | pandas |
| Parsing PDF | pdfplumber + LLM |
| Embeddings / RAG | langchain-chroma + OpenAI (legacy, matching désormais déterministe) |
| Benchmarking | BdF Webstat API + INSEE API |
| UI | Streamlit + Plotly |
| Export Word | python-docx |
| Validation modèles | Pydantic v2 |

---

## Tests

```bash
pytest                                                        # tous les tests (263)
pytest tests/test_fec_signals.py                             # moteur FEC (signaux)
pytest tests/test_fec_features.py                            # indicateurs FEC
pytest tests/test_mission_matcher.py                         # matching déterministe
pytest tests/test_rules.py -k "test_ebe_negatif"             # test par nom
pytest -x                                                     # stop au premier échec
```

---

## Licence

Usage interne cabinet. Ne pas distribuer.
