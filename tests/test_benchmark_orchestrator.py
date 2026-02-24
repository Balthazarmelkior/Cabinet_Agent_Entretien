"""
Tests de l'orchestrateur de benchmark sectoriel (benchmark/orchestrator.py).
Toutes les sources sont mockées — pas d'appels réseau réels.
"""
import pytest
from unittest.mock import MagicMock
from benchmark.orchestrator import BenchmarkOrchestrator, _interpretation
from benchmark.base import RatiosBruts
from models import RatioSectoriel


def _make_orchestrator():
    return BenchmarkOrchestrator(
        bdf=MagicMock(), insee=MagicMock(), llm=MagicMock()
    )


def _make_bdf_data(annee=2023, **ratio_overrides) -> RatiosBruts:
    """RatiosBruts complet simulant une réponse Banque de France."""
    defaults = dict(
        taux_ebe={"mediane": 8.0, "q1": 4.0, "q3": 12.0},
        taux_resultat_net={"mediane": 3.0, "q1": 1.0, "q3": 6.0},
        autonomie_financiere={"mediane": 35.0, "q1": 20.0, "q3": 55.0},
        couverture_dettes={"mediane": 3.0, "q1": 1.0, "q3": 6.0},
        delai_clients_jours={"mediane": 45.0, "q1": 25.0, "q3": 70.0},
        delai_fournisseurs_jours={"mediane": 40.0, "q1": 25.0, "q3": 60.0},
        ratio_liquidite_generale={"mediane": 1.2, "q1": 0.9, "q3": 1.8},
    )
    defaults.update(ratio_overrides)
    return RatiosBruts(
        source="Banque de France",
        annee_reference=annee,
        libelle_secteur="Commerce de détail",
        fiabilite=1,
        **defaults,
    )


# ── _tranche (CA → taille d'entreprise) ──────────────────────────────────────

@pytest.mark.parametrize("ca,expected", [
    (0, "TPE"),
    (500_000, "TPE"),
    (1_999_999, "TPE"),
    (2_000_000, "PME"),
    (10_000_000, "PME"),
    (49_999_999, "PME"),
    (50_000_000, "ETI"),
    (100_000_000, "ETI"),
])
def test_tranche_ca(ca, expected):
    assert _make_orchestrator()._tranche(ca) == expected


# ── _interpretation ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("val,med,q1,q3,sens,expected", [
    # Sens "plus" : plus élevé = meilleur
    (20, 10, 5, 15, "plus", "favorable"),              # val >= q3
    (12, 10, 5, 15, "plus", "dans la norme"),          # med <= val < q3
    (7, 10, 5, 15, "plus", "en dessous de la médiane"),  # q1 <= val < med
    (3, 10, 5, 15, "plus", "défavorable"),             # val < q1
    # Sens "moins" : plus bas = meilleur
    (3, 10, 5, 15, "moins", "favorable"),              # val <= q1
    (7, 10, 5, 15, "moins", "dans la norme"),          # q1 < val <= med
    (12, 10, 5, 15, "moins", "en dessous de la médiane"),  # med < val <= q3
    (20, 10, 5, 15, "moins", "défavorable"),           # val > q3
])
def test_interpretation(val, med, q1, q3, sens, expected):
    assert _interpretation(val, med, q1, q3, sens) == expected


# ── _commentaire ─────────────────────────────────────────────────────────────

def test_commentaire_points_forts():
    orc = _make_orchestrator()
    ratios = [
        RatioSectoriel(libelle="EBE", valeur_client=20, source="BdF",
                       interpretation="favorable", mediane_secteur=10),
    ]
    c = orc._commentaire(ratios, "Commerce")
    assert "Points forts" in c
    assert "EBE" in c


def test_commentaire_points_vigilance():
    orc = _make_orchestrator()
    ratios = [
        RatioSectoriel(libelle="Autonomie", valeur_client=10, source="BdF",
                       interpretation="défavorable", mediane_secteur=40),
    ]
    c = orc._commentaire(ratios, "Industrie")
    assert "vigilance" in c.lower()
    assert "Autonomie" in c


def test_commentaire_in_norme():
    orc = _make_orchestrator()
    ratios = [
        RatioSectoriel(libelle="EBE", valeur_client=10, source="BdF",
                       interpretation="dans la norme", mediane_secteur=10),
    ]
    c = orc._commentaire(ratios, "BTP")
    assert "norme" in c.lower()


def test_commentaire_mixed_ratios():
    orc = _make_orchestrator()
    ratios = [
        RatioSectoriel(libelle="EBE", valeur_client=20, source="BdF",
                       interpretation="favorable", mediane_secteur=10),
        RatioSectoriel(libelle="Liquidité", valeur_client=0.5, source="BdF",
                       interpretation="défavorable", mediane_secteur=1.2),
    ]
    c = orc._commentaire(ratios, "Services")
    assert "Points forts" in c
    assert "vigilance" in c.lower()


# ── _merge (fusion multi-sources) ────────────────────────────────────────────

def test_merge_prefers_higher_reliability():
    """La source fiabilité=1 (BdF) écrase fiabilité=3 (LLM) pour le même ratio."""
    orc = _make_orchestrator()
    bdf = RatiosBruts(
        source="BdF", annee_reference=2023, libelle_secteur="NAF 47", fiabilite=1,
        taux_ebe={"mediane": 8.0, "q1": 4.0, "q3": 12.0},
    )
    llm = RatiosBruts(
        source="LLM", annee_reference=2023, libelle_secteur="NAF 47", fiabilite=3,
        taux_ebe={"mediane": 5.0, "q1": 2.0, "q3": 9.0},
    )
    merged = orc._merge([bdf, llm])
    # BdF (fiabilite=1, mediane=8.0) doit gagner sur LLM (mediane=5.0)
    assert merged["taux_ebe"]["mediane"] == 8.0
    assert merged["taux_ebe"]["_source"] == "BdF"


