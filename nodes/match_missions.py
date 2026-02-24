# nodes/match_missions.py
import json
import os
from pathlib import Path
from langchain_openai import ChatOpenAI
from models import Mission, MissionRecommandee

SEUIL_RAG = int(os.getenv("RAG_THRESHOLD", "50"))

PROMPT_MATCHING = """Tu es associé d'un cabinet d'expertise comptable.
Propose uniquement les missions pertinentes au regard des signaux détectés.
Pour chaque mission retenue, rédige un argumentaire court (2-3 phrases) orienté BÉNÉFICE CLIENT.

Retourne UNIQUEMENT un JSON array :
[{"mission_id":"...","score_pertinence":0.0,"signaux_declencheurs":["CODE"],
  "argumentaire":"...","urgence":"immédiate|court terme|moyen terme"}]
Ne retourne pas les missions avec score < 0.5. Aucun texte hors JSON."""


def _load_catalogue(path: str) -> list[Mission]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return [Mission(**m) for m in data]


def match_missions(state: dict) -> dict:
    signaux  = state["signaux_detectes"]
    catalogue = _load_catalogue(state.get("catalogue_path", "data/catalogue_missions.json"))
    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

    if len(catalogue) <= SEUIL_RAG:
        from matching.llm_matcher import match_with_llm
        recommandations = match_with_llm(signaux, catalogue, llm)
    else:
        from matching.rag_matcher import RAGMatcher
        matcher = RAGMatcher(catalogue)
        recommandations = matcher.match(signaux, llm)

    # Toujours inclure les missions priorité=1
    ids_retenus = {r.mission.id for r in recommandations}
    for mission in catalogue:
        if mission.priorite_proposition == 1 and mission.id not in ids_retenus:
            recommandations.append(MissionRecommandee(
                mission=mission,
                score_pertinence=1.0,
                signaux_declencheurs=[],
                argumentaire=mission.benefice_client,
                urgence="court terme",
            ))

    recommandations.sort(key=lambda r: r.score_pertinence, reverse=True)
    return {"missions_recommandees": recommandations}
