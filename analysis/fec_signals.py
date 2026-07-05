# analysis/fec_signals.py
"""Détection des signaux famille A depuis IndicateursFEC (moteur hybride)."""
from __future__ import annotations

from typing import NamedTuple

from models import Signal, TypeSignal, Gravite
from analysis.fec_features import IndicateursFEC

R, O, C, X = TypeSignal.RISQUE, TypeSignal.OPPORTUNITE, TypeSignal.CONFORMITE, TypeSignal.OPTIMISATION
F, M, E = Gravite.FAIBLE, Gravite.MOYENNE, Gravite.ELEVEE


class GenericSpec(NamedTuple):
    op: str            # "seuil_eur" | "presence" | "absence" | "mouvement"
    comptes: list[str]
    sens: str          # "D" | "C" (ignoré pour "absence"/"mouvement")
    seuil_defaut: float
    type: TypeSignal
    gravite: Gravite
    titre: str
    levier: str


GENERIC_SIGNALS: dict[str, GenericSpec] = {
    # --- seuil_eur ---
    "PORTEFEUILLE_FINANCIER_IMPORTANT": GenericSpec("seuil_eur", ["26", "27", "50", "51"], "D", 500000, O, F,
        "Portefeuille financier important", "Diagnostic patrimonial, placements sur mesure"),
    "CESSION_ACTIFS_RECENTE": GenericSpec("seuil_eur", ["775", "757"], "C", 50000, O, F,
        "Cession d'actifs récente", "Réemploi, placement du produit de cession, valorisation"),
    "REMUNERATION_DIRIGEANT_ELEVEE": GenericSpec("seuil_eur", ["6411"], "D", 48000, X, M,
        "Rémunération dirigeant élevée", "Optimisation du statut social, arbitrage salaire/dividendes"),
    "FRAIS_CONTENTIEUX_ELEVES": GenericSpec("seuil_eur", ["6227"], "D", 1000, R, M,
        "Frais de contentieux élevés", "Sécurisation juridique, recouvrement, prévention"),
    "HONORAIRES_JURIDIQUES_ELEVES": GenericSpec("seuil_eur", ["6226", "6228"], "D", 2000, X, F,
        "Honoraires juridiques élevés", "SIRH, sécurisation juridique RH"),
    "FRAIS_ADMINISTRATIFS_ELEVES": GenericSpec("seuil_eur", ["626"], "D", 3000, X, F,
        "Frais administratifs élevés", "Assistanat administratif externalisé"),
    "REVENUS_LOCATIFS_ELEVES": GenericSpec("seuil_eur", ["706", "708"], "C", 30000, O, F,
        "Revenus locatifs élevés", "Comptabilité LMNP, structuration SCI, assurance PNO"),
    "PATRIMOINE_IMMO_IMPORTANT": GenericSpec("seuil_eur", ["213", "214"], "D", 300000, O, F,
        "Patrimoine immobilier important", "Gestion de portefeuille investisseurs, transmission"),
    "CA_LOCATIF_CONSOLIDE_ELEVE": GenericSpec("seuil_eur", ["706", "708"], "C", 80000, O, F,
        "CA locatif consolidé élevé", "Gestion de portefeuille investisseurs"),
    "IMMO_PRO_ELEVEE": GenericSpec("seuil_eur", ["213"], "D", 400000, O, F,
        "Immobilier professionnel élevé", "Structuration immobilier professionnel (SCI, holding)"),
    "LOYERS_VERSES_ELEVES": GenericSpec("seuil_eur", ["613"], "D", 60000, X, F,
        "Loyers versés élevés", "Structuration immobilier professionnel, acquisition des murs"),
    "PARC_MACHINES_IMPORTANT": GenericSpec("seuil_eur", ["215"], "D", 50000, C, F,
        "Parc de machines important", "Assurance bris de machine"),
    "ACTIFS_A_ASSURER": GenericSpec("seuil_eur", ["21", "3"], "D", 50000, C, F,
        "Actifs à assurer", "Multirisque entreprise"),
    # --- presence (> seuil, défaut 0) ---
    "CLIENTS_DOUTEUX": GenericSpec("presence", ["416"], "D", 0, R, M,
        "Clients douteux détectés", "Recouvrement de créances"),
    "CREANCES_PASSEES_EN_PERTE": GenericSpec("presence", ["654"], "D", 0, R, M,
        "Créances passées en perte", "Recouvrement, prévention des impayés"),
    "DEPRECIATION_CREANCES": GenericSpec("presence", ["491"], "C", 0, R, F,
        "Dépréciation de créances", "Recouvrement, assainissement du poste clients"),
    "PENALITES_FISCALES": GenericSpec("presence", ["6712"], "D", 0, R, E,
        "Pénalités fiscales", "Pack Sérénité (ECF + Zen Fiscal), sécurisation"),
    "PENALITES_SOCIALES": GenericSpec("presence", ["6714"], "D", 0, R, E,
        "Pénalités sociales", "Sécurisation juridique RH, audit social"),
    "PROVISION_RISQUE_SOCIAL": GenericSpec("presence", ["158", "1511"], "C", 0, R, M,
        "Provision pour risque social", "Sécurisation juridique RH"),
    "FONDS_COMMERCIAL_RECENT": GenericSpec("presence", ["207"], "D", 0, O, F,
        "Fonds commercial récent", "Étude de zone de chalandise, financement"),
    # --- mouvement (sign-agnostic, > seuil défaut 0) ---
    "CONSTRUCTION_EN_COURS": GenericSpec("mouvement", ["231"], "D", 0, O, F,
        "Construction en cours", "Assurance dommage ouvrage, recherche de financement"),
    "NOUVEL_ASSOCIE": GenericSpec("mouvement", ["4561", "108"], "D", 0, C, F,
        "Nouvel associé détecté", "Modification de société, pacte d'associés"),
    "TITRES_PARTICIPATION_DETECTES": GenericSpec("mouvement", ["261", "271"], "D", 0, O, F,
        "Titres de participation détectés", "Croissance externe, cession/acquisition"),
    "NOUVEAU_BAIL": GenericSpec("mouvement", ["275"], "D", 0, O, F,
        "Nouveau bail détecté", "Recherche de financement, garantie"),
    # --- absence (== 0) ---
    "ABSENCE_ASSURANCE_RC": GenericSpec("absence", ["616"], "D", 0, R, E,
        "Absence d'assurance responsabilité civile", "RC professionnelle, RC dirigeants"),
    "ABSENCE_PER_RETRAITE": GenericSpec("absence", ["646", "6467", "6468"], "D", 0, X, F,
        "Absence de PER retraite", "Retraite du dirigeant (PER), optimisation fiscale"),
}


