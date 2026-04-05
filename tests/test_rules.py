"""
Tests des règles de détection de signaux (analysis/rules.py).
Un test par règle, en isolant chaque condition.
"""
import pytest
from analysis.ratios import Ratios
from analysis.rules import detect_signals_from_rules
from models import TypeSignal, Gravite


def _ratios(**overrides) -> Ratios:
    """Ratios sains par défaut, remplaçables pour tester chaque règle isolément."""
    defaults = dict(
        taux_marge_brute=60.0,
        taux_ebe=20.0,
        taux_resultat_net=8.0,
        rentabilite_capitaux=15.0,
        ratio_liquidite_generale=2.5,
        couverture_dettes=2.0,
        autonomie_financiere=50.0,
        delai_clients_jours=35.0,
        delai_fournisseurs_jours=45.0,
        rotation_stocks_jours=30.0,
        variation_ca_pct=None,
        variation_resultat_pct=None,
        bfr=100_000.0,
        frng=300_000.0,
        tresorerie_nette=200_000.0,
        cycle_conversion_jours=20.0,
        tresorerie_nette_jours_ca=73.0,
        bfr_n1=None,
        frng_n1=None,
        tresorerie_nette_n1=None,
    )
    defaults.update(overrides)
    return Ratios(**defaults)


def _codes(ratios: Ratios) -> list[str]:
    return [s.code for s in detect_signals_from_rules(ratios)]


# ── Risques ───────────────────────────────────────────────────────────────────

class TestEbeSignals:
    def test_ebe_negatif_triggered(self):
        signals = detect_signals_from_rules(_ratios(taux_ebe=-1.0))
        codes = _codes(_ratios(taux_ebe=-1.0))
        assert "EBE_NEGATIF" in codes

    def test_ebe_negatif_is_gravite_elevee(self):
        signals = detect_signals_from_rules(_ratios(taux_ebe=-5.0))
        sig = next(s for s in signals if s.code == "EBE_NEGATIF")
        assert sig.gravite == Gravite.ELEVEE
        assert sig.type == TypeSignal.RISQUE

    def test_ebe_faible_triggered(self):
        assert "EBE_FAIBLE" in _codes(_ratios(taux_ebe=3.0))

    def test_ebe_faible_not_triggered_at_5pct(self):
        """Seuil inclusif : EBE = 5% ne déclenche pas EBE_FAIBLE."""
        codes = _codes(_ratios(taux_ebe=5.0))
        assert "EBE_FAIBLE" not in codes
        assert "EBE_NEGATIF" not in codes

    def test_ebe_negatif_excludes_ebe_faible(self):
        """Quand EBE < 0, seul EBE_NEGATIF est généré (pas EBE_FAIBLE)."""
        codes = _codes(_ratios(taux_ebe=-3.0))
        assert "EBE_NEGATIF" in codes
        assert "EBE_FAIBLE" not in codes


class TestEndettementSignal:
    def test_endettement_excessif_triggered(self):
        assert "ENDETTEMENT_EXCESSIF" in _codes(_ratios(couverture_dettes=6.0))

    def test_endettement_excessif_gravite_elevee(self):
        signals = detect_signals_from_rules(_ratios(couverture_dettes=10.0))
        sig = next(s for s in signals if s.code == "ENDETTEMENT_EXCESSIF")
        assert sig.gravite == Gravite.ELEVEE

    def test_endettement_not_triggered_below_5(self):
        assert "ENDETTEMENT_EXCESSIF" not in _codes(_ratios(couverture_dettes=4.9))


class TestLiquiditeSignals:
    def test_liquidite_critique_triggered(self):
        assert "LIQUIDITE_CRITIQUE" in _codes(_ratios(ratio_liquidite_generale=0.8))

    def test_liquidite_critique_excludes_tendue(self):
        codes = _codes(_ratios(ratio_liquidite_generale=0.8))
        assert "LIQUIDITE_CRITIQUE" in codes
        assert "LIQUIDITE_TENDUE" not in codes

    def test_liquidite_tendue_triggered(self):
        assert "LIQUIDITE_TENDUE" in _codes(_ratios(ratio_liquidite_generale=1.1))

    def test_liquidite_tendue_not_triggered_at_1_2(self):
        """Seuil : ratio = 1.2 ne déclenche pas LIQUIDITE_TENDUE."""
        codes = _codes(_ratios(ratio_liquidite_generale=1.2))
        assert "LIQUIDITE_TENDUE" not in codes
        assert "LIQUIDITE_CRITIQUE" not in codes


class TestDelaiClientsSignal:
    def test_delai_clients_eleve_triggered(self):
        assert "DELAI_CLIENTS_ELEVE" in _codes(_ratios(delai_clients_jours=75.0))

    def test_delai_clients_not_triggered_at_60(self):
        """Seuil : exactement 60j ne déclenche pas le signal."""
        assert "DELAI_CLIENTS_ELEVE" not in _codes(_ratios(delai_clients_jours=60.0))


class TestAutonomieSignal:
    def test_autonomie_faible_triggered(self):
        assert "AUTONOMIE_FAIBLE" in _codes(_ratios(autonomie_financiere=15.0))

    def test_autonomie_faible_not_triggered_at_20(self):
        assert "AUTONOMIE_FAIBLE" not in _codes(_ratios(autonomie_financiere=20.0))


