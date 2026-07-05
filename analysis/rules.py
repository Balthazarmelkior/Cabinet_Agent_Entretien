# analysis/rules.py
from models import Signal, TypeSignal, Gravite, DonneesFinancieres
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

    if ratios.taux_resultat_net > 5 and (ratios.rentabilite_capitaux or 0) > 15:
        signals.append(Signal(
            type=TypeSignal.OPTIMISATION, gravite=Gravite.FAIBLE,
            code="OPTIMISATION_FISCALE",
            titre=f"Potentiel d'optimisation fiscale (RN à {ratios.taux_resultat_net:.1f}%)",
            description="Le niveau de résultat ouvre des leviers d'optimisation fiscale et sociale.",
            levier="Holding, intéressement, PER, OBO, transmission anticipée"
        ))

    return signals


def detect_signals_from_donnees(d: DonneesFinancieres, ratios: Ratios) -> list[Signal]:
    """Signaux nécessitant des montants absolus (non portés par Ratios).

    Complète detect_signals_from_rules. Les codes émis sont alignés sur
    data/seuils_signaux.json. Certains seuils sont des proxys sur l'exercice N
    faute d'historique N-2 (Phase 1) — précisé dans la description.
    """
    signals: list[Signal] = []
    ca = d.chiffre_affaires.montant_n

    if d.charges_personnel.montant_n > 0:
        signals.append(Signal(
            type=TypeSignal.CONFORMITE, gravite=Gravite.FAIBLE,
            code="PRESENCE_SALARIES",
            titre="Présence de salariés",
            description="La société emploie du personnel (charges de personnel > 0).",
            levier="Prévoyance salariés, mutuelle collective, paie, épargne salariale",
        ))

    pct_masse = d.charges_personnel.montant_n / ca * 100 if ca else 0
    if pct_masse > 60:
        pct = pct_masse
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="MASSE_SALARIALE_ELEVEE",
            titre=f"Masse salariale élevée ({pct:.0f}% du CA)",
            description=f"Les charges de personnel représentent {pct:.0f}% du CA (seuil 60%).",
            levier="Audit social, intéressement/PEE, structuration des rémunérations",
        ))

    if d.tresorerie_actif.montant_n > 80_000:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="TRESORERIE_EXCEDENTAIRE",
            titre=f"Trésorerie excédentaire ({d.tresorerie_actif.montant_n:,.0f} €)",
            description="La trésorerie dépasse 80 000 € : capital potentiellement dormant.",
            levier="Placement de trésorerie, contrats de capitalisation, SCPI",
        ))

    tn1 = d.tresorerie_actif.montant_n1
    var_treso = (d.tresorerie_actif.montant_n - tn1) / tn1 * 100 if tn1 and tn1 > 0 else None
    if var_treso is not None and var_treso > 20:
        var = var_treso
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="HAUSSE_TRESORERIE",
            titre=f"Hausse de trésorerie ({var:+.0f}% vs N-1)",
            description="La trésorerie progresse fortement : marge de manœuvre nouvelle.",
            levier="Placement, investissement, distribution optimisée",
        ))

    if ratios.taux_marge_brute < 25:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="MARGE_BRUTE_FAIBLE",
            titre=f"Marge brute faible ({ratios.taux_marge_brute:.1f}%)",
            description="La marge brute est sous le seuil de vigilance (25%).",
            levier="Contrôle de gestion, calcul du prix de revient, politique tarifaire",
        ))

    if ratios.taux_resultat_net < 3:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="MARGE_NETTE_FAIBLE",
            titre=f"Marge nette faible ({ratios.taux_resultat_net:.1f}%)",
            description="Le résultat net représente moins de 3% du CA.",
            levier="DAF externalisée, optimisation des charges, pilotage des marges",
        ))

    va = d.achats_consommes.variation_pct
    vca = d.chiffre_affaires.variation_pct
    if va is not None and vca is not None and va > 10 and vca <= 0:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="HAUSSE_ACHATS_SANS_CA",
            titre=f"Achats en hausse ({va:+.0f}%) sans effet sur le CA ({vca:+.0f}%)",
            description="Les achats progressent alors que le CA stagne ou baisse : dérapage de marge.",
            levier="Analyse des consommations, renégociation fournisseurs, contrôle de gestion",
        ))

    if ratios.variation_resultat_pct is not None and ratios.variation_resultat_pct > 15:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="RESULTAT_EN_CROISSANCE",
            titre=f"Résultat en croissance ({ratios.variation_resultat_pct:+.0f}%)",
            description="Le résultat net progresse nettement vs N-1.",
            levier="Intéressement, optimisation fiscale, transmission anticipée",
        ))

    if d.resultat_net.montant_n > 150_000:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="RESULTAT_NET_ELEVE_RECURRENT",
            titre=f"Résultat net élevé ({d.resultat_net.montant_n:,.0f} €)",
            description="Résultat net supérieur à 150 000 € (proxy exercice N ; récurrence à confirmer sur 3 ans).",
            levier="Diagnostic patrimonial, holding, PER, placements",
        ))

    if d.capitaux_propres.montant_n > 500_000:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="CAPITAUX_PROPRES_ELEVES_SANS_HOLDING",
            titre=f"Capitaux propres élevés ({d.capitaux_propres.montant_n:,.0f} €)",
            description="Capitaux propres > 500 000 € : enjeu de structuration et de transmission (détention holding à vérifier).",
            levier="Création de holding, pacte Dutreil, restructuration patrimoniale",
        ))

    vcl = d.creances_clients.variation_pct
    if vcl is not None and vcl < -15:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.FAIBLE,
            code="EROSION_PORTEFEUILLE_CLIENTS",
            titre=f"Baisse des créances clients ({vcl:+.0f}%)",
            description="Les créances clients reculent de plus de 15% vs N-1 : érosion possible du portefeuille.",
            levier="Assistanat commercial, diagnostic commercial, relance de la prospection",
        ))

    return signals
