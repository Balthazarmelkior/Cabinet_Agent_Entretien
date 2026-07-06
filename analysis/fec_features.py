# analysis/fec_features.py
"""Extraction d'indicateurs fins depuis le FEC (débit/crédit par compte)."""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


def _sums_by_account(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """Retourne (debit_par_compte, credit_par_compte) agrégés par CompteNum."""
    comptes = df["CompteNum"].astype(str)
    if "Debit" in df.columns and "Credit" in df.columns:
        debit = pd.to_numeric(df["Debit"], errors="coerce").fillna(0)
        credit = pd.to_numeric(df["Credit"], errors="coerce").fillna(0)
    elif "Montant" in df.columns and "Sens" in df.columns:
        montant = pd.to_numeric(df["Montant"], errors="coerce").fillna(0)
        sens = df["Sens"].astype(str).str.upper().str[0]   # 'D'/'C'
        debit = montant.where(sens == "D", 0.0)
        credit = montant.where(sens == "C", 0.0)
    else:
        raise ValueError(
            "FEC illisible : colonnes attendues 'Debit'+'Credit' ou 'Montant'+'Sens'."
        )
    d = debit.groupby(comptes).sum().to_dict()
    c = credit.groupby(comptes).sum().to_dict()
    return {k: float(v) for k, v in d.items()}, {k: float(v) for k, v in c.items()}


class IndicateursFEC(BaseModel):
    debit_n: dict[str, float] = Field(default_factory=dict)
    credit_n: dict[str, float] = Field(default_factory=dict)
    debit_n1: dict[str, float] = Field(default_factory=dict)
    credit_n1: dict[str, float] = Field(default_factory=dict)
    ca_n: float = 0.0
    comptes: list[str] = Field(default_factory=list)
    paires_tiers: list[list[str]] = Field(default_factory=list)
    nb_ecritures_par_compte: dict[str, int] = Field(default_factory=dict)
    journaux: list[str] = Field(default_factory=list)
    mois: list[str] = Field(default_factory=list)

    def _agg(self, prefixes: list[str], *, n1: bool) -> tuple[float, float]:
        debit = self.debit_n1 if n1 else self.debit_n
        credit = self.credit_n1 if n1 else self.credit_n
        pref = tuple(prefixes)
        d = sum(v for k, v in debit.items() if k.startswith(pref))
        c = sum(v for k, v in credit.items() if k.startswith(pref))
        return d, c

    def solde(self, prefixes: list[str], sens: str = "D", *, n1: bool = False) -> float:
        if sens not in ("D", "C"):
            raise ValueError(f"sens invalide: {sens!r} (attendu 'D' ou 'C')")
        d, c = self._agg(prefixes, n1=n1)
        return (d - c) if sens == "D" else (c - d)

    def mouvement(self, prefixes: list[str], *, n1: bool = False) -> float:
        d, c = self._agg(prefixes, n1=n1)
        return d + c

    def variation_pct(self, prefixes: list[str], sens: str = "D") -> float | None:
        n1 = self.solde(prefixes, sens, n1=True)
        if not n1:
            return None
        n = self.solde(prefixes, sens)
        return round((n - n1) / abs(n1) * 100, 1)

    def ratio_pct(self, num: list[str], den: list[str], sens_num: str = "D", sens_den: str = "D") -> float | None:
        d = self.solde(den, sens_den)
        if not d:
            return None
        return round(self.solde(num, sens_num) / d * 100, 1)

    def nb_comptes(self, prefixes: list[str]) -> int:
        pref = tuple(prefixes)
        return sum(1 for c in self.comptes if c.startswith(pref))

    def nb_tiers(self, prefixes: list[str]) -> int:
        """Tiers distincts sous le(s) préfixe(s) : CompAuxNum si renseigné, sinon le
        sous-compte lui-même (repli quand la compta auxiliaire n'est pas tenue)."""
        pref = tuple(prefixes)
        keys = set()
        for compte, aux in self.paires_tiers:
            if compte.startswith(pref):
                keys.add(aux if aux else compte)
        return len(keys)

    def nb_ecritures(self, prefixes: list[str]) -> int:
        pref = tuple(prefixes)
        return sum(v for k, v in self.nb_ecritures_par_compte.items() if k.startswith(pref))

    def nb_journaux(self) -> int:
        return len(self.journaux)

    def nb_mois(self) -> int:
        return max(1, len(self.mois))


def _count_features(df: pd.DataFrame):
    cn = df["CompteNum"].astype(str)
    comptes = sorted(cn.unique().tolist())
    # nombre de LIGNES d'écriture par compte (proxy volume ; ACOMPTES = lignes/an au référentiel)
    nb_ecritures_par_compte = {k: int(v) for k, v in cn.value_counts().to_dict().items()}

    if "CompAuxNum" in df.columns:
        aux = df["CompAuxNum"].astype(str).str.strip()
        aux = aux.where(~aux.str.lower().isin(["nan", "none"]), "")
    else:
        aux = pd.Series([""] * len(df), index=df.index)
    paires_tiers = sorted({(c, a) for c, a in zip(cn, aux)})
    paires_tiers = [[c, a] for c, a in paires_tiers]

    if "JournalCode" in df.columns:
        journaux = sorted(
            j for j in df["JournalCode"].astype(str).str.strip().unique()
            if j and j.lower() not in ("nan", "none")
        )
    else:
        journaux = []

    if "EcritureDate" in df.columns:
        mois = sorted({
            str(d)[:6] for d in df["EcritureDate"].astype(str).str.strip()
            if str(d)[:6] and str(d)[:6].lower() not in ("nan", "none")
        })
    else:
        mois = []

    return comptes, paires_tiers, nb_ecritures_par_compte, journaux, mois


def compute_fec_features(df: pd.DataFrame, df_n1: pd.DataFrame | None = None) -> IndicateursFEC:
    debit_n, credit_n = _sums_by_account(df)
    debit_n1, credit_n1 = ({}, {})
    if df_n1 is not None:
        debit_n1, credit_n1 = _sums_by_account(df_n1)

    comptes, paires_tiers, nb_ecr, journaux, mois = _count_features(df)

    feat = IndicateursFEC(
        debit_n=debit_n, credit_n=credit_n,
        debit_n1=debit_n1, credit_n1=credit_n1,
        comptes=comptes, paires_tiers=paires_tiers,
        nb_ecritures_par_compte=nb_ecr, journaux=journaux, mois=mois,
    )
    feat.ca_n = feat.solde(["70"], "C")
    return feat
