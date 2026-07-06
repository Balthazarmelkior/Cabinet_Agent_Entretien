"""
Tests d'intégration bout-en-bout du pipeline LangGraph.

Ces tests valident :
1. La compilation du graphe
2. L'enchaînement complet avec des données synthétiques et LLM mockés
3. Le comportement en cas d'erreur de parsing FEC (bug documenté)
"""
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


PLAN_JSON = """{
    "synthese_executive": "Entreprise en croissance, vigilance sur la trésorerie.",
    "points_vigilance": ["BFR en tension", "Délais clients à surveiller"],
    "plan_entretien": [
        {"ordre": 1, "theme": "Trésorerie", "contexte_chiffre": "Liquidité 1.5",
         "question_ouverte": "Comment gérez-vous vos flux?", "mission_associee": null}
    ],
    "missions_a_proposer": [],
    "elements_a_recueillir": ["Prévisionnel de trésorerie"],
    "conclusion_conseillee": "Mettre en place un suivi mensuel."
}"""


def _create_synthetic_fec(rows: list[tuple[str, float]], date: str = "20240101") -> str:
    """Crée un fichier FEC temporaire avec colonne Montant."""
    header = (
        "JournalCode\tJournalLib\tEcritureNum\tEcritureDate\tCompteNum\tCompteLib\t"
        "CompAuxNum\tCompAuxLib\tPieceRef\tPieceDate\tEcritureLib\tMontant\n"
    )
    lines = [header]
    for i, (compte, montant) in enumerate(rows):
        lines.append(
            f"VT\tVentes\t{i:06d}\t{date}\t{compte}\tLib\t\t\t"
            f"P{i}\t{date}\tEcr\t{str(montant).replace('.', ',')}\n"
        )
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="latin1")
    f.writelines(lines)
    f.close()
    return f.name


SYNTHETIC_FEC_ROWS = [
    ("700000", 800_000),   # CA
    ("600000", 320_000),   # Achats
    ("610000", 80_000),    # Charges ext
    ("640000", 100_000),   # Charges pers
    ("411000", 90_000),    # Créances clients (41j)
    ("401000", 45_000),    # Dettes fournisseurs
    ("512000", 150_000),   # Trésorerie banque
    ("101000", 250_000),   # Capital
    ("164000", 80_000),    # Dettes financières
    ("120000", 70_000),    # Résultat net
    ("211000", 180_000),   # Immobilisations
    ("310000", 25_000),    # Stocks
]


# ── Compilation du graphe ─────────────────────────────────────────────────────

def test_graph_compiles_without_error():
    """Le graphe LangGraph se compile sans erreur ni appel LLM."""
    from graph import build_graph
    graph = build_graph()
    assert graph is not None


# ── Bug du FEC réel ───────────────────────────────────────────────────────────

def test_real_fec_parses_and_has_valid_ca(fec_path):
    """
    Le FEC standard DGFiP (colonnes Debit/Credit) se parse correctement.
    Le CA est positif car les comptes 70x sont traités comme créditeurs.
    """
    from parsers.fec_parser import parse_fec
    result = parse_fec(fec_path)
    assert result is not None
    assert result.chiffre_affaires.montant_n > 0


# ── Pipeline complet avec FEC synthétique ────────────────────────────────────

def test_full_pipeline_extract_and_detect(catalogue_path):
    """Les nodes extract + detect_signals fonctionnent avec un FEC synthétique."""
    tmp = _create_synthetic_fec(SYNTHETIC_FEC_ROWS)
    try:
        # 1. Extraction
        from nodes.extract_financial_data import extract_financial_data
        state = extract_financial_data({
            "fichier_path": tmp,
            "code_naf": "47.1Z",
        })
        assert state["donnees_financieres"] is not None
        donnees = state["donnees_financieres"]
        assert donnees.chiffre_affaires.montant_n == pytest.approx(800_000)

        # 2. Détection signaux
        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm("[]")
            from nodes.detect_signals import detect_signals
            sig_state = detect_signals({"donnees_financieres": donnees})

        assert "ratios" in sig_state
        assert "signaux_detectes" in sig_state
        assert sig_state["ratios"].taux_ebe == pytest.approx(37.5)  # 300k/800k
    finally:
        os.unlink(tmp)


