# Design — Moteur FEC Phase 2d : signaux mensuels

## Contexte

Phase 2c → 80/90 codes. Phase 2d ajoute 2 codes nécessitant une granularité
**mensuelle par compte**, absente de `IndicateursFEC` (qui n'a que `mois` = liste
des mois actifs, sans montants).

| Code | Mécanisme | Seuil | Param |
|---|---|---|---|
| `DECOUVERT_RECURRENT` | nb mois où le solde créditeur cumulé de `519` > 0 ≥ 3 | 3 mois | ✗ |
| `SAISONNALITE_FORTE` | coefficient de variation du CA mensuel (`70`) > seuil | 30 % | ✓ |

## Nouvelle infra : sommes mensuelles par compte

`IndicateursFEC` enrichi de :

```python
debit_mensuel: dict[str, dict[str, float]]   # mois(YYYYMM) -> compte -> ΣDébit
credit_mensuel: dict[str, dict[str, float]]  # mois(YYYYMM) -> compte -> ΣCrédit
```

Construits dans `compute_fec_features` via `_monthly_sums(df)` qui réutilise la
**même normalisation Débit/Crédit** que `_sums_by_account` (extraite en helper
`_normalize_amounts`) puis `groupby([mois, compte])`. Vide si pas d'`EcritureDate`.

Accesseurs :
- `solde_mensuel(prefixes, sens)` → `dict[mois, solde]` (mouvement net du mois).
- `solde_mensuel_cumule(prefixes, sens)` → `dict[mois, solde cumulé]` (mois triés,
  running balance ; nécessaire pour un solde de compte de bilan comme 519).

## Détecteurs

### `DECOUVERT_RECURRENT` (explicit, non-param)
`519` (concours bancaires courants) est un compte de passif : un **solde
créditeur cumulé > 0** en fin de mois = découvert mobilisé. On compte les mois où
`solde_mensuel_cumule(["519"], "C") > 0`. ≥ 3 → signal. Les à-nouveaux (journal AN
en début d'exercice) initialisent correctement le cumul.

### `SAISONNALITE_FORTE` (PARAM)
CA mensuel = `solde_mensuel(["70"], "C")` sur **tous les mois actifs** (un mois
sans vente compte comme 0 → renforce la saisonnalité). Coefficient de variation
`CV = écart-type / moyenne × 100`. Fire si `CV > seuil` (défaut 30).
**Garde** : `len(mois) < 6` ou `moyenne ≤ 0` → `None` (CV non significatif sur
trop peu de mois).

## Décisions

- `DECOUVERT_RECURRENT` → détecteur explicite (seuil 3 figé, `parametrable:false`).
- `SAISONNALITE_FORTE` → `PARAM_SIGNALS` (seuil éditable, `fn(feat, seuil)`), donc
  exposé automatiquement dans l'UI.
- Heuristique documentée : découvert = solde cumulé mensuel > 0 (et non simple
  présence de mouvement) ; saisonnalité = CV et non (max−min)/moyenne.

## Couverture cible

80 → **82/90 codes**.
