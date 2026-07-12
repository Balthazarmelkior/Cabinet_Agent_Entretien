# Plan — Moteur FEC Phase 2d : signaux mensuels

Spec : `docs/superpowers/specs/2026-07-06-moteur-fec-mensuel-design.md`. TDD strict.

## T1 — Infra sommes mensuelles (`fec_features.py`)
- RED (`tests/test_fec_features.py` ou `test_fec_signals.py`) :
  `solde_mensuel(["70"],"C")` renvoie `{mois: montant}` ; `solde_mensuel_cumule`
  cumule dans l'ordre des mois.
- GREEN : `_normalize_amounts`, `_monthly_sums`, champs `debit_mensuel`/
  `credit_mensuel`, accesseurs `solde_mensuel`/`solde_mensuel_cumule`.

## T2 — `DECOUVERT_RECURRENT` (explicit)
- RED : 519 créditeur sur 3 mois → présent ; 2 mois → absent.
- GREEN : `_decouvert_recurrent`, ajout à `_EXPLICIT_DETECTORS`.

## T3 — `SAISONNALITE_FORTE` (PARAM)
- RED : CA très dispersé sur 12 mois (CV > 30) → présent ; CA stable → absent ;
  < 6 mois → absent ; override abaisse.
- GREEN : `_saisonnalite_forte(feat, seuil)`, entrée `PARAM_SIGNALS`.

## T4 — E2E + garde-fous
- `seuils_parametrables` contient `SAISONNALITE_FORTE`.
- E2E : FEC synthétique 12 mois découvert+saisonnalité → missions
  `MISSION_PILOTAGE_PREVISIONNEL_TRESO` proposée.
- Full suite verte (~244 → ~254).
