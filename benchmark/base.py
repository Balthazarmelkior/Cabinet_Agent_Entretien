# benchmark/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RatiosBruts:
    source: str
    annee_reference: int
    libelle_secteur: str
    fiabilite: int  # 1=BdF (haute), 2=INSEE (moyenne), 3=LLM (estimée)

    taux_ebe:                 Optional[dict] = None
    taux_resultat_net:        Optional[dict] = None
    autonomie_financiere:     Optional[dict] = None
    couverture_dettes:        Optional[dict] = None
    delai_clients_jours:      Optional[dict] = None
    delai_fournisseurs_jours: Optional[dict] = None
    ratio_liquidite_generale: Optional[dict] = None


class BenchmarkSource(ABC):
    @abstractmethod
    def fetch(self, code_naf: str, annee: int, tranche_ca: str) -> Optional[RatiosBruts]:
        ...
