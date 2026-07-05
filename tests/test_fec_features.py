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
