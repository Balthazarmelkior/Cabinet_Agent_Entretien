# analysis/fec_features.py
"""Extraction d'indicateurs fins depuis le FEC (débit/crédit par compte)."""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


def _sums_by_account(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """Retourne (debit_par_compte, credit_par_compte) agrégés par CompteNum."""
    debit = pd.to_numeric(df.get("Debit"), errors="coerce").fillna(0)
    credit = pd.to_numeric(df.get("Credit"), errors="coerce").fillna(0)
    comptes = df["CompteNum"].astype(str)
    d = debit.groupby(comptes).sum().to_dict()
    c = credit.groupby(comptes).sum().to_dict()
    return {k: float(v) for k, v in d.items()}, {k: float(v) for k, v in c.items()}


class IndicateursFEC(BaseModel):
    debit_n: dict[str, float] = Field(default_factory=dict)
    credit_n: dict[str, float] = Field(default_factory=dict)
    debit_n1: dict[str, float] = Field(default_factory=dict)
    credit_n1: dict[str, float] = Field(default_factory=dict)
    ca_n: float = 0.0

    def _agg(self, prefixes: list[str], *, n1: bool) -> tuple[float, float]:
        debit = self.debit_n1 if n1 else self.debit_n
        credit = self.credit_n1 if n1 else self.credit_n
        pref = tuple(prefixes)
        d = sum(v for k, v in debit.items() if k.startswith(pref))
        c = sum(v for k, v in credit.items() if k.startswith(pref))
        return d, c

    def solde(self, prefixes: list[str], sens: str = "D", *, n1: bool = False) -> float:
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


def compute_fec_features(df: pd.DataFrame, df_n1: pd.DataFrame | None = None) -> IndicateursFEC:
    debit_n, credit_n = _sums_by_account(df)
    debit_n1, credit_n1 = ({}, {})
    if df_n1 is not None:
        debit_n1, credit_n1 = _sums_by_account(df_n1)

    feat = IndicateursFEC(
        debit_n=debit_n, credit_n=credit_n,
        debit_n1=debit_n1, credit_n1=credit_n1,
    )
    feat.ca_n = feat.solde(["70"], "C")
    return feat
