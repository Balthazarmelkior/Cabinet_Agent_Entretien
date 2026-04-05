# agents/carla/tools.py
import os
from urllib.parse import urlparse

import httpx
from langchain_core.tools import tool

from utils.async_helper import run_async

RELIABLE_DOMAINS = {
    "insee.fr",
    "banque-france.fr",
    "finess.sante.gouv.fr",
    "cci.fr",
    "bpifrance.fr",
    "economie.gouv.fr",
    "travail-emploi.gouv.fr",
}


@tool
def perplexity_search(query: str) -> str:
    """Recherche sectorielle en ligne via Perplexity.
    Retourne le contenu trouvé avec les sources citées.
    Input: requête de recherche en français."""
    import asyncio

    async def _call():
        api_key = os.getenv("PERPLEXITY_API_KEY", "")
        if not api_key:
            return "ERREUR: PERPLEXITY_API_KEY non configurée."

        async with httpx.AsyncClient(timeout=90.0) as client:
            response = await client.post(
                "https://api.perplexity.ai/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "sonar-pro",
                    "messages": [{"role": "user", "content": query}],
                    "return_citations": True,
                },
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])
        sources = [c if isinstance(c, str) else c.get("url", "") for c in citations]
        sources_str = "\n".join(f"- {s}" for s in sources[:10])
        return f"{content}\n\nSources:\n{sources_str}"

    return run_async(_call())


@tool
def source_validator(url: str) -> str:
    """Vérifie si une URL provient d'une source officielle fiable.
    Retourne 'fiable' ou 'non-fiable'. Input: URL à valider."""
    try:
        domain = urlparse(url).netloc.replace("www.", "")
    except Exception:
        domain = url

    if any(reliable in domain for reliable in RELIABLE_DOMAINS):
        return f"fiable (domaine officiel: {domain})"
    return f"non-fiable (domaine non reconnu: {domain}) — vérification manuelle recommandée"
