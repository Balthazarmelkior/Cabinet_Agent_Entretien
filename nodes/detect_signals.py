# nodes/detect_signals.py
import json
import logging
import os
from langchain_openai import ChatOpenAI

logger = logging.getLogger(__name__)
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from analysis.ratios import compute_ratios
from analysis.rules import detect_signals_from_rules
from models import Signal, TypeSignal, Gravite

PROMPT_LLM = """Tu es expert-comptable senior. Identifie les signaux QUALITATIFS supplémentaires
que les règles quantitatives ne peuvent pas détecter :
- Risques sectoriels ou conjoncturels
- Enjeux de gouvernance (succession, dirigeant, associés)
- Signaux sociaux (masse salariale, turnover)
- Opportunités patrimoniales liées au profil
- Obligations réglementaires spécifiques au secteur

Retourne UNIQUEMENT un JSON array ([] si aucun signal supplémentaire) :
[{"type":"risque|opportunite|conformite|optimisation","gravite":1|2|3,
  "code":"CODE_SNAKE","titre":"...","description":"...","levier":"..."}]"""


def detect_signals(state: dict) -> dict:
    donnees = state["donnees_financieres"]
    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

    ratios = compute_ratios(donnees)
    signaux = detect_signals_from_rules(ratios)

    # Enrichissement LLM
    context = {
        "donnees": donnees.model_dump(),
        "signaux_detectes": [s.code for s in signaux],
        "secteur": donnees.secteur_activite,
        "effectif": donnees.effectif,
        "forme_juridique": donnees.forme_juridique,
    }
    try:
        response = llm.invoke([
            SystemMessage(content=PROMPT_LLM),
            HumanMessage(content=json.dumps(context, ensure_ascii=False, default=str)),
        ])
        raw = JsonOutputParser().parse(response.content)
        for item in raw:
            if all(k in item for k in ["type", "gravite", "code", "titre", "description", "levier"]):
                signaux.append(Signal(
                    type=TypeSignal(item["type"]),
                    gravite=Gravite(item["gravite"]),
                    code=item["code"],
                    titre=item["titre"],
                    description=item["description"],
                    levier=item["levier"],
                ))
    except Exception as exc:
        logger.warning("LLM signal enrichment failed: %s", exc)
        # les règles suffisent si le LLM échoue

    signaux.sort(key=lambda s: s.gravite, reverse=True)
    return {"ratios": ratios, "signaux_detectes": signaux}
