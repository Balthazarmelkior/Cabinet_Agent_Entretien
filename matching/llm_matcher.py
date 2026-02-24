# matching/llm_matcher.py
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from models import Mission, MissionRecommandee, Signal

PROMPT = """Tu es associé d'un cabinet d'expertise comptable.
Propose uniquement les missions pertinentes (score >= 0.5) au regard des signaux.
Argumentaire 2-3 phrases max, orienté BÉNÉFICE CLIENT, pas technique.

Retourne UNIQUEMENT un JSON array :
[{"mission_id":"...","score_pertinence":0.0,"signaux_declencheurs":["CODE"],
  "argumentaire":"...","urgence":"immédiate|court terme|moyen terme"}]
Aucun texte hors JSON."""


def match_with_llm(
    signaux: list[Signal],
    catalogue: list[Mission],
    llm: ChatOpenAI,
) -> list[MissionRecommandee]:

    context = {
        "signaux": [{"code": s.code, "titre": s.titre, "type": s.type,
                     "gravite": s.gravite, "description": s.description} for s in signaux],
        "catalogue": [m.model_dump() for m in catalogue],
    }

    response = llm.invoke([
        SystemMessage(content=PROMPT),
        HumanMessage(content=json.dumps(context, ensure_ascii=False, default=str)),
    ])

    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    try:
        raw = JsonOutputParser().parse(content)
    except Exception:
        return []

    index = {m.id: m for m in catalogue}
    result = []
    for item in raw:
        mid = item.get("mission_id")
        if mid not in index:
            continue
        result.append(MissionRecommandee(
            mission=index[mid],
            score_pertinence=float(item.get("score_pertinence", 0.5)),
            signaux_declencheurs=item.get("signaux_declencheurs", []),
            argumentaire=item.get("argumentaire", ""),
            urgence=item.get("urgence", "moyen terme"),
        ))

    return sorted(result, key=lambda r: r.score_pertinence, reverse=True)
