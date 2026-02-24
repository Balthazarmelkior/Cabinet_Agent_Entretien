# app/components/charts.py
import plotly.graph_objects as go
import streamlit as st
from models import BenchmarkSectoriel
from collections import Counter


def render_benchmark_radar(benchmark: BenchmarkSectoriel):
    labels, vals_client, vals_med = [], [], []

    for r in benchmark.ratios:
        if r.mediane_secteur is None or r.quartile_q1 is None or r.quartile_q3 is None:
            continue
        rng = (r.quartile_q3 - r.quartile_q1) or 1
        labels.append(r.libelle)
        vals_client.append(round(min(max((r.valeur_client   - r.quartile_q1) / rng * 100, 0), 140), 1))
        vals_med.append(   round(min(max((r.mediane_secteur - r.quartile_q1) / rng * 100, 0), 140), 1))

    if not labels:
        st.info("Données benchmark insuffisantes pour le graphique radar.")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatterpolar(
        r=vals_client + [vals_client[0]], theta=labels + [labels[0]],
        fill="toself", name="Client",
        line=dict(color="#2255A4", width=2),
        fillcolor="rgba(34,85,164,0.15)",
    ))
    fig.add_trace(go.Scatterpolar(
        r=vals_med + [vals_med[0]], theta=labels + [labels[0]],
        fill="toself", name="Médiane secteur",
        line=dict(color="#E67E22", width=2, dash="dot"),
        fillcolor="rgba(230,126,34,0.08)",
    ))
    fig.update_layout(
        polar=dict(
            bgcolor="#F8F9FA",
            radialaxis=dict(visible=True, range=[0, 130], showticklabels=False, gridcolor="#E8ECF2"),
            angularaxis=dict(gridcolor="#E8ECF2"),
        ),
        showlegend=True,
        legend=dict(orientation="h", y=-0.15),
        height=400,
        margin=dict(t=20, b=50, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_signals_bar(signaux: list):
    if not signaux:
        st.info("Aucun signal détecté.")
        return

    TYPE_COLORS = {
        "risque":       "#C0392B",
        "opportunite":  "#1A9B5C",
        "optimisation": "#8B5CF6",
        "conformite":   "#F59E0B",
    }
    TYPE_LABELS = {
        "risque": "Risques", "opportunite": "Opportunités",
        "optimisation": "Optimisation", "conformite": "Conformité",
    }
    GRAVITE_LABELS = {3: "Élevée", 2: "Moyenne", 1: "Faible"}
    GRAVITE_OPACITY= {3: 1.0, 2: 0.65, 1: 0.4}

    types   = sorted(set(s.type for s in signaux))
    counts  = Counter((s.type, s.gravite) for s in signaux)

    fig = go.Figure()
    for g in [3, 2, 1]:
        fig.add_trace(go.Bar(
            name=f"Gravité {GRAVITE_LABELS[g]}",
            x=[TYPE_LABELS.get(t, t) for t in types],
            y=[counts.get((t, g), 0) for t in types],
            marker_color=[TYPE_COLORS.get(t, "#999") for t in types],
            marker_opacity=GRAVITE_OPACITY[g],
            text=[counts.get((t, g), 0) or "" for t in types],
            textposition="inside",
        ))

    fig.update_layout(
        barmode="stack",
        height=280,
        margin=dict(t=10, b=10, l=0, r=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=True,
        legend=dict(orientation="h", y=-0.3),
        yaxis=dict(gridcolor="#F0F0F0", title="Nombre"),
        xaxis=dict(gridcolor="rgba(0,0,0,0)"),
    )
    st.plotly_chart(fig, use_container_width=True)
