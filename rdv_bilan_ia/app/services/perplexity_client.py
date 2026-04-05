import logging
from typing import Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PerplexitySource(BaseModel):
    url: str
    titre: str = ""


class PerplexityResponse(BaseModel):
    content: str
    sources: list[PerplexitySource]
    sources_valides: bool = True


class PerplexityClient:
    BASE_URL = "https://api.perplexity.ai"
    MODEL = "sonar-pro"

    async def search(
        self,
        query: str,
        search_domain_filter: Optional[list[str]] = None,
        **kwargs,
    ) -> PerplexityResponse:
        from rdv_bilan_ia.app.config import settings

        payload = {
            "model": self.MODEL,
            "messages": [{"role": "user", "content": query}],
            "return_citations": True,
            "search_recency_filter": "month",
        }
        if search_domain_filter:
            payload["search_domain_filter"] = search_domain_filter
        payload.update(kwargs)

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.PERPLEXITY_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        content = data["choices"][0]["message"]["content"]
        citations = data.get("citations", [])

        sources = [
            PerplexitySource(
                url=c if isinstance(c, str) else c.get("url", ""),
                titre=c.get("title", "") if isinstance(c, dict) else "",
            )
            for c in citations
        ]

        # Validate sources: check for known reliable domains
        trusted_domains = {"insee.fr", "banque-france.fr", "finess.sante.gouv.fr"}
        sources_valides = any(
            any(domain in s.url for domain in trusted_domains) for s in sources
        )

        return PerplexityResponse(
            content=content,
            sources=sources,
            sources_valides=sources_valides,
        )


perplexity_client = PerplexityClient()
