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
        st.markdown('<div class="section-card"><div class="section-title">📁 Fichier client</div>', unsafe_allow_html=True)
        fichier = st.file_uploader(
            "FEC (.txt/.csv) ou bilan PDF",
            type=["pdf", "txt", "csv"],
            label_visibility="collapsed",
        )
        if fichier:
            ext = Path(fichier.name).suffix.upper()
            st.success(f"✅ {fichier.name} — {ext} — {fichier.size // 1024} Ko")
        st.markdown('</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-card"><div class="section-title">⚙ Paramètres</div>', unsafe_allow_html=True)
        nom_client = st.text_input("Nom du client *", placeholder="SARL Dupont & Fils")
        c1, c2 = st.columns([3, 1])
        with c1:
            code_naf = st.text_input("Code NAF * (5 car.)", placeholder="4711F", max_chars=5)
        with c2:
            st.markdown("<br>", unsafe_allow_html=True)
            st.link_button("Chercher NAF", "https://www.insee.fr/fr/metadonnees/nafr2/")
        catalogue = st.text_input("Catalogue missions", value="data/catalogue_missions.json")
        st.markdown('</div>', unsafe_allow_html=True)

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
        run_analysis(fichier, nom_client, code_naf, catalogue)


# ─────────────────────────────────────────────────────────────────────────────
# ANALYSE
# ─────────────────────────────────────────────────────────────────────────────
def run_analysis(fichier, nom_client, code_naf, catalogue_path):
    from graph import build_graph

    tmp_path = None
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(fichier.name).suffix) as tmp:
        tmp.write(fichier.read())
        tmp_path = tmp.name

    etapes = [
        (0.15, "📄 Extraction des données financières..."),
        (0.35, "📐 Calcul des ratios..."),
        (0.55, "🔍 Détection des signaux..."),
        (0.72, "📊 Benchmarking sectoriel..."),
        (0.87, "🎯 Matching des missions..."),
        (0.95, "📝 Génération de la fiche d'entretien..."),
    ]

    bar    = st.progress(0.0)
    status = st.empty()

    try:
        graph       = build_graph()
        final_state = {}
        step_idx    = 0

        for event in graph.stream({
            "fichier_path":   tmp_path,
            "catalogue_path": catalogue_path,
            "code_naf":       code_naf.upper().strip(),
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


# ─────────────────────────────────────────────────────────────────────────────
# DASHBOARD
# ─────────────────────────────────────────────────────────────────────────────
def render_dashboard():
    from app.components.charts   import render_benchmark_radar, render_signals_bar
    from app.components.cards    import render_signal, render_mission
    from app.components.download import get_word_bytes

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
             f"{ratios.taux_ebe:.1f}% du CA", ratios.taux_ebe >= 5)
    kpi_html(c3, "Résultat net", fmt(donnees.resultat_net.montant_n),
             dpct(donnees.resultat_net.variation_pct),
             (donnees.resultat_net.variation_pct or 0) >= 0)
    kpi_html(c4, "Trésorerie", fmt(donnees.tresorerie_actif.montant_n))
    kpi_html(c5, "Signaux",
             str(len(signaux)),
             f"{sum(1 for s in signaux if s.gravite == 3)} critique(s)",
             sum(1 for s in signaux if s.gravite == 3) == 0)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    t_bench, t_sig, t_mis, t_fiche = st.tabs([
        "📊 Benchmark sectoriel",
        f"🔍 Signaux ({len(signaux)})",
        f"🎯 Missions ({len(missions)})",
        "📋 Fiche entretien",
    ])

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
                    with st.expander(f"{pt.ordre}. {pt.theme}", expanded=(pt.ordre <= 2)):
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


# ─────────────────────────────────────────────────────────────────────────────
# ROUTING
# ─────────────────────────────────────────────────────────────────────────────
if st.session_state.get("analyse_done"):
    render_dashboard()
else:
    render_form()