def _desc_generic(op: str, comptes: list[str], seuil: float, valeur: float) -> str:
    j = "/".join(comptes)
    if op == "seuil_eur":
        return f"Comptes {j} : {valeur:,.0f} € (seuil {seuil:,.0f} €)."
    if op in ("presence", "mouvement"):
        return f"Comptes {j} : mouvement détecté ({valeur:,.0f} €)."
    return f"Comptes {j} : aucune écriture (compte absent)."


def _eval_generic(code: str, feat: IndicateursFEC, seuils_overrides: dict[str, float]) -> Signal | None:
    spec = GENERIC_SIGNALS[code]
    seuil = float(seuils_overrides.get(code, spec.seuil_defaut))
    if spec.op == "absence":
        if feat.mouvement(spec.comptes) != 0:
            return None
        valeur = 0.0
    elif spec.op == "mouvement":
        valeur = feat.mouvement(spec.comptes)
        if not (valeur > seuil):
            return None
    else:  # seuil_eur | presence
        valeur = feat.solde(spec.comptes, spec.sens)
        if not (valeur > seuil):
            return None
    return Signal(type=spec.type, gravite=spec.gravite, code=code, titre=spec.titre,
                  description=_desc_generic(spec.op, spec.comptes, seuil, valeur), levier=spec.levier)


def seuils_parametrables(referentiel: dict) -> dict[str, float]:
    """code -> seuil défaut, pour les signaux GENERIC parametrable:true (source unique UI + moteur)."""
    out: dict[str, float] = {}
    for code, spec in GENERIC_SIGNALS.items():
        ref = referentiel.get(code, {})
        if ref.get("parametrable") and ref.get("seuil_valeur") is not None:
            out[code] = float(ref["seuil_valeur"])
    return out


def detect_signals_from_fec(feat: IndicateursFEC, seuils_overrides: dict[str, float] | None = None) -> list[Signal]:
    overrides = seuils_overrides or {}
    signals: list[Signal] = []
    for code in GENERIC_SIGNALS:
        sig = _eval_generic(code, feat, overrides)
        if sig is not None:
            signals.append(sig)
    # (détecteurs explicites ajoutés en Task 3)
    return signals
