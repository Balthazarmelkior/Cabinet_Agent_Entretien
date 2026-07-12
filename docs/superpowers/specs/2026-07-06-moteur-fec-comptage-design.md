# Moteur FEC — Comptage / distinct (Phase 2b) — Design

**Date:** 2026-07-06
**Statut:** Validé (design), prêt pour plan d'implémentation
**Contexte:** Suite de la Phase 2a (moteur FEC famille A). Cf. `docs/superpowers/specs/2026-07-05-moteur-fec-famille-a-design.md` et la mémoire projet `catalogue-tyls-matching-deterministe`.

## Objectif

Émettre les 7 signaux « comptage / distinct » du référentiel `data/seuils_signaux.json`, détectables en comptant des entités distinctes dans le FEC (sous-comptes, tiers CompAuxNum, journaux, écritures). Réutilise et étend `IndicateursFEC` (Phase 2a) ; aucune modification du pipeline ni du matcher.

**Codes couverts (7) :** `EMPRUNTS_MULTIPLES`, `MULTI_BIENS_IMMOBILIERS`, `PARC_VEHICULES_IMPORTANT`, `NOMBREUX_FOURNISSEURS`, `ACOMPTES_FREQUENTS`, `COMPLEXITE_COMPTABLE`, `VOLUME_FACTURATION_ELEVE`.

**Hors périmètre (sous-phases suivantes) :** mensuel (`DECOUVERT_RECURRENT`, `SAISONNALITE_FORTE`), N-2 (`DIVIDENDES_RECURRENTS`), libellé/flux (`IMMO_LOCATIF_DETECTE`, `NON_EQUIPE_FACTURE_ELECTRONIQUE`, `NOUVELLES_ACTIVITES`, `NOUVEL_EMPRUNT`, `FIN_EMPRUNT_PROCHE`, `INVESTISSEMENT_RECENT`), quick wins (`BAISSE_MARGE_BRUTE`, `FRAIS_TRANSPORT_ELEVES`, `SEUIL_TVA_MICRO_DEPASSE`, `DEPASSEMENT_SEUILS_CAC`), difficiles (`DELAI_FACTURATION_LONG`, `BALANCE_AGEE_DEGRADEE`, `ABSENCE_COMPTABILITE_ANALYTIQUE`).

## Hypothèses de comptage (validées sur le FEC réel du repo)

Inspection de `input/443021456FEC20250831.txt` :
- **Fournisseurs** : compte `401` porte **1 seul sous-compte** mais **26 `CompAuxNum` distincts** → les tiers fournisseurs sont tenus en comptabilité auxiliaire (CompAuxNum), pas en sous-comptes. Le comptage fournisseurs se fait donc sur **CompAuxNum distinct** (repli : sous-compte si CompAuxNum vide).
- **Emprunts / biens / véhicules** : tenus en **sous-comptes distincts** (ex. `1641xxx` = un emprunt, `2131xxx` = un bien). Pour ce client : 0 emprunt, 0 bien 213, 1 compte 2182 — aucun déclenchement, cohérent.
- **Journaux** : 7 distincts (`AC, AN, BNP, OD, OI, SA, VE`) → `COMPLEXITE_COMPTABLE` (seuil 8) ne déclenche pas. Correct.
- **Volume** : 53 écritures compte 70/an (~4/mois), 144 compte 60/an (~12/mois) → sous les seuils 30/50 par mois. Correct.

Métrique généralisée retenue :
- **sous-comptes distincts** sous un préfixe → emprunts, biens, véhicules.
- **tiers distincts** (CompAuxNum sinon sous-compte) sous un préfixe → fournisseurs.
- **écritures** (lignes) sous un préfixe → acomptes, volume.
- **journaux distincts** (JournalCode) → complexité.

## Architecture (extension de Phase 2a)

Aucun nouveau nœud, aucun changement de state. `compute_fec_features(df, df_n1)` calcule en plus les features de comptage depuis le **même `df`** déjà chargé.

```
extract_financial_data → compute_fec_features(df, df_n1) → IndicateursFEC (+ champs comptage)
detect_signals → detect_signals_from_fec(feat, overrides)
    ├─ boucle GENERIC_SIGNALS      (Phase 2a, 26)
    ├─ boucle COUNT_SIGNALS        ← NOUVEAU (6)
    ├─ _EXPLICIT_DETECTORS         (Phase 2a, 19) + _volume_facturation ← NOUVEAU (1)
```

### `IndicateursFEC` — nouveaux champs (dans `analysis/fec_features.py`)
Calculés à l'extraction, tolérants aux colonnes absentes :
```python
    comptes: list[str] = []                        # CompteNum distincts
    paires_tiers: list[list[str]] = []             # [CompteNum, CompAuxNum] distincts (aux "" si absent)
    nb_ecritures_par_compte: dict[str, int] = {}   # lignes par CompteNum
    journaux: list[str] = []                        # JournalCode distincts ("" ignoré)
    mois: list[str] = []                            # "YYYY-MM" distincts (EcritureDate[:6])
```
Accesseurs :
```python
    def nb_comptes(self, prefixes) -> int          # sous-comptes distincts sous le(s) préfixe(s)
    def nb_tiers(self, prefixes) -> int            # tiers distincts : CompAuxNum si présent, sinon CompteNum
    def nb_ecritures(self, prefixes) -> int        # somme des lignes
    def nb_journaux(self) -> int
    def nb_mois(self) -> int                        # ≥ 1 (pour éviter division par 0 en aval)
```
`nb_tiers(["401"])` : parmi `paires_tiers` dont le compte commence par 401, compte les clés distinctes `aux or compte`.

