# parsers/fec_parser.py
import pandas as pd
from models import DonneesFinancieres, PosteComptable

MAPPING_PCG = {
    "chiffre_affaires":       ["70"],
    "production_stockee":     ["71", "72"],
    "achats_consommes":       ["60"],
    "charges_externes":       ["61", "62"],
    "charges_personnel":      ["63", "64"],
    "resultat_exploitation":  ["67", "68"],
    "immobilisations_nettes": ["20", "21", "22", "23"],
    "stocks":                 ["31", "32", "33", "34", "35", "37"],
    "creances_clients":       ["41"],
    "tresorerie_actif":       ["51", "52", "53"],
    "capitaux_propres":       ["10", "11", "12", "13", "14"],
    "dettes_financieres":     ["16"],
    "dettes_fournisseurs":    ["40"],
}


def _somme(df: pd.DataFrame, racines: list[str]) -> float:
    mask = df["CompteNum"].str.startswith(tuple(racines))
    return float(df[mask]["Montant"].sum())


def _poste(df: pd.DataFrame, racines: list[str], libelle: str) -> PosteComptable:
    return PosteComptable(libelle=libelle, montant_n=round(_somme(df, racines), 2))


def parse_fec(fec_path: str) -> DonneesFinancieres:
    df = pd.read_csv(
        fec_path,
        sep="\t",
        encoding="latin1",
        dtype={"CompteNum": str, "Montant": str},
        decimal=","
    )

    df["Montant"] = (
        df["Montant"]
        .str.replace(r"\s", "", regex=True)
        .str.replace(",", ".")
        .pipe(pd.to_numeric, errors="coerce")
        .fillna(0)
    )

    ca           = _somme(df, MAPPING_PCG["chiffre_affaires"])
    achats       = _somme(df, MAPPING_PCG["achats_consommes"])
    charges_ext  = _somme(df, MAPPING_PCG["charges_externes"])
    charges_pers = _somme(df, MAPPING_PCG["charges_personnel"])
    ebe_val      = ca - achats - charges_ext - charges_pers

    try:
        exercice = int(df["EcritureDate"].str[:4].mode()[0])
    except Exception:
        exercice = 0

    return DonneesFinancieres(
        exercice_n           = exercice,
        chiffre_affaires     = PosteComptable(libelle="Chiffre d'affaires",     montant_n=round(ca, 2)),
        achats_consommes     = PosteComptable(libelle="Achats consommés",        montant_n=round(achats, 2)),
        charges_externes     = PosteComptable(libelle="Charges externes",        montant_n=round(charges_ext, 2)),
        charges_personnel    = PosteComptable(libelle="Charges de personnel",    montant_n=round(charges_pers, 2)),
        ebe                  = PosteComptable(libelle="EBE",                     montant_n=round(ebe_val, 2)),
        resultat_exploitation= _poste(df, MAPPING_PCG["resultat_exploitation"],  "Résultat exploitation"),
        resultat_net         = _poste(df, ["12"],                                "Résultat net"),
        immobilisations_nettes=_poste(df, MAPPING_PCG["immobilisations_nettes"],"Immobilisations nettes"),
        stocks               = _poste(df, MAPPING_PCG["stocks"],                 "Stocks"),
        creances_clients     = _poste(df, MAPPING_PCG["creances_clients"],       "Créances clients"),
        tresorerie_actif     = _poste(df, MAPPING_PCG["tresorerie_actif"],       "Trésorerie"),
        capitaux_propres     = _poste(df, MAPPING_PCG["capitaux_propres"],       "Capitaux propres"),
        dettes_financieres   = _poste(df, MAPPING_PCG["dettes_financieres"],     "Dettes financières"),
        dettes_fournisseurs  = _poste(df, MAPPING_PCG["dettes_fournisseurs"],    "Dettes fournisseurs"),
    )
