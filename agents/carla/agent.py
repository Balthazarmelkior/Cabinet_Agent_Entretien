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

SYSTEM_PROMPT = """Tu es Carla, analyste sectorielle senior et stratégiste spécialisée dans les PME et commerces français.
Ta mission : produire une analyse sectorielle complète, stratégique et prospective,
rigoureusement sourcée, PLUS une analyse SWOT du secteur et une synthèse micro-économique
avec des questions stratégiques pour préparer un rendez-vous bilan client.

Sources privilégiées : INSEE, Banque de France, CCI, BPI France, Ministère de l'Économie.

Méthode de travail :
1. Utilise perplexity_search pour CHAQUE thématique (tendances, ratios, réglementation, perspectives)
2. Valide chaque source avec source_validator
3. Si une source n'est pas fiable, cherche une alternative officielle
4. N'invente aucun chiffre — si la donnée n'existe pas, dis-le

Retourne UNIQUEMENT un JSON strict :
{
  "note_sectorielle": "... (Markdown complet structuré avec : vue d'ensemble, tendances, ratios médians, réglementation, perspectives — 1000-1500 mots)",
  "swot": {
    "forces": ["force 1 du secteur", "force 2"],
    "faiblesses": ["faiblesse 1", "faiblesse 2"],
    "opportunites": ["opportunité 1", "opportunité 2"],
    "menaces": ["menace 1", "menace 2"]
  },
  "analyse_micro": "Synthèse micro-économique : lecture des grands équilibres du secteur, marges typiques, points de fragilité structurels, facteurs clés de succès (300-500 mots)",
  "questions_rdv": [
    "Question stratégique 1 pour le dirigeant",
    "Question stratégique 2",
    "Question stratégique 3",
    "Question stratégique 4",
    "Question stratégique 5"
  ],
  "sources": [{"url": "...", "titre": "..."}],
  "sources_valides": true
}
Aucun texte hors JSON."""


class CarlaResult(BaseModel):
    note: str
    sources: list[dict]
    sources_valides: bool
    swot: dict = {}
    analyse_micro: str = ""
    questions_rdv: list[str] = []


def _parse_json(text: str) -> dict:
    """Extrait le JSON de la réponse LLM, même entouré de ```."""
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    return json.loads(text)


def run_carla(code_naf: str, secteur: str) -> CarlaResult:
    """Lance l'agent CARLA pour produire analyse sectorielle + SWOT + questions RDV."""
    llm = ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o"),
        temperature=0.2,
    )
    agent = create_react_agent(llm, [perplexity_search, source_validator])

    prompt = (
        f"Produis une analyse sectorielle complète pour le secteur NAF {code_naf} ({secteur}). "
        f"Fais au moins 2 recherches Perplexity sur des thématiques différentes "
        f"(tendances/chiffres et réglementation/perspectives). "
        f"Valide les sources principales. "
        f"Inclus l'analyse SWOT, la synthèse micro-économique et 5 questions stratégiques "
        f"pour un rendez-vous bilan avec le dirigeant."
    )

    try:
        response = agent.invoke({
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ]
        })
        last_message = response["messages"][-1].content

        try:
            data = _parse_json(last_message)
            return CarlaResult(
                note=data.get("note_sectorielle", last_message),
                sources=data.get("sources", []),
                sources_valides=data.get("sources_valides", True),
                swot=data.get("swot", {}),
                analyse_micro=data.get("analyse_micro", ""),
                questions_rdv=data.get("questions_rdv", []),
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
