import pandas as pd
import tempfile
import os
from parsers.fec_parser import extraire_tresorerie_mensuelle, extraire_ca_mensuel
from models import SoldeMensuel


def _write_fec(rows: list[dict]) -> str:
    """Crée un fichier FEC temporaire avec les colonnes minimales."""
    df = pd.DataFrame(rows)
    path = os.path.join(tempfile.gettempdir(), "test_fec.txt")
    df.to_csv(path, sep="\t", index=False, encoding="latin1")
    return path


def test_tresorerie_mensuelle_basic():
    rows = [
        {"CompteNum": "5120000", "EcritureDate": "20240115", "Debit": "10000", "Credit": "0"},
        {"CompteNum": "5120000", "EcritureDate": "20240215", "Debit": "5000", "Credit": "2000"},
        {"CompteNum": "5120000", "EcritureDate": "20240315", "Debit": "0", "Credit": "8000"},
        {"CompteNum": "6010000", "EcritureDate": "20240115", "Debit": "3000", "Credit": "0"},
    ]
    path = _write_fec(rows)
    result = extraire_tresorerie_mensuelle(path)

    assert len(result) == 3
    assert all(isinstance(s, SoldeMensuel) for s in result)
    assert result[0].mois == "2024-01"
    assert result[0].solde == 10000.0
    assert result[1].mois == "2024-02"
    assert result[1].solde == 13000.0  # 10000 + 5000 - 2000
    assert result[2].mois == "2024-03"
    assert result[2].solde == 5000.0   # 13000 - 8000


def test_tresorerie_mensuelle_no_treasury_accounts():
    rows = [
        {"CompteNum": "6010000", "EcritureDate": "20240115", "Debit": "3000", "Credit": "0"},
    ]
    path = _write_fec(rows)
    result = extraire_tresorerie_mensuelle(path)
    assert result == []


def test_tresorerie_mensuelle_multiple_accounts():
    rows = [
        {"CompteNum": "5120000", "EcritureDate": "20240115", "Debit": "10000", "Credit": "0"},
        {"CompteNum": "5300000", "EcritureDate": "20240115", "Debit": "500", "Credit": "0"},
    ]
    path = _write_fec(rows)
    result = extraire_tresorerie_mensuelle(path)

    assert len(result) == 1
    assert result[0].solde == 10500.0  # 10000 + 500


def test_ca_mensuel_cumule():
    rows = [
        {"CompteNum": "7010000", "EcritureDate": "20240115", "Debit": "0", "Credit": "50000"},
        {"CompteNum": "7010000", "EcritureDate": "20240215", "Debit": "0", "Credit": "60000"},
        {"CompteNum": "7010000", "EcritureDate": "20240315", "Debit": "0", "Credit": "45000"},
        {"CompteNum": "6010000", "EcritureDate": "20240115", "Debit": "30000", "Credit": "0"},
    ]
    path = _write_fec(rows)
    result = extraire_ca_mensuel(path)

    assert len(result) == 3
    assert result[0].mois == "2024-01"
    assert result[0].solde == 50000.0
    assert result[1].mois == "2024-02"
    assert result[1].solde == 110000.0  # 50000 + 60000
    assert result[2].mois == "2024-03"
    assert result[2].solde == 155000.0  # 110000 + 45000


def test_ca_mensuel_no_revenue():
    rows = [
        {"CompteNum": "6010000", "EcritureDate": "20240115", "Debit": "3000", "Credit": "0"},
    ]
    path = _write_fec(rows)
    result = extraire_ca_mensuel(path)
    assert result == []
