# app/components/cards.py
import streamlit as st
from models import Signal, MissionRecommandee

GRAVITE_ICON = {3: "🔴", 2: "🟠", 1: "🔵"}
TYPE_CSS = {
    "risque":        lambda g: f"signal-risque-{g}",
    "opportunite":   lambda _: "signal-opportunite",
    "optimisation":  lambda _: "signal-optimisation",
    "conformite":    lambda _: "signal-conformite",
}
URGENCE_CSS   = {"immédiate": "immediate", "court terme": "court", "moyen terme": "moyen"}
URGENCE_BADGE = {
    "immédiate":   ("badge badge-red",    "🔴 Immédiate"),
    "court terme": ("badge badge-orange", "🟠 Court terme"),
    "moyen terme": ("badge badge-blue",   "🔵 Moyen terme"),
}


def render_signal(signal: Signal):
    css = TYPE_CSS.get(signal.type, lambda g: "signal-risque-1")(signal.gravite)
    icon = GRAVITE_ICON.get(signal.gravite, "⚪")
    st.markdown(f"""
    <div class="{css}">
        <div class="signal-titre">{icon} {signal.titre}</div>
        <div class="signal-desc">{signal.description}</div>
        <div class="signal-levier">→ {signal.levier}</div>
    </div>""", unsafe_allow_html=True)


def render_mission(reco: MissionRecommandee, signaux_by_code: dict[str, Signal] | None = None):
    m           = reco.mission
    urgence_css = URGENCE_CSS.get(reco.urgence, "moyen")
    badge_cls, badge_label = URGENCE_BADGE.get(reco.urgence, ("badge badge-blue", reco.urgence))
    score_pct   = int(reco.score_pertinence * 100)
    honoraires  = f'<span class="badge badge-green">{m.honoraires_indicatifs}</span>' \
                  if m.honoraires_indicatifs else ""

    signaux_by_code = signaux_by_code or {}
    if reco.signaux_declencheurs:
        chips = " ".join(
            f'<span class="badge badge-grey" title="{code}">'
            f'{signaux_by_code[code].titre if code in signaux_by_code else code.replace("_", " ").capitalize()}'
            f"</span>"
            for code in reco.signaux_declencheurs
        )
        declencheurs = f'<div class="mission-declencheurs">🧩 Déclenchée par : {chips}</div>'
    else:
        declencheurs = (
            '<div class="mission-declencheurs">📌 Proposée systématiquement '
            "(priorité 1, aucun signal requis)</div>"
        )

    st.markdown(f"""
    <div class="mission-card mission-urgence-{urgence_css}">
        <div class="mission-titre">{m.titre}</div>
        <div class="mission-arg">{reco.argumentaire}</div>
        {declencheurs}
        <div class="mission-meta">
            <span class="{badge_cls}">{badge_label}</span>
            <span class="badge badge-score">Pertinence {score_pct}%</span>
            {honoraires}
        </div>
    </div>""", unsafe_allow_html=True)
