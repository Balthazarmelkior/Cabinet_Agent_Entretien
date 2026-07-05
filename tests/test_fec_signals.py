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
