# analysis/rules.py
from models import Signal, TypeSignal, Gravite
from analysis.ratios import Ratios


def detect_signals_from_rules(ratios: Ratios) -> list[Signal]:
    signals: list[Signal] = []

    # ── RISQUES ───────────────────────────────────────────────────────────────

    if ratios.taux_ebe < 0:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.ELEVEE,
            code="EBE_NEGATIF",
            titre="EBE négatif",
            description=f"L'EBE est à {ratios.taux_ebe:.1f}% du CA : l'exploitation ne couvre pas ses charges fixes.",
            levier="Revoir la structure de coûts, envisager un plan de redressement"
        ))
    elif ratios.taux_ebe < 5:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="EBE_FAIBLE",
            titre=f"EBE insuffisant ({ratios.taux_ebe:.1f}%)",
            description=f"L'EBE représente {ratios.taux_ebe:.1f}% du CA, en dessous du seuil recommandé (5-10%).",
            levier="Analyse de rentabilité par produit/service, optimisation des charges"
        ))

    if ratios.couverture_dettes > 5:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.ELEVEE,
            code="ENDETTEMENT_EXCESSIF",
            titre=f"Endettement excessif ({ratios.couverture_dettes:.1f} ans d'EBE)",
            description=f"Les dettes financières représentent {ratios.couverture_dettes:.1f} années d'EBE (seuil critique : 5 ans).",
            levier="Restructuration de la dette, apport en capitaux propres"
        ))

    if ratios.ratio_liquidite_generale < 1:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.ELEVEE,
            code="LIQUIDITE_CRITIQUE",
            titre=f"Liquidité insuffisante (ratio {ratios.ratio_liquidite_generale:.2f})",
            description="Le passif court terme dépasse l'actif circulant : risque de cessation de paiement.",
            levier="Plan de trésorerie urgent, négociation bancaire, affacturage"
        ))
    elif ratios.ratio_liquidite_generale < 1.2:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="LIQUIDITE_TENDUE",
            titre=f"Liquidité tendue (ratio {ratios.ratio_liquidite_generale:.2f})",
            description="La marge de sécurité de trésorerie est insuffisante.",
            levier="Mise en place d'un suivi prévisionnel de trésorerie"
        ))

    if ratios.delai_clients_jours > 60:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="DELAI_CLIENTS_ELEVE",
            titre=f"Délai clients élevé ({int(ratios.delai_clients_jours)} jours)",
            description=f"Le délai de règlement clients dépasse 60 jours, générant un BFR important.",
            levier="Révision des CGV, relances clients, affacturage, escompte de règlement"
        ))

    if ratios.autonomie_financiere < 20:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="AUTONOMIE_FAIBLE",
            titre=f"Faible autonomie financière ({ratios.autonomie_financiere:.1f}%)",
            description=f"Les capitaux propres représentent seulement {ratios.autonomie_financiere:.1f}% du passif.",
            levier="Augmentation de capital, incorporation de réserves, OBO"
        ))

    if ratios.variation_ca_pct is not None and ratios.variation_ca_pct < -10:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.ELEVEE,
            code="BAISSE_CA_SIGNIFICATIVE",
            titre=f"Chute du CA ({ratios.variation_ca_pct:+.1f}%)",
            description=f"Le CA a diminué de {abs(ratios.variation_ca_pct):.1f}% vs N-1 : diagnostic commercial urgent.",
            levier="Audit commercial, repositionnement offre, diversification clients"
        ))

    if ratios.delai_fournisseurs_jours < 30 and ratios.delai_clients_jours > 45:
        signals.append(Signal(
            type=TypeSignal.OPTIMISATION, gravite=Gravite.MOYENNE,
            code="DESEQUILIBRE_BFR",
            titre=f"BFR déséquilibré (clients {int(ratios.delai_clients_jours)}j / fournisseurs {int(ratios.delai_fournisseurs_jours)}j)",
            description="Vous payez vos fournisseurs plus vite que vos clients ne vous paient.",
            levier="Négociation délais fournisseurs, optimisation recouvrement clients"
        ))

    # ── OPPORTUNITÉS ──────────────────────────────────────────────────────────

    if ratios.taux_ebe > 15:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="FORTE_RENTABILITE",
            titre=f"Excellente rentabilité ({ratios.taux_ebe:.1f}% d'EBE)",
            description="La société génère une forte capacité d'autofinancement.",
            levier="Investissement, dividendes, épargne salariale, optimisation fiscale"
        ))

    if ratios.variation_ca_pct is not None and ratios.variation_ca_pct > 20:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.MOYENNE,
            code="FORTE_CROISSANCE",
            titre=f"Forte croissance ({ratios.variation_ca_pct:+.1f}%)",
            description="La croissance soutenue appelle des besoins en structure et financement.",
            levier="Accompagnement structuration, financement BFR, recrutement"
        ))

    if ratios.couverture_dettes < 1 and ratios.taux_ebe > 10:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="CAPACITE_INVESTISSEMENT",
            titre="Capacité d'investissement disponible",
            description="Faible endettement et bonne rentabilité : marge de manœuvre pour investir.",
            levier="Conseil en investissement, dispositifs fiscaux, immobilier professionnel"
        ))

    # ── OPTIMISATION ──────────────────────────────────────────────────────────

    if ratios.taux_resultat_net > 5 and ratios.rentabilite_capitaux > 15:
        signals.append(Signal(
            type=TypeSignal.OPTIMISATION, gravite=Gravite.FAIBLE,
            code="OPTIMISATION_FISCALE",
            titre=f"Potentiel d'optimisation fiscale (RN à {ratios.taux_resultat_net:.1f}%)",
            description="Le niveau de résultat ouvre des leviers d'optimisation fiscale et sociale.",
            levier="Holding, intéressement, PER, OBO, transmission anticipée"
        ))

    return signals
