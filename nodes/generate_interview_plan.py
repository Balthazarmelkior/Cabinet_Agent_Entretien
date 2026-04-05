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

Tu disposes de TOUTES les données suivantes pour construire ta fiche :
- Données financières du client (CA, EBE, résultat net, trésorerie, etc.) avec variations N/N-1
- Ratios clés de rentabilité, liquidité, solvabilité
- Analyse de trésorerie détaillée (BFR, FRNG, trésorerie nette, cycle de conversion)
- Analyse sectorielle sourcée (tendances, SWOT, réglementation, perspectives)
- Benchmark sectoriel (positionnement vs médianes du secteur)
- Signaux détectés (risques, opportunités, optimisations, conformité)
- Missions recommandées avec argumentaires

PRINCIPES :
- Exploite TOUTES les données fournies, pas seulement le compte de résultat
- Ancre chaque point dans un chiffre précis (ratio, montant, variation %)
- Intègre le contexte sectoriel (tendances, réglementation) dans tes recommandations
- Analyse la trésorerie en profondeur : BFR, FRNG, cycle de conversion, pas juste le solde
- Compare systématiquement au benchmark sectoriel quand disponible
- Missions présentées sous l'angle BÉNÉFICE CLIENT uniquement
- Questions ouvertes qui invitent le client à parler de sa stratégie
- Conclusion qui crée une dynamique d'action

Retourne UNIQUEMENT un JSON :
{
  "synthese_executive": "... (paragraphe de 200-300 mots couvrant performance, trésorerie, positionnement sectoriel et perspectives)",
  "points_vigilance": ["... (chaque point avec un chiffre précis et le contexte sectoriel)"],
  "plan_entretien": [
    {"ordre":1,"theme":"...","contexte_chiffre":"... (inclure ratio, benchmark, variation)","question_ouverte":"...","mission_associee":null}
  ],
  "missions_a_proposer": [
    {"titre":"...","argumentaire_personnalise":"... (ancré dans les données du client)","urgence":"...","benefice_attendu":"..."}
  ],
  "elements_a_recueillir": ["..."],
  "conclusion_conseillee": "..."
}
Aucun texte hors JSON."""


def generate_interview_plan(state: dict) -> dict:
    donnees  = state.get("donnees_financieres")
    ratios   = state.get("ratios")
    signaux  = state.get("signaux_detectes", [])
    missions = state.get("missions_recommandees", [])
    benchmark = state.get("benchmark")

    if not donnees or not ratios:
        logger.error("generate_interview_plan: données ou ratios manquants")
        return {"fiche_entretien": FicheEntretien(
            client_exercice="Données manquantes",
            synthese_executive="La génération a échoué : données financières ou ratios manquants.",
            conclusion_conseillee="Relancer l'analyse.",
        )}

    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0.2)

    def _n1(poste):
        return poste.montant_n1

    note_sectorielle = state.get("note_sectorielle", "")

    context = {
        "client": {
            "exercice": donnees.exercice_n,
            "secteur": donnees.secteur_activite,
            "forme_juridique": donnees.forme_juridique,
            "effectif": donnees.effectif,
            "ca": donnees.chiffre_affaires.montant_n,
            "ca_n1": _n1(donnees.chiffre_affaires),
            "variation_ca_pct": donnees.chiffre_affaires.variation_pct,
            "resultat_net": donnees.resultat_net.montant_n,
            "resultat_net_n1": _n1(donnees.resultat_net),
            "variation_resultat_pct": donnees.resultat_net.variation_pct,
            "ebe": donnees.ebe.montant_n,
            "ebe_n1": _n1(donnees.ebe),
            "variation_ebe_pct": donnees.ebe.variation_pct,
            "tresorerie": donnees.tresorerie_actif.montant_n,
            "tresorerie_n1": _n1(donnees.tresorerie_actif),
            "charges_personnel": donnees.charges_personnel.montant_n,
            "charges_personnel_n1": _n1(donnees.charges_personnel),
            "dettes_financieres": donnees.dettes_financieres.montant_n,
            "dettes_financieres_n1": _n1(donnees.dettes_financieres),
        },
        "ratios_cles": {
            "taux_ebe": ratios.taux_ebe,
            "couverture_dettes": ratios.couverture_dettes,
            "liquidite": ratios.ratio_liquidite_generale,
            "delai_clients_jours": ratios.delai_clients_jours,
            "variation_ca": ratios.variation_ca_pct,
        },
        "tresorerie_detaillee": {
            "bfr": ratios.bfr,
            "frng": ratios.frng,
            "tresorerie_nette": ratios.tresorerie_nette,
            "tresorerie_nette_jours_ca": ratios.tresorerie_nette_jours_ca,
            "cycle_conversion_jours": ratios.cycle_conversion_jours,
            "delai_clients_jours": ratios.delai_clients_jours,
            "delai_fournisseurs_jours": ratios.delai_fournisseurs_jours,
            "rotation_stocks_jours": ratios.rotation_stocks_jours,
            "bfr_n1": ratios.bfr_n1,
            "frng_n1": ratios.frng_n1,
            "tresorerie_nette_n1": ratios.tresorerie_nette_n1,
        },
        "analyse_sectorielle": note_sectorielle[:3000] if note_sectorielle else None,
        "swot_sectoriel": state.get("swot"),
        "analyse_micro": state.get("analyse_micro", "")[:1500] if state.get("analyse_micro") else None,
        "questions_strategiques_carla": state.get("questions_rdv", []),
        "benchmark_commentaire": benchmark.commentaire_global if benchmark else None,
        "benchmark_ratios": [
            {"libelle": r.libelle, "valeur_client": r.valeur_client,
             "mediane_secteur": r.mediane_secteur, "interpretation": r.interpretation}
            for r in (benchmark.ratios if benchmark else [])
        ],
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
