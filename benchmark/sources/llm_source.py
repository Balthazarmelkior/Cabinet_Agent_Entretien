# benchmark/sources/llm_source.py
import json
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from benchmark.base import BenchmarkSource, RatiosBruts

PROMPT = """Tu es expert en analyse sectorielle française (Banque de France, INSEE, observatoires).
Fournis les ratios financiers de référence pour ce secteur.
Sois précis — donne des valeurs chiffrées réalistes issues des données sectorielles françaises.

Retourne UNIQUEMENT un JSON :
{
  "libelle_secteur": "...",
  "annee_reference": 2023,
  "ratios": {
    "taux_ebe":                {"mediane": 0.0, "q1": 0.0, "q3": 0.0},
    "taux_resultat_net":       {"mediane": 0.0, "q1": 0.0, "q3": 0.0},
    "autonomie_financiere":    {"mediane": 0.0, "q1": 0.0, "q3": 0.0},
    "couverture_dettes":       {"mediane": 0.0, "q1": 0.0, "q3": 0.0},
    "delai_clients_jours":     {"mediane": 0.0, "q1": 0.0, "q3": 0.0},
    "delai_fournisseurs_jours":{"mediane": 0.0, "q1": 0.0, "q3": 0.0},
    "ratio_liquidite_generale":{"mediane": 0.0, "q1": 0.0, "q3": 0.0}
  }
}
Aucun texte hors JSON."""

RATIO_KEYS = [
    "taux_ebe", "taux_resultat_net", "autonomie_financiere", "couverture_dettes",
    "delai_clients_jours", "delai_fournisseurs_jours", "ratio_liquidite_generale",
]


class LLMSource(BenchmarkSource):

    def __init__(self, llm: ChatOpenAI):
        self.llm = llm

    def fetch(self, code_naf: str, annee: int, tranche_ca: str) -> RatiosBruts | None:
        context = {"code_naf": code_naf, "annee": annee, "taille": tranche_ca}
        try:
            response = self.llm.invoke([
                SystemMessage(content=PROMPT),
                HumanMessage(content=json.dumps(context)),
            ])
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            raw = JsonOutputParser().parse(content)
            ratios = raw.get("ratios", {})
            return RatiosBruts(
                source="Estimation LLM (données sectorielles françaises)",
                annee_reference=int(raw.get("annee_reference", annee - 1)),
                libelle_secteur=raw.get("libelle_secteur", f"Secteur {code_naf}"),
                fiabilite=3,
                **{k: ratios.get(k) for k in RATIO_KEYS},
            )
        except Exception:
            return None
