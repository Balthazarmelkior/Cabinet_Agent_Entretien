import json
from pathlib import Path
import pandas as pd
import pytest
from analysis.fec_features import compute_fec_features
from analysis.fec_signals import (
    detect_signals_from_fec, seuils_parametrables, GENERIC_SIGNALS,
)

ROOT = Path(__file__).resolve().parent.parent
SEUILS = json.loads((ROOT / "data" / "seuils_signaux.json").read_text(encoding="utf-8"))


def _df(rows):
    return pd.DataFrame(
        [{"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt} for c, d, cr, dt in rows]
    )


def _codes(df, df_n1=None, overrides=None):
    feat = compute_fec_features(df, df_n1)
    return {s.code for s in detect_signals_from_fec(feat, overrides or {})}


def test_seuil_eur_declenche():
    assert "REMUNERATION_DIRIGEANT_ELEVEE" in _codes(_df([("641100", 60000, 0, "20240131")]))


def test_seuil_eur_borne_non_declenchee():
    assert "REMUNERATION_DIRIGEANT_ELEVEE" not in _codes(_df([("641100", 40000, 0, "20240131")]))


def test_presence_declenche():
    assert "PENALITES_FISCALES" in _codes(_df([("671200", 500, 0, "20240131")]))


def test_absence_declenche_si_compte_absent():
    assert "ABSENCE_ASSURANCE_RC" in _codes(_df([("606000", 1000, 0, "20240101")]))


def test_absence_non_declenchee_si_compte_present():
    assert "ABSENCE_ASSURANCE_RC" not in _codes(_df([("616000", 1200, 0, "20240101")]))


def test_crediteur_produit_locatif():
    assert "REVENUS_LOCATIFS_ELEVES" in _codes(_df([("706000", 0, 35000, "20240630")]))


def test_seuils_parametrables_couvre_referentiel():
    params = seuils_parametrables(SEUILS)
    attendus = {c for c, v in SEUILS.items()
                if v.get("parametrable") and c in GENERIC_SIGNALS}
    assert attendus.issubset(set(params))
    assert params["REMUNERATION_DIRIGEANT_ELEVEE"] == 48000


def test_override_abaisse_le_seuil():
    df = _df([("641100", 30000, 0, "20240131")])
    assert "REMUNERATION_DIRIGEANT_ELEVEE" not in _codes(df)
    assert "REMUNERATION_DIRIGEANT_ELEVEE" in _codes(df, overrides={"REMUNERATION_DIRIGEANT_ELEVEE": 25000})


def test_presence_honore_override():
    # PENALITES_FISCALES parametrable : override à 1000 supprime un petit montant
    df = _df([("671200", 500, 0, "20240201")])
    assert "PENALITES_FISCALES" in _codes(df)                      # défaut 0
    assert "PENALITES_FISCALES" not in _codes(df, overrides={"PENALITES_FISCALES": 1000})


def test_mouvement_nouvel_associe_sans_nettage():
    # écriture au débit ET au crédit sur les comptes → mouvement > 0 quel que soit le solde net
    df = _df([("4561", 10000, 0, "20240101"), ("108000", 0, 5000, "20240101")])
    assert "NOUVEL_ASSOCIE" in _codes(df)


def test_construction_en_cours_via_mouvement():
    assert "CONSTRUCTION_EN_COURS" in _codes(_df([("231000", 40000, 0, "20240101")]))


def test_signaux_sont_des_models_signal():
    from models import Signal
    feat = compute_fec_features(_df([("641100", 60000, 0, "20240131")]))
    sigs = detect_signals_from_fec(feat, {})
    assert all(isinstance(s, Signal) for s in sigs)


# --- Détecteurs explicites ---

def test_ratio_charges_sociales_elevees():
    df = _df([("645000", 50000, 0, "20240101"), ("641100", 100000, 0, "20240101")])  # 50% > 45%
    assert "CHARGES_SOCIALES_ELEVEES" in _codes(df)
    df2 = _df([("645000", 40000, 0, "20240101"), ("641100", 100000, 0, "20240101")])  # 40% < 45%
    assert "CHARGES_SOCIALES_ELEVEES" not in _codes(df2)


def test_composite_compte_courant_crediteur():
    assert "COMPTE_COURANT_CREDITEUR_ELEVE" in _codes(_df([("4551", 0, 80000, "20240101")]))
    assert "COMPTE_COURANT_CREDITEUR_ELEVE" not in _codes(_df([("4551", 0, 30000, "20240101")]))


def test_composite_absence_prevoyance_madelin():
    assert "ABSENCE_PREVOYANCE_MADELIN" in _codes(_df([("641100", 40000, 0, "20240101")]))
    df = _df([("641100", 40000, 0, "20240101"), ("646700", 2000, 0, "20240101")])
    assert "ABSENCE_PREVOYANCE_MADELIN" not in _codes(df)


def test_composite_sous_remuneration_dirigeant():
    df = _df([("120000", 0, 100000, "20241231"), ("641100", 30000, 0, "20240101")])
    assert "SOUS_REMUNERATION_DIRIGEANT" in _codes(df)


def test_variation_frais_financiers_en_hausse():
    df_n = _df([("661000", 12000, 0, "20240101")])
    df_n1 = _df([("661000", 10000, 0, "20230101")])  # +20%
    assert "FRAIS_FINANCIERS_EN_HAUSSE" in _codes(df_n, df_n1)


def test_variation_absente_sans_n1():
    df_n = _df([("661000", 99999, 0, "20240101")])
    assert "FRAIS_FINANCIERS_EN_HAUSSE" not in _codes(df_n)


def test_resultat_bnc_eleve():
    assert "RESULTAT_BNC_ELEVE" in _codes(_df([("120000", 0, 120000, "20241231")]))  # RN 120k > 100k


def test_sous_remuneration_dirigeant_sans_salaire():
    # 6411 = 0 (dividendes uniquement) + RN 100k > 80k → doit déclencher
    df = _df([("120000", 0, 100000, "20241231")])
    assert "SOUS_REMUNERATION_DIRIGEANT" in _codes(df)


# --- Couverture des 12 détecteurs restants ---

def test_ratio_dividendes_eleve():
    df = _df([("457000", 0, 70000, "20240101"), ("641100", 100000, 0, "20240101")])  # 70% > 60%
    assert "RATIO_DIVIDENDES_ELEVE" in _codes(df)
    df2 = _df([("457000", 0, 50000, "20240101"), ("641100", 100000, 0, "20240101")])  # 50%
    assert "RATIO_DIVIDENDES_ELEVE" not in _codes(df2)


def test_charges_sociales_perso_elevees():
    df = _df([("646000", 40000, 0, "20240101"), ("120000", 0, 100000, "20241231")])  # 40% > 30%
    assert "CHARGES_SOCIALES_PERSO_ELEVEES" in _codes(df)
    df2 = _df([("646000", 20000, 0, "20240101"), ("120000", 0, 100000, "20241231")])  # 20%
    assert "CHARGES_SOCIALES_PERSO_ELEVEES" not in _codes(df2)


def test_amortissements_avances():
    df = _df([("281300", 0, 90000, "20240101"), ("213000", 100000, 0, "20240101")])  # 90% > 80%
    assert "AMORTISSEMENTS_AVANCES" in _codes(df)
    df2 = _df([("281300", 0, 70000, "20240101"), ("213000", 100000, 0, "20240101")])  # 70%
    assert "AMORTISSEMENTS_AVANCES" not in _codes(df2)


def test_absence_interessement():
    assert "ABSENCE_INTERESSEMENT" in _codes(_df([("120000", 0, 100000, "20241231")]))
    df = _df([("120000", 0, 100000, "20241231"), ("641400", 2000, 0, "20240101")])
    assert "ABSENCE_INTERESSEMENT" not in _codes(df)


def test_absence_provision_ifc():
    assert "ABSENCE_PROVISION_IFC" in _codes(_df([("641100", 120000, 0, "20240101")]))
    df = _df([("641100", 120000, 0, "20240101"), ("153000", 0, 5000, "20240101")])
    assert "ABSENCE_PROVISION_IFC" not in _codes(df)


def test_absence_force_commerciale():
    assert "ABSENCE_FORCE_COMMERCIALE" in _codes(_df([("706000", 0, 250000, "20240101")]))
    df = _df([("706000", 0, 250000, "20240101"), ("622100", 3000, 0, "20240101")])
    assert "ABSENCE_FORCE_COMMERCIALE" not in _codes(df)


def test_depenses_pub_sans_effet():
    df_n = _df([("623100", 6000, 0, "20240101"), ("706000", 0, 200000, "20240101")])
    df_n1 = _df([("706000", 0, 200000, "20230101")])  # CA plat
    assert "DEPENSES_PUB_SANS_EFFET" in _codes(df_n, df_n1)
    df_n1_hausse = _df([("706000", 0, 150000, "20230101")])  # CA en hausse
    assert "DEPENSES_PUB_SANS_EFFET" not in _codes(df_n, df_n1_hausse)


def test_immo_locatif_non_amorti():
    assert "IMMO_LOCATIF_NON_AMORTI" in _codes(_df([("213000", 100000, 0, "20240101")]))
    df = _df([("213000", 100000, 0, "20240101"), ("281300", 0, 1000, "20240101")])
    assert "IMMO_LOCATIF_NON_AMORTI" not in _codes(df)


def test_frais_bancaires_en_hausse():
    df_n = _df([("627000", 12000, 0, "20240101")])
    df_n1 = _df([("627000", 10000, 0, "20230101")])  # +20%
    assert "FRAIS_BANCAIRES_EN_HAUSSE" in _codes(df_n, df_n1)


def test_hausse_immobilisations():
    df_n = _df([("215000", 120000, 0, "20240101")])
    df_n1 = _df([("215000", 100000, 0, "20230101")])  # +20%
    assert "HAUSSE_IMMOBILISATIONS" in _codes(df_n, df_n1)


def test_honoraires_exceptionnels_en_hausse():
    df_n = _df([("622600", 15000, 0, "20240101")])
    df_n1 = _df([("622600", 10000, 0, "20230101")])  # +50%
    assert "HONORAIRES_EXCEPTIONNELS_EN_HAUSSE" in _codes(df_n, df_n1)


def test_variation_remuneration_dirigeant():
    df_n = _df([("641100", 60000, 0, "20240101")])
    df_n1 = _df([("641100", 50000, 0, "20230101")])  # +20% ≥ 15%
    assert "VARIATION_REMUNERATION_DIRIGEANT" in _codes(df_n, df_n1)
    df_n2 = _df([("641100", 52000, 0, "20240101")])
    df_n1_2 = _df([("641100", 50000, 0, "20230101")])  # +4% < 15%
    assert "VARIATION_REMUNERATION_DIRIGEANT" not in _codes(df_n2, df_n1_2)


def test_augmentation_capital():
    df_n = _df([("101000", 0, 50000, "20240101")])
    df_n1 = _df([("101000", 0, 30000, "20230101")])  # capital en hausse
    assert "AUGMENTATION_CAPITAL" in _codes(df_n, df_n1)
    df_n_egal = _df([("101000", 0, 30000, "20240101")])
    assert "AUGMENTATION_CAPITAL" not in _codes(df_n_egal, df_n1)


def test_cca_gravite_paliers():
    from analysis.fec_features import compute_fec_features
    from analysis.fec_signals import detect_signals_from_fec
    from models import Gravite
    def _grav(montant):
        feat = compute_fec_features(_df([("4551", 0, montant, "20240101")]))
        s = next(x for x in detect_signals_from_fec(feat, {}) if x.code == "COMPTE_COURANT_CREDITEUR_ELEVE")
        return s.gravite
    assert _grav(90000) == Gravite.FAIBLE
    assert _grav(120000) == Gravite.MOYENNE
    assert _grav(160000) == Gravite.ELEVEE


def _dfx(rows):
    return pd.DataFrame([
        {"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt,
         "CompAuxNum": aux, "JournalCode": jc}
        for c, d, cr, dt, aux, jc in rows
    ])


def _codesx(df, overrides=None):
    feat = compute_fec_features(df)
    return {s.code for s in detect_signals_from_fec(feat, overrides or {})}


def test_emprunts_multiples():
    df = _dfx([("164100", 0, 1, "20240101", "", "OD"),
               ("164200", 0, 1, "20240101", "", "OD"),
               ("164300", 0, 1, "20240101", "", "OD")])
    assert "EMPRUNTS_MULTIPLES" in _codesx(df)
    df2 = _dfx([("164100", 0, 1, "20240101", "", "OD"),
                ("164200", 0, 1, "20240101", "", "OD")])
    assert "EMPRUNTS_MULTIPLES" not in _codesx(df2)


def test_nombreux_fournisseurs_via_aux():
    rows = [("401000", 0, 1, "20240101", f"F{i:03}", "AC") for i in range(50)]
    assert "NOMBREUX_FOURNISSEURS" in _codesx(_dfx(rows))
    rows2 = [("401000", 0, 1, "20240101", f"F{i:03}", "AC") for i in range(49)]
    assert "NOMBREUX_FOURNISSEURS" not in _codesx(_dfx(rows2))


def test_complexite_comptable():
    rows = [("600000", 1, 0, "20240101", "", jc) for jc in
            ["AC", "VE", "BQ", "OD", "OI", "SA", "AN", "CA"]]
    assert "COMPLEXITE_COMPTABLE" in _codesx(_dfx(rows))


def test_acomptes_frequents():
    rows = [("419100", 100, 0, f"202401{d:02}", "", "VE") for d in range(1, 6)]
    assert "ACOMPTES_FREQUENTS" in _codesx(_dfx(rows))


def test_count_override_abaisse_seuil():
    df = _dfx([("164100", 0, 1, "20240101", "", "OD"),
               ("164200", 0, 1, "20240101", "", "OD")])
    assert "EMPRUNTS_MULTIPLES" not in _codesx(df)
    assert "EMPRUNTS_MULTIPLES" in _codesx(df, overrides={"EMPRUNTS_MULTIPLES": 2})


def test_volume_facturation_emises():
    rows = [("700000", 0, 100, "20240115", "", "VE") for _ in range(30)]
    assert "VOLUME_FACTURATION_ELEVE" in _codesx(_dfx(rows))


def test_volume_facturation_recues():
    rows = [("600000", 100, 0, "20240115", "", "AC") for _ in range(50)]
    assert "VOLUME_FACTURATION_ELEVE" in _codesx(_dfx(rows))


def test_volume_facturation_non_declenche():
    rows = [("700000", 0, 100, "20240115", "", "VE") for _ in range(10)]
    assert "VOLUME_FACTURATION_ELEVE" not in _codesx(_dfx(rows))


def test_multi_biens_immobiliers():
    df = _dfx([("213100", 100000, 0, "20240101", "", "OD"),
               ("213200", 80000, 0, "20240101", "", "OD")])   # 2 sous-comptes → 2 biens
    assert "MULTI_BIENS_IMMOBILIERS" in _codesx(df)
    df1 = _dfx([("213100", 100000, 0, "20240101", "", "OD")])  # 1 bien
    assert "MULTI_BIENS_IMMOBILIERS" not in _codesx(df1)


def test_parc_vehicules_important():
    rows = [(f"21820{i}", 20000, 0, "20240101", "", "OD") for i in range(5)]  # 5 véhicules
    assert "PARC_VEHICULES_IMPORTANT" in _codesx(_dfx(rows))
    rows4 = [(f"21820{i}", 20000, 0, "20240101", "", "OD") for i in range(4)]  # 4
    assert "PARC_VEHICULES_IMPORTANT" not in _codesx(_dfx(rows4))


def test_acomptes_frequents_borne():
    rows = [("419100", 100, 0, f"202401{d:02}", "", "VE") for d in range(1, 5)]  # 4 < 5
    assert "ACOMPTES_FREQUENTS" not in _codesx(_dfx(rows))


def test_complexite_comptable_borne():
    rows = [("600000", 1, 0, "20240101", "", jc) for jc in
            ["AC", "VE", "BQ", "OD", "OI", "SA", "AN"]]  # 7 < 8
    assert "COMPLEXITE_COMPTABLE" not in _codesx(_dfx(rows))


def test_seuils_parametrables_inclut_comptage():
    params = seuils_parametrables(SEUILS)
    for code in ["EMPRUNTS_MULTIPLES", "NOMBREUX_FOURNISSEURS", "COMPLEXITE_COMPTABLE"]:
        if SEUILS.get(code, {}).get("parametrable"):
            assert code in params
    assert "VOLUME_FACTURATION_ELEVE" not in params


def test_titre_signal_resout_les_deux_tables():
    from analysis.fec_signals import titre_signal
    assert titre_signal("REMUNERATION_DIRIGEANT_ELEVEE")
    assert titre_signal("EMPRUNTS_MULTIPLES") == "Emprunts multiples"
    assert titre_signal("CODE_INCONNU") == "CODE_INCONNU"


# ── Phase 2c : quick wins agrégats ───────────────────────────────────────────
# T1 — SEUIL_TVA_MICRO_DEPASSE (GENERIC seuil_eur)
def test_seuil_tva_micro_declenche():
    assert "SEUIL_TVA_MICRO_DEPASSE" in _codes(_df([("706000", 0, 80000, "20240630")]))


def test_seuil_tva_micro_borne():
    assert "SEUIL_TVA_MICRO_DEPASSE" not in _codes(_df([("706000", 0, 70000, "20240630")]))


def test_seuil_tva_micro_override():
    df = _df([("706000", 0, 40000, "20240630")])
    assert "SEUIL_TVA_MICRO_DEPASSE" in _codes(df, overrides={"SEUIL_TVA_MICRO_DEPASSE": 30000})


# T2 — FRAIS_TRANSPORT_ELEVES (explicit, montant OU nombre)
def test_frais_transport_via_montant():
    assert "FRAIS_TRANSPORT_ELEVES" in _codes(_df([("624100", 10000, 0, "20240131")]))


def test_frais_transport_non_declenche():
    rows = [("624100", 500, 0, f"202401{d:02}") for d in range(1, 11)]  # 5000 €, 10 écritures
    assert "FRAIS_TRANSPORT_ELEVES" not in _codes(_df(rows))


def test_frais_transport_via_nombre():
    rows = [("624200", 20, 0, f"2024{m:02}{d:02}") for m in range(1, 7) for d in range(1, 11)]
    # 60 écritures, 1200 € : déclenche par le nombre
    assert "FRAIS_TRANSPORT_ELEVES" in _codes(_df(rows))


# T3 — INVESTISSEMENT_RECENT (PARAM, delta N/N-1)
def test_investissement_recent_declenche():
    df = _df([("215000", 60000, 0, "20240601")])
    df_n1 = _df([("606000", 1000, 0, "20230101")])  # N-1 présent, pas d'immo
    assert "INVESTISSEMENT_RECENT" in _codes(df, df_n1)


def test_investissement_recent_sans_n1():
    assert "INVESTISSEMENT_RECENT" not in _codes(_df([("215000", 60000, 0, "20240601")]))


def test_investissement_recent_override():
    df = _df([("215000", 30000, 0, "20240601")])
    df_n1 = _df([("606000", 1000, 0, "20230101")])
    assert "INVESTISSEMENT_RECENT" not in _codes(df, df_n1)
    assert "INVESTISSEMENT_RECENT" in _codes(df, df_n1, overrides={"INVESTISSEMENT_RECENT": 25000})


# T4 — NOUVEL_EMPRUNT (PARAM, delta 164/C N/N-1)
def test_nouvel_emprunt_declenche():
    df = _df([("164000", 0, 60000, "20240301")])
    df_n1 = _df([("606000", 1000, 0, "20230101")])
    assert "NOUVEL_EMPRUNT" in _codes(df, df_n1)


def test_nouvel_emprunt_stable():
    df = _df([("164000", 0, 60000, "20240301")])
    df_n1 = _df([("164000", 0, 60000, "20230301")])  # même solde -> pas de nouvel emprunt
    assert "NOUVEL_EMPRUNT" not in _codes(df, df_n1)


def test_nouvel_emprunt_sans_n1():
    assert "NOUVEL_EMPRUNT" not in _codes(_df([("164000", 0, 60000, "20240301")]))


# T5 — BAISSE_MARGE_BRUTE (PARAM, marge points N/N-1)
def _df_marge(ca, achats, dt):
    return _df([("706000", 0, ca, dt), ("607000", achats, 0, dt)])


def test_baisse_marge_declenche():
    df = _df_marge(100000, 60000, "20240630")     # marge 40 %
    df_n1 = _df_marge(100000, 50000, "20230630")  # marge 50 % -> baisse 10 pts
    assert "BAISSE_MARGE_BRUTE" in _codes(df, df_n1)


def test_baisse_marge_faible():
    df = _df_marge(100000, 53000, "20240630")     # marge 47 %
    df_n1 = _df_marge(100000, 50000, "20230630")  # marge 50 % -> baisse 3 pts < 5
    assert "BAISSE_MARGE_BRUTE" not in _codes(df, df_n1)


def test_baisse_marge_sans_n1():
    assert "BAISSE_MARGE_BRUTE" not in _codes(_df_marge(100000, 60000, "20240630"))


# T6 — DELAI_FACTURATION_LONG (PARAM, DSO)
def test_delai_facturation_long_declenche():
    df = _df([("411000", 30000, 0, "20240630"), ("706000", 0, 365000, "20240630")])  # DSO 30 j
    assert "DELAI_FACTURATION_LONG" in _codes(df)


def test_delai_facturation_court():
    df = _df([("411000", 10000, 0, "20240630"), ("706000", 0, 365000, "20240630")])  # DSO 10 j
    assert "DELAI_FACTURATION_LONG" not in _codes(df)


def test_delai_facturation_ca_nul():
    df = _df([("411000", 30000, 0, "20240630")])  # pas de CA -> pas de division
    assert "DELAI_FACTURATION_LONG" not in _codes(df)


# T7 — seuils paramétrables couvrent les codes PARAM
def test_seuils_parametrables_inclut_param_signals():
    params = seuils_parametrables(SEUILS)
    for code in ["INVESTISSEMENT_RECENT", "NOUVEL_EMPRUNT", "BAISSE_MARGE_BRUTE",
                 "DELAI_FACTURATION_LONG"]:
        assert code in params


def test_titre_signal_resout_param_signals():
    from analysis.fec_signals import titre_signal
    assert titre_signal("BAISSE_MARGE_BRUTE") != "BAISSE_MARGE_BRUTE"


# ── Phase 2d : signaux mensuels ──────────────────────────────────────────────
# T2 — DECOUVERT_RECURRENT (explicit)
def test_decouvert_recurrent_declenche():
    rows = [("519000", 0, 5000, f"2024{m:02}15") for m in range(1, 4)]  # 3 mois créditeurs
    assert "DECOUVERT_RECURRENT" in _codes(_df(rows))


def test_decouvert_recurrent_deux_mois():
    rows = [("519000", 0, 5000, f"2024{m:02}15") for m in range(1, 3)]  # 2 mois < 3
    assert "DECOUVERT_RECURRENT" not in _codes(_df(rows))


def test_decouvert_recurrent_solde_resorbe():
    # crédit puis remboursement total le mois suivant -> cumulé <= 0 ensuite
    rows = [("519000", 0, 5000, "20240115"), ("519000", 5000, 0, "20240215"),
            ("519000", 5000, 0, "20240315")]
    assert "DECOUVERT_RECURRENT" not in _codes(_df(rows))  # 1 seul mois > 0


# T3 — SAISONNALITE_FORTE (PARAM)
def _ca_mensuel(montants):
    return _df([("706000", 0, m, f"2024{i+1:02}15") for i, m in enumerate(montants)])


def test_saisonnalite_forte_declenche():
    df = _ca_mensuel([100000, 10000] * 6)  # 12 mois très dispersés
    assert "SAISONNALITE_FORTE" in _codes(df)


def test_saisonnalite_ca_stable():
    df = _ca_mensuel([50000] * 12)
    assert "SAISONNALITE_FORTE" not in _codes(df)


def test_saisonnalite_trop_peu_de_mois():
    df = _ca_mensuel([100000, 0, 0, 100000])  # 4 mois < 6
    assert "SAISONNALITE_FORTE" not in _codes(df)


def test_saisonnalite_override_abaisse():
    df = _ca_mensuel([50000] * 11 + [60000])  # CV ~5% < 30
    assert "SAISONNALITE_FORTE" not in _codes(df)
    assert "SAISONNALITE_FORTE" in _codes(df, overrides={"SAISONNALITE_FORTE": 3})


def test_seuils_parametrables_inclut_saisonnalite():
    assert "SAISONNALITE_FORTE" in seuils_parametrables(SEUILS)


# ── Phase 2e : nouvelles activités (comptes 70x N vs N-1) ─────────────────────
def test_nouvelles_activites_declenche():
    df = _df([("706000", 0, 50000, "20240115"), ("707000", 0, 20000, "20240115")])
    df_n1 = _df([("706000", 0, 40000, "20230115")])  # 707 est nouveau
    assert "NOUVELLES_ACTIVITES" in _codes(df, df_n1)


def test_nouvelles_activites_aucun_nouveau():
    df = _df([("706000", 0, 50000, "20240115")])
    df_n1 = _df([("706000", 0, 40000, "20230115")])
    assert "NOUVELLES_ACTIVITES" not in _codes(df, df_n1)


def test_nouvelles_activites_sans_n1():
    df = _df([("706000", 0, 50000, "20240115"), ("707000", 0, 20000, "20240115")])
    assert "NOUVELLES_ACTIVITES" not in _codes(df)
