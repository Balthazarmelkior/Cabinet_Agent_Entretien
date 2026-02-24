# nodes/benchmark_sectoriel.py
import os
from langchain_openai import ChatOpenAI
from benchmark.orchestrator import BenchmarkOrchestrator
from benchmark.sources.bdf import BanqueDeFranceSource
from benchmark.sources.insee import InseeSource
from benchmark.sources.llm_source import LLMSource


def benchmark_sectoriel(state: dict) -> dict:
    donnees = state["donnees_financieres"]
    ratios  = state["ratios"]
    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

    orchestrator = BenchmarkOrchestrator(
        bdf   = BanqueDeFranceSource(cache_dir=os.getenv("BDF_CACHE_DIR", "data/bdf_cache")),
        insee = InseeSource(api_key=os.getenv("INSEE_API_KEY", "")),
        llm   = LLMSource(llm),
    )

    benchmark = orchestrator.build(
        ratios_client    = ratios,
        code_naf         = state.get("code_naf") or donnees.code_naf or "0000Z",
        secteur_activite = donnees.secteur_activite or "Secteur non précisé",
        ca               = donnees.chiffre_affaires.montant_n,
        annee            = donnees.exercice_n,
    )

    return {"benchmark": benchmark}
