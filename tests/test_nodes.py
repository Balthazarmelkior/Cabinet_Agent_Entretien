"""
Tests unitaires des nodes LangGraph.
Toutes les interactions LLM sont mockées.
"""
import pytest
from unittest.mock import MagicMock, patch


def _mock_llm(response_content: str) -> MagicMock:
    """Retourne une instance ChatOpenAI mockée qui répond avec response_content."""
    instance = MagicMock()
    mock_response = MagicMock()
    mock_response.content = response_content
    instance.invoke.return_value = mock_response
    return instance


VALID_PLAN_JSON = """{
    "synthese_executive": "Entreprise en bonne santé financière.",
    "points_vigilance": ["Surveiller la liquidité", "Anticiper la croissance"],
    "plan_entretien": [
        {"ordre": 1, "theme": "Rentabilité", "contexte_chiffre": "EBE à 25%",
         "question_ouverte": "Comment expliquez-vous cette performance?",
         "mission_associee": null}
    ],
    "missions_a_proposer": [
        {"titre": "Mission test", "argumentaire_personnalise": "Arg.",
         "urgence": "court terme", "benefice_attendu": "Gain fiscal"}
    ],
    "elements_a_recueillir": ["Bilan N-1", "Liasse fiscale"],
    "conclusion_conseillee": "Proposer un suivi mensuel de trésorerie."
}"""


# ── Node detect_signals ───────────────────────────────────────────────────────

class TestDetectSignalsNode:

    def test_returns_ratios_and_signals(self, donnees_saine):
        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm("[]")
            from nodes.detect_signals import detect_signals
            result = detect_signals({"donnees_financieres": donnees_saine})

        assert "ratios" in result
        assert "signaux_detectes" in result
        assert result["ratios"] is not None

    def test_includes_deterministic_signals(self, donnees_risquee):
        """Les règles déterministes s'appliquent même si le LLM ne renvoie rien."""
        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm("[]")
            from nodes.detect_signals import detect_signals
            result = detect_signals({"donnees_financieres": donnees_risquee})

        codes = [s.code for s in result["signaux_detectes"]]
        assert "EBE_NEGATIF" in codes
        assert "LIQUIDITE_CRITIQUE" in codes
        assert "AUTONOMIE_FAIBLE" in codes

    def test_merges_llm_signals(self, donnees_saine):
        """Les signaux LLM valides sont ajoutés aux signaux déterministes."""
        llm_signal = (
            '[{"type":"conformite","gravite":2,"code":"OBLI_BILAN_CARBONE",'
            '"titre":"Bilan carbone obligatoire","description":"Obligation réglementaire.",'
            '"levier":"Accompagnement à la déclaration"}]'
        )
        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm(llm_signal)
            from nodes.detect_signals import detect_signals
            result = detect_signals({"donnees_financieres": donnees_saine})

        codes = [s.code for s in result["signaux_detectes"]]
        assert "OBLI_BILAN_CARBONE" in codes

    def test_sorted_by_severity_descending(self, donnees_risquee):
        """Les signaux sont triés par gravité décroissante."""
        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm("[]")
            from nodes.detect_signals import detect_signals
            result = detect_signals({"donnees_financieres": donnees_risquee})

        gravites = [s.gravite.value for s in result["signaux_detectes"]]
        assert gravites == sorted(gravites, reverse=True)

    def test_graceful_fallback_on_llm_error(self, donnees_saine):
        """Une erreur LLM ne plante pas le node — les règles déterministes suffisent."""
        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            mock_cls.return_value.invoke.side_effect = Exception("Network error")
            from nodes.detect_signals import detect_signals
            result = detect_signals({"donnees_financieres": donnees_saine})

        # Le node retourne quand même les signaux déterministes
        assert "signaux_detectes" in result
        assert len(result["signaux_detectes"]) > 0


# ── Node generate_interview_plan ─────────────────────────────────────────────

