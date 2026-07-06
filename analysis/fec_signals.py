# analysis/fec_signals.py
"""Détection des signaux famille A depuis IndicateursFEC (moteur hybride)."""
from __future__ import annotations

from typing import Callable, NamedTuple

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
    "SEUIL_TVA_MICRO_DEPASSE": GenericSpec("seuil_eur", ["70"], "C", 77000, C, M,
        "Seuil de TVA/micro dépassé", "Accompagnement changement de régime fiscal (réel, franchise)"),
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


class CountSpec(NamedTuple):
    metric: str            # "nb_comptes" | "nb_tiers" | "nb_ecritures" | "nb_journaux"
    comptes: list[str]
    seuil_defaut: int
    type: TypeSignal
    gravite: Gravite
    titre: str
    levier: str


COUNT_SIGNALS: dict[str, CountSpec] = {
    "EMPRUNTS_MULTIPLES": CountSpec("nb_comptes", ["164"], 3, O, F,
        "Emprunts multiples", "Recherche de financement, restructuration de dette"),
    # Heuristique : sous-comptes distincts sous 213 = biens distincts. Risque de faux positif
    # si un même bien est éclaté (2131 bâtiment / 2135 agencements / 2138 infra). À affiner si besoin.
    "MULTI_BIENS_IMMOBILIERS": CountSpec("nb_comptes", ["213"], 2, O, F,
        "Multi-biens immobiliers", "Gestion de SCI, gestion de portefeuille investisseurs"),
    "PARC_VEHICULES_IMPORTANT": CountSpec("nb_comptes", ["2182"], 5, C, F,
        "Parc de véhicules important", "Flotte automobile (assurance)"),
    "NOMBREUX_FOURNISSEURS": CountSpec("nb_tiers", ["401"], 50, C, F,
        "Nombreux fournisseurs", "Mise en place facture électronique"),
    "ACOMPTES_FREQUENTS": CountSpec("nb_ecritures", ["4191"], 5, C, F,
        "Acomptes fréquents", "Mise en place facture électronique"),
    "COMPLEXITE_COMPTABLE": CountSpec("nb_journaux", [], 8, O, M,
        "Comptabilité complexe", "DAF externalisée, contrôle de gestion"),
}


def seuils_parametrables(referentiel: dict) -> dict[str, float]:
    """code -> seuil défaut, pour les signaux GENERIC + COUNT parametrable:true."""
    out: dict[str, float] = {}
    for table in (GENERIC_SIGNALS, COUNT_SIGNALS, PARAM_SIGNALS):
        for code in table:
            ref = referentiel.get(code, {})
            if ref.get("parametrable") and ref.get("seuil_valeur") is not None:
                out[code] = float(ref["seuil_valeur"])
    return out


def titre_signal(code: str) -> str:
    """Titre lisible d'un code, cherché dans GENERIC puis COUNT (repli = code)."""
    if code in GENERIC_SIGNALS:
        return GENERIC_SIGNALS[code].titre
    if code in COUNT_SIGNALS:
        return COUNT_SIGNALS[code].titre
    if code in PARAM_SIGNALS:
        return PARAM_SIGNALS[code].titre
    return code


def _count_metric(feat: IndicateursFEC, spec: CountSpec) -> int:
    if spec.metric == "nb_comptes":
        return feat.nb_comptes(spec.comptes)
    if spec.metric == "nb_tiers":
        return feat.nb_tiers(spec.comptes)
    if spec.metric == "nb_ecritures":
        return feat.nb_ecritures(spec.comptes)
    return feat.nb_journaux()


def _eval_count(code: str, feat: IndicateursFEC, seuils_overrides: dict[str, float]) -> Signal | None:
    spec = COUNT_SIGNALS[code]
    seuil = float(seuils_overrides.get(code, spec.seuil_defaut))
    valeur = _count_metric(feat, spec)
    if valeur < seuil:
        return None
    return Signal(type=spec.type, gravite=spec.gravite, code=code, titre=spec.titre,
                  description=f"{spec.titre} : {int(valeur)} détecté(s) (seuil {int(seuil)}).",
                  levier=spec.levier)


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


def _sig(code, typ, grav, titre, desc, levier) -> Signal:
    return Signal(type=typ, gravite=grav, code=code, titre=titre, description=desc, levier=levier)


# --- Ratios ---
def _charges_sociales_elevees(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["645"], ["641"], "D", "D")
    if r is None or r <= 45:
        return None
    return _sig("CHARGES_SOCIALES_ELEVEES", X, M, "Charges sociales élevées",
                f"Charges sociales / salaires bruts = {r:.0f}% (seuil 45%).",
                "Audit et optimisation sociale, intéressement/PEE")


