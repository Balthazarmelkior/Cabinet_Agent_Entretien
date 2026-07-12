"""Tests de l'anonymisation FEC."""
import numpy as np
import pandas as pd

from parsers.anonymizer import anonymize_fec_df


def _df_base() -> pd.DataFrame:
    return pd.DataFrame({
        "CompteNum": pd.array(["411000", "401500", "512000"], dtype="string"),
        "CompteLib": ["Client Dupont", "Fourn Martin", "Banque"],
        "EcritureLib": ["Facture Dupont", "Achat Martin", "Virement"],
    })


def test_comptes_tiers_tronques():
    df = anonymize_fec_df(_df_base())
    assert list(df["CompteNum"]) == ["411000", "401000", "512000"]
    assert list(df["CompteLib"]) == ["***", "***", "Banque"]


def test_ecriture_lib_masquee_longueur_preservee():
    df = anonymize_fec_df(_df_base())
    assert df["EcritureLib"].iloc[0] == "*" * len("Facture Dupont")


def test_compauxnum_vide_float64_ne_plante_pas():
    """Régression : CompAuxNum entièrement vide → inférée float64 par pandas.
    L'assignation de CompteNum (string) dedans levait TypeError."""
    df = _df_base()
    df["CompAuxNum"] = np.nan  # float64, comme un FEC sans comptes auxiliaires
    df["CompAuxLib"] = np.nan

    result = anonymize_fec_df(df)

    assert result["CompAuxNum"].iloc[0] == "411000"
    assert pd.isna(result["CompAuxNum"].iloc[2])
    assert result["CompAuxLib"].iloc[0] == "***"
