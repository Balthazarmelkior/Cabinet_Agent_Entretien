# nodes/match_missions.py
import os
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


def _to_model(m: MissionDC) -> Mission:
    return Mission(
        id=m.id, titre=m.titre, description=m.description,
        benefice_client=m.benefice_client, codes_signaux=m.codes_signaux,
        honoraires_indicatifs=m.honoraires_indicatifs,
        priorite_proposition=m.priorite_proposition,
    )


def match_missions(state: dict) -> dict:
    signaux = state.get("signaux_detectes", []) or []
    codes_actifs = [s.code for s in signaux]

    catalogue_path = _resolve(state.get("catalogue_path", "data/catalogue_missions_tyls.json"))
    seuils_path = _resolve(state.get("seuils_path", os.getenv("SEUILS_PATH", "data/seuils_signaux.json")))

    matcher = MissionMatcher.from_files(catalogue_path, seuils_path)
    matches = matcher.match(codes_actifs)

    recommandations: list[MissionRecommandee] = []
    ids_retenus: set[str] = set()

    for m in matches:
        mission = _to_model(m.mission)
        ids_retenus.add(mission.id)
        score = 1.0 if mission.priorite_proposition == 1 else min(1.0, round(0.5 + 0.1 * m.score, 2))
        recommandations.append(MissionRecommandee(
            mission=mission,
            score_pertinence=score,
            signaux_declencheurs=[s.code for s in m.signaux_declencheurs],
            argumentaire=mission.benefice_client,
            urgence=_URGENCE.get(mission.priorite_proposition, "moyen terme"),
        ))

    # Toujours inclure les missions priorité 1, même sans signal déclencheur
    for m in matcher.missions:
        if m.priorite_proposition == 1 and m.id not in ids_retenus:
            mission = _to_model(m)
            recommandations.append(MissionRecommandee(
                mission=mission,
                score_pertinence=1.0,
                signaux_declencheurs=[],
                argumentaire=mission.benefice_client,
                urgence="immédiate",
            ))

    recommandations.sort(key=lambda r: r.score_pertinence, reverse=True)
    return {"missions_recommandees": recommandations}
