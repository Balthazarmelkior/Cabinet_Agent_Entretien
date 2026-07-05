# Moteur FEC — Extraction + détection famille A (Phase 2a) — Design

**Date:** 2026-07-05
**Statut:** Validé (design), prêt pour plan d'implémentation
**Contexte:** Suite de la Phase 1 (matching déterministe TYLS). Cf. `docs/superpowers/plans/2026-07-05-catalogue-tyls-matching-deterministe.md` et la mémoire projet `catalogue-tyls-matching-deterministe`.

## Objectif

Émettre les signaux « famille A » du référentiel `data/seuils_signaux.json` — ceux détectables par **seuil sur compte fin de l'exercice courant** (y compris règles composées même-année, ratios de comptes, et variations N/N-1) — afin que le matcher déterministe existant déclenche les missions correspondantes. Aucune modification du matching : on ajoute uniquement de nouveaux codes signaux au flux de détection.

**Hors périmètre (sous-phases 2b+)** : comptage/distinct (emprunts, fournisseurs, véhicules, biens, écritures, journaux), séries mensuelles (`DECOUVERT_RECURRENT`…), récurrence multi-années N-2 (`DIVIDENDES_RECURRENTS`…), heuristiques de libellé (`IMMO_LOCATIF_DETECTE`, `NON_EQUIPE_FACTURE_ELECTRONIQUE`), flux d'emprunt (`NOUVEL_EMPRUNT`, `FIN_EMPRUNT_PROCHE`, `INVESTISSEMENT_RECENT`).

## Architecture

### Flux de données
```
extract_financial_data (node)
  ├─ parse_fec(fec, fec_n1) → DonneesFinancieres          (inchangé)
  └─ compute_fec_features(df, df_n1) → IndicateursFEC      ← NOUVEAU
        ↓ écrit dans BillanState["indicateurs_fec"]
detect_signals (node)
  ├─ detect_signals_from_rules(ratios)                     (existant)
  ├─ detect_signals_from_donnees(donnees, ratios)          (existant)
  └─ detect_signals_from_fec(features, seuils_config)      ← NOUVEAU
```

### Nouveaux fichiers / modifications
| Fichier | Rôle |
|---|---|
| `analysis/fec_features.py` (nouveau) | `compute_fec_features(df, df_n1) -> IndicateursFEC` |
| `analysis/fec_signals.py` (nouveau) | `detect_signals_from_fec(features, seuils) -> list[Signal]` : moteur générique + détecteurs explicites |
| `models.py` (modif) | ajout du modèle `IndicateursFEC` |
| `graph.py` (modif) | `BillanState` gagne `indicateurs_fec: Optional[IndicateursFEC]` |
| `nodes/extract_financial_data.py` (modif) | calcule et stocke `indicateurs_fec` |
| `nodes/detect_signals.py` (modif) | appelle `detect_signals_from_fec` et concatène |