def test_merge_llm_fills_missing_ratios():
    """LLM comble les ratios absents de BdF."""
    orc = _make_orchestrator()
    bdf = RatiosBruts(
        source="BdF", annee_reference=2023, libelle_secteur="NAF 47", fiabilite=1,
        taux_ebe={"mediane": 8.0, "q1": 4.0, "q3": 12.0},
        # Pas de ratio_liquidite_generale
    )
    llm = RatiosBruts(
        source="LLM", annee_reference=2023, libelle_secteur="NAF 47", fiabilite=3,
        ratio_liquidite_generale={"mediane": 1.2, "q1": 0.9, "q3": 1.8},
    )
    merged = orc._merge([bdf, llm])
    assert "taux_ebe" in merged
    assert "ratio_liquidite_generale" in merged


# ── build() complet ────────────────────────────────────────────────────────────

def test_build_returns_valid_benchmark(donnees_saine):
    """build() produit un BenchmarkSectoriel correctement structuré."""
    from analysis.ratios import compute_ratios

    mock_bdf = MagicMock()
    mock_bdf.fetch.return_value = _make_bdf_data()
    mock_insee = MagicMock()
    mock_insee.fetch.return_value = None
    mock_llm = MagicMock()
    mock_llm.fetch.return_value = None

    orc = BenchmarkOrchestrator(mock_bdf, mock_insee, mock_llm)
    ratios = compute_ratios(donnees_saine)

    result = orc.build(
        ratios_client=ratios,
        code_naf="47.1Z",
        secteur_activite="Commerce de détail",
        ca=donnees_saine.chiffre_affaires.montant_n,
        annee=donnees_saine.exercice_n,
    )

    assert result.code_naf == "47.1Z"
    assert result.libelle_secteur == "Commerce de détail"
    assert len(result.ratios) > 0
    assert result.commentaire_global != ""


def test_build_ebe_interpretation_favorable(donnees_saine):
    """EBE client 25% > Q3 secteur 12% → interprétation 'favorable'."""
    from analysis.ratios import compute_ratios

    mock_bdf = MagicMock()
    mock_bdf.fetch.return_value = _make_bdf_data(
        taux_ebe={"mediane": 8.0, "q1": 4.0, "q3": 12.0}
    )
    mock_insee = MagicMock()
    mock_insee.fetch.return_value = None
    mock_llm = MagicMock()
    mock_llm.fetch.return_value = None

    orc = BenchmarkOrchestrator(mock_bdf, mock_insee, mock_llm)
    ratios = compute_ratios(donnees_saine)

    result = orc.build(
        ratios_client=ratios,
        code_naf="47.1Z",
        secteur_activite="Commerce",
        ca=1_000_000,
        annee=2024,
    )

    ebe_ratio = next((r for r in result.ratios if "EBE" in r.libelle), None)
    assert ebe_ratio is not None
    assert ebe_ratio.interpretation == "favorable"


def test_build_falls_back_to_llm_when_bdf_fails(donnees_saine):
    """Si BdF et INSEE échouent, le benchmark LLM est utilisé."""
    from analysis.ratios import compute_ratios

    mock_bdf = MagicMock()
    mock_bdf.fetch.return_value = None  # BdF échoue
    mock_insee = MagicMock()
    mock_insee.fetch.return_value = None  # INSEE échoue aussi
    mock_llm = MagicMock()
    mock_llm.fetch.return_value = RatiosBruts(
        source="LLM", annee_reference=2023, libelle_secteur="Services", fiabilite=3,
        taux_ebe={"mediane": 7.0, "q1": 3.0, "q3": 11.0},
    )

    orc = BenchmarkOrchestrator(mock_bdf, mock_insee, mock_llm)
    ratios = compute_ratios(donnees_saine)

    result = orc.build(
        ratios_client=ratios,
        code_naf="62.0Z",
        secteur_activite="Services IT",
        ca=1_000_000,
        annee=2024,
    )

    mock_llm.fetch.assert_called_once()
    assert len(result.ratios) > 0


def test_build_ecart_mediane_calculated(donnees_saine):
    """L'écart à la médiane (%) est calculé pour chaque ratio."""
    from analysis.ratios import compute_ratios

    mock_bdf = MagicMock()
    mock_bdf.fetch.return_value = _make_bdf_data(
        taux_ebe={"mediane": 10.0, "q1": 5.0, "q3": 15.0}
    )
    mock_insee = MagicMock()
    mock_insee.fetch.return_value = None
    mock_llm = MagicMock()
    mock_llm.fetch.return_value = None

    orc = BenchmarkOrchestrator(mock_bdf, mock_insee, mock_llm)
    ratios = compute_ratios(donnees_saine)  # taux_ebe = 25%

    result = orc.build(
        ratios_client=ratios, code_naf="47.1Z",
        secteur_activite="Commerce", ca=1_000_000, annee=2024,
    )

    ebe_ratio = next(r for r in result.ratios if "EBE" in r.libelle)
    # Écart = (25 - 10) / 10 * 100 = 150%
    assert ebe_ratio.ecart_mediane_pct == pytest.approx(150.0)
