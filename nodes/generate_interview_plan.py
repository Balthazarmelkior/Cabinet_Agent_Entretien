# nodes/generate_interview_plan.py
import json
import logging
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import JsonOutputParser
from models import FicheEntretien, PointEntretien

logger = logging.getLogger(__name__)

PROMPT = """Tu es associé senior d'un cabinet d'expertise comptable.
Rédige la fiche de préparation d'entretien bilan.

PRINCIPES :
- Ton professionnel orienté conseil, chaque point ancré dans un chiffre
- Missions présentées sous l'angle BÉNÉFICE CLIENT uniquement
- Questions ouvertes qui invitent le client à parler
- Conclusion qui crée une dynamique d'action

Retourne UNIQUEMENT un JSON :
{
  "synthese_executive": "...",
  "points_vigilance": ["..."],
  "plan_entretien": [
    {"ordre":1,"theme":"...","contexte_chiffre":"...","question_ouverte":"...","mission_associee":null}
  ],
  "missions_a_proposer": [
    {"titre":"...","argumentaire_personnalise":"...","urgence":"...","benefice_attendu":"..."}
  ],
  "elements_a_recueillir": ["..."],
  "conclusion_conseillee": "..."
}
Aucun texte hors JSON."""


def generate_interview_plan(state: dict) -> dict:
    donnees  = state["donnees_financieres"]
    ratios   = state["ratios"]
    signaux  = state["signaux_detectes"]
    missions = state["missions_recommandees"]
    benchmark = state.get("benchmark")
    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0.2)

    context = {
        "client": {
            "exercice": donnees.exercice_n,
            "secteur": donnees.secteur_activite,
            "forme_juridique": donnees.forme_juridique,
            "effectif": donnees.effectif,
            "ca": donnees.chiffre_affaires.montant_n,
            "resultat_net": donnees.resultat_net.montant_n,
            "tresorerie": donnees.tresorerie_actif.montant_n,
        },
        "ratios_cles": {
            "taux_ebe": ratios.taux_ebe,
            "couverture_dettes": ratios.couverture_dettes,
            "liquidite": ratios.ratio_liquidite_generale,
            "delai_clients_jours": ratios.delai_clients_jours,
            "variation_ca": ratios.variation_ca_pct,
        },
        "benchmark_commentaire": benchmark.commentaire_global if benchmark else None,
        "signaux": [
            {"type": s.type, "gravite": s.gravite, "titre": s.titre,
             "description": s.description, "levier": s.levier}
            for s in signaux
        ],
        "missions": [
            {"id": r.mission.id, "titre": r.mission.titre,
             "argumentaire": r.argumentaire, "urgence": r.urgence,
             "benefice_client": r.mission.benefice_client}
            for r in missions
        ],
    }

    response = llm.invoke([
        SystemMessage(content=PROMPT),
        HumanMessage(content=json.dumps(context, ensure_ascii=False, default=str)),
    ])

    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    try:
        raw = JsonOutputParser().parse(content)
        fiche = FicheEntretien(
            client_exercice      = f"Exercice {donnees.exercice_n}",
            synthese_executive   = raw["synthese_executive"],
            points_vigilance     = raw.get("points_vigilance", []),
            plan_entretien       = [PointEntretien(**p) for p in raw.get("plan_entretien", [])],
            missions_a_proposer  = raw.get("missions_a_proposer", []),
            elements_a_recueillir= raw.get("elements_a_recueillir", []),
            conclusion_conseillee= raw.get("conclusion_conseillee", ""),
        )
    except Exception as exc:
        logger.warning("Interview plan parsing failed, returning fallback fiche: %s", exc)
        fiche = FicheEntretien(
            client_exercice      = f"Exercice {donnees.exercice_n}",
            synthese_executive   = "La génération automatique a échoué. Veuillez relancer l'analyse.",
            conclusion_conseillee= "",
        )

    return {"fiche_entretien": fiche}