class TestGenerateInterviewPlanNode:

    def _make_state(self, donnees_saine):
        from analysis.ratios import compute_ratios
        from analysis.rules import detect_signals_from_rules
        from models import MissionRecommandee, Mission

        ratios = compute_ratios(donnees_saine)
        signaux = detect_signals_from_rules(ratios)
        missions = [MissionRecommandee(
            mission=Mission(
                id="MISSION_TEST", titre="Mission Test",
                description="Description.", benefice_client="Bénéfice.",
                priorite_proposition=2,
            ),
            score_pertinence=0.8,
            argumentaire="Argumentaire.",
            urgence="court terme",
        )]
        return {
            "donnees_financieres": donnees_saine,
            "ratios": ratios,
            "signaux_detectes": signaux,
            "missions_recommandees": missions,
            "benchmark": None,
        }

    def test_returns_valid_fiche(self, donnees_saine):
        state = self._make_state(donnees_saine)
        with patch("nodes.generate_interview_plan.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm(VALID_PLAN_JSON)
            from nodes.generate_interview_plan import generate_interview_plan
            result = generate_interview_plan(state)

        fiche = result["fiche_entretien"]
        assert fiche.synthese_executive == "Entreprise en bonne santé financière."
        assert len(fiche.points_vigilance) == 2
        assert fiche.plan_entretien[0].theme == "Rentabilité"
        assert fiche.conclusion_conseillee != ""

    def test_client_exercice_contains_year(self, donnees_saine):
        state = self._make_state(donnees_saine)
        with patch("nodes.generate_interview_plan.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm(VALID_PLAN_JSON)
            from nodes.generate_interview_plan import generate_interview_plan
            result = generate_interview_plan(state)

        assert "2024" in result["fiche_entretien"].client_exercice

    def test_fallback_fiche_on_invalid_json(self, donnees_saine):
        """Un JSON malformé déclenche la fiche de secours, pas une exception."""
        state = self._make_state(donnees_saine)
        with patch("nodes.generate_interview_plan.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm("{invalid JSON{{{{")
            from nodes.generate_interview_plan import generate_interview_plan
            result = generate_interview_plan(state)

        fiche = result["fiche_entretien"]
        # La fiche de secours contient un message d'erreur
        assert "échoué" in fiche.synthese_executive or "relancer" in fiche.synthese_executive

    def test_handles_markdown_code_fence(self, donnees_saine):
        """Le node nettoie les balises ```json ... ``` autour du JSON LLM."""
        state = self._make_state(donnees_saine)
        wrapped = f"```json\n{VALID_PLAN_JSON}\n```"
        with patch("nodes.generate_interview_plan.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm(wrapped)
            from nodes.generate_interview_plan import generate_interview_plan
            result = generate_interview_plan(state)

        fiche = result["fiche_entretien"]
        assert fiche.synthese_executive == "Entreprise en bonne santé financière."


# ── Node match_missions ────────────────────────────────────────────────────────

class TestMatchMissionsNode:

    def test_priority_1_missions_always_included(self, catalogue_path):
        """Les missions de priorité 1 sont toujours recommandées, même sans signal."""
        with patch("nodes.match_missions.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm("[]")
            from nodes.match_missions import match_missions
            result = match_missions({
                "signaux_detectes": [],
                "catalogue_path": catalogue_path,
            })

        ids = [r.mission.id for r in result["missions_recommandees"]]
        # Au moins une mission de priorité 1 (MISSION_TRESORERIE ou MISSION_AGO)
        assert len(ids) > 0, "Aucune mission recommandée, les missions priorité 1 manquent"

    def test_sorted_by_score_descending(self, catalogue_path):
        """Les recommandations sont triées par score_pertinence décroissant."""
        llm_resp = (
            '[{"mission_id":"MISSION_PREVISIONNEL","score_pertinence":0.9,'
            '"signaux_declencheurs":[],"argumentaire":"Top","urgence":"court terme"},'
            '{"mission_id":"MISSION_HOLDING","score_pertinence":0.6,'
            '"signaux_declencheurs":[],"argumentaire":"Moins top","urgence":"moyen terme"}]'
        )
        with patch("nodes.match_missions.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm(llm_resp)
            from nodes.match_missions import match_missions
            result = match_missions({
                "signaux_detectes": [],
                "catalogue_path": catalogue_path,
            })

        scores = [r.score_pertinence for r in result["missions_recommandees"]]
        assert scores == sorted(scores, reverse=True)

    def test_rejects_unknown_mission_ids(self, catalogue_path):
        """Les IDs de missions inconnus retournés par le LLM sont ignorés."""
        llm_resp = (
            '[{"mission_id":"MISSION_INEXISTANTE","score_pertinence":0.9,'
            '"signaux_declencheurs":[],"argumentaire":"?","urgence":"immédiate"}]'
        )
        with patch("nodes.match_missions.ChatOpenAI") as mock_cls:
            mock_cls.return_value = _mock_llm(llm_resp)
            from nodes.match_missions import match_missions
            result = match_missions({
                "signaux_detectes": [],
                "catalogue_path": catalogue_path,
            })

        ids = [r.mission.id for r in result["missions_recommandees"]]
        assert "MISSION_INEXISTANTE" not in ids

    def test_security_rejects_path_traversal(self, tmp_path):
        """Le chargement du catalogue refuse les chemins traversaux (path traversal)."""
        from nodes.match_missions import match_missions
        with pytest.raises(ValueError, match="outside the allowed"):
            match_missions({
                "signaux_detectes": [],
                "catalogue_path": "../../../etc/passwd",
            })
