# app/main.py
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import html as html_lib
import streamlit as st
import tempfile
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

st.set_page_config(
    page_title="Entretien Bilan",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,400;0,9..40,500;0,9..40,600;1,9..40,400&family=DM+Serif+Display&display=swap');

*, body { font-family: 'DM Sans', sans-serif !important; }
h1, h2, h3 { font-family: 'DM Serif Display', serif !important; }

[data-testid="stAppViewContainer"] { background: #F2F4F8; }
[data-testid="stHeader"] { background: transparent; }

.app-header {
    background: linear-gradient(135deg, #0A1A3A 0%, #0F2044 50%, #1B3A6B 100%);
    padding: 2rem 2.5rem 1.8rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    color: white;
    box-shadow: 0 4px 24px rgba(15,32,68,0.18);
}
.app-header h1 { margin:0; font-size:1.9rem; color:white; letter-spacing:-0.02em; }
.app-header p  { margin:.4rem 0 0; opacity:.7; font-size:.88rem; }

.kpi-card {
    background:white; border-radius:12px; padding:1.1rem 1.4rem;
    border:1px solid #E2E8F0; box-shadow:0 1px 6px rgba(0,0,0,0.05);
    height:100%;
}
.kpi-label { font-size:.72rem; color:#64748B; font-weight:600;
             letter-spacing:.06em; text-transform:uppercase; }
.kpi-value { font-size:1.6rem; font-weight:700; color:#0F2044;
             margin:.25rem 0 .1rem; line-height:1; }
.kpi-delta-pos { color:#16A34A; font-size:.8rem; font-weight:500; }
.kpi-delta-neg { color:#DC2626; font-size:.8rem; font-weight:500; }
.kpi-neutral   { color:#64748B; font-size:.8rem; }

.section-card {
    background:white; border-radius:14px; padding:1.4rem 1.6rem;
    border:1px solid #E2E8F0; box-shadow:0 1px 8px rgba(0,0,0,0.04);
    margin-bottom:.8rem;
}
.section-title {
    font-family:'DM Serif Display',serif !important;
    font-size:1.05rem; color:#0F2044;
    margin-bottom:.9rem; padding-bottom:.5rem;
    border-bottom:2px solid #EEF2F8;
}

/* Signaux */
.signal-risque-3    {border-left:4px solid #DC2626;background:#FEF2F2;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;}
.signal-risque-2    {border-left:4px solid #EA580C;background:#FFF7ED;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;}
.signal-risque-1    {border-left:4px solid #2563EB;background:#EFF6FF;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;}
.signal-opportunite {border-left:4px solid #16A34A;background:#F0FDF4;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;}
.signal-optimisation{border-left:4px solid #7C3AED;background:#F5F3FF;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;}
.signal-conformite  {border-left:4px solid #D97706;background:#FFFBEB;border-radius:8px;padding:.75rem 1rem;margin-bottom:.5rem;}
.signal-titre{font-weight:600;font-size:.88rem;color:#0F2044;}
.signal-desc {font-size:.8rem;color:#475569;margin-top:.2rem;line-height:1.4;}
.signal-levier{font-size:.75rem;color:#94A3B8;margin-top:.3rem;font-style:italic;}

/* Missions */
.mission-card{background:white;border:1px solid #E2E8F0;border-radius:10px;padding:1rem 1.1rem;margin-bottom:.6rem;}
.mission-urgence-immediate{border-top:3px solid #DC2626;}
.mission-urgence-court    {border-top:3px solid #EA580C;}
.mission-urgence-moyen    {border-top:3px solid #2563EB;}
.mission-titre{font-weight:600;color:#0F2044;font-size:.92rem;}
.mission-arg  {color:#475569;font-size:.82rem;margin-top:.35rem;line-height:1.45;}
.mission-meta {display:flex;gap:.6rem;margin-top:.55rem;flex-wrap:wrap;}
.badge{font-size:.7rem;font-weight:600;padding:.18rem .55rem;border-radius:20px;letter-spacing:.02em;}
.badge-red   {background:#FEE2E2;color:#B91C1C;}
.badge-orange{background:#FEF3C7;color:#B45309;}
.badge-blue  {background:#DBEAFE;color:#1D4ED8;}
.badge-green {background:#D1FAE5;color:#065F46;}
.badge-score {background:#EEF2FF;color:#3730A3;}

/* Overrides Streamlit */
.stButton>button{border-radius:8px !important;font-weight:600 !important;}
div[data-testid="stMetric"]{background:white;border-radius:12px;padding:.8rem;border:1px solid #E2E8F0;}
[data-testid="stTab"] button{font-size:.88rem !important;}
.stDownloadButton>button{background:#0F2044 !important;color:white !important;border-radius:8px !important;font-weight:600 !important;}

/* File uploader */
[data-testid="stFileUploader"] {width:100% !important;}
[data-testid="stFileUploader"] section {padding:.8rem !important;}
[data-testid="stFileUploader"] button {
    font-size:0 !important;
    padding:.45rem 1rem !important;
    border-radius:6px !important;
}
[data-testid="stFileUploader"] button::after {
    content:"Parcourir";
    font-size:.82rem !important;
    font-weight:500;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="app-header">
    <h1>📊 Préparation entretien bilan</h1>
    <p>Analyse financière · Benchmarking sectoriel · Recommandations de missions</p>
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# FORMULAIRE
# ─────────────────────────────────────────────────────────────────────────────
def render_form():
    col_left, col_right = st.columns([1, 1], gap="large")

    with col_left:
        with st.container(border=True):
            st.markdown("#### 📁 Fichiers client")
            fichier = st.file_uploader(
                "FEC ou bilan N *",
                type=["pdf", "txt", "csv"],
                label_visibility="visible",
                key="fec_n",
                help="FEC (.txt/.csv) ou bilan PDF de l'exercice N",
            )
            if fichier:
                ext = Path(fichier.name).suffix.upper()
                st.success(f"N : {fichier.name} — {ext} — {fichier.size // 1024} Ko")

            fichier_n1 = st.file_uploader(
                "FEC N-1 (optionnel)",
                type=["txt", "csv"],
                label_visibility="visible",
                key="fec_n1",
                help="FEC de l'exercice N-1 pour les comparaisons",
            )
            if fichier_n1:
                ext_n1 = Path(fichier_n1.name).suffix.upper()
                st.success(f"N-1 : {fichier_n1.name} — {ext_n1} — {fichier_n1.size // 1024} Ko")

    with col_right:
        with st.container(border=True):
            st.markdown("#### ⚙ Paramètres")
            nom_client = st.text_input("Nom du client *", placeholder="SARL Dupont & Fils")
            c1, c2 = st.columns([3, 1])
            with c1:
                code_naf = st.text_input("Code NAF * (5 car.)", placeholder="4711F", max_chars=5)
            with c2:
                st.markdown("<br>", unsafe_allow_html=True)
                st.link_button("Chercher NAF", "https://www.insee.fr/fr/metadonnees/nafr2/")
            catalogue = st.text_input("Catalogue missions", value="data/catalogue_missions.json")
            anonymiser = st.checkbox(
                "🔒 Anonymiser les données",
                value=True,
                help="Masque les noms de société, SIREN et libellés tiers avant envoi aux agents IA",
            )

    st.markdown("<br>", unsafe_allow_html=True)
    _, col_btn, _ = st.columns([1, 2, 1])
    with col_btn:
        lancer = st.button(
            "🚀 Lancer l'analyse",
            use_container_width=True,
            type="primary",
            disabled=not (fichier and nom_client and code_naf),
        )

    if lancer:
        run_analysis(fichier, nom_client, code_naf, catalogue, fichier_n1, anonymiser)


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis(fichier, nom_client, code_naf, catalogue_path, fichier_n1=None, anonymize=False):
    from graph import build_graph

    tmp_path    = None
    tmp_path_n1 = None

    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(fichier.name).suffix) as tmp:
        tmp.write(fichier.read())
        tmp_path = tmp.name

    if fichier_n1:
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(fichier_n1.name).suffix) as tmp_n1:
            tmp_n1.write(fichier_n1.read())
            tmp_path_n1 = tmp_n1.name

    etapes = [
        (0.12, "📄 Extraction des données financières..."),
        (0.28, "📐 Calcul des ratios..."),
        (0.42, "🔍 Détection des signaux..."),
        (0.55, "📊 Benchmarking sectoriel..."),
        (0.62, "🌐 Analyse sectorielle Perplexity..."),
        (0.75, "🎯 Matching des missions..."),
        (0.85, "📝 Génération de la fiche d'entretien..."),
        (0.95, "🎬 Génération des slides Gamma..."),
    ]

    bar    = st.progress(0.0)
    status = st.empty()

    try:
        graph       = build_graph()
        final_state = {}
        step_idx    = 0

        for event in graph.stream({
            "fichier_path":    tmp_path,
            "fichier_path_n1": tmp_path_n1,
            "catalogue_path":  catalogue_path,
            "code_naf":        code_naf.upper().strip(),
            "anonymize":       anonymize,
        }):
            if step_idx < len(etapes):
                pct, label = etapes[step_idx]
                bar.progress(pct, text=label)
                step_idx += 1
            # Chaque event = {node_name: {clés mises à jour par ce node}}
            # On accumule toutes les clés pour reconstituer l'état complet.
            for node_output in event.values():
                final_state.update(node_output)

        bar.progress(1.0, text="✅ Analyse terminée !")
        status.empty()

        st.session_state["analyse"]      = final_state
        st.session_state["nom_client"]   = nom_client
        st.session_state["code_naf"]     = code_naf.upper().strip()
        st.session_state["analyse_done"] = True
        st.rerun()

    except Exception as e:
        bar.empty()
        st.error(f"❌ Erreur lors de l'analyse : {e}")
        raise

    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)
        if tmp_path_n1:
            Path(tmp_path_n1).unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
def render_dashboard():
    from app.components.charts   import render_benchmark_radar, render_signals_bar
    from app.components.cards    import render_signal, render_mission
    from app.components.download import get_word_bytes
    from app.components.treasury import render_bfr_waterfall, render_cycle_bars, render_treasury_gauge

    analyse   = st.session_state["analyse"]
    donnees   = analyse["donnees_financieres"]
    ratios    = analyse["ratios"]
    benchmark = analyse.get("benchmark")
    signaux   = analyse.get("signaux_detectes", [])
    missions  = analyse.get("missions_recommandees", [])
    fiche     = analyse.get("fiche_entretien")
    client    = st.session_state["nom_client"]
    naf       = st.session_state.get("code_naf", "")

    # Bandeau client
    col_info, col_reset = st.columns([5, 1])
    with col_info:
        sect = benchmark.libelle_secteur if benchmark else donnees.secteur_activite or ""
        st.markdown(f"**{client}** · Exercice {donnees.exercice_n} · NAF {naf} · {sect}")
    with col_reset:
        if st.button("← Nouvelle analyse"):
            for k in ["analyse", "nom_client", "code_naf", "analyse_done"]:
                st.session_state.pop(k, None)
            st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────────────────────
    c1, c2, c3, c4, c5 = st.columns(5)

    def fmt(v):  return f"{v:,.0f} €".replace(",", "\u202f")
    def dpct(v): return f"{v:+.1f}%" if v is not None else None

    def kpi_html(col, label, value, delta=None, pos=True):
        d_html = ""
        if delta:
            cls = "kpi-delta-pos" if pos else "kpi-delta-neg"
            d_html = f'<div class="{cls}">{"▲" if pos else "▼"} {delta}</div>'
        col.markdown(f"""
        <div class="kpi-card">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {d_html}
        </div>""", unsafe_allow_html=True)

    kpi_html(c1, "Chiffre d'affaires", fmt(donnees.chiffre_affaires.montant_n),
             dpct(donnees.chiffre_affaires.variation_pct),
             (donnees.chiffre_affaires.variation_pct or 0) >= 0)
    kpi_html(c2, "EBE", fmt(donnees.ebe.montant_n),
             dpct(donnees.ebe.variation_pct) if donnees.ebe.variation_pct is not None else f"{ratios.taux_ebe:.1f}% du CA",
             (donnees.ebe.variation_pct or ratios.taux_ebe - 5) >= 0)
    kpi_html(c3, "Résultat net", fmt(donnees.resultat_net.montant_n),
             dpct(donnees.resultat_net.variation_pct),
             (donnees.resultat_net.variation_pct or 0) >= 0)
    kpi_html(c4, "Trésorerie", fmt(donnees.tresorerie_actif.montant_n),
             dpct(donnees.tresorerie_actif.variation_pct),
             (donnees.tresorerie_actif.variation_pct or 0) >= 0)
    kpi_html(c5, "Signaux",
             str(len(signaux)),
             f"{sum(1 for s in signaux if s.gravite == 3)} critique(s)",
             sum(1 for s in signaux if s.gravite == 3) == 0)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    has_n1 = donnees.chiffre_affaires.montant_n1 is not None
    tab_labels = [
        "📊 Benchmark sectoriel",
        "🌐 Analyse sectorielle",
        "💰 Trésorerie",
        f"🔍 Signaux ({len(signaux)})",
        f"🎯 Missions ({len(missions)})",
        "📋 Fiche entretien",
        "🎬 Slides Gamma",
    ]
    if has_n1:
        tab_labels.insert(3, "📈 Évolution N/N-1")

    all_tabs = st.tabs(tab_labels)

    if has_n1:
        t_bench, t_secteur, t_treso, t_evol, t_sig, t_mis, t_fiche, t_slides = all_tabs
    else:
        t_bench, t_secteur, t_treso, t_sig, t_mis, t_fiche, t_slides = all_tabs
        t_evol = None

    # ── Benchmark ─────────────────────────────────────────────────────────────
    with t_bench:
        if not benchmark:
            st.info("Benchmark non disponible.")
        else:
            src = benchmark.ratios[0].source if benchmark.ratios else "—"
            st.markdown(f"""
            <div style="background:#EEF2FF;border-radius:10px;padding:.75rem 1.2rem;margin-bottom:1rem;font-size:.85rem;">
                <b>{html_lib.escape(benchmark.libelle_secteur)}</b> · Référence {benchmark.annee_reference}
                · {benchmark.taille_entreprise} · Source : {html_lib.escape(src)}
            </div>""", unsafe_allow_html=True)

            col_r, col_t = st.columns([1, 1], gap="large")
            with col_r:
                st.markdown('<div class="section-title">Radar sectoriel</div>', unsafe_allow_html=True)
                render_benchmark_radar(benchmark)

            with col_t:
                st.markdown('<div class="section-title">Détail des ratios</div>', unsafe_allow_html=True)
                ICON = {"favorable": "🟢", "dans la norme": "🟡",
                        "en dessous de la médiane": "🟠", "défavorable": "🔴",
                        "données insuffisantes": "⚪"}
                for r in benchmark.ratios:
                    icon  = ICON.get(r.interpretation, "⚪")
                    med   = f"{r.mediane_secteur:.1f}" if r.mediane_secteur else "—"
                    ecart = f"{r.ecart_mediane_pct:+.1f}%" if r.ecart_mediane_pct else "—"
                    ecart_color = "#16A34A" if (r.ecart_mediane_pct or 0) > 0 else "#DC2626"
                    st.markdown(f"""
                    <div style="display:flex;justify-content:space-between;align-items:center;
                                padding:.45rem 0;border-bottom:1px solid #F1F5F9;font-size:.83rem;">
                        <span style="color:#475569;">{icon} {r.libelle}</span>
                        <span>
                            <b>{r.valeur_client:.1f}</b>
                            <span style="color:#94A3B8;font-size:.75rem;"> vs {med} sect.</span>
                            <span style="color:{ecart_color};font-size:.75rem;font-weight:600;"> {ecart}</span>
                        </span>
                    </div>""", unsafe_allow_html=True)

            st.info(f"💬 {benchmark.commentaire_global}")

    # ── Évolution N/N-1 ───────────────────────────────────────────────────────
    if t_evol is not None:
        with t_evol:
            exercice_n1 = donnees.exercice_n - 1
            st.markdown(
                f'<div class="section-title">Comparatif exercice {donnees.exercice_n} vs {exercice_n1}</div>',
                unsafe_allow_html=True,
            )
            postes = [
                donnees.chiffre_affaires,
                donnees.achats_consommes,
                donnees.charges_externes,
                donnees.charges_personnel,
                donnees.ebe,
                donnees.resultat_exploitation,
                donnees.resultat_net,
                donnees.immobilisations_nettes,
                donnees.stocks,
                donnees.creances_clients,
                donnees.tresorerie_actif,
                donnees.capitaux_propres,
                donnees.dettes_financieres,
                donnees.dettes_fournisseurs,
            ]
            rows_html = ""
            for p in postes:
                n_fmt  = fmt(p.montant_n)
                n1_fmt = fmt(p.montant_n1) if p.montant_n1 is not None else "—"
                var    = p.variation_pct
                if var is None:
                    var_html = '<span style="color:#94A3B8;">—</span>'
                elif var >= 0:
                    var_html = f'<span style="color:#16A34A;font-weight:600;">▲ {var:+.1f}%</span>'
                else:
                    var_html = f'<span style="color:#DC2626;font-weight:600;">▼ {var:.1f}%</span>'
                rows_html += f"""
                <tr style="border-bottom:1px solid #F1F5F9;">
                    <td style="padding:.4rem .6rem;color:#475569;font-size:.83rem;">{p.libelle}</td>
                    <td style="padding:.4rem .6rem;text-align:right;font-weight:600;font-size:.83rem;">{n_fmt}</td>
                    <td style="padding:.4rem .6rem;text-align:right;color:#64748B;font-size:.83rem;">{n1_fmt}</td>
                    <td style="padding:.4rem .6rem;text-align:right;font-size:.83rem;">{var_html}</td>
                </tr>"""

            st.markdown(f"""
            <table style="width:100%;border-collapse:collapse;">
                <thead>
                    <tr style="background:#F8FAFC;">
                        <th style="padding:.5rem .6rem;text-align:left;font-size:.75rem;color:#64748B;text-transform:uppercase;letter-spacing:.05em;">Poste</th>
                        <th style="padding:.5rem .6rem;text-align:right;font-size:.75rem;color:#64748B;text-transform:uppercase;letter-spacing:.05em;">N ({donnees.exercice_n})</th>
                        <th style="padding:.5rem .6rem;text-align:right;font-size:.75rem;color:#64748B;text-transform:uppercase;letter-spacing:.05em;">N-1 ({exercice_n1})</th>
                        <th style="padding:.5rem .6rem;text-align:right;font-size:.75rem;color:#64748B;text-transform:uppercase;letter-spacing:.05em;">Variation</th>
                    </tr>
                </thead>
                <tbody>{rows_html}</tbody>
            </table>
            """, unsafe_allow_html=True)

    # ── Signaux ───────────────────────────────────────────────────────────────
    with t_sig:
        if not signaux:
            st.info("Aucun signal détecté.")
        else:
            col_g, col_l = st.columns([1, 1], gap="large")
            with col_g:
                render_signals_bar(signaux)
            with col_l:
                filtre = st.radio(
                    "Filtrer",
                    ["Tous", "🔴 Risques", "🟢 Opportunités", "🟣 Optimisation", "🟡 Conformité"],
                    horizontal=True, label_visibility="collapsed",
                )
                MAP = {"Tous": None, "🔴 Risques": "risque", "🟢 Opportunités": "opportunite",
                       "🟣 Optimisation": "optimisation", "🟡 Conformité": "conformite"}
                affichés = [s for s in signaux if not MAP[filtre] or s.type == MAP[filtre]]
                for s in affichés:
                    render_signal(s)

    # ── Missions ──────────────────────────────────────────────────────────────
    with t_mis:
        if not missions:
            st.info("Aucune mission recommandée.")
        else:
            c_left, c_right = st.columns(2, gap="large")
            for i, reco in enumerate(missions):
                with (c_left if i % 2 == 0 else c_right):
                    render_mission(reco)

    # ── Fiche entretien ───────────────────────────────────────────────────────
    with t_fiche:
        if not fiche:
            st.info("Fiche non générée.")
        else:
            col_f, col_d = st.columns([2, 1], gap="large")

            with col_f:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">Synthèse exécutive</div>', unsafe_allow_html=True)
                st.markdown(fiche.synthese_executive)
                st.markdown('</div>', unsafe_allow_html=True)

                if fiche.points_vigilance:
                    pts = "\n\n".join(f"- {p}" for p in fiche.points_vigilance)
                    st.warning(f"⚠️ **Points de vigilance**\n\n{pts}")

                st.markdown('<div class="section-title" style="margin-top:1rem;">Plan d\'entretien</div>',
                            unsafe_allow_html=True)
                for pt in fiche.plan_entretien:
                    with st.expander(f"{pt.ordre} — {pt.theme}", expanded=(pt.ordre <= 2)):
                        st.caption(pt.contexte_chiffre)
                        st.markdown(f"*❓ {pt.question_ouverte}*")
                        if pt.mission_associee:
                            st.markdown(f"→ `{pt.mission_associee}`")

            with col_d:
                st.markdown('<div class="section-card">', unsafe_allow_html=True)
                st.markdown('<div class="section-title">📥 Export</div>', unsafe_allow_html=True)
                word_bytes = get_word_bytes(fiche)
                st.download_button(
                    label="⬇ Télécharger la fiche Word",
                    data=word_bytes,
                    file_name=f"entretien_{client.replace(' ','_')}_{donnees.exercice_n}.docx",
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True,
                )
                st.markdown("---")
                st.markdown("**Éléments à recueillir**")
                for i, elem in enumerate(fiche.elements_a_recueillir):
                    st.checkbox(elem, key=f"elem_{i}")
                st.markdown("---")
                st.markdown("**Comment conclure**")
                st.info(fiche.conclusion_conseillee)
                st.markdown('</div>', unsafe_allow_html=True)

    # ── Analyse sectorielle ──────────────────────────────────────────────────────
    with t_secteur:
        note = analyse.get("note_sectorielle")
        sources = analyse.get("sources_perplexity", [])
        valides = analyse.get("sources_valides", False)

        if not note or note == "Analyse sectorielle non disponible.":
            st.info("Analyse sectorielle non disponible (clé PERPLEXITY_API_KEY non configurée ou erreur API).")
        else:
            if valides:
                st.markdown("""
                <div style="background:#D1FAE5;border-radius:8px;padding:.6rem 1rem;
                    margin-bottom:1rem;font-size:.85rem;color:#065F46;">
                    <b>✅ Sources validées</b> — Données issues de sources officielles (INSEE, Banque de France, CCI)
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div style="background:#FEF3C7;border-radius:8px;padding:.6rem 1rem;
                    margin-bottom:1rem;font-size:.85rem;color:#92400E;">
                    <b>⚠️ Sources non vérifiées</b> — Les sources n'ont pas pu être validées sur des domaines officiels
                </div>""", unsafe_allow_html=True)

            st.markdown('<div class="section-card">', unsafe_allow_html=True)
            st.markdown(note)
            st.markdown('</div>', unsafe_allow_html=True)

            if sources:
                st.markdown('<div class="section-title" style="margin-top:1rem;">📎 Sources</div>',
                            unsafe_allow_html=True)
                for s in sources:
                    url = s.get("url", "")
                    titre = s.get("titre", url)
                    if url:
                        st.markdown(f"- [{html_lib.escape(titre or url)}]({url})")

    # ── Trésorerie ────────────────────────────────────────────────────────────
    with t_treso:
        def var_pct(n, n1):
            if n1 is None or n1 == 0:
                return None
            return round((n - n1) / abs(n1) * 100, 1)

        bfr_var = var_pct(ratios.bfr, ratios.bfr_n1)
        frng_var = var_pct(ratios.frng, ratios.frng_n1)
        tn_var = var_pct(ratios.tresorerie_nette, ratios.tresorerie_nette_n1)

        c1, c2, c3, c4 = st.columns(4)
        kpi_html(c1, "BFR", fmt(ratios.bfr),
                 dpct(bfr_var) if bfr_var is not None else None,
                 (bfr_var or 0) <= 0)
        kpi_html(c2, "FRNG", fmt(ratios.frng),
                 dpct(frng_var) if frng_var is not None else None,
                 (frng_var or 0) >= 0)
        kpi_html(c3, "Trésorerie nette", fmt(ratios.tresorerie_nette),
                 dpct(tn_var) if tn_var is not None else None,
                 (tn_var or 0) >= 0)
        kpi_html(c4, "Cycle de conversion",
                 f"{ratios.cycle_conversion_jours:.0f} jours",
                 None, True)

        st.markdown("<br>", unsafe_allow_html=True)

        col_wf, col_cy = st.columns([1, 1], gap="large")
        with col_wf:
            st.markdown('<div class="section-title">Décomposition du BFR</div>', unsafe_allow_html=True)
            render_bfr_waterfall(ratios, donnees)
        with col_cy:
            st.markdown('<div class="section-title">Cycle de conversion (jours)</div>', unsafe_allow_html=True)
            render_cycle_bars(ratios, benchmark)

        st.markdown('<div class="section-title">Trésorerie nette</div>', unsafe_allow_html=True)
        col_gauge, col_interp = st.columns([1, 1], gap="large")
        with col_gauge:
            render_treasury_gauge(ratios)
        with col_interp:
            jours = ratios.tresorerie_nette_jours_ca
            if jours < 0:
                st.error(f"**Trésorerie nette négative** ({jours:.0f} jours de CA) — Le FRNG ne couvre pas le BFR. Risque de cessation de paiement.")
            elif jours < 15:
                st.warning(f"**Trésorerie tendue** ({jours:.0f} jours de CA) — Marge de sécurité insuffisante. Un suivi prévisionnel est recommandé.")
            else:
                st.success(f"**Trésorerie confortable** ({jours:.0f} jours de CA) — L'entreprise dispose d'une marge de manoeuvre financière.")

            if has_n1 and ratios.tresorerie_nette_n1 is not None:
                delta = ratios.tresorerie_nette - ratios.tresorerie_nette_n1
                if delta > 0:
                    st.markdown(f"📈 Amélioration de **{fmt(delta)}** vs N-1")
                elif delta < 0:
                    st.markdown(f"📉 Dégradation de **{fmt(abs(delta))}** vs N-1")
                else:
                    st.markdown("➡️ Stable vs N-1")

    # ── Slides Gamma ─────────────────────────────────────────────────────────
    with t_slides:
        slides_url = analyse.get("slides_url")
        contenu = analyse.get("contenu_slides", "")

        if not slides_url:
            st.info("Présentation non disponible (clé GAMMA_API_KEY non configurée ou erreur API).")
            if contenu:
                st.markdown("**Aperçu du contenu généré :**")
                with st.expander("Contenu Markdown", expanded=False):
                    st.markdown(contenu)
        else:
            st.markdown(f"""
            <div style="background:#EEF2FF;border-radius:10px;padding:.75rem 1.2rem;
                margin-bottom:1rem;font-size:.85rem;">
                <b>🎬 Présentation générée</b> — 10 slides
            </div>""", unsafe_allow_html=True)

            st.link_button("🔗 Ouvrir la présentation Gamma", slides_url, use_container_width=True)

            st.markdown(f"""
            <iframe src="{slides_url}/embed" width="100%" height="500"
                    frameborder="0" style="border-radius:12px;margin-top:1rem;"
                    allowfullscreen></iframe>
            """, unsafe_allow_html=True)

            if contenu:
                with st.expander("📄 Contenu source (Markdown)"):
                    st.code(contenu, language="markdown")


# ─────────────────────────────────────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("analyse_done"):
    render_dashboard()
else:
    render_form()
