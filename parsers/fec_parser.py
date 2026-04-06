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
    "tresorerie_actif":       ["50", "51", "52", "53"],
    "capitaux_propres":       ["10", "11", "12", "13", "14"],
    "dettes_financieres":     ["16"],
    "dettes_fournisseurs":    ["40"],
}


def _somme(df: pd.DataFrame, racines: list[str]) -> float:
    mask = df["CompteNum"].str.startswith(tuple(racines))
    return float(df[mask]["Montant"].sum())


def _load_df(fec_path: str) -> pd.DataFrame:
    df = pd.read_csv(
        fec_path,
        sep="\t",
        encoding="latin1",
        dtype={"CompteNum": str, "EcritureDate": str, "Montant": str},
        decimal=","
    )

    if "Montant" not in df.columns:
        for col in ("Debit", "Credit"):
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
        credit_normal = df["CompteNum"].str.match(r"^(1|40|7)")
        df["Montant"] = df["Debit"] - df["Credit"]
        df.loc[credit_normal, "Montant"] = (
            df.loc[credit_normal, "Credit"] - df.loc[credit_normal, "Debit"]
        )
    else:
        df["Montant"] = (
            df["Montant"]
            .str.replace(r"\s", "", regex=True)
            .str.replace(",", ".")
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0)
        )

    return df


def _extract_sums(df: pd.DataFrame) -> dict:
    ca           = _somme(df, MAPPING_PCG["chiffre_affaires"])
    achats       = _somme(df, MAPPING_PCG["achats_consommes"])
    charges_ext  = _somme(df, MAPPING_PCG["charges_externes"])
    charges_pers = _somme(df, MAPPING_PCG["charges_personnel"])
    ebe_val      = ca - achats - charges_ext - charges_pers

    try:
        exercice = int(df["EcritureDate"].str[:4].mode()[0])
    except Exception:
        exercice = 0

    return {
        "exercice":              exercice,
        "chiffre_affaires":      ca,
        "achats_consommes":      achats,
        "charges_externes":      charges_ext,
        "charges_personnel":     charges_pers,
        "ebe":                   ebe_val,
        "resultat_exploitation": _somme(df, MAPPING_PCG["resultat_exploitation"]),
        "resultat_net":          _somme(df, ["7"]) - _somme(df, ["6"]),
        "immobilisations_nettes":_somme(df, MAPPING_PCG["immobilisations_nettes"]),
        "stocks":                _somme(df, MAPPING_PCG["stocks"]),
        "creances_clients":      _somme(df, MAPPING_PCG["creances_clients"]),
        "tresorerie_actif":      _somme(df, MAPPING_PCG["tresorerie_actif"]),
        "capitaux_propres":      _somme(df, MAPPING_PCG["capitaux_propres"]),
        "dettes_financieres":    _somme(df, MAPPING_PCG["dettes_financieres"]),
        "dettes_fournisseurs":   _somme(df, MAPPING_PCG["dettes_fournisseurs"]),
    }


def _variation(n: float, n1: float | None) -> float | None:
    if n1 is None or n1 == 0:
        return None
    return round((n - n1) / abs(n1) * 100, 1)


def _poste(libelle: str, n: float, n1: float | None = None) -> PosteComptable:
    return PosteComptable(
        libelle=libelle,
        montant_n=round(n, 2),
        montant_n1=round(n1, 2) if n1 is not None else None,
        variation_pct=_variation(n, n1),
    )


