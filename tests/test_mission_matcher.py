from pathlib import Path
import pytest
from matching.mission_matcher import MissionMatcher

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "data" / "catalogue_missions_tyls.json"
SEUILS = ROOT / "data" / "seuils_signaux.json"


@pytest.fixture
def matcher():
    return MissionMatcher.from_files(CATALOGUE, SEUILS)


def test_from_files_loads_and_coherence_ok(matcher):
    # 79 missions, 90 signaux, cohérence catalogue/référentiel valide (pas de ValueError)
    assert len(matcher.missions) == 79
    assert len(matcher.signaux) == 90


def test_signal_reads_dict_referential(matcher):
    sig = matcher.signaux["TRESORERIE_EXCEDENTAIRE"]
    assert sig.categorie == "TRESORERIE"
    assert "512" in sig.comptes_fec
    assert sig.seuil_texte  # champ non vide
    assert sig.libelle  # libellé synthétisé, jamais vide


def test_match_deterministe_par_signaux(matcher):
    matches = matcher.match({"TRESORERIE_EXCEDENTAIRE", "HAUSSE_TRESORERIE"})
    ids = {m.mission.id for m in matches}
    # Placement de trésorerie est déclenché par ces deux signaux
    assert "MISSION_PATRIMOINE_TRESORERIE" in ids
    treso = next(m for m in matches if m.mission.id == "MISSION_PATRIMOINE_TRESORERIE")
    assert treso.score >= 2
    assert {s.code for s in treso.signaux_declencheurs} >= {"TRESORERIE_EXCEDENTAIRE", "HAUSSE_TRESORERIE"}


def test_missions_sans_signal_jamais_declenchees(matcher):
    # MISSION_COMPTA_EXPERTISE a codes_signaux=[] → jamais dans un match par signal
    matches = matcher.match({"TRESORERIE_EXCEDENTAIRE"})
    assert "MISSION_COMPTA_EXPERTISE" not in {m.mission.id for m in matches}


def test_tri_priorite_puis_score(matcher):
    matches = matcher.match({"LIQUIDITE_CRITIQUE", "DELAI_CLIENTS_ELEVE", "DECOUVERT_RECURRENT"})
    priorites = [m.mission.priorite_proposition for m in matches]
    assert priorites == sorted(priorites)
