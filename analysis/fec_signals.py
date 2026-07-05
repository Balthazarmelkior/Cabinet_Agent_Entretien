# analysis/fec_signals.py
"""Détection des signaux famille A depuis IndicateursFEC (moteur hybride)."""
from __future__ import annotations

from models import Signal, TypeSignal, Gravite
from analysis.fec_features import IndicateursFEC

R, O, C, X = TypeSignal.RISQUE, TypeSignal.OPPORTUNITE, TypeSignal.CONFORMITE, TypeSignal.OPTIMISATION
F, M, E = Gravite.FAIBLE, Gravite.MOYENNE, Gravite.ELEVEE

# code -> (op, comptes, sens, seuil_defaut, type, gravite, titre, levier)
#   op ∈ {"seuil_eur", "presence", "absence"}
GENERIC_SIGNALS: dict[str, tuple] = {
    # --- seuil_eur ---
    "PORTEFEUILLE_FINANCIER_IMPORTANT": ("seuil_eur", ["26", "27", "50", "51"], "D", 500000, O, F,
        "Portefeuille financier important", "Diagnostic patrimonial, placements sur mesure"),
    "CESSION_ACTIFS_RECENTE": ("seuil_eur", ["775", "757"], "C", 50000, O, F,
        "Cession d'actifs récente", "Réemploi, placement du produit de cession, valorisation"),
    "REMUNERATION_DIRIGEANT_ELEVEE": ("seuil_eur", ["6411"], "D", 48000, X, M,
        "Rémunération dirigeant élevée", "Optimisation du statut social, arbitrage salaire/dividendes"),
    "FRAIS_CONTENTIEUX_ELEVES": ("seuil_eur", ["6227"], "D", 1000, R, M,
        "Frais de contentieux élevés", "Sécurisation juridique, recouvrement, prévention"),
    "HONORAIRES_JURIDIQUES_ELEVES": ("seuil_eur", ["6226", "6228"], "D", 2000, X, F,
        "Honoraires juridiques élevés", "SIRH, sécurisation juridique RH"),
    "FRAIS_ADMINISTRATIFS_ELEVES": ("seuil_eur", ["626"], "D", 3000, X, F,
        "Frais administratifs élevés", "Assistanat administratif externalisé"),
    "REVENUS_LOCATIFS_ELEVES": ("seuil_eur", ["706", "708"], "C", 30000, O, F,
        "Revenus locatifs élevés", "Comptabilité LMNP, structuration SCI, assurance PNO"),
    "PATRIMOINE_IMMO_IMPORTANT": ("seuil_eur", ["213", "214"], "D", 300000, O, F,
        "Patrimoine immobilier important", "Gestion de portefeuille investisseurs, transmission"),
    "CA_LOCATIF_CONSOLIDE_ELEVE": ("seuil_eur", ["706", "708"], "C", 80000, O, F,
        "CA locatif consolidé élevé", "Gestion de portefeuille investisseurs"),
    "IMMO_PRO_ELEVEE": ("seuil_eur", ["213"], "D", 400000, O, F,
        "Immobilier professionnel élevé", "Structuration immobilier professionnel (SCI, holding)"),
    "LOYERS_VERSES_ELEVES": ("seuil_eur", ["613"], "D", 60000, X, F,
        "Loyers versés élevés", "Structuration immobilier professionnel, acquisition des murs"),
    "PARC_MACHINES_IMPORTANT": ("seuil_eur", ["215"], "D", 50000, C, F,
        "Parc de machines important", "Assurance bris de machine"),
    "ACTIFS_A_ASSURER": ("seuil_eur", ["21", "3"], "D", 50000, C, F,
        "Actifs à assurer", "Multirisque entreprise"),
    # --- presence (> 0) ---
    "CLIENTS_DOUTEUX": ("presence", ["416"], "D", 0, R, M,
        "Clients douteux détectés", "Recouvrement de créances"),
    "CREANCES_PASSEES_EN_PERTE": ("presence", ["654"], "D", 0, R, M,
        "Créances passées en perte", "Recouvrement, prévention des impayés"),
    "DEPRECIATION_CREANCES": ("presence", ["491"], "C", 0, R, F,
        "Dépréciation de créances", "Recouvrement, assainissement du poste clients"),
    "PENALITES_FISCALES": ("presence", ["6712"], "D", 0, R, E,
        "Pénalités fiscales", "Pack Sérénité (ECF + Zen Fiscal), sécurisation"),
    "PENALITES_SOCIALES": ("presence", ["6714"], "D", 0, R, E,
        "Pénalités sociales", "Sécurisation juridique RH, audit social"),
    "PROVISION_RISQUE_SOCIAL": ("presence", ["158", "1511"], "C", 0, R, M,
        "Provision pour risque social", "Sécurisation juridique RH"),
    "FONDS_COMMERCIAL_RECENT": ("presence", ["207"], "D", 0, O, F,
        "Fonds commercial récent", "Étude de zone de chalandise, financement"),
    "CONSTRUCTION_EN_COURS": ("presence", ["231"], "D", 0, O, F,
        "Construction en cours", "Assurance dommage ouvrage, recherche de financement"),
    "NOUVEL_ASSOCIE": ("presence", ["4561", "108"], "C", 0, C, F,
        "Nouvel associé détecté", "Modification de société, pacte d'associés"),
    "TITRES_PARTICIPATION_DETECTES": ("presence", ["261", "271"], "D", 0, O, F,
        "Titres de participation détectés", "Croissance externe, cession/acquisition"),
    "NOUVEAU_BAIL": ("presence", ["275"], "D", 0, O, F,
        "Nouveau bail détecté", "Recherche de financement, garantie"),
    # --- absence (== 0) ---
    "ABSENCE_ASSURANCE_RC": ("absence", ["616"], "D", 0, R, E,
        "Absence d'assurance responsabilité civile", "RC professionnelle, RC dirigeants"),
    "ABSENCE_PER_RETRAITE": ("absence", ["646", "6467", "6468"], "D", 0, X, F,
        "Absence de PER retraite", "Retraite du dirigeant (PER), optimisation fiscale"),
}


def _desc_generic(op: str, comptes: list[str], seuil: float, valeur: float) -> str:
    j = "/".join(comptes)
    if op == "seuil_eur":
        return f"Comptes {j} : {valeur:,.0f} € (seuil {seuil:,.0f} €)."
    if op == "presence":
        return f"Comptes {j} : présence détectée ({valeur:,.0f} €)."
    return f"Comptes {j} : aucune écriture (compte absent)."


def _eval_generic(code: str, feat: IndicateursFEC, seuils_overrides: dict[str, float]) -> Signal | None:
    op, comptes, sens, defaut, typ, grav, titre, levier = GENERIC_SIGNALS[code]
    seuil = float(seuils_overrides.get(code, defaut))
    if op == "absence":
        if feat.mouvement(comptes) != 0:
            return None
        valeur = 0.0
    else:
        valeur = feat.solde(comptes, sens)
        seuil_test = seuil if op == "seuil_eur" else 0
        if not (valeur > seuil_test):
            return None
    return Signal(type=typ, gravite=grav, code=code, titre=titre,
                  description=_desc_generic(op, comptes, seuil, valeur), levier=levier)


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