Le `df` brut est déjà chargé par `parsers.fec_parser._load_df`. `compute_fec_features` réutilise ce df (et celui de N-1 s'il existe) — pas de re-parsing.

## `IndicateursFEC` (couche d'extraction)

Modèle Pydantic construit **une fois** depuis le(s) df brut(s). Interface minimale et fine :

```python
class IndicateursFEC(BaseModel):
    soldes_n: dict[str, float]     # préfixe compte fin -> solde signé (magnitude métier)
    soldes_n1: dict[str, float]    # idem exercice N-1 (vide si pas de FEC N-1)
    ca_n: float                    # mémorisé pour les règles composées « … et CA > X »

    def solde(self, prefixes: list[str], *, n1: bool = False) -> float: ...
    def variation_pct(self, prefixes: list[str]) -> float | None: ...      # None si N-1 absent/0
    def ratio_pct(self, num: list[str], den: list[str]) -> float | None: ... # None si dénominateur 0
```

`compute_fec_features` pré-agrège les soldes par **préfixe de compte utile** (l'union des `comptes_fec` du référentiel famille A, plus 12/70/CA pour les règles composées), pour N et N-1.

### Convention de signe (POINT DE CORRECTION CRITIQUE)
`_load_df` calcule `Montant` avec une normalisation crédit pour les racines `^(1|40|7)` seulement (`Montant = Crédit − Débit` pour ces comptes, `Débit − Crédit` sinon). Conséquences à gérer explicitement dans `compute_fec_features` :
- **Comptes de charges (classe 6)** : `Débit − Crédit` → solde **positif** = montant de charge. ✅ direct pour `616`, `6411`, `6712`, etc.
- **Comptes de produits (classe 7)** : normalisés crédit → **positif** = produit. ✅ direct pour `706`, `708`, `775`, `757`.
- **Compte courant d'associé créditeur `455`** (classe 4, hors `40`) : `Débit − Crédit` → un solde **créditeur** ressort **négatif**. La détection `455 > 50 000` doit comparer la **magnitude créditrice**, donc travailler sur `max(0, −solde(455))` (ou `abs`). Idem tout compte de passif hors classe 1.
- **Capital `101`, capitaux propres (classe 1)** : normalisés crédit → positif.

`compute_fec_features` **normalise chaque solde en magnitude métier positive attendue par le seuil** (documenté par compte), pour que les détecteurs comparent des grandeurs homogènes. Les tests couvrent explicitement `455` créditeur, un compte de charge, un compte de produit et un compte de bilan actif.

## Détection hybride (`detect_signals_from_fec`)

### Moteur générique (piloté par `seuils_signaux.json`)
Traite les entrées machine-lisibles via 3 opérateurs dérivés du couple (`seuil_valeur`, `seuil_unite`, `seuil_texte`) :
- `seuil_eur` : `solde(comptes) > seuil_valeur` (unité `EUR`, `seuil_valeur` numérique).
- `presence` : `solde(comptes) > 0` (unité `EUR`, `seuil_valeur == 0`, `seuil_texte` « > 0 € »).
- `absence` : `solde(comptes) == 0` (règle « = 0 »).

Le moteur lit la table `GENERIC_SIGNALS` (mapping code → opérateur + type/gravité/titre/levier), applique le seuil du référentiel (surchargé si `parametrable`), et émet le `Signal`. Ajouter un signal simple = ajouter une ligne dans `GENERIC_SIGNALS` + s'assurer que ses comptes sont pré-agrégés.

> Justification du mapping explicite plutôt que 100 % JSON : le référentiel ne porte ni le type/gravité/levier ni la sémantique de signe/magnitude. Le mapping `GENERIC_SIGNALS` centralise ces métadonnées ; le **seuil chiffré** reste, lui, la seule source de vérité côté JSON (paramétrable).

### Détecteurs explicites
Une fonction par règle composée / ratio / variation, renvoyant `Signal | None`. Regroupées par nature dans `fec_signals.py`.

### Seuils paramétrables
Les entrées `parametrable: true` avec `seuil_valeur` non nul lisent leur seuil depuis le référentiel, surchargeable via une config d'environnement (`FEC_SEUILS_OVERRIDE` = chemin JSON optionnel de surcharges `{code: valeur}`). Pas de valeur en dur pour ces cas. Les seuils `parametrable: false` (règles structurelles) restent définis dans le code du détecteur explicite.

## Périmètre exhaustif — 45 codes famille A

### Générique — `seuil_eur` (13)
| Code | Comptes | Seuil |
|---|---|---|
| PORTEFEUILLE_FINANCIER_IMPORTANT | 26,27,50,51 | > 500 000 € |
| CESSION_ACTIFS_RECENTE | 775,757 | > 50 000 € |
| REMUNERATION_DIRIGEANT_ELEVEE | 6411 | > 48 000 € |
| FRAIS_CONTENTIEUX_ELEVES | 6227 | > 1 000 € |
| HONORAIRES_JURIDIQUES_ELEVES | 6226,6228 | > 2 000 € |
| FRAIS_ADMINISTRATIFS_ELEVES | 626 | > 3 000 € |
| REVENUS_LOCATIFS_ELEVES | 706,708 | > 30 000 € |
| PATRIMOINE_IMMO_IMPORTANT | 213,214 | > 300 000 € |
| CA_LOCATIF_CONSOLIDE_ELEVE | 706,708 | > 80 000 € |
| IMMO_PRO_ELEVEE | 213 | > 400 000 € |
| LOYERS_VERSES_ELEVES | 613 | > 60 000 € |
| PARC_MACHINES_IMPORTANT | 215 | > 50 000 € |
| ACTIFS_A_ASSURER | 21,3 | > 50 000 € |

### Générique — `presence` compte > 0 (11)
| Code | Comptes |
|---|---|
| CLIENTS_DOUTEUX | 416 |
| CREANCES_PASSEES_EN_PERTE | 654 |
| DEPRECIATION_CREANCES | 491 |
| PENALITES_FISCALES | 6712 |
| PENALITES_SOCIALES | 6714 |
| PROVISION_RISQUE_SOCIAL | 158,1511 |
| FONDS_COMMERCIAL_RECENT | 207 |
| CONSTRUCTION_EN_COURS | 231 |
| NOUVEL_ASSOCIE | 4561,108 |
| TITRES_PARTICIPATION_DETECTES | 261,271 |
| NOUVEAU_BAIL | 275 |

> Note : `NOUVEL_ASSOCIE`, `TITRES_PARTICIPATION_DETECTES`, `NOUVEAU_BAIL`, `CONSTRUCTION_EN_COURS` sont des « nouveaux mouvements » dans le référentiel ; en Phase 2a on les approxime par **présence d'un solde > 0** sur l'exercice courant (la détection stricte de « mouvement nouveau » vs N-1 relèvera d'une sous-phase flux). Approximation documentée dans la description du signal émis.

### Générique — `absence` compte = 0 (2)
| Code | Comptes |
|---|---|
| ABSENCE_ASSURANCE_RC | 616 |
| ABSENCE_PER_RETRAITE | 646,6467,6468 |

### Explicite — ratio de comptes (4)
| Code | Règle |
|---|---|
| CHARGES_SOCIALES_ELEVEES | 645 / 641 > 45 % |
| RATIO_DIVIDENDES_ELEVE | 457 / 6411 > 60 % |
| CHARGES_SOCIALES_PERSO_ELEVEES | 646 / 12 > 30 % |
| AMORTISSEMENTS_AVANCES | 2813 / 213 > 80 % |

### Explicite — composite même-année (8)
| Code | Règle |
|---|---|
| COMPTE_COURANT_CREDITEUR_ELEVE | magnitude créditrice 455 > 50 000 € (paliers 100/150/200 K€ → gravité croissante) |
| ABSENCE_INTERESSEMENT | 6414 = 0 ET RN(12) > 80 000 € |
| ABSENCE_PROVISION_IFC | 153 = 0 ET 641 > 100 000 € |
| ABSENCE_PREVOYANCE_MADELIN | 6467 = 0 ET 6411 > 36 000 € |
| SOUS_REMUNERATION_DIRIGEANT | RN(12) > 80 000 € ET 6411 < 40 000 € |
| ABSENCE_FORCE_COMMERCIALE | 6221 = 0 ET CA > 200 000 € |
| DEPENSES_PUB_SANS_EFFET | 6231 > 5 000 € ET variation CA ≤ 0 % |
| IMMO_LOCATIF_NON_AMORTI | (213,214 > 0) ET (2813,2814 = 0) |

### Explicite — variation N/N-1 (6)
| Code | Règle |
|---|---|
| VARIATION_REMUNERATION_DIRIGEANT | 6411 : |Δ| > 15 % N/N-1 |
| FRAIS_FINANCIERS_EN_HAUSSE | 661 : +20 % N/N-1 |
| FRAIS_BANCAIRES_EN_HAUSSE | 627 : +20 % N/N-1 |
| HAUSSE_IMMOBILISATIONS | 21 : +20 % N/N-1 |
| HONORAIRES_EXCEPTIONNELS_EN_HAUSSE | 6226 : +50 % N/N-1 |
| AUGMENTATION_CAPITAL | 101 : variation > 0 N/N-1 |

> Les 6 signaux de variation et `BAISSE_MARGE_BRUTE` **n'émettent rien** si le FEC N-1 est absent (`variation_pct` → `None`) — dégradation propre, pas d'erreur.

### Explicite — divers (1 + note)
| Code | Règle |
|---|---|
| RESULTAT_BNC_ELEVE | RN(12) > 100 000 € (proxy résultat exercice) |

**Décompte moteur FEC (Phase 2a) = 45 codes** :
- Générique : 13 `seuil_eur` + 11 `presence` + 2 `absence` = **26**
- Explicite : 4 ratio + 8 composite + 6 variation + 1 divers (`RESULTAT_BNC_ELEVE`) = **19**

Exclusions notées :
- `BAISSE_MARGE_BRUTE` — dérivable des postes déjà agrégés ; rattaché à `detect_signals_from_donnees` (Phase 1), hors moteur FEC.
- `FRAIS_TRANSPORT_ELEVES` (6241,6242, « 10 000 €/an OU > 50 écritures ») — seule la borne EUR est réalisable ici, mais `seuil_valeur: null` la rend non générique et la borne « écritures » relève du comptage ; **reportée en sous-phase comptage** (non comptée dans les 45).

## Gestion des erreurs
- FEC N-1 absent → tous les signaux de variation renvoient `None` (non émis), aucun crash.
- Compte absent du FEC → `solde()` renvoie `0.0` (les `absence`/`presence` restent corrects ; un `absence` sur compte réellement absent émet légitimement le signal « = 0 »).
- Division par zéro dans `ratio_pct`/`variation_pct` → `None`, signal non émis.
- Codes émis mais absents du référentiel : impossible ici puisque tous proviennent du référentiel.

## Tests
- `tests/test_fec_features.py` : `compute_fec_features` sur un FEC synthétique fin (lignes multi-comptes, N et N-1). Vérifie les soldes par préfixe, la **convention de signe** (455 créditeur → magnitude positive ; charge classe 6 ; produit classe 7 ; actif bilan), `variation_pct`/`ratio_pct` (dont cas `None`).
- `tests/test_fec_signals.py` : pour le moteur générique, un cas déclenché + un cas juste sous le seuil par opérateur ; pour **chaque détecteur explicite**, cas déclenché + cas borne non déclenché ; cas « FEC N-1 absent → aucun signal de variation ».
- E2E (`tests/test_pipeline_e2e.py`) : un FEC synthétique riche (dirigeant sur-rémunéré, 455 créditeur, 616=0, 6712>0…) traverse `extract_financial_data → detect_signals → match_missions` et fait remonter au moins les missions attendues (`MISSION_PROTECTION_STATUT_SOCIAL`, `MISSION_PROTECTION_RC_PRO`, `MISSION_COMPTA_PACK_SERENITE`, `MISSION_PATRIMOINE_SUCCESSION`).
- Cible : suite complète verte, aucune régression sur les 151 tests Phase 1.

## Décisions actées
- Approche extraction : objet features unique `IndicateursFEC` (vs étendre `DonneesFinancieres` / requêter le df par signal).
- Détection : hybride (moteur générique JSON-driven + détecteurs explicites).
- Priorisation : largeur (couche extraction + famille A) avant profondeur métier.
- Le vocabulaire des codes reste aligné 1:1 sur `seuils_signaux.json` → matcher inchangé.
