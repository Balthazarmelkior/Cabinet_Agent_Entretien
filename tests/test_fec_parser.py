"""
Tests du parseur FEC.

BUG CRITIQUE IDENTIFIÉ :
    Le parseur accède à df['Montant'] mais le FEC standard DGFiP contient
    des colonnes 'Debit' et 'Credit' séparées, pas une colonne 'Montant'.
    → KeyError à l'exécution.

CORRECTION REQUISE dans parsers/fec_parser.py :
    Calculer df['Montant'] = df['Debit'] - df['Credit'] (ou selon le sens
    du compte) après la lecture du CSV.
"""
import os
import tempfile
import pytest
import pandas as pd
from pathlib import Path


# ── Structure du fichier réel ─────────────────────────────────────────────────

def test_fec_file_exists(fec_path):
    """Le fichier FEC fourni existe dans input/."""
    assert Path(fec_path).exists(), f"FEC introuvable : {fec_path}"


def test_fec_has_expected_columns(fec_path):
    """Le FEC standard DGFiP contient les colonnes Debit, Credit, CompteNum, EcritureDate."""
    df = pd.read_csv(fec_path, sep="\t", encoding="latin1", nrows=1)
    for col in ("Debit", "Credit", "CompteNum", "EcritureDate"):
        assert col in df.columns, f"Colonne obligatoire absente : {col}"


def test_fec_has_no_montant_column(fec_path):
    """Confirme l'absence de la colonne 'Montant' dans ce FEC — source du bug."""
    df = pd.read_csv(fec_path, sep="\t", encoding="latin1", nrows=1)
    assert "Montant" not in df.columns, (
        "Une colonne 'Montant' a été trouvée — le bug n'existe peut-être pas pour ce fichier."
    )


def test_fec_year_is_2024_or_2025(fec_path):
    """L'exercice se clôturant le 31/08/2025, les écritures sont de 2024 ou 2025."""
    df = pd.read_csv(fec_path, sep="\t", encoding="latin1", dtype=str, nrows=500)
    assert "EcritureDate" in df.columns
    year = int(df["EcritureDate"].dropna().str[:4].mode()[0])
    assert year in (2024, 2025), f"Année inattendue : {year}"


def test_fec_compte_num_has_account_codes(fec_path):
    """CompteNum contient des codes commençant par 4 (clients), 7 (produits), etc."""
    df = pd.read_csv(fec_path, sep="\t", encoding="latin1", dtype={"CompteNum": str})
    assert df["CompteNum"].str.startswith("4").any(), "Aucun compte 4x (clients/fournisseurs)"
    assert df["CompteNum"].str.startswith("7").any(), "Aucun compte 7x (produits)"


def test_fec_row_count(fec_path):
    """Le FEC contient un nombre significatif d'écritures (>100)."""
    df = pd.read_csv(fec_path, sep="\t", encoding="latin1")
    assert len(df) > 100, f"Seulement {len(df)} lignes — fichier trop petit ?"


# ── Parsing du FEC réel (format Debit/Credit standard DGFiP) ─────────────────

def test_real_fec_parses_without_error(fec_path):
    """Le FEC standard DGFiP (Debit/Credit) se parse sans erreur après correction."""
    from parsers.fec_parser import parse_fec
    result = parse_fec(fec_path)
    assert result is not None


def test_real_fec_has_positive_ca(fec_path):
    """Le CA extrait du FEC réel est positif (comptes 70x créditeurs → Credit - Debit)."""
    from parsers.fec_parser import parse_fec
    result = parse_fec(fec_path)
    assert result.chiffre_affaires.montant_n > 0, (
        f"CA nul ou négatif : {result.chiffre_affaires.montant_n}"
    )


def test_real_fec_exercice_year(fec_path):
    """L'année d'exercice extraite est 2024 ou 2025 (clôture août 2025)."""
    from parsers.fec_parser import parse_fec
    result = parse_fec(fec_path)
    assert result.exercice_n in (2024, 2025), f"Année inattendue : {result.exercice_n}"


def test_real_fec_coherent_financial_data(fec_path):
    """Les postes du bilan actif sont positifs ou nuls."""
    from parsers.fec_parser import parse_fec
    result = parse_fec(fec_path)
    assert result.creances_clients.montant_n >= 0
    assert result.tresorerie_actif.montant_n >= 0


# ── Tests avec FEC synthétique (format Montant) ───────────────────────────────

def _write_synthetic_fec(rows: list[tuple[str, float]], exercice_date: str = "20240101") -> str:
    """Écrit un FEC synthétique avec colonne 'Montant' et retourne le chemin."""
    header = (
        "JournalCode\tJournalLib\tEcritureNum\tEcritureDate\tCompteNum\tCompteLib\t"
        "CompAuxNum\tCompAuxLib\tPieceRef\tPieceDate\tEcritureLib\tMontant\n"
    )
    lines = [header]
    for i, (compte, montant) in enumerate(rows):
        lines.append(
            f"VT\tVentes\t{i:06d}\t{exercice_date}\t{compte}\tLib\t\t\t"
            f"P{i}\t{exercice_date}\tEcr\t{str(montant).replace('.', ',')}\n"
        )
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="latin1"
    )
    f.writelines(lines)
    f.close()
    return f.name


