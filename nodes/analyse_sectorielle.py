# nodes/analyse_sectorielle.py
"""
Node d'analyse sectorielle — utilise l'agent CARLA (ReAct loop)
pour produire une note sectorielle sourcée via Perplexity + validation.
Fallback sur LLM si CARLA échoue.
"""
import logging
import os

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)


def analyse_sectorielle(state: dict) -> dict:
    donnees = state["donnees_financieres"]
    code_naf = state.get("code_naf") or donnees.code_naf or "0000Z"
    secteur = donnees.secteur_activite or "Secteur non précisé"

    # Agent CARLA : ReAct loop Perplexity + validation sources
    if os.getenv("PERPLEXITY_API_KEY", ""):
        try:
            from agents.carla.agent import run_carla
            result = run_carla(code_naf=code_naf, secteur=secteur)
            if result.note and "non disponible" not in result.note:
                return {
                    "note_sectorielle": result.note,
                    "sources_perplexity": result.sources,
                    "sources_valides": result.sources_valides,
                }
        except Exception:
            logger.exception("Agent CARLA failed for NAF %s", code_naf)

    # Fallback: LLM estimation (sans Perplexity)
    try:
        llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0.2)
        prompt = (
            f"Tu es analyste sectoriel senior. Rédige une note sectorielle complète "
            f"pour le secteur NAF {code_naf} ({secteur}). "
            f"Inclus : vue d'ensemble, tendances, ratios médians, SWOT, "
            f"réglementation, perspectives 12-24 mois. "
            f"Format Markdown structuré, 1000-1500 mots."
        )
        response = llm.invoke([
            SystemMessage(content="Tu es analyste sectoriel."),
            HumanMessage(content=prompt),
        ])
        return {
            "note_sectorielle": response.content,
            "sources_perplexity": [],
            "sources_valides": False,
        }
    except Exception:
        logger.exception("LLM fallback also failed")
        return {
            "note_sectorielle": "Analyse sectorielle non disponible.",
            "sources_perplexity": [],
            "sources_valides": False,
        }