Colonnes source (`CompAuxNum`, `JournalCode`) absentes du df (fixtures synthétiques) → champs vides, accesseurs renvoient 0 (aucun signal de comptage émis, dégradation propre).

### Détection (dans `analysis/fec_signals.py`)

Nouvelle table `COUNT_SIGNALS` (NamedTuple `CountSpec`), pour les 6 signaux « métrique ≥ seuil » :
```python
class CountSpec(NamedTuple):
    metric: str          # "nb_comptes" | "nb_tiers" | "nb_ecritures" | "nb_journaux"
    comptes: list[str]   # préfixe(s) ; ignoré pour nb_journaux
    seuil_defaut: int
    type: TypeSignal
    gravite: Gravite
    titre: str
    levier: str
```
| Code | metric | comptes | seuil |
|---|---|---|---|
| EMPRUNTS_MULTIPLES | nb_comptes | ["164"] | 3 |
| MULTI_BIENS_IMMOBILIERS | nb_comptes | ["213"] | 2 |
| PARC_VEHICULES_IMPORTANT | nb_comptes | ["2182"] | 5 |
| NOMBREUX_FOURNISSEURS | nb_tiers | ["401"] | 50 |
| ACOMPTES_FREQUENTS | nb_ecritures | ["4191"] | 5 |
| COMPLEXITE_COMPTABLE | nb_journaux | [] | 8 |

`_eval_count(code, feat, overrides)` : dispatche `metric` → accesseur, émet le `Signal` si `valeur >= seuil` (comparaison **inclusive** ; le référentiel dit « ≥ N »). Seuil = `overrides.get(code, seuil_defaut)`.

`VOLUME_FACTURATION_ELEVE` = détecteur explicite `_volume_facturation` (double seuil mensuel, `parametrable:false` dans le référentiel) :
```python
def _volume_facturation(f):
    mois = f.nb_mois()
    emises = f.nb_ecritures(["70"]) / mois
    recues = f.nb_ecritures(["60"]) / mois
    if emises >= 30 or recues >= 50:  # émet ...
```
Types/gravités : comptage = surtout CONFORMITE/OPPORTUNITE faible→moyenne (missions assurance flotte/bris, gestion SCI/portefeuille, facture électronique, DAF externalisée). Détail dans le plan.

### Seuils paramétrables (UI Streamlit)
`seuils_parametrables(referentiel)` étendu : parcourt aussi `COUNT_SIGNALS` et ajoute les codes `parametrable:true` avec `seuil_valeur` non nul (unité `NOMBRE`). Ils apparaissent alors automatiquement dans l'expander « ⚙️ Seuils de détection » existant (l'UI lit `.titre` du spec via un accès unifié). `VOLUME_FACTURATION_ELEVE` (parametrable:false) n'est pas exposé.

> Note d'implémentation : l'expander UI (Phase 2a) lit `GENERIC_SIGNALS[code].titre`. Comme `seuils_parametrables` renverra désormais aussi des codes de `COUNT_SIGNALS`, l'UI doit résoudre le titre depuis l'une ou l'autre table. Fournir un helper `titre_signal(code) -> str` dans `fec_signals.py` (cherche dans GENERIC_SIGNALS puis COUNT_SIGNALS) et l'utiliser dans l'expander.

## Gestion des erreurs
- Colonnes `CompAuxNum`/`JournalCode` absentes → listes vides → accesseurs = 0 → aucun signal de comptage (pas de crash).
- `nb_mois()` renvoie au minimum 1 (jamais de division par 0 dans `_volume_facturation`).
- Tous les codes émis existent au référentiel (vérifié : les 7 y figurent).

## Tests
- `tests/test_fec_features.py` : nouveaux tests d'extraction comptage sur un df synthétique portant `CompAuxNum` et `JournalCode` — `nb_comptes` (sous-comptes distincts), `nb_tiers` (CompAuxNum distinct + repli sous-compte), `nb_ecritures`, `nb_journaux`, `nb_mois` (dont ≥1 sur df vide), et le cas colonnes absentes → 0.
- `tests/test_fec_signals.py` : pour chaque signal de comptage, cas déclenché + cas juste sous le seuil ; test surcharge (override d'un seuil de comptage change l'émission) ; `_volume_facturation` sur les deux branches (émises ≥30 ; reçues ≥50) et cas non déclenché.
- E2E (`tests/test_pipeline_e2e.py`) : un FEC synthétique avec 26 CompAuxNum sous 401 → `NOMBREUX_FOURNISSEURS` remonte jusqu'à la mission `MISSION_COMPTA_FX_MISE_EN_PLACE` (facture électronique).
- Non-régression : les 198 tests Phase 1/2a restent verts.

## Décisions actées
- Extraction : extension de `IndicateursFEC` (mêmes df, pas de nouveau nœud ni state).
- Fournisseurs comptés par **CompAuxNum** (validé : 26 tiers réels sous 1 sous-compte 401) ; emprunts/biens/véhicules par **sous-comptes distincts**.
- Détection : table `COUNT_SIGNALS` (6, métrique ≥ seuil, inclusif) + 1 détecteur explicite `VOLUME_FACTURATION_ELEVE`.
- Seuils de comptage paramétrables exposés dans l'UI via `seuils_parametrables` étendu + helper `titre_signal`.
- Vocabulaire aligné 1:1 sur `seuils_signaux.json` → matcher inchangé. Couverture après 2b : **74/90 codes**.