def _ratio_dividendes_eleve(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["457"], ["6411"], "C", "D")
    if r is None or r <= 60:
        return None
    return _sig("RATIO_DIVIDENDES_ELEVE", X, M, "Ratio dividendes/salaire élevé",
                f"Dividendes / rémunération = {r:.0f}% (seuil 60%).",
                "Rémunération optimisée du dirigeant, statut social")


def _charges_sociales_perso_elevees(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["646"], ["12"], "D", "C")
    if r is None or r <= 30:
        return None
    return _sig("CHARGES_SOCIALES_PERSO_ELEVEES", X, F, "Charges sociales personnelles élevées",
                f"Cotisations perso dirigeant / résultat = {r:.0f}% (seuil 30%).",
                "Optimisation du statut social du dirigeant")


def _amortissements_avances(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["2813"], ["213"], "C", "D")
    if r is None or r <= 80:
        return None
    return _sig("AMORTISSEMENTS_AVANCES", O, F, "Amortissements avancés",
                f"Amortissements / valeur brute immeubles = {r:.0f}% (seuil 80%).",
                "Arbitrage patrimonial, réinvestissement, cession")


# --- Composites même-année ---
def _compte_courant_crediteur_eleve(f: IndicateursFEC) -> Signal | None:
    v = f.solde(["455"], "C")
    if v <= 50000:
        return None
    grav = E if v > 150000 else (M if v > 100000 else F)
    return _sig("COMPTE_COURANT_CREDITEUR_ELEVE", O, grav, "Compte courant d'associé créditeur élevé",
                f"Compte courant d'associé créditeur : {v:,.0f} € (seuil 50 000 €).",
                "Diagnostic patrimonial, placement, succession & transmission")


def _absence_interessement(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["6414"]) != 0 or f.solde(["12"], "C") <= 80000:
        return None
    return _sig("ABSENCE_INTERESSEMENT", X, F, "Absence d'intéressement",
                "Aucune prime d'intéressement (6414 = 0) alors que le résultat dépasse 80 000 €.",
                "Intéressement des salariés, PEE")


def _absence_provision_ifc(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["153"]) != 0 or f.solde(["641"], "D") <= 100000:
        return None
    return _sig("ABSENCE_PROVISION_IFC", R, M, "Absence de provision IFC",
                "Aucune provision pour indemnités de fin de carrière (153 = 0) avec une masse salariale > 100 000 €.",
                "Indemnités de fin de carrière (IFC)")


def _absence_prevoyance_madelin(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["6467"]) != 0 or f.solde(["6411"], "D") <= 36000:
        return None
    return _sig("ABSENCE_PREVOYANCE_MADELIN", R, M, "Absence de prévoyance Madelin",
                "Aucune cotisation prévoyance (6467 = 0) alors que la rémunération dépasse 36 000 €.",
                "Prévoyance dirigeant (Madelin)")


def _sous_remuneration_dirigeant(f: IndicateursFEC) -> Signal | None:
    if f.solde(["12"], "C") <= 80000 or f.solde(["6411"], "D") >= 40000:
        return None
    return _sig("SOUS_REMUNERATION_DIRIGEANT", X, M, "Sous-rémunération du dirigeant",
                "Résultat > 80 000 € mais rémunération dirigeant < 40 000 € : arbitrage à étudier.",
                "Rémunération optimisée du dirigeant, statut social")


def _absence_force_commerciale(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["6221"]) != 0 or f.ca_n <= 200000:
        return None
    return _sig("ABSENCE_FORCE_COMMERCIALE", O, M, "Absence de force commerciale",
                "Aucune commission commerciale (6221 = 0) avec un CA > 200 000 €.",
                "Assistanat commercial, développement commercial")


def _depenses_pub_sans_effet(f: IndicateursFEC) -> Signal | None:
    var_ca = f.variation_pct(["70"], "C")
    if f.solde(["6231"], "D") <= 5000 or var_ca is None or var_ca > 0:
        return None
    return _sig("DEPENSES_PUB_SANS_EFFET", R, F, "Dépenses publicitaires sans effet",
                "Dépenses de publicité > 5 000 € sans progression du CA.",
                "Assistanat commercial, étude de zone de chalandise")


def _immo_locatif_non_amorti(f: IndicateursFEC) -> Signal | None:
    if f.solde(["213", "214"], "D") <= 0 or f.mouvement(["2813", "2814"]) != 0:
        return None
    return _sig("IMMO_LOCATIF_NON_AMORTI", O, M, "Immobilier locatif non amorti",
                "Biens immobiliers présents (213/214) sans amortissement constaté (2813/2814 = 0).",
                "Comptabilité LMNP au réel (amortissement)")