def test_full_pipeline_benchmark(catalogue_path):
    """Le node benchmark fonctionne avec données synthétiques et BdF mockée."""
    from benchmark.base import RatiosBruts

    tmp = _create_synthetic_fec(SYNTHETIC_FEC_ROWS)
    try:
        from nodes.extract_financial_data import extract_financial_data
        state = extract_financial_data({"fichier_path": tmp, "code_naf": "47.1Z"})
        donnees = state["donnees_financieres"]

        mock_bdf_data = RatiosBruts(
            source="Banque de France", annee_reference=2023,
            libelle_secteur="Commerce de détail", fiabilite=1,
            taux_ebe={"mediane": 8.0, "q1": 4.0, "q3": 12.0},
            taux_resultat_net={"mediane": 3.0, "q1": 1.0, "q3": 6.0},
            autonomie_financiere={"mediane": 35.0, "q1": 20.0, "q3": 55.0},
            couverture_dettes={"mediane": 3.0, "q1": 1.0, "q3": 6.0},
            delai_clients_jours={"mediane": 45.0, "q1": 25.0, "q3": 70.0},
            delai_fournisseurs_jours={"mediane": 40.0, "q1": 25.0, "q3": 60.0},
            ratio_liquidite_generale={"mediane": 1.2, "q1": 0.9, "q3": 1.8},
        )

        with patch("benchmark.sources.bdf.BanqueDeFranceSource.fetch",
                   return_value=mock_bdf_data), \
             patch("benchmark.sources.insee.InseeSource.fetch", return_value=None), \
             patch("nodes.benchmark_sectoriel.ChatOpenAI"):
            from nodes.benchmark_sectoriel import benchmark_sectoriel
            bench_state = benchmark_sectoriel({
                "donnees_financieres": donnees,
                "code_naf": "47.1Z",
            })

        assert bench_state["benchmark"] is not None
        assert bench_state["benchmark"].code_naf == "47.1Z"
        assert len(bench_state["benchmark"].ratios) > 0
    finally:
        os.unlink(tmp)


def test_full_pipeline_match_missions(catalogue_path):
    """Le node match_missions retourne des missions (incluant les priorité 1)."""
    from analysis.ratios import compute_ratios
    from analysis.rules import detect_signals_from_rules

    tmp = _create_synthetic_fec(SYNTHETIC_FEC_ROWS)
    try:
        from nodes.extract_financial_data import extract_financial_data
        state = extract_financial_data({"fichier_path": tmp, "code_naf": "47.1Z"})
        donnees = state["donnees_financieres"]
        ratios = compute_ratios(donnees)
        signaux = detect_signals_from_rules(ratios)

        from nodes.match_missions import match_missions
        match_state = match_missions({
            "signaux_detectes": signaux,
            "catalogue_path": catalogue_path,
        })

        assert "missions_recommandees" in match_state
        assert len(match_state["missions_recommandees"]) > 0
    finally:
        os.unlink(tmp)


def test_end_to_end_all_nodes_sequential(catalogue_path):
    """
    Enchaînement manuel des 5 nodes (sans LangGraph) avec données synthétiques.
    Vérifie que la fiche finale est produite sans erreur.
    """
    from benchmark.base import RatiosBruts
    from unittest.mock import patch

    tmp = _create_synthetic_fec(SYNTHETIC_FEC_ROWS)
    mock_bdf = RatiosBruts(
        source="Banque de France", annee_reference=2023,
        libelle_secteur="Commerce", fiabilite=1,
        taux_ebe={"mediane": 8.0, "q1": 4.0, "q3": 12.0},
        taux_resultat_net={"mediane": 3.0, "q1": 1.0, "q3": 5.0},
        autonomie_financiere={"mediane": 35.0, "q1": 20.0, "q3": 55.0},
        couverture_dettes={"mediane": 3.0, "q1": 1.0, "q3": 6.0},
        delai_clients_jours={"mediane": 45.0, "q1": 25.0, "q3": 70.0},
        delai_fournisseurs_jours={"mediane": 40.0, "q1": 25.0, "q3": 60.0},
        ratio_liquidite_generale={"mediane": 1.2, "q1": 0.9, "q3": 1.8},
    )

    try:
        with patch("nodes.detect_signals.ChatOpenAI") as m1, \
             patch("nodes.generate_interview_plan.ChatOpenAI") as m2, \
             patch("nodes.benchmark_sectoriel.ChatOpenAI"), \
             patch("benchmark.sources.bdf.BanqueDeFranceSource.fetch",
                   return_value=mock_bdf), \
             patch("benchmark.sources.insee.InseeSource.fetch", return_value=None):

            m1.return_value = _mock_llm("[]")
            m2.return_value = _mock_llm(PLAN_JSON)

            from nodes.extract_financial_data import extract_financial_data
            from nodes.detect_signals import detect_signals
            from nodes.benchmark_sectoriel import benchmark_sectoriel
            from nodes.match_missions import match_missions
            from nodes.generate_interview_plan import generate_interview_plan

            s1 = extract_financial_data({"fichier_path": tmp, "code_naf": "47.1Z"})
            s2 = detect_signals(s1)
            s3 = benchmark_sectoriel({**s1, "code_naf": "47.1Z"})
            s4 = match_missions({**s2, "catalogue_path": catalogue_path})
            s5 = generate_interview_plan({**s1, **s2, **s3, **s4})

        fiche = s5["fiche_entretien"]
        assert fiche is not None
        assert fiche.client_exercice.startswith("Exercice")
        assert fiche.synthese_executive != ""
        assert isinstance(fiche.plan_entretien, list)
        assert isinstance(fiche.elements_a_recueillir, list)
    finally:
        os.unlink(tmp)


