"""
Tests du calcul des ratios financiers (analysis/ratios.py).
"""
import pytest
from analysis.ratios import compute_ratios, ZeroRevenueError
from models import DonneesFinancieres, PosteComptable


# ── Entreprise saine ──────────────────────────────────────────────────────────

def test_taux_marge_brute(donnees_saine):
    """Marge brute = (CA - Achats) / CA = (1M - 400k) / 1M = 60%."""
    r = compute_ratios(donnees_saine)
    assert r.taux_marge_brute == pytest.approx(60.0)


def test_taux_ebe(donnees_saine):
    """EBE% = 250k / 1M = 25%."""
    r = compute_ratios(donnees_saine)
    assert r.taux_ebe == pytest.approx(25.0)


def test_taux_resultat_net(donnees_saine):
    """Résultat net% = 160k / 1M = 16%."""
    r = compute_ratios(donnees_saine)
    assert r.taux_resultat_net == pytest.approx(16.0)


def test_rentabilite_capitaux(donnees_saine):
    """ROE = 160k / 500k = 32%."""
    r = compute_ratios(donnees_saine)
    assert r.rentabilite_capitaux == pytest.approx(32.0)


def test_couverture_dettes(donnees_saine):
    """Dettes fin / EBE = 100k / 250k = 0.4 ans."""
    r = compute_ratios(donnees_saine)
    assert r.couverture_dettes == pytest.approx(0.4)


def test_ratio_liquidite_generale(donnees_saine):
    """Actif circulant (60k+100k+200k) / Dettes CT (60k) = 6.0."""
    r = compute_ratios(donnees_saine)
    assert r.ratio_liquidite_generale == pytest.approx(6.0)


def test_autonomie_financiere(donnees_saine):
    """CP (500k) / Total passif (500k+100k+60k) * 100 ≈ 75.8%."""
    r = compute_ratios(donnees_saine)
    assert r.autonomie_financiere == pytest.approx(75.8, abs=0.1)


def test_delai_clients_jours(donnees_saine):
    """Clients (100k) / CA (1M) * 365 = 36.5j → arrondi à 36 ou 37."""
    r = compute_ratios(donnees_saine)
    assert r.delai_clients_jours == pytest.approx(36.5, abs=1.0)


def test_delai_fournisseurs_jours(donnees_saine):
    """Fourn (60k) / Achats (400k) * 365 = 54.75j → arrondi à 55."""
    r = compute_ratios(donnees_saine)
    assert r.delai_fournisseurs_jours == pytest.approx(54.75, abs=1.0)


def test_rotation_stocks_jours(donnees_saine):
    """Stocks (60k) / Achats (400k) * 365 = 54.75j → arrondi à 55."""
    r = compute_ratios(donnees_saine)
    assert r.rotation_stocks_jours == pytest.approx(54.75, abs=1.0)


# ── Cas limites ───────────────────────────────────────────────────────────────

def test_zero_revenue_raises_error():
    """Un CA nul doit lever ZeroRevenueError — pas un ZeroDivisionError silencieux."""
    d = DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=0),
        achats_consommes=PosteComptable(libelle="Achats", montant_n=0),
        charges_externes=PosteComptable(libelle="Charges ext", montant_n=0),
        charges_personnel=PosteComptable(libelle="Charges pers", montant_n=0),
        ebe=PosteComptable(libelle="EBE", montant_n=0),
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=0),
        resultat_net=PosteComptable(libelle="RN", montant_n=0),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=0),
        stocks=PosteComptable(libelle="Stocks", montant_n=0),
        creances_clients=PosteComptable(libelle="Clients", montant_n=0),
        tresorerie_actif=PosteComptable(libelle="Tréso", montant_n=0),
        capitaux_propres=PosteComptable(libelle="CP", montant_n=0),
        dettes_financieres=PosteComptable(libelle="Dettes fin", montant_n=0),
        dettes_fournisseurs=PosteComptable(libelle="Dettes fourn", montant_n=0),
    )
    with pytest.raises(ZeroRevenueError):
        compute_ratios(d)


def test_couverture_dettes_99_when_ebe_negative(donnees_risquee):
    """Quand EBE ≤ 0, couverture_dettes vaut 99.0 pour éviter division par zéro."""
    r = compute_ratios(donnees_risquee)
    assert r.couverture_dettes == 99.0


def test_rentabilite_capitaux_none_when_zero_equity():
    """Quand CP = 0, rentabilite_capitaux est None (pas de ZeroDivisionError)."""
    d = DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=500_000),
        achats_consommes=PosteComptable(libelle="Achats", montant_n=200_000),
        charges_externes=PosteComptable(libelle="Charges ext", montant_n=50_000),
        charges_personnel=PosteComptable(libelle="Charges pers", montant_n=80_000),
        ebe=PosteComptable(libelle="EBE", montant_n=170_000),
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=150_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=100_000),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=200_000),
        stocks=PosteComptable(libelle="Stocks", montant_n=30_000),
        creances_clients=PosteComptable(libelle="Clients", montant_n=50_000),
        tresorerie_actif=PosteComptable(libelle="Tréso", montant_n=100_000),
        capitaux_propres=PosteComptable(libelle="CP", montant_n=0),
        dettes_financieres=PosteComptable(libelle="Dettes fin", montant_n=100_000),
        dettes_fournisseurs=PosteComptable(libelle="Dettes fourn", montant_n=40_000),
    )
    r = compute_ratios(d)
    assert r.rentabilite_capitaux is None