# --- Variations N/N-1 ---
def _variation_haus(code, comptes, sens, seuil, typ, grav, titre, levier):
    def _f(f: IndicateursFEC) -> Signal | None:
        v = f.variation_pct(comptes, sens)
        if v is None or v < seuil:
            return None
        return _sig(code, typ, grav, titre, f"{titre} : {v:+.0f}% vs N-1 (seuil +{seuil:.0f}%).", levier)
    return _f


_frais_financiers_en_hausse = _variation_haus(
    "FRAIS_FINANCIERS_EN_HAUSSE", ["661"], "D", 20, R, M,
    "Frais financiers en hausse", "Prévisionnel de trésorerie, restructuration de dette")
_frais_bancaires_en_hausse = _variation_haus(
    "FRAIS_BANCAIRES_EN_HAUSSE", ["627"], "D", 20, X, F,
    "Frais bancaires en hausse", "Assistanat administratif, renégociation bancaire")
_hausse_immobilisations = _variation_haus(
    "HAUSSE_IMMOBILISATIONS", ["21"], "D", 20, C, F,
    "Hausse des immobilisations", "Multirisque entreprise, garantie emprunteur")
_honoraires_exceptionnels_en_hausse = _variation_haus(
    "HONORAIRES_EXCEPTIONNELS_EN_HAUSSE", ["6226"], "D", 50, C, F,
    "Honoraires exceptionnels en hausse", "Cession & acquisition, accompagnement")


def _variation_remuneration_dirigeant(f: IndicateursFEC) -> Signal | None:
    v = f.variation_pct(["6411"], "D")
    if v is None or abs(v) < 15:
        return None
    return _sig("VARIATION_REMUNERATION_DIRIGEANT", C, F, "Variation de rémunération du dirigeant",
                f"Rémunération dirigeant : {v:+.0f}% vs N-1 (seuil ±15%).",
                "Prévoyance dirigeant, conseil RH")


def _augmentation_capital(f: IndicateursFEC) -> Signal | None:
    n1 = f.solde(["101"], "C", n1=True)
    if not n1 or f.solde(["101"], "C") - n1 <= 0:
        return None
    return _sig("AUGMENTATION_CAPITAL", C, F, "Augmentation de capital",
                "Le capital social (101) a augmenté vs N-1.",
                "Modification de société, secrétariat juridique")


# --- Divers ---
def _resultat_bnc_eleve(f: IndicateursFEC) -> Signal | None:
    if f.solde(["12"], "C") <= 100000:
        return None
    return _sig("RESULTAT_BNC_ELEVE", X, M, "Résultat élevé (BNC)",
                f"Résultat de l'exercice : {f.solde(['12'], 'C'):,.0f} € (seuil 100 000 €).",
                "Structuration des professions libérales (SEL, SPFPL)")


def _volume_facturation(f: IndicateursFEC) -> Signal | None:
    mois = f.nb_mois()
    emises = f.nb_ecritures(["70"]) / mois
    recues = f.nb_ecritures(["60"]) / mois
    if emises < 30 and recues < 50:
        return None
    return _sig("VOLUME_FACTURATION_ELEVE", C, M, "Volume de facturation élevé",
                f"Facturation : {emises:.0f} émises/mois, {recues:.0f} reçues/mois "
                f"(seuils 30 émises / 50 reçues).",
                "Externalisation de la facturation électronique, formation facture électronique")


def _frais_transport_eleves(f: IndicateursFEC) -> Signal | None:
    if f.solde(["6241", "6242"], "D") < 10000 and f.nb_ecritures(["6241", "6242"]) <= 50:
        return None
    return _sig("FRAIS_TRANSPORT_ELEVES", C, F, "Frais de transport élevés",
                "Frais de transport ≥ 10 000 € ou > 50 écritures/an.",
                "Flotte automobile (assurance), optimisation logistique")


_EXPLICIT_DETECTORS = [
    _charges_sociales_elevees, _ratio_dividendes_eleve, _charges_sociales_perso_elevees,
    _amortissements_avances, _compte_courant_crediteur_eleve, _absence_interessement,
    _absence_provision_ifc, _absence_prevoyance_madelin, _sous_remuneration_dirigeant,
    _absence_force_commerciale, _depenses_pub_sans_effet, _immo_locatif_non_amorti,
    _frais_financiers_en_hausse, _frais_bancaires_en_hausse, _hausse_immobilisations,
    _honoraires_exceptionnels_en_hausse, _variation_remuneration_dirigeant,
    _augmentation_capital, _resultat_bnc_eleve, _volume_facturation,
    _frais_transport_eleves,
]


