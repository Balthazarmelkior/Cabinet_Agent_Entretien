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
