# Plan — Moteur FEC Phase 2c : quick wins agrégats

Spec : `docs/superpowers/specs/2026-07-06-moteur-fec-quickwins-design.md`.
TDD strict, tests dans `tests/test_fec_signals.py`.

## T1 — `SEUIL_TVA_MICRO_DEPASSE` (GENERIC seuil_eur)
- RED : CA 70/C = 80 000 → code présent ; 70 000 → absent ; override abaisse.
- GREEN : ajouter entrée `GENERIC_SIGNALS`.

## T2 — `FRAIS_TRANSPORT_ELEVES` (explicit non-param)
- RED : 6241 = 10 000 € → présent ; 5 000 € & 10 écritures → absent ;
  1 000 € mais 60 écritures → présent (branche count).
- GREEN : détecteur `_frais_transport_eleves`, ajout à `_EXPLICIT_DETECTORS`.

## T3 — Table `PARAM_SIGNALS` + `INVESTISSEMENT_RECENT`
- RED : Δ immo (21) 60 000 vs N-1 0 → présent ; sans N-1 → absent ;
  override abaisse ; `seuils_parametrables` contient le code.
- GREEN : `ParamSpec`, `PARAM_SIGNALS`, boucle dans `detect_signals_from_fec`,
  extension `seuils_parametrables` + `titre_signal`, détecteur.

## T4 — `NOUVEL_EMPRUNT` (PARAM)
- RED : 164/C monte de 60 000 vs N-1 → présent ; stable → absent ; sans N-1 → absent.

## T5 — `BAISSE_MARGE_BRUTE` (PARAM)
- RED : marge passe de 40 % à 30 % (−10 pts) → présent ; −3 pts → absent ;
  sans N-1 → absent ; CA nul → absent.

## T6 — `DELAI_FACTURATION_LONG` (PARAM)
- RED : 411 = 30 000, CA = 365 000 → DSO 30 j > 15 → présent ;
  411 = 10 000, CA = 365 000 → DSO 10 j → absent ; CA nul → absent.

## T7 — E2E + garde-fous
- `seuils_parametrables` couvre bien les 4 codes PARAM (test référentiel).
- E2E : un FEC synthétique déclenche ≥1 des nouveaux codes → mission proposée
  (mirroir de `test_pipeline_e2e.py`).
- Full suite : `pytest` vert (attendu ~223 → ~240).
