# nodes/extract_financial_data.py
import os
from pathlib import Path
from langchain_openai import ChatOpenAI


def extract_financial_data(state: dict) -> dict:
    file_path = Path(state["fichier_path"])
    file_path_n1 = state.get("fichier_path_n1")
    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

    suffix = file_path.suffix.lower()
    anonymize = state.get("anonymize", False)

    if suffix in [".txt", ".csv", ""]:
        from parsers.fec_parser import parse_fec, extraire_tresorerie_mensuelle, extraire_ca_mensuel, _load_df
        donnees = parse_fec(str(file_path), str(file_path_n1) if file_path_n1 else None, anonymize=anonymize)

        # Extraction des soldes mensuels (df partagé pour éviter le double chargement)
        df_n = _load_df(str(file_path))
        soldes_mensuels = extraire_tresorerie_mensuelle(str(file_path), df=df_n)
        ca_mensuel_n = extraire_ca_mensuel(str(file_path), df=df_n)
        ca_mensuel_n1 = extraire_ca_mensuel(str(file_path_n1)) if file_path_n1 else []
    elif suffix == ".pdf":
        from parsers.pdf_parser import parse_pdf
        donnees = parse_pdf(str(file_path), llm, anonymize=anonymize)
        soldes_mensuels = []
        ca_mensuel_n = []
        ca_mensuel_n1 = []
    else:
        raise ValueError(f"Format non supporté : {suffix}. Attendu : .txt, .csv, .pdf")

    # Injection du code NAF si fourni manuellement
    if state.get("code_naf"):
        donnees.code_naf = state["code_naf"]

    return {
        "donnees_financieres": donnees,
        "soldes_mensuels": soldes_mensuels,
        "ca_mensuel_n": ca_mensuel_n,
        "ca_mensuel_n1": ca_mensuel_n1,
    }