def test_synthetic_fec_parses_ca():
    """Le parseur extrait correctement le CA depuis un FEC avec colonne Montant."""
    from parsers.fec_parser import parse_fec

    tmp = _write_synthetic_fec([
        ("700000", 500_000),   # CA
        ("600000", 200_000),   # Achats
        ("610000", 50_000),    # Charges ext
        ("640000", 80_000),    # Charges pers
        ("411000", 60_000),    # Clients
        ("401000", 30_000),    # Fournisseurs
        ("512000", 100_000),   # Banque
        ("101000", 150_000),   # Capital
        ("164000", 50_000),    # Dettes financières
        ("120000", 20_000),    # Résultat net (compte 12)
        ("211000", 120_000),   # Immobilisations
        ("310000", 20_000),    # Stocks
    ])
    try:
        result = parse_fec(tmp)
        assert result.chiffre_affaires.montant_n == 500_000.0
        assert result.achats_consommes.montant_n == 200_000.0
        assert result.charges_externes.montant_n == 50_000.0
        assert result.charges_personnel.montant_n == 80_000.0
        assert result.exercice_n == 2024
    finally:
        os.unlink(tmp)


def test_synthetic_fec_computes_ebe():
    """L'EBE est calculé comme CA - Achats - Charges ext - Charges pers."""
    from parsers.fec_parser import parse_fec

    tmp = _write_synthetic_fec([
        ("700000", 1_000_000),  # CA
        ("600000", 400_000),    # Achats
        ("610000", 150_000),    # Charges ext
        ("640000", 200_000),    # Charges pers
        ("411000", 100_000),    # Clients
        ("401000", 60_000),     # Fournisseurs
        ("512000", 200_000),    # Banque
        ("101000", 500_000),    # Capital
        ("164000", 100_000),    # Dettes fin
        ("120000", 160_000),    # Résultat net
        ("211000", 300_000),    # Immo
        ("310000", 60_000),     # Stocks
    ])
    try:
        result = parse_fec(tmp)
        ebe_attendu = 1_000_000 - 400_000 - 150_000 - 200_000  # 250 000
        assert result.ebe.montant_n == pytest.approx(ebe_attendu)
    finally:
        os.unlink(tmp)


def test_synthetic_fec_extracts_year():
    """L'année d'exercice est extraite depuis EcritureDate."""
    from parsers.fec_parser import parse_fec

    tmp = _write_synthetic_fec(
        [("700000", 100_000)],
        exercice_date="20230101"
    )
    try:
        result = parse_fec(tmp)
        assert result.exercice_n == 2023
    finally:
        os.unlink(tmp)


def test_synthetic_fec_groups_multiple_entries_same_account():
    """Plusieurs écritures sur le même compte sont sommées."""
    from parsers.fec_parser import parse_fec

    tmp = _write_synthetic_fec([
        ("700000", 300_000),   # CA ligne 1
        ("700100", 200_000),   # CA ligne 2 (sous-compte 70)
        ("411000", 50_000),
        ("401000", 20_000),
        ("512000", 80_000),
        ("101000", 200_000),
        ("600000", 100_000),
        ("610000", 30_000),
        ("640000", 50_000),
        ("164000", 40_000),
        ("120000", 10_000),
        ("211000", 50_000),
        ("310000", 5_000),
    ])
    try:
        result = parse_fec(tmp)
        assert result.chiffre_affaires.montant_n == 500_000.0  # 300k + 200k
    finally:
        os.unlink(tmp)


# ── Séparateurs et encodages alternatifs ──────────────────────────────────────

def _write_fec_variant(sep: str, encoding: str, debit_col: str = "Debit",
                       credit_col: str = "Credit") -> str:
    """FEC synthétique Debit/Credit avec séparateur et encodage paramétrables."""
    cols = ["JournalCode", "JournalLib", "EcritureNum", "EcritureDate", "CompteNum",
            "CompteLib", "CompAuxNum", "CompAuxLib", "PieceRef", "PieceDate",
            "EcritureLib", debit_col, credit_col]
    rows = [
        ("701000", "0,00", "500000,00"),
        ("411000", "500000,00", "0,00"),
    ]
    lines = [sep.join(cols) + "\n"]
    for i, (compte, debit, credit) in enumerate(rows):
        lines.append(sep.join([
            "VT", "Ventes", f"{i:06d}", "20240101", compte, "Lib", "", "",
            f"P{i}", "20240101", "Ecr", debit, credit,
        ]) + "\n")
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding=encoding
    )
    f.writelines(lines)
    f.close()
    return f.name


@pytest.mark.parametrize("sep,encoding", [
    ("|", "latin1"),
    (";", "latin1"),
    ("\t", "utf-8-sig"),
])
def test_fec_alternate_separators_and_encodings(sep, encoding):
    """La norme FEC autorise tab ou pipe ; certains exports utilisent ; ou UTF-8 BOM."""
    from parsers.fec_parser import _load_df

    tmp = _write_fec_variant(sep, encoding)
    try:
        df = _load_df(tmp)
        assert "Montant" in df.columns
        assert float(df[df["CompteNum"] == "701000"]["Montant"].iloc[0]) == 500_000.0
    finally:
        os.unlink(tmp)


def test_fec_accented_debit_credit_columns():
    """Colonnes 'Débit'/'Crédit' accentuées normalisées vers Debit/Credit."""
    from parsers.fec_parser import _load_df

    tmp = _write_fec_variant("\t", "utf-8", debit_col="Débit", credit_col="Crédit")
    try:
        df = _load_df(tmp)
        assert float(df[df["CompteNum"] == "701000"]["Montant"].iloc[0]) == 500_000.0
    finally:
        os.unlink(tmp)


def test_fec_invalid_file_raises_clear_error():
    """Fichier sans colonnes FEC → ValueError explicite, pas KeyError."""
    from parsers.fec_parser import _load_df

    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="latin1")
    f.write("foo;bar\n1;2\n")
    f.close()
    try:
        with pytest.raises(ValueError, match="colonnes attendues absentes"):
            _load_df(f.name)
    finally:
        os.unlink(f.name)