def test_variation_pct_propagated_from_model():
    """Les variations N/N-1 déclarées dans le modèle sont exposées dans Ratios."""
    d = DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=1_000_000, variation_pct=15.0),
        achats_consommes=PosteComptable(libelle="Achats", montant_n=400_000),
        charges_externes=PosteComptable(libelle="Charges ext", montant_n=150_000),
        charges_personnel=PosteComptable(libelle="Charges pers", montant_n=200_000),
        ebe=PosteComptable(libelle="EBE", montant_n=250_000),
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=220_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=160_000, variation_pct=-5.0),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=300_000),
        stocks=PosteComptable(libelle="Stocks", montant_n=60_000),
        creances_clients=PosteComptable(libelle="Clients", montant_n=100_000),
        tresorerie_actif=PosteComptable(libelle="Tréso", montant_n=200_000),
        capitaux_propres=PosteComptable(libelle="CP", montant_n=500_000),
        dettes_financieres=PosteComptable(libelle="Dettes fin", montant_n=100_000),
        dettes_fournisseurs=PosteComptable(libelle="Dettes fourn", montant_n=60_000),
    )
    r = compute_ratios(d)
    assert r.variation_ca_pct == 15.0
    assert r.variation_resultat_pct == -5.0


def test_variation_pct_none_when_not_set(donnees_saine):
    """Quand variation_pct n'est pas renseignée, les ratios de variation sont None."""
    r = compute_ratios(donnees_saine)
    assert r.variation_ca_pct is None
    assert r.variation_resultat_pct is None


def test_delai_fournisseurs_zero_when_no_purchases():
    """Si achats = 0, delai_fournisseurs_jours = 0 (pas de ZeroDivisionError)."""
    d = DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=500_000),
        achats_consommes=PosteComptable(libelle="Achats", montant_n=0),
        charges_externes=PosteComptable(libelle="Charges ext", montant_n=100_000),
        charges_personnel=PosteComptable(libelle="Charges pers", montant_n=150_000),
        ebe=PosteComptable(libelle="EBE", montant_n=250_000),
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=230_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=180_000),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=100_000),
        stocks=PosteComptable(libelle="Stocks", montant_n=0),
        creances_clients=PosteComptable(libelle="Clients", montant_n=50_000),
        tresorerie_actif=PosteComptable(libelle="Tréso", montant_n=200_000),
        capitaux_propres=PosteComptable(libelle="CP", montant_n=400_000),
        dettes_financieres=PosteComptable(libelle="Dettes fin", montant_n=50_000),
        dettes_fournisseurs=PosteComptable(libelle="Dettes fourn", montant_n=20_000),
    )
    r = compute_ratios(d)
    assert r.delai_fournisseurs_jours == 0.0
    assert r.rotation_stocks_jours == 0.0


# ── Trésorerie (entreprise saine) ────────────────────────────────────────────
# donnees_saine: clients=100k, stocks=60k, fourn=60k, CP=500k, dettes_fin=100k, immo=300k, CA=1M

def test_bfr_saine(donnees_saine):
    """BFR = clients(100k) + stocks(60k) - fournisseurs(60k) = 100k."""
    r = compute_ratios(donnees_saine)
    assert r.bfr == pytest.approx(100_000)


def test_frng_saine(donnees_saine):
    """FRNG = (CP 500k + dettes_fin 100k) - immo 300k = 300k."""
    r = compute_ratios(donnees_saine)
    assert r.frng == pytest.approx(300_000)


def test_tresorerie_nette_saine(donnees_saine):
    """Treso nette = FRNG(300k) - BFR(100k) = 200k."""
    r = compute_ratios(donnees_saine)
    assert r.tresorerie_nette == pytest.approx(200_000)


def test_cycle_conversion_jours_saine(donnees_saine):
    """Cycle = clients(36.5j) + stocks(54.75j) - fourn(54.75j) = 36.5j."""
    r = compute_ratios(donnees_saine)
    assert r.cycle_conversion_jours == pytest.approx(36.5, abs=1.0)


def test_tresorerie_nette_jours_ca_saine(donnees_saine):
    """Treso nette jours CA = 200k / 1M * 365 = 73j."""
    r = compute_ratios(donnees_saine)
    assert r.tresorerie_nette_jours_ca == pytest.approx(73.0, abs=1.0)


# ── Trésorerie (entreprise risquée) ─────────────────────────────────────────
# donnees_risquee: clients=50k, stocks=5k, fourn=100k, CP=30k, dettes_fin=200k, immo=200k, CA=500k

def test_bfr_risquee(donnees_risquee):
    """BFR = clients(50k) + stocks(5k) - fournisseurs(100k) = -45k."""
    r = compute_ratios(donnees_risquee)
    assert r.bfr == pytest.approx(-45_000)


def test_frng_risquee(donnees_risquee):
    """FRNG = (CP 30k + dettes_fin 200k) - immo 200k = 30k."""
    r = compute_ratios(donnees_risquee)
    assert r.frng == pytest.approx(30_000)


def test_tresorerie_nette_risquee(donnees_risquee):
    """Treso nette = FRNG(30k) - BFR(-45k) = 75k."""
    r = compute_ratios(donnees_risquee)
    assert r.tresorerie_nette == pytest.approx(75_000)


def test_tresorerie_nette_jours_ca_risquee(donnees_risquee):
    """Treso nette jours CA = 75k / 500k * 365 = 54.75j."""
    r = compute_ratios(donnees_risquee)
    assert r.tresorerie_nette_jours_ca == pytest.approx(54.75, abs=1.0)


# ── N-1 variants ────────────────────────────────────────────────────────────

def test_bfr_n1_none_when_no_n1(donnees_saine):
    """BFR N-1 is None when montant_n1 not set."""
    r = compute_ratios(donnees_saine)
    assert r.bfr_n1 is None
    assert r.frng_n1 is None
    assert r.tresorerie_nette_n1 is None