def parse_fec(fec_path: str, fec_path_n1: str | None = None, anonymize: bool = False) -> DonneesFinancieres:
    df = _load_df(fec_path)
    if anonymize:
        from parsers.anonymizer import anonymize_fec_df
        df = anonymize_fec_df(df)
    sums = _extract_sums(df)

    sums_n1 = None
    if fec_path_n1:
        df_n1 = _load_df(fec_path_n1)
        if anonymize:
            df_n1 = anonymize_fec_df(df_n1)
        sums_n1 = _extract_sums(df_n1)

    def n1(key):
        return sums_n1[key] if sums_n1 else None

    return DonneesFinancieres(
        exercice_n            = sums["exercice"],
        chiffre_affaires      = _poste("Chiffre d'affaires",     sums["chiffre_affaires"],      n1("chiffre_affaires")),
        achats_consommes      = _poste("Achats consommés",        sums["achats_consommes"],      n1("achats_consommes")),
        charges_externes      = _poste("Charges externes",        sums["charges_externes"],      n1("charges_externes")),
        charges_personnel     = _poste("Charges de personnel",    sums["charges_personnel"],     n1("charges_personnel")),
        ebe                   = _poste("EBE",                     sums["ebe"],                   n1("ebe")),
        resultat_exploitation = _poste("Résultat exploitation",   sums["resultat_exploitation"], n1("resultat_exploitation")),
        resultat_net          = _poste("Résultat net",            sums["resultat_net"],          n1("resultat_net")),
        immobilisations_nettes= _poste("Immobilisations nettes",  sums["immobilisations_nettes"],n1("immobilisations_nettes")),
        stocks                = _poste("Stocks",                  sums["stocks"],                n1("stocks")),
        creances_clients      = _poste("Créances clients",        sums["creances_clients"],      n1("creances_clients")),
        tresorerie_actif      = _poste("Trésorerie",              sums["tresorerie_actif"],      n1("tresorerie_actif")),
        capitaux_propres      = _poste("Capitaux propres",        sums["capitaux_propres"],      n1("capitaux_propres")),
        dettes_financieres    = _poste("Dettes financières",      sums["dettes_financieres"],    n1("dettes_financieres")),
        dettes_fournisseurs   = _poste("Dettes fournisseurs",     sums["dettes_fournisseurs"],   n1("dettes_fournisseurs")),
    )


def extraire_tresorerie_mensuelle(fec_path: str, df: "pd.DataFrame | None" = None) -> list["SoldeMensuel"]:
    """Extrait les soldes mensuels cumulés des comptes de trésorerie (50-53)."""
    from models import SoldeMensuel

    if df is None:
        df = _load_df(fec_path)
    mask = df["CompteNum"].str.startswith(("50", "51", "52", "53"))
    df_treso = df[mask].copy()

    if df_treso.empty:
        return []

    df_treso["mois"] = df_treso["EcritureDate"].str[:6].apply(
        lambda x: f"{x[:4]}-{x[4:6]}"
    )

    if "Montant" not in df.columns or df_treso["Montant"].isna().all():
        df_treso["flux"] = df_treso["Debit"] - df_treso["Credit"]
    else:
        df_treso["flux"] = df_treso["Montant"]

    mensuel = df_treso.groupby("mois")["flux"].sum().sort_index()

    soldes = []
    cumul = 0.0
    for mois, flux in mensuel.items():
        cumul += flux
        soldes.append(SoldeMensuel(mois=str(mois), solde=round(cumul, 2)))

    return soldes


def extraire_ca_mensuel(fec_path: str, df: "pd.DataFrame | None" = None) -> list["SoldeMensuel"]:
    """Extrait le CA cumulé mois par mois depuis les comptes 70."""
    from models import SoldeMensuel

    if df is None:
        df = _load_df(fec_path)
    mask = df["CompteNum"].str.startswith("70")
    df_ca = df[mask].copy()

    if df_ca.empty:
        return []

    df_ca["mois"] = df_ca["EcritureDate"].str[:6].apply(
        lambda x: f"{x[:4]}-{x[4:6]}"
    )

    # Comptes 70 matchent ^7 → _load_df calcule Credit - Debit → Montant positif pour le CA
    mensuel = df_ca.groupby("mois")["Montant"].sum().sort_index()

    soldes = []
    cumul = 0.0
    for mois, ca in mensuel.items():
        cumul += ca
        soldes.append(SoldeMensuel(mois=str(mois), solde=round(cumul, 2)))

    return soldes
