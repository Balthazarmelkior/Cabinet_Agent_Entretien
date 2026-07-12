# nodes/match_missions.py
import os
from functools import lru_cache
from pathlib import Path
from models import Mission, MissionRecommandee
from matching.mission_matcher import MissionMatcher, Mission as MissionDC

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_URGENCE = {1: "immédiate", 2: "court terme", 3: "moyen terme"}


def _resolve(path: str) -> Path:
    resolved = (Path(path) if Path(path).is_absolute() else (_DATA_DIR.parent / path)).resolve()
    if not resolved.is_relative_to(_DATA_DIR):
        raise ValueError(f"Path '{path}' is outside the allowed data directory.")
    return resolved


@lru_cache(maxsize=8)
def _get_matcher(catalogue: str, seuils: str) -> MissionMatcher:
    return MissionMatcher.from_files(catalogue, seuils)


def _to_model(m: MissionDC) -> Mission:
    return Mission(
        id=m.id, titre=m.titre, description=m.description,
        benefice_client=m.benefice_client, codes_signaux=m.codes_signaux,
        honoraires_indicatifs=m.honoraires_indicatifs,
        priorite_proposition=m.priorite_proposition,
    )


def _make_reco(m: MissionDC, score: float, declencheurs: list[str]) -> MissionRecommandee:
    mission = _to_model(m)
    return MissionRecommandee(
        mission=mission,
        score_pertinence=score,
        signaux_declencheurs=declencheurs,
        argumentaire=mission.benefice_client,
        urgence=_URGENCE.get(m.priorite_proposition, "moyen terme"),
    )


def match_missions(state: dict) -> dict:
    signaux = state.get("signaux_detectes", []) or []
    codes_actifs = [s.code for s in signaux]

    catalogue_path = _resolve(state.get("catalogue_path", os.getenv("CATALOGUE_PATH", "data/catalogue_missions_tyls.json")))
    seuils_path = _resolve(state.get("seuils_path", os.getenv("SEUILS_PATH", "data/seuils_signaux.json")))

    matcher = _get_matcher(str(catalogue_path), str(seuils_path))
    matches = matcher.match(codes_actifs)

    recommandations: list[MissionRecommandee] = []
    ids_retenus: set[str] = set()

    for m in matches:
        ids_retenus.add(m.mission.id)
        score = 1.0 if m.mission.priorite_proposition == 1 else min(1.0, round(0.5 + 0.1 * m.score, 2))
        recommandations.append(
            _make_reco(m.mission, score, [s.code for s in m.signaux_declencheurs])
        )

    # Toujours inclure les missions priorité 1, même sans signal déclencheur
    for m in matcher.missions:
        if m.priorite_proposition == 1 and m.id not in ids_retenus:
            recommandations.append(_make_reco(m, 1.0, []))

    recommandations.sort(key=lambda r: (-r.score_pertinence, r.mission.priorite_proposition))
    return {"missions_recommandees": recommandations}
