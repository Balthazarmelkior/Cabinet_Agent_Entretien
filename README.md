# 📊 Agent Entretien Bilan — Cabinet Comptable

Agent LangGraph qui analyse un bilan client (FEC ou PDF), benchmark les ratios par rapport au secteur, détecte les signaux financiers et recommande des missions du cabinet. L'expert-comptable reçoit une fiche d'entretien prête à l'emploi.

---

## Fonctionnalités

- **Parsing automatique** FEC (CSV tabulé, norme DGFiP) et bilan PDF
- **Calcul de ratios** : rentabilité, liquidité, solvabilité, activité
- **Benchmarking sectoriel** : Banque de France → INSEE → LLM (fallback automatique)
- **Détection de signaux** : règles déterministes + enrichissement LLM
- **Matching de missions** : catalogue JSON, RAG vectoriel si > 50 missions
- **Fiche d'entretien** exportable en Word (.docx)
- **UI Streamlit** dashboard single-page

---

## Architecture

```
cabinet_agent/
├── app/
│   ├── main.py                  # UI Streamlit (point d'entrée)
│   └── components/
│       ├── charts.py            # Graphiques Plotly (radar, bar)
│       ├── cards.py             # Composants HTML signaux & missions
│       └── download.py          # Export Word en mémoire
├── parsers/
│   ├── fec_parser.py            # Parser FEC déterministe (pandas)
│   └── pdf_parser.py            # Parser PDF via LLM + pdfplumber
├── analysis/
│   ├── ratios.py                # Calcul des ratios financiers
│   ├── rules.py                 # Règles de détection des signaux
│   └── llm_signals.py           # Signaux qualitatifs via LLM
├── benchmark/
│   ├── base.py                  # Interface commune + RatiosBruts
│   ├── orchestrator.py          # Fusion des 3 sources
│   └── sources/
│       ├── bdf.py               # Banque de France (API Webstat)
│       ├── insee.py             # INSEE Esane
│       └── llm_source.py        # Fallback LLM
├── matching/
│   ├── llm_matcher.py           # Matching direct (catalogue court)
│   └── rag_matcher.py           # Matching vectoriel (catalogue long)
├── nodes/                       # Nœuds LangGraph
│   ├── extract_financial_data.py
│   ├── detect_signals.py
│   ├── benchmark_sectoriel.py
│   ├── match_missions.py
│   └── generate_interview_plan.py
├── output/
│   └── word_generator.py        # Export Word (python-docx)
├── models.py                    # Modèles Pydantic
├── graph.py                     # StateGraph LangGraph
├── data/
│   └── catalogue_missions.json  # Catalogue des missions du cabinet
├── requirements.txt
└── .env.example
```

---

## Installation

### 1. Cloner et créer l'environnement

```bash
git clone <repo>
cd cabinet_agent
python -m venv .venv
source .venv/bin/activate        # Linux/Mac
# .venv\Scripts\activate         # Windows
pip install -r requirements.txt
```

### 2. Variables d'environnement

```bash
cp .env.example .env
# Éditer .env avec vos clés API
```

```env
OPENAI_API_KEY=sk-...
INSEE_API_KEY=...          # optionnel — fallback LLM si absent
```

> **INSEE API Key** : inscription gratuite sur https://api.insee.fr/

### 3. Personnaliser le catalogue de missions

Éditer `data/catalogue_missions.json` avec les missions de votre cabinet.
Voir la structure dans [data/catalogue_missions.json](data/catalogue_missions.json).

### 4. Lancer l'UI

```bash
streamlit run app/main.py
```

Ouvrir http://localhost:8501

---

## Utilisation

1. **Déposer le fichier** FEC (`.txt` ou `.csv`) ou bilan PDF
2. **Saisir le code NAF** à 5 caractères (ex: `4711F`) — visible sur le Kbis
3. **Renseigner le nom du client**
4. Cliquer **Lancer l'analyse**
5. Explorer les 4 onglets : Benchmark · Signaux · Missions · Fiche entretien
6. **Télécharger** la fiche Word

---

## Format FEC attendu

Le FEC doit respecter la norme DGFiP (Article A47 A-1 du LPF) :
- Séparateur : tabulation
- Encodage : latin-1 (ISO-8859-1)
- Colonnes obligatoires : `JournalCode`, `EcritureDate`, `CompteNum`, `Montant`

---

## Catalogue de missions

Structure JSON attendue :

```json
[
  {
    "id": "MISSION_TRESORERIE",
    "titre": "Tableau de bord trésorerie",
    "description": "Mise en place d'un suivi mensuel prévisionnel",
    "benefice_client": "Anticiper les tensions et éviter les découverts",
    "codes_signaux": ["LIQUIDITE_CRITIQUE", "DELAI_CLIENTS_ELEVE"],
    "honoraires_indicatifs": "800-1500€/an",
    "priorite_proposition": 1
  }
]
```

`priorite_proposition` : `1` = toujours proposer, `2` = selon contexte, `3` = rarement

---

## Stack technique

| Composant | Technologie |
|-----------|-------------|
| Orchestration agents | LangGraph |
| LLM | OpenAI GPT-4o |
| Parsing FEC | pandas |
| Parsing PDF | pdfplumber + LLM |
| Embeddings / RAG | langchain-chroma + OpenAI |
| Benchmarking | BdF Webstat API + INSEE API |
| UI | Streamlit |
| Graphiques | Plotly |
| Export Word | python-docx |
| Validation modèles | Pydantic v2 |

---

## Ajout de nouvelles règles de signaux

Éditer `analysis/rules.py` — ajouter un bloc dans `detect_signals_from_rules()` :

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

## Licence

Usage interne cabinet. Ne pas distribuer.
