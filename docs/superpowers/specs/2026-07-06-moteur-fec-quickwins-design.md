# Design — Moteur FEC Phase 2c : quick wins agrégats

## Contexte

Phases 2a/2b ont couvert 74/90 codes du référentiel `data/seuils_signaux.json`.
Phase 2c ajoute 6 codes **calculables depuis le FEC N (+ montants N/N-1)** avec
l'`IndicateursFEC` existant, sans nouvelle infra d'extraction.

Réserve pour 2d+ : mensuel (per-compte monthly), libellé-flux, N-2, difficiles.

## Codes couverts (6)

| Code | Mécanisme | Seuil défaut | Param |
|---|---|---|---|
| `SEUIL_TVA_MICRO_DEPASSE` | CA (`solde(70,C)`) > seuil | 77 000 € | ✓ |
| `FRAIS_TRANSPORT_ELEVES` | `solde(6241/6242,D) ≥ 10 000 €` **OU** `nb_ecritures > 50` | 10 000 € / 50 | ✗ |
| `INVESTISSEMENT_RECENT` | Δ `solde(20/21/23,D)` N vs N-1 ≥ seuil | 50 000 € | ✓ |
| `NOUVEL_EMPRUNT` | Δ `solde(164,C)` N vs N-1 ≥ seuil | 50 000 € | ✓ |
| `BAISSE_MARGE_BRUTE` | `marge_n1 − marge_n ≥ seuil` (points) | 5 pts | ✓ |
| `DELAI_FACTURATION_LONG` | DSO = `solde(411,D)/solde(70,C)×365` > seuil | 15 jours | ✓ |

`marge = (solde(70,C) − solde(60,D)) / solde(70,C) × 100`.

## Décisions d'architecture

### 1. `SEUIL_TVA_MICRO_DEPASSE` → table `GENERIC_SIGNALS`

Simple `op="seuil_eur"` (comptes `["70"]`, sens `C`, seuil 77 000). Réutilise
tout le plumbing existant (override, `seuils_parametrables`, `titre_signal`).

### 2. `FRAIS_TRANSPORT_ELEVES` → détecteur explicite non-paramétrable

Composite montant-OU-nombre → hors du modèle `GENERIC`. Seuils figés
(`parametrable:false` au référentiel). Ajouté à `_EXPLICIT_DETECTORS`.

### 3. Nouvelle table `PARAM_SIGNALS` pour les détecteurs composites paramétrables

Les 4 codes restants ont une logique composite (Δ N/N-1, marge, DSO) **et** un
seuil éditable dans l'UI. Les détecteurs explicites actuels prennent `(feat)` et
ont des seuils figés → inadaptés. On introduit :

```python
class ParamSpec(NamedTuple):
    fn: Callable[[IndicateursFEC, float], Signal | None]   # (feat, seuil) -> Signal|None
    seuil_defaut: float
    titre: str

PARAM_SIGNALS: dict[str, ParamSpec] = { ... }
```

- `detect_signals_from_fec` boucle sur `PARAM_SIGNALS`, résout
  `overrides.get(code, spec.seuil_defaut)` puis appelle `spec.fn(feat, seuil)`.
- `seuils_parametrables` ajoute `PARAM_SIGNALS` à la boucle (déjà filtrée par
  `ref.parametrable` + `seuil_valeur`), donc ces codes apparaissent dans l'UI.
- `titre_signal` consulte aussi `PARAM_SIGNALS`.

Le seuil défaut de chaque `ParamSpec` = `seuil_valeur` du référentiel (cohérence
avec le défaut affiché par l'UI, comme GENERIC/COUNT).

### 4. Garde N-1 pour les deltas

`INVESTISSEMENT_RECENT`, `NOUVEL_EMPRUNT`, `BAISSE_MARGE_BRUTE` comparent N vs
N-1. Sans FEC N-1, `debit_n1/credit_n1` sont vides → un delta absolu vaudrait le
cumul N (faux positif). **Garde** : `if not feat.debit_n1 and not feat.credit_n1:
return None`. Cohérent avec `variation_pct` qui rend `None` sans N-1.

### 5. Garde CA>0

`BAISSE_MARGE_BRUTE` et `DELAI_FACTURATION_LONG` divisent par le CA → `return
None` si `solde(70,C) <= 0`.

## Hors périmètre

- Aucun changement de catalogue : les missions référençant ces codes se
  déclenchent automatiquement via le matcher existant.
- `type`/`gravite` sont display-only (le matcher n'utilise que `code`).
- UI `number_input` garde `step=1000` (seuils en points/jours un peu clunky mais
  éditables à la main — hors périmètre).

## Couverture cible

74 → **80/90 codes**.