# --- Détecteurs composites paramétrables (seuil éditable dans l'UI) ---
class ParamSpec(NamedTuple):
    fn: Callable[[IndicateursFEC, float], "Signal | None"]
    seuil_defaut: float
    titre: str


def _a_un_n1(f: IndicateursFEC) -> bool:
    return bool(f.debit_n1 or f.credit_n1)


def _investissement_recent(f: IndicateursFEC, seuil: float) -> Signal | None:
    if not _a_un_n1(f):
        return None
    delta = f.solde(["20", "21", "23"], "D") - f.solde(["20", "21", "23"], "D", n1=True)
    if delta < seuil:
        return None
    return _sig("INVESTISSEMENT_RECENT", O, F, "Investissement récent",
                f"Immobilisations : +{delta:,.0f} € vs N-1 (seuil {seuil:,.0f} €).",
                "Recherche de financement, garantie emprunteur, assurance des actifs")


def _nouvel_emprunt(f: IndicateursFEC, seuil: float) -> Signal | None:
    if not _a_un_n1(f):
        return None
    delta = f.solde(["164"], "C") - f.solde(["164"], "C", n1=True)
    if delta < seuil:
        return None
    return _sig("NOUVEL_EMPRUNT", O, F, "Nouvel emprunt",
                f"Emprunts (164) : +{delta:,.0f} € vs N-1 (seuil {seuil:,.0f} €).",
                "Recherche de financement, garantie, assurance emprunteur")


def _baisse_marge_brute(f: IndicateursFEC, seuil: float) -> Signal | None:
    if not _a_un_n1(f):
        return None
    ca_n, ca_n1 = f.solde(["70"], "C"), f.solde(["70"], "C", n1=True)
    if ca_n <= 0 or ca_n1 <= 0:
        return None
    marge_n = (ca_n - f.solde(["60"], "D")) / ca_n * 100
    marge_n1 = (ca_n1 - f.solde(["60"], "D", n1=True)) / ca_n1 * 100
    baisse = marge_n1 - marge_n
    if baisse < seuil:
        return None
    return _sig("BAISSE_MARGE_BRUTE", R, M, "Baisse de la marge brute",
                f"Marge brute : {marge_n:.0f}% vs {marge_n1:.0f}% N-1 "
                f"(−{baisse:.0f} pts, seuil {seuil:.0f}).",
                "Analyse de rentabilité, contrôle de gestion, politique de prix")


def _delai_facturation_long(f: IndicateursFEC, seuil: float) -> Signal | None:
    ca = f.solde(["70"], "C")
    if ca <= 0:
        return None
    dso = f.solde(["411"], "D") / ca * 365
    if dso <= seuil:
        return None
    return _sig("DELAI_FACTURATION_LONG", X, F, "Délai de facturation long",
                f"Encours clients ≈ {dso:.0f} jours de CA (seuil {seuil:.0f} j).",
                "Optimisation du cycle de facturation, relance et recouvrement")


PARAM_SIGNALS: dict[str, ParamSpec] = {
    "INVESTISSEMENT_RECENT": ParamSpec(_investissement_recent, 50000, "Investissement récent"),
    "NOUVEL_EMPRUNT": ParamSpec(_nouvel_emprunt, 50000, "Nouvel emprunt"),
    "BAISSE_MARGE_BRUTE": ParamSpec(_baisse_marge_brute, 5, "Baisse de la marge brute"),
    "DELAI_FACTURATION_LONG": ParamSpec(_delai_facturation_long, 15, "Délai de facturation long"),
}


def detect_signals_from_fec(feat: IndicateursFEC, seuils_overrides: dict[str, float] | None = None) -> list[Signal]:
    overrides = seuils_overrides or {}
    signals: list[Signal] = []
    for code in GENERIC_SIGNALS:
        sig = _eval_generic(code, feat, overrides)
        if sig is not None:
            signals.append(sig)
    for code in COUNT_SIGNALS:
        sig = _eval_count(code, feat, overrides)
        if sig is not None:
            signals.append(sig)
    for detector in _EXPLICIT_DETECTORS:
        sig = detector(feat)
        if sig is not None:
            signals.append(sig)
    for code, spec in PARAM_SIGNALS.items():
        seuil = float(overrides.get(code, spec.seuil_defaut))
        sig = spec.fn(feat, seuil)
        if sig is not None:
            signals.append(sig)
    return signals
