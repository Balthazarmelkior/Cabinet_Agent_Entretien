# shared/slide_builder.py
"""
Shared slide content builder used by both Streamlit and FastAPI pipelines.
Builds structured Markdown from pipeline state for Gamma presentation generation.
"""


def _fmt(v: float) -> str:
    return f"{v:,.0f} €".replace(",", "\u202f")


def build_slide_content(state: dict) -> str:
    """Build structured Markdown for a 10-slide presentation from pipeline state.

    Works with both BillanState (Streamlit, Pydantic models) and
    WorkflowState (FastAPI, plain dicts). Accesses attributes via getattr
    with fallbacks to dict access for maximum compatibility.
    """
    donnees = state.get("donnees_financieres")
    ratios = state.get("ratios")
    note = state.get("note_sectorielle", "")
    benchmark = state.get("benchmark")
    signaux = state.get("signaux_detectes", [])
    fiche = state.get("fiche_entretien")
    swot = state.get("swot", {})

    lines = ["# Préparation Rendez-vous Bilan", ""]

    # Slide 1-2: Synthèse exécutive
    if fiche:
        synthese = getattr(fiche, "synthese_executive", None) or (fiche.get("synthese_executive") if isinstance(fiche, dict) else "")
        if synthese:
            lines += ["## Synthèse Exécutive", synthese, ""]

    # Slide 3: Chiffres clés
    if donnees:
        ca = getattr(donnees, "chiffre_affaires", None)
        if ca:
            ca_n = getattr(ca, "montant_n", 0)
            ca_var = getattr(ca, "variation_pct", None)
            lines += [
                "## Chiffres Clés",
                f"- **Chiffre d'affaires** : {_fmt(ca_n)}" + (f" ({ca_var:+.1f}% vs N-1)" if ca_var is not None else ""),
            ]
            ebe = getattr(donnees, "ebe", None)
            if ebe:
                ebe_line = f"- **EBE** : {_fmt(getattr(ebe, 'montant_n', 0))}"
                if ratios:
                    taux_ebe = getattr(ratios, "taux_ebe", None)
                    if taux_ebe is not None:
                        ebe_line += f" ({taux_ebe:.1f}% du CA)"
                lines.append(ebe_line)
            rn = getattr(donnees, "resultat_net", None)
            if rn:
                lines.append(f"- **Résultat net** : {_fmt(getattr(rn, 'montant_n', 0))}")
            treso = getattr(donnees, "tresorerie_actif", None)
            if treso:
                lines.append(f"- **Trésorerie** : {_fmt(getattr(treso, 'montant_n', 0))}")
            lines.append("")

    # Slide 4: Analyse de trésorerie
    if ratios and hasattr(ratios, "bfr"):
        lines += [
            "## Analyse de Trésorerie",
            f"- **BFR** : {_fmt(ratios.bfr)}",
            f"- **FRNG** : {_fmt(ratios.frng)}",
            f"- **Trésorerie nette** : {_fmt(ratios.tresorerie_nette)} ({ratios.tresorerie_nette_jours_ca:.0f} jours de CA)",
            f"- **Cycle de conversion** : {ratios.cycle_conversion_jours:.0f} jours (clients {ratios.delai_clients_jours:.0f}j + stocks {ratios.rotation_stocks_jours:.0f}j - fournisseurs {ratios.delai_fournisseurs_jours:.0f}j)",
            "",
        ]

    # Slide 5: Contexte sectoriel
    if note:
        lines += ["## Contexte Sectoriel", note[:2000], ""]

    # Slide 5b: SWOT sectoriel
    if swot and any(swot.get(k) for k in ("forces", "faiblesses", "opportunites", "menaces")):
        lines += ["## Analyse SWOT Sectorielle", ""]
        for label, key in [("Forces", "forces"), ("Faiblesses", "faiblesses"),
                           ("Opportunités", "opportunites"), ("Menaces", "menaces")]:
            items = swot.get(key, [])
            if items:
                lines.append(f"**{label} :**")
                for item in items:
                    lines.append(f"- {item}")
                lines.append("")

    # Slide 6: Benchmark
    if benchmark:
        libelle = getattr(benchmark, "libelle_secteur", "") or (benchmark.get("libelle_secteur", "") if isinstance(benchmark, dict) else "")
        annee = getattr(benchmark, "annee_reference", "") or (benchmark.get("annee_reference", "") if isinstance(benchmark, dict) else "")
        commentaire = getattr(benchmark, "commentaire_global", "") or (benchmark.get("commentaire_global", "") if isinstance(benchmark, dict) else "")
        bench_ratios = getattr(benchmark, "ratios", []) or (benchmark.get("ratios", []) if isinstance(benchmark, dict) else [])

        lines += [
            "## Positionnement Sectoriel",
            f"**{libelle}** — Référence {annee}",
            "",
        ]
        for r in bench_ratios[:7]:
            r_libelle = getattr(r, "libelle", "") or (r.get("libelle", "") if isinstance(r, dict) else "")
            r_val = getattr(r, "valeur_client", 0) or (r.get("valeur_client", 0) if isinstance(r, dict) else 0)
            r_med = getattr(r, "mediane_secteur", None) or (r.get("mediane_secteur") if isinstance(r, dict) else None)
            r_ecart = getattr(r, "ecart_mediane_pct", None) or (r.get("ecart_mediane_pct") if isinstance(r, dict) else None)
            r_interp = getattr(r, "interpretation", "") or (r.get("interpretation", "") if isinstance(r, dict) else "")
            med = f"{r_med:.1f}" if r_med else "—"
            ecart = f" ({r_ecart:+.1f}%)" if r_ecart else ""
            lines.append(f"- {r_libelle} : **{r_val:.1f}** vs secteur {med}{ecart} — {r_interp}")
        if commentaire:
            lines += ["", f"*{commentaire}*", ""]

    # Slide 7: Signaux
    if signaux:
        risques = [s for s in signaux if getattr(s, "type", s.get("type") if isinstance(s, dict) else "") in ("risque",)]
        opportunites = [s for s in signaux if getattr(s, "type", s.get("type") if isinstance(s, dict) else "") in ("opportunite", "optimisation")]
        if risques:
            lines += ["## Points de Vigilance", ""]
            for s in risques[:5]:
                titre = getattr(s, "titre", "") or (s.get("titre", "") if isinstance(s, dict) else "")
                desc = getattr(s, "description", "") or (s.get("description", "") if isinstance(s, dict) else "")
                lines.append(f"- **{titre}** — {desc}")
            lines.append("")
        if opportunites:
            lines += ["## Opportunités", ""]
            for s in opportunites[:5]:
                titre = getattr(s, "titre", "") or (s.get("titre", "") if isinstance(s, dict) else "")
                desc = getattr(s, "description", "") or (s.get("description", "") if isinstance(s, dict) else "")
                lines.append(f"- **{titre}** — {desc}")
            lines.append("")

    # Slide 8-9: Plan d'entretien
    if fiche:
        plan = getattr(fiche, "plan_entretien", []) or (fiche.get("plan_entretien", []) if isinstance(fiche, dict) else [])
        if plan:
            lines += ["## Plan d'Entretien", ""]
            for pt in plan:
                ordre = getattr(pt, "ordre", "") or (pt.get("ordre", "") if isinstance(pt, dict) else "")
                theme = getattr(pt, "theme", "") or (pt.get("theme", "") if isinstance(pt, dict) else "")
                contexte = getattr(pt, "contexte_chiffre", "") or (pt.get("contexte_chiffre", "") if isinstance(pt, dict) else "")
                question = getattr(pt, "question_ouverte", "") or (pt.get("question_ouverte", "") if isinstance(pt, dict) else "")
                mission = getattr(pt, "mission_associee", None) or (pt.get("mission_associee") if isinstance(pt, dict) else None)
                lines.append(f"### {ordre}. {theme}")
                lines.append(contexte)
                lines.append(f"*{question}*")
                if mission:
                    lines.append(f"→ Mission : {mission}")
                lines.append("")

    # Slide 10: Missions recommandées
    if fiche:
        missions = getattr(fiche, "missions_a_proposer", []) or (fiche.get("missions_a_proposer", []) if isinstance(fiche, dict) else [])
        if missions:
            lines += ["## Missions Recommandées", ""]
            for m in missions:
                titre = m.get("titre", "") if isinstance(m, dict) else getattr(m, "titre", "")
                urgence = m.get("urgence", "") if isinstance(m, dict) else getattr(m, "urgence", "")
                benefice = m.get("benefice_attendu", "") if isinstance(m, dict) else getattr(m, "benefice_attendu", "")
                lines.append(f"- **{titre}** [{urgence}] — {benefice}")
            lines.append("")

    # Points de vigilance
    if fiche:
        pts = getattr(fiche, "points_vigilance", []) or (fiche.get("points_vigilance", []) if isinstance(fiche, dict) else [])
        if pts:
            lines += ["## Points de Vigilance", ""]
            for p in pts:
                lines.append(f"- {p}")
            lines.append("")

    return "\n".join(lines)
