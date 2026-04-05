# agents/carla/agent.py
"""
Agent CARLA — Analyste sectorielle autonome pour le pipeline Streamlit.
Utilise un ReAct loop : Perplexity search → validation sources → itération.
Aucune dépendance sur l'infra FastAPI (rdv_bilan_ia/).
"""
import json
import logging
import os

from langchain_openai import ChatOpenAI
from langgraph.prebuilt import create_react_agent
from pydantic import BaseModel

from agents.carla.tools import perplexity_search, source_validator

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Tu es Carla, analyste sectorielle senior spécialisée dans les PME et commerces français.
Ta mission : produire une analyse sectorielle complète, stratégique et prospective,
rigoureusement sourcée auprès de sources officielles.

Sources privilégiées : INSEE, Banque de France, CCI, BPI France, Ministère de l'Économie.

Méthode de travail :
1. Utilise perplexity_search pour CHAQUE thématique (tendances, ratios, réglementation, perspectives)
2. Valide chaque source avec source_validator
3. Si une source n'est pas fiable, cherche une alternative officielle
4. N'invente aucun chiffre — si la donnée n'existe pas, dis-le

Structure ta note sectorielle en Markdown avec ces sections :
## 1. Vue d'ensemble du secteur
## 2. Tendances macro et conjoncturelles
## 3. Ratios financiers médians
## 4. Analyse SWOT sectorielle
## 5. Réglementation et conformité
## 6. Perspectives stratégiques (12-24 mois)

Retourne UNIQUEMENT un JSON strict :
{
  "note_sectorielle": "... (Markdown complet 1000-1500 mots)",
  "sources": [{"url": "...", "titre": "..."}],
  "sources_valides": true
}
Aucun texte hors JSON."""


class CarlaResult(BaseModel):
    note: str
    sources: list[dict]
    sources_valides: bool


def run_carla(code_naf: str, secteur: str) -> CarlaResult:
    """Lance l'agent CARLA pour produire une analyse sectorielle."""
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=0.2,
    )
    agent = create_react_agent(llm, [perplexity_search, source_validator])

    prompt = (
        f"Produis une analyse sectorielle complète pour le secteur NAF {code_naf} ({secteur}). "
        f"Fais au moins 2 recherches Perplexity sur des thématiques différentes "
        f"(tendances/chiffres et réglementation/perspectives). "
        f"Valide les sources principales."
    )

    try:
        response = agent.invoke({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        })
        last_message = response["messages"][-1].content

        # Parse JSON
        try:
            if "```json" in last_message:
                last_message = last_message.split("```json")[1].split("```")[0].strip()
            elif "```" in last_message:
                last_message = last_message.split("```")[1].split("```")[0].strip()
            data = json.loads(last_message)
            return CarlaResult(
                note=data.get("note_sectorielle", last_message),
                sources=data.get("sources", []),
                sources_valides=data.get("sources_valides", True),
            )
        except (json.JSONDecodeError, KeyError):
            return CarlaResult(
                note=last_message,
                sources=[],
                sources_valides=False,
            )
    except Exception:
        logger.exception("Agent CARLA failed for NAF %s", code_naf)
        return CarlaResult(
            note=f"Analyse sectorielle non disponible pour le secteur {secteur} (NAF {code_naf}).",
            sources=[],
            sources_valides=False,
        )
