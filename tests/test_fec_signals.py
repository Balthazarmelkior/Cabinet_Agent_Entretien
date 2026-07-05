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


def test_signaux_sont_des_models_signal():
    from models import Signal
    feat = compute_fec_features(_df([("641100", 60000, 0, "20240131")]))
    sigs = detect_signals_from_fec(feat, {})
    assert all(isinstance(s, Signal) for s in sigs)
