# app/components/activity.py
import plotly.graph_objects as go
import streamlit as st
from app.components.date_utils import mois_labels as _mois_labels


def render_ca_curve(
    ca_n: list,
    ca_n1: list | None,
    seuil_rentabilite: float,
):
    """Courbe CA cumulé N (+ N-1 optionnel) avec seuil de rentabilité."""
    if not ca_n:
        st.info("Données mensuelles non disponibles (uniquement pour les fichiers FEC).")
        return

    mois = _mois_labels(ca_n)
    valeurs_n = [s.solde for s in ca_n]

    fig = go.Figure()

    # CA cumulé N
    fig.add_trace(go.Scatter(
        x=mois,
        y=valeurs_n,
        mode="lines+markers",
        name="CA cumulé N",
        line=dict(color="#3B82F6", width=2.5),
        marker=dict(size=7, color="#3B82F6"),
    ))

    # CA cumulé N-1
    if ca_n1:
        mois_n1 = _mois_labels(ca_n1)
        valeurs_n1 = [s.solde for s in ca_n1]
        fig.add_trace(go.Scatter(
            x=mois_n1,
            y=valeurs_n1,
            mode="lines",
            name="CA cumulé N-1",
            line=dict(color="#94A3B8", width=2, dash="dash"),
        ))

    # Seuil de rentabilité
    fig.add_trace(go.Scatter(
        x=mois,
        y=[seuil_rentabilite] * len(mois),
        mode="lines",
        name=f"Point mort ({seuil_rentabilite:,.0f} €)".replace(",", "\u202f"),
        line=dict(color="#16A34A", width=2, dash="dash"),
    ))

    fig.update_layout(
        height=400,
        margin=dict(t=30, b=30, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#F0F0F0", tickformat=","),
        xaxis=dict(gridcolor="#F0F0F0"),
        legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
