# parsers/anonymizer.py
"""Anonymisation des données FEC et textes PDF avant traitement par les agents IA."""
import re
import pandas as pd

# Préfixes des comptes tiers (clients, fournisseurs, personnel, associés)
PREFIXES_TIERS = ("401", "411", "421", "455")

# Patterns d'identification dans les textes PDF
_PDF_PATTERNS = [
    # SIREN (9 chiffres) ou SIRET (14 chiffres), avec ou sans espaces/tirets
    (r"\b\d{3}[\s\-]?\d{3}[\s\-]?\d{3}(?:[\s\-]?\d{5})?\b", "[SIREN]"),
    # Formes juridiques suivies d'un nom de société
    (
        r"\b(SARL|SAS|SASU|SA|EURL|SCI|SNC|EIRL|GIE|SCOP)\s+"
        r"[A-ZÀÂÉÈÊËÎÏÔÙÛÜ][A-ZÀ-Ÿa-zà-ÿ0-9\s&'\-\.]{2,50}",
        "[SOCIÉTÉ]",
    ),
    # Adresses : numéro + type de voie + nom + code postal
    (
        r"\b\d{1,4}[,\s]+(rue|avenue|boulevard|allée|impasse|chemin|route|place|voie)"
        r"\b[A-Za-zÀ-ÿ\s\-\.,0-9]{5,60}\b\d{5}\b",
        "[ADRESSE]",
        re.IGNORECASE,
    ),
]


def anonymize_fec_df(df: pd.DataFrame) -> pd.DataFrame:
    """Masque les colonnes identifiantes d'un DataFrame FEC.

    Colonnes traitées :
    - EcritureLib → remplacé par des astérisques (longueur préservée)
    - CompteNum   → tronqué à xxx000 pour les comptes tiers (401x, 411x, 421x, 455x)
    - CompAuxNum  → synchronisé avec CompteNum modifié
    - CompteLib   → remplacé par *** pour les comptes tiers
    - CompAuxLib  → remplacé par *** pour les comptes tiers
    """
    df = df.copy()

    if "EcritureLib" in df.columns:
        df["EcritureLib"] = df["EcritureLib"].apply(
            lambda x: "*" * len(str(x)) if pd.notna(x) else x
        )

    if "CompteNum" not in df.columns:
        return df

    mask_tiers = df["CompteNum"].str.startswith(PREFIXES_TIERS, na=False)

    df.loc[mask_tiers, "CompteNum"] = (
        df.loc[mask_tiers, "CompteNum"].str[:3] + "000"
    )

    if "CompAuxNum" in df.columns:
        df.loc[mask_tiers, "CompAuxNum"] = df.loc[mask_tiers, "CompteNum"]

    for col in ("CompteLib", "CompAuxLib"):
        if col in df.columns:
            df.loc[mask_tiers, col] = "***"

    return df


def anonymize_pdf_text(text: str) -> str:
    """Masque les informations identifiantes dans le texte extrait d'un PDF."""
    for args in _PDF_PATTERNS:
        if len(args) == 3:
            pattern, replacement, flags = args
            text = re.sub(pattern, replacement, text, flags=flags)
        else:
            pattern, replacement = args
            text = re.sub(pattern, replacement, text)
    return text
