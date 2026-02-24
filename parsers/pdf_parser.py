# parsers/pdf_parser.py
import json
import pdfplumber
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from models import DonneesFinancieres, PosteComptable

SYSTEM_PROMPT = """Tu es expert-comptable français. On te donne le texte brut d'un bilan comptable ou d'une liasse fiscale.
Extrais les données et retourne UNIQUEMENT un JSON valide :
{
  "exercice_n": 2023,
  "secteur_activite": null,
  "effectif": null,
  "forme_juridique": null,
  "chiffre_affaires":      {"montant_n": 0, "montant_n1": null},
  "achats_consommes":      {"montant_n": 0, "montant_n1": null},
  "charges_externes":      {"montant_n": 0, "montant_n1": null},
  "charges_personnel":     {"montant_n": 0, "montant_n1": null},
  "ebe":                   {"montant_n": 0, "montant_n1": null},
  "resultat_exploitation": {"montant_n": 0, "montant_n1": null},
  "resultat_net":          {"montant_n": 0, "montant_n1": null},
  "immobilisations_nettes":{"montant_n": 0, "montant_n1": null},
  "stocks":                {"montant_n": 0, "montant_n1": null},
  "creances_clients":      {"montant_n": 0, "montant_n1": null},
  "tresorerie_actif":      {"montant_n": 0, "montant_n1": null},
  "capitaux_propres":      {"montant_n": 0, "montant_n1": null},
  "dettes_financieres":    {"montant_n": 0, "montant_n1": null},
  "dettes_fournisseurs":   {"montant_n": 0, "montant_n1": null}
}
Montants en euros entiers. null si non trouvé. Aucun texte hors JSON."""

LIBELLES = {
    "chiffre_affaires":       "Chiffre d'affaires",
    "achats_consommes":       "Achats consommés",
    "charges_externes":       "Charges externes",
    "charges_personnel":      "Charges de personnel",
    "ebe":                    "EBE",
    "resultat_exploitation":  "Résultat exploitation",
    "resultat_net":           "Résultat net",
    "immobilisations_nettes": "Immobilisations nettes",
    "stocks":                 "Stocks",
    "creances_clients":       "Créances clients",
    "tresorerie_actif":       "Trésorerie",
    "capitaux_propres":       "Capitaux propres",
    "dettes_financieres":     "Dettes financières",
    "dettes_fournisseurs":    "Dettes fournisseurs",
}


def _extract_text(pdf_path: str, max_chars: int = 14_000) -> str:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text(x_tolerance=3, y_tolerance=3)
            if text:
                pages.append(text)
    full = "\n\n--- PAGE ---\n\n".join(pages)
    return full[:max_chars] + ("\n[... tronqué ...]" if len(full) > max_chars else "")


def parse_pdf(pdf_path: str, llm: ChatOpenAI) -> DonneesFinancieres:
    raw_text = _extract_text(pdf_path)

    response = llm.invoke([
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"Bilan :\n\n{raw_text}"),
    ])

    # Nettoyer les éventuels backticks markdown
    content = response.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]

    data = json.loads(content)

    def to_poste(key: str) -> PosteComptable:
        d = data.get(key, {}) or {}
        n  = d.get("montant_n")  or 0
        n1 = d.get("montant_n1")

        vp = None
        if n1 and n1 != 0:
            vp = round((n - n1) / abs(n1) * 100, 1)

        return PosteComptable(
            libelle=LIBELLES.get(key, key),
            montant_n=float(n),
            montant_n1=float(n1) if n1 is not None else None,
            variation_pct=vp,
        )

    return DonneesFinancieres(
        exercice_n            = int(data.get("exercice_n") or 0),
        secteur_activite      = data.get("secteur_activite"),
        effectif              = data.get("effectif"),
        forme_juridique       = data.get("forme_juridique"),
        chiffre_affaires      = to_poste("chiffre_affaires"),
        achats_consommes      = to_poste("achats_consommes"),
        charges_externes      = to_poste("charges_externes"),
        charges_personnel     = to_poste("charges_personnel"),
        ebe                   = to_poste("ebe"),
        resultat_exploitation = to_poste("resultat_exploitation"),
        resultat_net          = to_poste("resultat_net"),
        immobilisations_nettes= to_poste("immobilisations_nettes"),
        stocks                = to_poste("stocks"),
        creances_clients      = to_poste("creances_clients"),
        tresorerie_actif      = to_poste("tresorerie_actif"),
        capitaux_propres      = to_poste("capitaux_propres"),
        dettes_financieres    = to_poste("dettes_financieres"),
        dettes_fournisseurs   = to_poste("dettes_fournisseurs"),
    )
