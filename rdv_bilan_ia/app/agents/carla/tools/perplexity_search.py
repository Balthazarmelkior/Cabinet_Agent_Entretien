from langchain_core.tools import BaseTool

TRUSTED_DOMAINS = ["insee.fr", "banque-france.fr", "finess.sante.gouv.fr", "cci.fr"]


class PerplexitySearchTool(BaseTool):
    name: str = "perplexity_search"
    description: str = (
        "Recherche sectorielle sourcée via Perplexity. "
        "Utilise uniquement des sources officielles (INSEE, Banque de France, CCI). "
        "Input: requête de recherche sectorielle en français."
    )

    async def _arun(self, query: str) -> str:
        from rdv_bilan_ia.app.services.perplexity_client import perplexity_client

        result = await perplexity_client.search(query=query)
        sources_str = "\n".join(f"- {s.url}" for s in result.sources[:5])
        return f"{result.content}\n\nSources:\n{sources_str}"

    def _run(self, query: str) -> str:
        raise NotImplementedError("Use async version")