def test_fec_signals_drive_missions(catalogue_path, donnees_saine):
    """Un FEC synthétique famille A (rémunération, 455 créditeur, pénalités) produit
    des signaux FEC qui déclenchent les missions catalogue correspondantes."""
    import pandas as pd
    from analysis.fec_features import compute_fec_features
    from nodes.detect_signals import detect_signals
    from nodes.match_missions import match_missions

    df = pd.DataFrame([
        {"CompteNum": "641100", "Debit": 60000, "Credit": 0, "EcritureDate": "20240131"},
        {"CompteNum": "4551",   "Debit": 0, "Credit": 90000, "EcritureDate": "20240131"},
        {"CompteNum": "671200", "Debit": 800, "Credit": 0, "EcritureDate": "20240201"},
    ])
    feat = compute_fec_features(df)

    with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
        mock_cls.return_value = _mock_llm("[]")
        s = detect_signals({"donnees_financieres": donnees_saine, "indicateurs_fec": feat, "seuils_overrides": {}})

    codes = {sig.code for sig in s["signaux_detectes"]}
    assert {"REMUNERATION_DIRIGEANT_ELEVEE", "COMPTE_COURANT_CREDITEUR_ELEVE", "PENALITES_FISCALES"} <= codes

    m = match_missions({**s, "catalogue_path": catalogue_path})
    ids = {r.mission.id for r in m["missions_recommandees"]}
    assert "MISSION_PROTECTION_STATUT_SOCIAL" in ids           # rémunération dirigeant
    assert "MISSION_COMPTA_PACK_SERENITE" in ids               # pénalités fiscales


def test_fournisseurs_drive_facture_electronique(catalogue_path, donnees_saine):
    """Un FEC synthétique avec 55 fournisseurs distincts déclenche NOMBREUX_FOURNISSEURS
    et la mission catalogue associée."""
    import pandas as pd
    from analysis.fec_features import compute_fec_features
    from nodes.detect_signals import detect_signals
    from nodes.match_missions import match_missions

    rows = [{"CompteNum": "401000", "Debit": 0, "Credit": 100,
             "EcritureDate": "20240115", "CompAuxNum": f"F{i:03}", "JournalCode": "AC"}
            for i in range(55)]
    feat = compute_fec_features(pd.DataFrame(rows))

    with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
        mock_cls.return_value = _mock_llm("[]")
        s = detect_signals({"donnees_financieres": donnees_saine, "indicateurs_fec": feat, "seuils_overrides": {}})

    assert "NOMBREUX_FOURNISSEURS" in {sig.code for sig in s["signaux_detectes"]}

    m = match_missions({**s, "catalogue_path": catalogue_path})
    ids = {r.mission.id for r in m["missions_recommandees"]}
    assert "MISSION_COMPTA_FX_MISE_EN_PLACE" in ids


def test_quickwins_signals_drive_missions(catalogue_path, donnees_saine):
    """Un FEC synthétique déclenche des signaux quick-wins (2c) qui pilotent
    les missions catalogue correspondantes."""
    import pandas as pd
    from analysis.fec_features import compute_fec_features
    from nodes.detect_signals import detect_signals
    from nodes.match_missions import match_missions

    df = pd.DataFrame([
        {"CompteNum": "706000", "Debit": 0, "Credit": 365000, "EcritureDate": "20240630"},
        {"CompteNum": "411000", "Debit": 30000, "Credit": 0, "EcritureDate": "20240630"},  # DSO 30j
    ])
    feat = compute_fec_features(df)

    with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
        mock_cls.return_value = _mock_llm("[]")
        s = detect_signals({"donnees_financieres": donnees_saine, "indicateurs_fec": feat, "seuils_overrides": {}})

    codes = {sig.code for sig in s["signaux_detectes"]}
    assert {"DELAI_FACTURATION_LONG", "SEUIL_TVA_MICRO_DEPASSE"} <= codes

    m = match_missions({**s, "catalogue_path": catalogue_path})
    ids = {r.mission.id for r in m["missions_recommandees"]}
    assert "MISSION_COMPTA_FX_EXTERNALISATION" in ids           # délai facturation long
    assert "MISSION_AVOCATS_CREATION" in ids                    # seuil TVA/micro


# ── Tests de robustesse ────────────────────────────────────────────────────────

def test_unsupported_file_format_raises_value_error():
    """Un fichier avec une extension non supportée lève ValueError."""
    from nodes.extract_financial_data import extract_financial_data
    with pytest.raises(ValueError, match="Format non supporté"):
        extract_financial_data({"fichier_path": "rapport.xlsx", "code_naf": "47.1Z"})


def test_catalogue_path_validation_rejects_traversal():
    """Tentative de path traversal sur le catalogue → ValueError."""
    from nodes.match_missions import match_missions
    with pytest.raises(ValueError, match="outside the allowed"):
        match_missions({
            "signaux_detectes": [],
            "catalogue_path": "../../../../etc/shadow",
        })


# ── Helpers locaux ────────────────────────────────────────────────────────────

def _mock_llm(content: str) -> MagicMock:
    instance = MagicMock()
    resp = MagicMock()
    resp.content = content
    instance.invoke.return_value = resp
    return instance
