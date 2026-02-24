# models.py
from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


# ─── Données financières ──────────────────────────────────────────────────────

class PosteComptable(BaseModel):
    libelle: str
    montant_n: float
    montant_n1: Optional[float] = None
    variation_pct: Optional[float] = None


class DonneesFinancieres(BaseModel):
    # Compte de résultat
    chiffre_affaires: PosteComptable
    production_stockee: Optional[PosteComptable] = None
    achats_consommes: PosteComptable
    charges_externes: PosteComptable
    charges_personnel: PosteComptable
    ebe: PosteComptable
    resultat_exploitation: PosteComptable
    resultat_net: PosteComptable

    # Bilan actif
    immobilisations_nettes: PosteComptable
    stocks: PosteComptable
    creances_clients: PosteComptable
    tresorerie_actif: PosteComptable

    # Bilan passif
    capitaux_propres: PosteComptable
    dettes_financieres: PosteComptable
    dettes_fournisseurs: PosteComptable

    # Méta
    exercice_n: int
    secteur_activite: Optional[str] = None
    effectif: Optional[int] = None
    forme_juridique: Optional[str] = None
    code_naf: Optional[str] = None


# ─── Signaux ──────────────────────────────────────────────────────────────────

class TypeSignal(str, Enum):
    RISQUE       = "risque"
    OPPORTUNITE  = "opportunite"
    CONFORMITE   = "conformite"
    OPTIMISATION = "optimisation"


class Gravite(int, Enum):
    FAIBLE  = 1
    MOYENNE = 2
    ELEVEE  = 3


class Signal(BaseModel):
    type: TypeSignal
    gravite: Gravite
    code: str
    titre: str
    description: str
    levier: str


# ─── Benchmark sectoriel ──────────────────────────────────────────────────────

class RatioSectoriel(BaseModel):
    libelle: str
    valeur_client: float
    mediane_secteur: Optional[float] = None
    quartile_q1: Optional[float] = None
    quartile_q3: Optional[float] = None
    source: str
    interpretation: str
    ecart_mediane_pct: Optional[float] = None


class BenchmarkSectoriel(BaseModel):
    code_naf: str
    libelle_secteur: str
    annee_reference: int
    taille_entreprise: str
    ratios: list[RatioSectoriel]
    commentaire_global: str


# ─── Missions ─────────────────────────────────────────────────────────────────

class Mission(BaseModel):
    id: str
    titre: str
    description: str
    benefice_client: str
    codes_signaux: list[str] = Field(default_factory=list)
    honoraires_indicatifs: Optional[str] = None
    priorite_proposition: int = 2


class MissionRecommandee(BaseModel):
    mission: Mission
    score_pertinence: float
    signaux_declencheurs: list[str] = Field(default_factory=list)
    argumentaire: str
    urgence: str


# ─── Fiche entretien ──────────────────────────────────────────────────────────

class PointEntretien(BaseModel):
    ordre: int
    theme: str
    contexte_chiffre: str
    question_ouverte: str
    mission_associee: Optional[str] = None


class FicheEntretien(BaseModel):
    client_exercice: str
    synthese_executive: str
    points_vigilance: list[str] = Field(default_factory=list)
    plan_entretien: list[PointEntretien] = Field(default_factory=list)
    missions_a_proposer: list[dict] = Field(default_factory=list)
    elements_a_recueillir: list[str] = Field(default_factory=list)
    conclusion_conseillee: str
