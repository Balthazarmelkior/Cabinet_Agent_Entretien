# graph.py
from __future__ import annotations

from typing import TypedDict, Optional
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv

load_dotenv()

from models import (
    DonneesFinancieres, FicheEntretien, BenchmarkSectoriel,
    Signal, MissionRecommandee
)
from analysis.ratios import Ratios


class BillanState(TypedDict, total=False):
    # ── Inputs ────────────────────────────────────────────────────────────────
    fichier_path: str
    catalogue_path: str
    code_naf: str

    # ── Intermédiaires ────────────────────────────────────────────────────────
    donnees_financieres: Optional[DonneesFinancieres]
    ratios: Optional[Ratios]
    signaux_detectes: Optional[list[Signal]]
    benchmark: Optional[BenchmarkSectoriel]
    missions_recommandees: Optional[list[MissionRecommandee]]

    # ── Output ────────────────────────────────────────────────────────────────
    fiche_entretien: Optional[FicheEntretien]


def build_graph() -> any:
    from nodes.extract_financial_data import extract_financial_data
    from nodes.detect_signals import detect_signals
    from nodes.benchmark_sectoriel import benchmark_sectoriel
    from nodes.match_missions import match_missions
    from nodes.generate_interview_plan import generate_interview_plan

    builder = StateGraph(BillanState)

    builder.add_node("extract_financial_data", extract_financial_data)
    builder.add_node("detect_signals",         detect_signals)
    builder.add_node("benchmark_sectoriel",    benchmark_sectoriel)
    builder.add_node("match_missions",         match_missions)
    builder.add_node("generate_interview_plan",generate_interview_plan)

    # Extraction → parallèle (signaux + benchmark)
    builder.set_entry_point("extract_financial_data")
    builder.add_edge("extract_financial_data", "detect_signals")
    builder.add_edge("extract_financial_data", "benchmark_sectoriel")

    # Convergence → matching → fiche
    builder.add_edge("detect_signals",      "match_missions")
    builder.add_edge("benchmark_sectoriel", "match_missions")
    builder.add_edge("match_missions",      "generate_interview_plan")
    builder.add_edge("generate_interview_plan", END)

    return builder.compile()


def prepare_entretien_bilan(
    fichier_path: str,
    catalogue_path: str,
    code_naf: str,
) -> BillanState:
    """Point d'entrée principal."""
    graph = build_graph()
    return graph.invoke({
        "fichier_path":   fichier_path,
        "catalogue_path": catalogue_path,
        "code_naf":       code_naf.upper().strip(),
    })
