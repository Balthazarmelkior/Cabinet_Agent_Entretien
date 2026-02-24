"""
Fixtures partagées pour tous les tests.
"""
import os
import sys
from pathlib import Path

# Ajoute la racine du projet au PYTHONPATH
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Clé API factice pour éviter les erreurs de validation OpenAI dans les tests mockés
os.environ.setdefault("OPENAI_API_KEY", "sk-test-fake-key-for-unit-tests")

import pytest
from models import DonneesFinancieres, PosteComptable

FEC_PATH = str(ROOT / "input" / "443021456FEC20250831.txt")
CATALOGUE_PATH = str(ROOT / "data" / "catalogue_missions.json")


@pytest.fixture
def fec_path():
    return FEC_PATH


@pytest.fixture
def catalogue_path():
    return CATALOGUE_PATH


@pytest.fixture
def donnees_saine():
    """Entreprise en bonne santé : EBE 25%, liquidité élevée, faible dette."""
    return DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=1_000_000),
        achats_consommes=PosteComptable(libelle="Achats", montant_n=400_000),
        charges_externes=PosteComptable(libelle="Charges ext", montant_n=150_000),
        charges_personnel=PosteComptable(libelle="Charges pers", montant_n=200_000),
        ebe=PosteComptable(libelle="EBE", montant_n=250_000),       # 25%
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=220_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=160_000),  # 16%
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=300_000),
        stocks=PosteComptable(libelle="Stocks", montant_n=60_000),
        creances_clients=PosteComptable(libelle="Clients", montant_n=100_000),   # 36.5j
        tresorerie_actif=PosteComptable(libelle="Tréso", montant_n=200_000),
        capitaux_propres=PosteComptable(libelle="CP", montant_n=500_000),        # 75.8%
        dettes_financieres=PosteComptable(libelle="Dettes fin", montant_n=100_000),  # 0.4 ans
        dettes_fournisseurs=PosteComptable(libelle="Dettes fourn", montant_n=60_000),
    )


@pytest.fixture
def donnees_risquee():
    """Entreprise en difficulté : EBE négatif, liquidité critique, dette élevée."""
    return DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=500_000),
        achats_consommes=PosteComptable(libelle="Achats", montant_n=300_000),
        charges_externes=PosteComptable(libelle="Charges ext", montant_n=100_000),
        charges_personnel=PosteComptable(libelle="Charges pers", montant_n=120_000),
        ebe=PosteComptable(libelle="EBE", montant_n=-20_000),        # -4% → EBE_NEGATIF
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=-30_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=-25_000),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=200_000),
        stocks=PosteComptable(libelle="Stocks", montant_n=5_000),
        creances_clients=PosteComptable(libelle="Clients", montant_n=50_000),    # 36.5j
        tresorerie_actif=PosteComptable(libelle="Tréso", montant_n=5_000),
        # actif circ = 60k < dettes_fourn = 100k → LIQUIDITE_CRITIQUE
        capitaux_propres=PosteComptable(libelle="CP", montant_n=30_000),         # 9.1% → AUTONOMIE_FAIBLE
        dettes_financieres=PosteComptable(libelle="Dettes fin", montant_n=200_000),
        dettes_fournisseurs=PosteComptable(libelle="Dettes fourn", montant_n=100_000),
    )
