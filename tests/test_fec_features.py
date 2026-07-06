import pandas as pd
import pytest
from analysis.fec_features import IndicateursFEC, compute_fec_features


def _df(rows):
    # rows: list de (CompteNum, Debit, Credit, EcritureDate)
    return pd.DataFrame(
        [{"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt} for c, d, cr, dt in rows]
    )


def test_solde_debiteur_charge():
    f = compute_fec_features(_df([("641100", 60000, 0, "20240131")]))
    assert f.solde(["6411"], "D") == 60000
    assert f.solde(["6411"], "C") == -60000


def test_solde_crediteur_compte_courant_associe():
    f = compute_fec_features(_df([("4551", 0, 80000, "20240131")]))
    assert f.solde(["455"], "C") == 80000
    assert f.solde(["455"], "D") == -80000


def test_solde_crediteur_produit():
    f = compute_fec_features(_df([("706000", 0, 30000, "20240630")]))
    assert f.solde(["706", "708"], "C") == 30000


def test_prefixes_agregation():
    f = compute_fec_features(_df([
        ("213100", 100000, 0, "20240101"),
        ("214000", 50000, 0, "20240101"),
    ]))
    assert f.solde(["213", "214"], "D") == 150000
    assert f.solde(["213"], "D") == 100000


def test_absence_mouvement():
    f = compute_fec_features(_df([("606000", 1000, 0, "20240101")]))
    assert f.mouvement(["616"]) == 0
    assert f.mouvement(["606"]) == 1000


def test_variation_pct_et_none_sans_n1():
    df_n = _df([("661000", 12000, 0, "20240101")])
    df_n1 = _df([("661000", 10000, 0, "20230101")])
    f = compute_fec_features(df_n, df_n1)
    assert f.variation_pct(["661"], "D") == 20.0
    f_sans = compute_fec_features(df_n)
    assert f_sans.variation_pct(["661"], "D") is None


def test_ratio_pct_et_none_si_denominateur_nul():
    f = compute_fec_features(_df([
        ("645000", 45000, 0, "20240101"),
        ("641100", 100000, 0, "20240101"),
    ]))
    assert f.ratio_pct(["645"], ["641"], "D", "D") == 45.0
    f0 = compute_fec_features(_df([("645000", 45000, 0, "20240101")]))
    assert f0.ratio_pct(["645"], ["641"], "D", "D") is None


def test_ca_memorise():
    f = compute_fec_features(_df([("706000", 0, 200000, "20240101")]))
    assert f.ca_n == 200000


def test_sens_invalide_leve():
    f = compute_fec_features(_df([("641100", 60000, 0, "20240131")]))
    with pytest.raises(ValueError):
        f.solde(["6411"], "X")


def test_montant_sens_format():
    df = pd.DataFrame([
        {"CompteNum": "706000", "Montant": 30000, "Sens": "C", "EcritureDate": "20240630"},
        {"CompteNum": "641100", "Montant": 60000, "Sens": "D", "EcritureDate": "20240131"},
    ])
    f = compute_fec_features(df)
    assert f.solde(["706"], "C") == 30000
    assert f.solde(["6411"], "D") == 60000


def test_colonnes_manquantes_leve():
    df = pd.DataFrame([{"CompteNum": "706000", "EcritureDate": "20240630"}])
    with pytest.raises(ValueError, match="FEC illisible"):
        compute_fec_features(df)


def _dfx(rows):
    # rows: (CompteNum, Debit, Credit, EcritureDate, CompAuxNum, JournalCode)
    return pd.DataFrame([
        {"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt,
         "CompAuxNum": aux, "JournalCode": jc}
        for c, d, cr, dt, aux, jc in rows
    ])


def test_nb_comptes_sous_comptes_distincts():
    f = compute_fec_features(_dfx([
        ("164100", 0, 10000, "20240101", "", "OD"),
        ("164200", 0, 20000, "20240101", "", "OD"),
        ("164200", 0, 5000, "20240201", "", "OD"),
        ("512000", 100, 0, "20240101", "", "BQ"),
    ]))
    assert f.nb_comptes(["164"]) == 2
    assert f.nb_comptes(["213"]) == 0


def test_nb_tiers_via_compauxnum():
    f = compute_fec_features(_dfx([
        ("401000", 0, 100, "20240101", "F001", "AC"),
        ("401000", 0, 200, "20240102", "F002", "AC"),
        ("401000", 0, 300, "20240103", "F003", "AC"),
        ("401000", 0, 300, "20240104", "F003", "AC"),
    ]))
    assert f.nb_tiers(["401"]) == 3


def test_nb_tiers_repli_sous_compte_si_aux_vide():
    f = compute_fec_features(_dfx([
        ("401100", 0, 100, "20240101", "", "AC"),
        ("401200", 0, 200, "20240102", "", "AC"),
    ]))
    assert f.nb_tiers(["401"]) == 2


def test_nb_ecritures_et_journaux_et_mois():
    f = compute_fec_features(_dfx([
        ("419100", 500, 0, "20240115", "", "VE"),
        ("419100", 300, 0, "20240210", "", "VE"),
        ("700000", 0, 1000, "20240115", "", "VE"),
        ("600000", 800, 0, "20240310", "", "AC"),
    ]))
    assert f.nb_ecritures(["4191"]) == 2
    assert f.nb_journaux() == 2
    assert f.nb_mois() == 3


def test_comptage_colonnes_absentes_renvoie_zero():
    f = compute_fec_features(pd.DataFrame([
        {"CompteNum": "401100", "Debit": 0, "Credit": 100, "EcritureDate": "20240101"},
    ]))
    assert f.nb_tiers(["401"]) == 1
    assert f.nb_journaux() == 0
    assert f.nb_mois() == 1


def test_nb_mois_minimum_un_sur_df_vide_de_dates():
    f = compute_fec_features(pd.DataFrame([
        {"CompteNum": "700000", "Debit": 0, "Credit": 1000, "EcritureDate": ""},
    ]))
    assert f.nb_mois() == 1


def test_nb_mois_ignore_dates_nan():
    import numpy as np
    df = pd.DataFrame([
        {"CompteNum": "700000", "Debit": 0, "Credit": 1000, "EcritureDate": "20240115"},
        {"CompteNum": "700000", "Debit": 0, "Credit": 500,  "EcritureDate": np.nan},
    ])
    f = compute_fec_features(df)
    assert f.nb_mois() == 1   # le NaN ne crée pas de faux mois


def test_nb_ecritures_somme_plusieurs_sous_comptes():
    f = compute_fec_features(_dfx([
        ("607100", 1, 0, "20240101", "", "AC"),
        ("607200", 1, 0, "20240102", "", "AC"),
        ("607200", 1, 0, "20240103", "", "AC"),
    ]))
    assert f.nb_ecritures(["607"]) == 3   # somme sur 2 sous-comptes


def test_nb_tiers_aux_partage_entre_sous_comptes():
    # même CompAuxNum sur 2 sous-comptes différents → 1 tier
    f = compute_fec_features(_dfx([
        ("401100", 0, 100, "20240101", "F001", "AC"),
        ("401200", 0, 200, "20240102", "F001", "AC"),
    ]))
    assert f.nb_tiers(["401"]) == 1
