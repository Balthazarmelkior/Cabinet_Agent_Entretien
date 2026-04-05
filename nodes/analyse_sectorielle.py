import asyncio
import json
import logging
import os

import httpx
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger(__name__)

TRUSTED_DOMAINS = ["insee.fr", "banque-france.fr", "cci.fr", "finess.sante.gouv.fr"]

PROMPT = """Tu es analyste sectoriel expert. Rédige une note sectorielle structurée
pour le secteur NAF {code_naf} ({secteur}).

Inclus :
- Tendances macro du secteur (croissance, emploi, investissement)
- Ratios financiers médians du secteur
- Risques et opportunités spécifiques
- Réglementation récente impactante

Source tes affirmations (INSEE, Banque de France, CCI).
Format Markdown structuré, 500-800 mots."""


async def _search_perplexity(query: str) -> dict:
    api_key = os.getenv("PERPLEXITY_API_KEY", "")
    if not api_key:
        return {"content": "", "sources": [], "sources_valides": False}

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            "https://api.perplexity.ai/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.1-sonar-large-128k-online",
                "messages": [{"role": "user", "content": query}],
                "return_citations": True,
                "search_recency_filter": "month",
                "search_domain_filter": TRUSTED_DOMAINS,
            },
        )
        response.raise_for_status()
        data = response.json()

    content = data["choices"][0]["message"]["content"]
    citations = data.get("citations", [])
    sources = [
        {"url": c if isinstance(c, str) else c.get("url", ""),
         "titre": c.get("title", "") if isinstance(c, dict) else ""}
        for c in citations
    ]
    sources_valides = any(
        any(domain in s["url"] for domain in TRUSTED_DOMAINS)
        for s in sources
    )
    return {"content": content, "sources": sources, "sources_valides": sources_valides}


def analyse_sectorielle(state: dict) -> dict:
    donnees = state["donnees_financieres"]
    code_naf = state.get("code_naf") or donnees.code_naf or "0000Z"
    secteur = donnees.secteur_activite or "Secteur non précisé"

    query = PROMPT.format(code_naf=code_naf, secteur=secteur)

    try:
        result = asyncio.run(_search_perplexity(query))
        if result["content"]:
            return {
                "note_sectorielle": result["content"],
                "sources_perplexity": result["sources"],
                "sources_valides": result["sources_valides"],
            }
    except Exception:
        logger.exception("Perplexity search failed for NAF %s", code_naf)

    # Fallback: LLM estimation
    try:
        llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0.2)
        response = llm.invoke([
            SystemMessage(content="Tu es analyste sectoriel."),
            HumanMessage(content=query),
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
