# Analyse detaillee de la tresorerie — Design Spec

## Objectif

Ajouter un onglet "Tresorerie" au dashboard Streamlit avec des indicateurs BFR/FRNG/tresorerie nette, un graphique waterfall BFR, un graphique cycle de conversion en jours, et une jauge de tresorerie nette avec zones de risque.

## Indicateurs a calculer

Ajout dans `analysis/ratios.py` (dataclass `Ratios`) :

| Indicateur | Formule | Type |
|---|---|---|
| `bfr` | creances_clients + stocks - dettes_fournisseurs | float (euros) |
| `frng` | (capitaux_propres + dettes_financieres) - immobilisations_nettes | float (euros) |
| `tresorerie_nette` | frng - bfr | float (euros) |
| `cycle_conversion_jours` | delai_clients_jours + rotation_stocks_jours - delai_fournisseurs_jours | float (jours) |
| `tresorerie_nette_jours_ca` | tresorerie_nette / ca * 365 | float (jours de CA) |
| `bfr_n1` | idem N-1, None si pas de N-1 | Optional[float] |
| `frng_n1` | idem N-1, None si pas de N-1 | Optional[float] |
| `tresorerie_nette_n1` | idem N-1, None si pas de N-1 | Optional[float] |

## Contenu de l'onglet

### Zone haute — 4 KPI cards

Meme style HTML que les KPI existants (`kpi-card`). Chaque carte affiche :
- Label (BFR / FRNG / Tresorerie nette / Cycle conversion)
- Montant N formate en euros (ou jours pour le cycle)
- Variation N/N-1 en % avec fleche coloree (si N-1 disponible)

### Zone milieu gauche — Waterfall BFR

Graphique Plotly waterfall :
- Barre "Creances clients" (positive, bleu)
- Barre "Stocks" (positive, bleu)
- Barre "Dettes fournisseurs" (negative, rouge)
- Barre "BFR" (total, bleu fonce)

### Zone milieu droite — Cycle de conversion (jours)

Barres horizontales Plotly :
- Delai clients (jours)
- Rotation stocks (jours)
- Delai fournisseurs (jours, affiche en negatif)
- Cycle total (barre finale)

Si benchmark disponible, overlay des medianes sectorielles sur chaque barre.

### Zone basse — Jauge tresorerie nette

Plotly gauge indicator :
- Rouge : < 0 jours de CA
- Orange : 0-15 jours de CA
- Vert : > 15 jours de CA
- Aiguille sur la valeur client en jours de CA
- Sous-titre avec montant en euros

## Fichiers

| Action | Fichier | Responsabilite |
|---|---|---|
| Modifier | `analysis/ratios.py` | Ajouter 8 champs + calculs dans `compute_ratios()` |
| Creer | `app/components/treasury.py` | 3 fonctions Plotly : `render_bfr_waterfall()`, `render_cycle_bars()`, `render_treasury_gauge()` |
| Modifier | `app/main.py` | Nouvel onglet entre "Analyse sectorielle" et "Signaux" |

## Hors scope

- Pas de projection / prediction
- Pas de nouveau modele Pydantic
- Pas de modification du pipeline LangGraph
- Pas de nouveau node