class TestBaisseCASignal:
    def test_baisse_ca_significative_triggered(self):
        codes = _codes(_ratios(variation_ca_pct=-15.0))
        assert "BAISSE_CA_SIGNIFICATIVE" in codes

    def test_baisse_ca_gravite_elevee(self):
        signals = detect_signals_from_rules(_ratios(variation_ca_pct=-20.0))
        sig = next(s for s in signals if s.code == "BAISSE_CA_SIGNIFICATIVE")
        assert sig.gravite == Gravite.ELEVEE

    def test_baisse_ca_not_triggered_below_minus_10(self):
        """Une baisse de -10% ne déclenche pas le signal (seuil est < -10)."""
        assert "BAISSE_CA_SIGNIFICATIVE" not in _codes(_ratios(variation_ca_pct=-10.0))

    def test_baisse_ca_not_triggered_when_none(self):
        assert "BAISSE_CA_SIGNIFICATIVE" not in _codes(_ratios(variation_ca_pct=None))


class TestBFRSignal:
    def test_desequilibre_bfr_triggered(self):
        """Clients > 45j ET fournisseurs < 30j → DESEQUILIBRE_BFR."""
        codes = _codes(_ratios(delai_clients_jours=60.0, delai_fournisseurs_jours=20.0))
        assert "DESEQUILIBRE_BFR" in codes

    def test_desequilibre_bfr_not_triggered_when_balanced(self):
        """Délais équilibrés → pas de signal BFR."""
        codes = _codes(_ratios(delai_clients_jours=40.0, delai_fournisseurs_jours=40.0))
        assert "DESEQUILIBRE_BFR" not in codes

    def test_desequilibre_bfr_not_triggered_clients_below_45(self):
        codes = _codes(_ratios(delai_clients_jours=44.0, delai_fournisseurs_jours=20.0))
        assert "DESEQUILIBRE_BFR" not in codes

    def test_desequilibre_bfr_not_triggered_fourn_above_30(self):
        codes = _codes(_ratios(delai_clients_jours=60.0, delai_fournisseurs_jours=31.0))
        assert "DESEQUILIBRE_BFR" not in codes


# ── Opportunités & optimisations ─────────────────────────────────────────────

class TestOpportuniteSignals:
    def test_forte_rentabilite_triggered(self):
        codes = _codes(_ratios(taux_ebe=20.0))
        assert "FORTE_RENTABILITE" in codes

    def test_forte_rentabilite_type(self):
        signals = detect_signals_from_rules(_ratios(taux_ebe=20.0))
        sig = next(s for s in signals if s.code == "FORTE_RENTABILITE")
        assert sig.type == TypeSignal.OPPORTUNITE

    def test_forte_rentabilite_not_triggered_at_15(self):
        """Seuil exclusif : exactement 15% ne déclenche pas le signal."""
        assert "FORTE_RENTABILITE" not in _codes(_ratios(taux_ebe=15.0))

    def test_forte_croissance_triggered(self):
        assert "FORTE_CROISSANCE" in _codes(_ratios(variation_ca_pct=25.0))

    def test_forte_croissance_not_triggered_at_20(self):
        assert "FORTE_CROISSANCE" not in _codes(_ratios(variation_ca_pct=20.0))

    def test_capacite_investissement_triggered(self):
        """Faible dette (< 1 an) ET bonne rentabilité (> 10%)."""
        codes = _codes(_ratios(couverture_dettes=0.5, taux_ebe=15.0))
        assert "CAPACITE_INVESTISSEMENT" in codes

    def test_capacite_investissement_not_triggered_high_debt(self):
        codes = _codes(_ratios(couverture_dettes=2.0, taux_ebe=15.0))
        assert "CAPACITE_INVESTISSEMENT" not in codes

    def test_optimisation_fiscale_triggered(self):
        """RN > 5% ET ROE > 15% → optimisation fiscale."""
        codes = _codes(_ratios(taux_resultat_net=8.0, rentabilite_capitaux=20.0))
        assert "OPTIMISATION_FISCALE" in codes

    def test_optimisation_fiscale_not_triggered_low_roe(self):
        codes = _codes(_ratios(taux_resultat_net=8.0, rentabilite_capitaux=10.0))
        assert "OPTIMISATION_FISCALE" not in codes


# ── Entreprise sans risques ───────────────────────────────────────────────────

def test_no_risk_signals_for_excellent_company():
    """Une entreprise financièrement saine ne génère aucun signal de risque."""
    ratios_sains = _ratios(
        taux_ebe=20.0,
        couverture_dettes=0.5,
        ratio_liquidite_generale=3.0,
        delai_clients_jours=30.0,
        autonomie_financiere=60.0,
        variation_ca_pct=5.0,
    )
    signals = detect_signals_from_rules(ratios_sains)
    risques = [s for s in signals if s.type == TypeSignal.RISQUE]
    assert risques == [], f"Signaux de risque inattendus : {[s.code for s in risques]}"


def test_signals_sorted_by_severity_when_multiple():
    """Les signaux doivent pouvoir être triés par gravité décroissante (comportement du node)."""
    ratios = _ratios(
        taux_ebe=-5.0,           # ELEVEE
        ratio_liquidite_generale=1.1,  # MOYENNE (tendue)
        delai_clients_jours=70.0,      # MOYENNE
    )
    signals = detect_signals_from_rules(ratios)
    # Vérifier que EBE_NEGATIF (gravite=3) est présent
    codes = [s.code for s in signals]
    assert "EBE_NEGATIF" in codes
    # Après tri, le premier signal devrait être de gravité ELEVEE
    signals_sorted = sorted(signals, key=lambda s: s.gravite, reverse=True)
    assert signals_sorted[0].gravite == Gravite.ELEVEE
