# Design — Moteur FEC Phase 2e + statut des codes restants

## Phase 2e (livrée) : `NOUVELLES_ACTIVITES`

Seul code de la famille « libellé-flux » réalisable proprement sans heuristique
textuelle. `IndicateursFEC` enrichi de `comptes_n1` (liste des comptes du FEC
N-1, via `_count_features(df_n1)`). Détecteur explicite : un compte `70x` présent
en N mais absent de N-1 = nouvelle activité. Garde : `comptes_n1` vide → `None`.

`compute_fec_features` lit le df **brut** (`_load_df`, avant anonymisation), donc
la comparaison de comptes est fiable.

**84/90 → non : 83/90 codes couverts.**

## Codes restants (7) — pourquoi non déterministes ici

| Code | Blocage | Piste |
|---|---|---|
| `IMMO_LOCATIF_DETECTE` | Distinguer immeuble locatif vs exploitation = mots-clés libellé (`locat`, `loyer`, `bail`) → faux-positifs, contraire à l'éthos déterministe | Enrichissement LLM qualitatif (déjà en place dans `detect_signals`) |
| `NON_EQUIPE_FACTURE_ELECTRONIQUE` | Preuve d'**absence** (0 écriture PDP/Chorus) impossible à établir sûrement depuis le FEC | Question manuelle en entretien |
| `FIN_EMPRUNT_PROCHE` | Besoin du **montant d'origine** de l'emprunt (< 10 % restant) — non présent dans un FEC N/N-1 | Saisie manuelle / tableau d'amortissement |
| `DIVIDENDES_RECURRENTS` | Besoin de **3 exercices** (N, N-1, N-2) — le pipeline charge au plus N-1 | 3e FEC ou historique |
| `BALANCE_AGEE_DEGRADEE` | Besoin des **dates d'échéance** clients (aging) — absentes du FEC standard | Balance âgée dédiée |
| `ABSENCE_COMPTABILITE_ANALYTIQUE` | Détection « pas d'analytique » floue (pas de marqueur FEC fiable) | Question manuelle |
| `DEPASSEMENT_SEUILS_CAC` | Besoin de l'**effectif** (50 salariés) — hors FEC | `donnees.effectif` (déjà saisi) → règle dédiée possible |

## Conclusion

Le moteur FEC déterministe plafonne à **83/90** sur données FEC (N + N-1). Les 7
restants nécessitent une donnée hors périmètre (effectif, N-2, échéances, montant
d'origine) ou relèvent d'une détection qualitative (LLM) ou d'une saisie manuelle
en entretien — à traiter hors du moteur FEC numérique.

Piste rapide hors-FEC : `DEPASSEMENT_SEUILS_CAC` est calculable depuis
`donnees.effectif` + CA + total bilan (déjà dans `DonneesFinancieres`) via une
règle dans `analysis/rules.py` (`detect_signals_from_donnees`), sans FEC.
