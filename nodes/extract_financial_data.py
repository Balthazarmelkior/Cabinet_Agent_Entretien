# nodes/extract_financial_data.py
import os
from pathlib import Path
from langchain_openai import ChatOpenAI


def extract_financial_data(state: dict) -> dict:
    file_path = Path(state["fichier_path"])
    file_path_n1 = state.get("fichier_path_n1")
    llm = ChatOpenAI(model=os.getenv("LLM_MODEL", "gpt-4o"), temperature=0)

    suffix = file_path.suffix.lower()

    if suffix in [".txt", ".csv", ""]:
        from parsers.fec_parser import parse_fec
        donnees = parse_fec(str(file_path), str(file_path_n1) if file_path_n1 else None)
    elif suffix == ".pdf":
        from parsers.pdf_parser import parse_pdf
        donnees = parse_pdf(str(file_path), llm)
    else:
        raise ValueError(f"Format non supporté : {suffix}. Attendu : .txt, .csv, .pdf")

    # Injection du code NAF si fourni manuellement
    if state.get("code_naf"):
        donnees.code_naf = state["code_naf"]

    return {"donnees_financieres": donnees}
