# app/components/treasury.py
import plotly.graph_objects as go
import streamlit as st
from analysis.ratios import Ratios


def render_bfr_waterfall(ratios: Ratios, donnees):
    """Waterfall chart: Creances + Stocks - Fournisseurs = BFR."""
    clients = donnees.creances_clients.montant_n
    stocks = donnees.stocks.montant_n
    fourn = donnees.dettes_fournisseurs.montant_n

    fig = go.Figure(go.Waterfall(
        name="BFR",
        orientation="v",
        measure=["relative", "relative", "relative", "total"],
        x=["Créances clients", "Stocks", "Dettes fournisseurs", "BFR"],
        y=[clients, stocks, -fourn, 0],
        text=[f"{clients:,.0f} €", f"{stocks:,.0f} €", f"-{fourn:,.0f} €", f"{ratios.bfr:,.0f} €"],
        textposition="outside",
        connector={"line": {"color": "#94A3B8", "width": 1, "dash": "dot"}},
        increasing={"marker": {"color": "#3B82F6"}},
        decreasing={"marker": {"color": "#EF4444"}},
        totals={"marker": {"color": "#0F2044"}},
    ))
    fig.update_layout(
        height=350,
        margin=dict(t=20, b=20, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#F0F0F0", tickformat=","),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_cycle_bars(ratios: Ratios, benchmark=None):
    """Horizontal bars: delai clients, rotation stocks, delai fournisseurs, cycle total."""
    labels = ["Délai clients", "Rotation stocks", "Délai fournisseurs", "Cycle total"]
    values = [
        ratios.delai_clients_jours,
        ratios.rotation_stocks_jours,
        -ratios.delai_fournisseurs_jours,
        ratios.cycle_conversion_jours,
    ]
    colors = ["#3B82F6", "#3B82F6", "#16A34A", "#0F2044"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=labels,
        x=values,
        orientation="h",
        marker_color=colors,
        text=[f"{abs(v):.0f}j" for v in values],
        textposition="outside",
    ))

    # Benchmark overlay
    if benchmark:
        bench_map = {r.libelle: r.mediane_secteur for r in benchmark.ratios if r.mediane_secteur}
        bench_vals = []
        for label in labels[:3]:
            key_map = {
                "Délai clients": ["Délai clients", "Délai de règlement clients"],
                "Rotation stocks": ["Rotation stocks", "Rotation des stocks"],
                "Délai fournisseurs": ["Délai fournisseurs", "Délai de règlement fournisseurs"],
            }
            val = None
            for k in key_map.get(label, []):
                if k in bench_map:
                    val = bench_map[k]
                    break
            bench_vals.append(val)

        if any(v is not None for v in bench_vals):
            bench_x = []
            bench_y = []
            for i, v in enumerate(bench_vals):
                if v is not None:
                    bench_y.append(labels[i])
                    bench_x.append(v if i < 2 else -v)
            fig.add_trace(go.Scatter(
                y=bench_y,
                x=bench_x,
                mode="markers",
                marker=dict(symbol="diamond", size=12, color="#E67E22", line=dict(width=1, color="white")),
                name="Médiane secteur",
            ))

    fig.update_layout(
        height=300,
        margin=dict(t=10, b=10, l=10, r=40),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(gridcolor="#F0F0F0", title="Jours"),
        showlegend=benchmark is not None,
        legend=dict(orientation="h", y=-0.2),
    )
    st.plotly_chart(fig, use_container_width=True)


def render_treasury_gauge(ratios: Ratios):
    """Gauge indicator for tresorerie nette in days of CA."""
    jours = ratios.tresorerie_nette_jours_ca
    montant = ratios.tresorerie_nette

    # Color based on days
    if jours < 0:
        bar_color = "#DC2626"
    elif jours < 15:
        bar_color = "#F59E0B"
    else:
        bar_color = "#16A34A"

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=jours,
        number={"suffix": " jours de CA", "font": {"size": 24}},
        gauge={
            "axis": {"range": [-30, 120], "ticksuffix": "j"},
            "bar": {"color": bar_color, "thickness": 0.75},
            "steps": [
                {"range": [-30, 0], "color": "#FEE2E2"},
                {"range": [0, 15], "color": "#FEF3C7"},
                {"range": [15, 120], "color": "#D1FAE5"},
            ],
            "threshold": {
                "line": {"color": "#0F2044", "width": 3},
                "thickness": 0.8,
                "value": jours,
            },
        },
        title={"text": f"Trésorerie nette : {montant:,.0f} €".replace(",", "\u202f")},
    ))
    fig.update_layout(
        height=280,
        margin=dict(t=60, b=10, l=30, r=30),
        paper_bgcolor="rgba(0,0,0,0)",
    )
    st.plotly_chart(fig, use_container_width=True)


def render_tresorerie_curve(soldes: list, bfr: float):
    """Courbe trésorerie mensuelle avec seuil BFR."""
    from app.components.date_utils import mois_labels as _mois_labels

    if not soldes:
        st.info("Données mensuelles non disponibles (uniquement pour les fichiers FEC).")
        return

    mois_labels = _mois_labels(soldes)

    valeurs = [s.solde for s in soldes]

    fig = go.Figure()

    # Courbe trésorerie
    fig.add_trace(go.Scatter(
        x=mois_labels,
        y=valeurs,
        mode="lines+markers",
        name="Trésorerie",
        line=dict(color="#3B82F6", width=2.5),
        marker=dict(size=7, color="#3B82F6"),
        fill="tozeroy",
        fillcolor="rgba(59, 130, 246, 0.08)",
    ))

    # Ligne seuil BFR
    fig.add_trace(go.Scatter(
        x=mois_labels,
        y=[bfr] * len(mois_labels),
        mode="lines",
        name=f"Seuil BFR ({bfr:,.0f} €)".replace(",", "\u202f"),
        line=dict(color="#DC2626", width=2, dash="dash"),
    ))

    fig.update_layout(
        height=350,
        margin=dict(t=30, b=30, l=20, r=20),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        yaxis=dict(gridcolor="#F0F0F0", tickformat=","),
        xaxis=dict(gridcolor="#F0F0F0"),
        legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)
