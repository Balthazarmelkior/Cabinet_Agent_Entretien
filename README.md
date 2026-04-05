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
- **Détection de signaux** : règles déterministes + enrichissement LLM
- **Matching de missions** : catalogue JSON, RAG vectoriel si > 50 missions
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
│   └── rules.py            # Règles de détection de signaux
├── app/
│   ├── main.py             # UI Streamlit (formulaire + dashboard)
│   └── components/
│       ├── cards.py        # Cartes signaux + missions
│       ├── charts.py       # Radar benchmark + barres signaux
│       ├── download.py     # Export Word
│       └── treasury.py     # Graphiques trésorerie (waterfall, cycle, jauge)
├── benchmark/              # Orchestrateur multi-sources (BdF, INSEE, LLM)
├── matching/               # Matching missions (LLM direct ou RAG)
├── nodes/                  # Nodes LangGraph (pipeline Streamlit)
│   ├── analyse_sectorielle.py  # Agent CARLA → note + SWOT + micro + questions
│   ├── benchmark_sectoriel.py  # BdF → INSEE → LLM fallback
│   ├── detect_signals.py       # Règles + enrichissement LLM
│   ├── extract_financial_data.py
│   ├── generate_interview_plan.py  # Fiche entretien (toutes données)
│   ├── generate_slides.py     # Gamma API v1.0
│   └── match_missions.py
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
- Colonnes obligatoires : `JournalCode`, `EcritureDate`, `CompteNum`, `Montant`

---

## Catalogue de missions (`data/catalogue_missions.json`)

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

Éditer `analysis/rules.py` :

```python
if ratios.mon_ratio < seuil:
    signals.append(Signal(
        type=TypeSignal.RISQUE,
        gravite=Gravite.MOYENNE,
        code="MON_CODE_SIGNAL",
        titre="Titre court",
        description="Description chiffrée.",
        levier="Ce que le cabinet peut proposer"
    ))
```

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Orchestration | LangGraph (StateGraph) |
| LLM | OpenAI GPT-4o |
| Analyse sectorielle | Agent CARLA — Perplexity (`sonar-pro`) + ReAct loop |
| Présentation | Gamma API v1.0 (`public-api.gamma.app`) |
| Anonymisation | spaCy `fr_core_news_md` + Microsoft Presidio |
| API | FastAPI + Uvicorn |
| Base de données | PostgreSQL (SQLAlchemy async) |
| Queue / Cache | Redis |
| Parsing FEC | pandas |
| Parsing PDF | pdfplumber + LLM |
| Embeddings / RAG | langchain-chroma + OpenAI |
| Benchmarking | BdF Webstat API + INSEE API |
| UI | Streamlit + Plotly |
| Export Word | python-docx |
| Validation modèles | Pydantic v2 |

---

## Tests

```bash
pytest                                                        # tous les tests (122)
pytest tests/test_fec_parser.py                              # fichier unique
pytest tests/test_ratios.py                                  # ratios + trésorerie
pytest tests/test_rules.py -k "test_ebe_negatif"             # test par nom
pytest -x                                                     # stop au premier échec
```

---

## Licence

Usage interne cabinet. Ne pas distribuer.
