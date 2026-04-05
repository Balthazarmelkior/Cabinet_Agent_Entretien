# Treasury Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a "Tresorerie" tab to the Streamlit dashboard with BFR/FRNG/tresorerie nette indicators, waterfall BFR chart, cycle de conversion bars, and tresorerie nette gauge.

**Architecture:** Extend the existing `Ratios` dataclass with 8 new fields computed from `DonneesFinancieres`. Create a dedicated Plotly chart component file. Add a new tab to the dashboard. No LangGraph changes.

**Tech Stack:** Python dataclasses, Plotly (already used), Streamlit (already used).

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Modify | `analysis/ratios.py:12-32,34-70` | Add 8 fields to `Ratios`, compute them in `compute_ratios()` |
| Create | `app/components/treasury.py` | 3 Plotly chart functions |
| Modify | `app/main.py:311-330` | Add tab label + tab content |
| Modify | `tests/test_ratios.py` | Add tests for new ratio fields |

---

### Task 1: Add treasury fields to Ratios and compute them

**Files:**
- Modify: `analysis/ratios.py:12-32` (Ratios dataclass)
- Modify: `analysis/ratios.py:34-70` (compute_ratios function)
- Test: `tests/test_ratios.py`

- [ ] **Step 1: Write failing tests for new treasury ratios**

Add to `tests/test_ratios.py`:

```python
# ── Trésorerie (entreprise saine) ────────────────────────────────────────────
# donnees_saine values:
# creances_clients=100k, stocks=60k, dettes_fournisseurs=60k
# capitaux_propres=500k, dettes_financieres=100k, immobilisations_nettes=300k
# CA=1M, tresorerie_actif=200k

def test_bfr_saine(donnees_saine):
    """BFR = clients(100k) + stocks(60k) - fournisseurs(60k) = 100k."""
    r = compute_ratios(donnees_saine)
    assert r.bfr == pytest.approx(100_000)


def test_frng_saine(donnees_saine):
    """FRNG = (CP 500k + dettes_fin 100k) - immo 300k = 300k."""
    r = compute_ratios(donnees_saine)
    assert r.frng == pytest.approx(300_000)


def test_tresorerie_nette_saine(donnees_saine):
    """Treso nette = FRNG(300k) - BFR(100k) = 200k."""
    r = compute_ratios(donnees_saine)
    assert r.tresorerie_nette == pytest.approx(200_000)


def test_cycle_conversion_jours_saine(donnees_saine):
    """Cycle = clients(36.5j) + stocks(54.75j) - fourn(54.75j) = 36.5j."""
    r = compute_ratios(donnees_saine)
    assert r.cycle_conversion_jours == pytest.approx(36.5, abs=1.0)


def test_tresorerie_nette_jours_ca_saine(donnees_saine):
    """Treso nette jours CA = 200k / 1M * 365 = 73j."""
    r = compute_ratios(donnees_saine)
    assert r.tresorerie_nette_jours_ca == pytest.approx(73.0, abs=1.0)


# ── Trésorerie (entreprise risquée) ─────────────────────────────────────────
# donnees_risquee values:
# creances_clients=50k, stocks=5k, dettes_fournisseurs=100k
# capitaux_propres=30k, dettes_financieres=200k, immobilisations_nettes=200k
# CA=500k, tresorerie_actif=5k

def test_bfr_risquee(donnees_risquee):
    """BFR = clients(50k) + stocks(5k) - fournisseurs(100k) = -45k (BFR négatif)."""
    r = compute_ratios(donnees_risquee)
    assert r.bfr == pytest.approx(-45_000)


def test_frng_risquee(donnees_risquee):
    """FRNG = (CP 30k + dettes_fin 200k) - immo 200k = 30k."""
    r = compute_ratios(donnees_risquee)
    assert r.frng == pytest.approx(30_000)


def test_tresorerie_nette_risquee(donnees_risquee):
    """Treso nette = FRNG(30k) - BFR(-45k) = 75k."""
    r = compute_ratios(donnees_risquee)
    assert r.tresorerie_nette == pytest.approx(75_000)


def test_tresorerie_nette_jours_ca_risquee(donnees_risquee):
    """Treso nette jours CA = 75k / 500k * 365 = 54.75j."""
    r = compute_ratios(donnees_risquee)
    assert r.tresorerie_nette_jours_ca == pytest.approx(54.75, abs=1.0)


# ── N-1 variants (None when no N-1 data) ────────────────────────────────────

def test_bfr_n1_none_when_no_n1(donnees_saine):
    """BFR N-1 is None when montant_n1 not set."""
    r = compute_ratios(donnees_saine)
    assert r.bfr_n1 is None
    assert r.frng_n1 is None
    assert r.tresorerie_nette_n1 is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_ratios.py -k "bfr or frng or tresorerie_nette or cycle_conversion" -v`
Expected: FAIL — `Ratios` has no attribute `bfr`

- [ ] **Step 3: Add fields to Ratios dataclass**

In `analysis/ratios.py`, add after the `variation_resultat_pct` field (line 31):

```python
    # Trésorerie
    bfr: float
    frng: float
    tresorerie_nette: float
    cycle_conversion_jours: float
    tresorerie_nette_jours_ca: float
    bfr_n1: Optional[float]
    frng_n1: Optional[float]
    tresorerie_nette_n1: Optional[float]
```

- [ ] **Step 4: Compute the new fields in compute_ratios()**

In `analysis/ratios.py`, in the `compute_ratios()` function, add before the `return Ratios(...)`:

```python
    bfr  = clients + stocks - dettes_fourn
    frng = (cp + dettes_fin) - d.immobilisations_nettes.montant_n
    tn   = frng - bfr
    tn_jours = round(tn / ca * 365, 1)
```

And compute N-1 variants:

```python
    # N-1 variants
    bfr_n1 = None
    frng_n1 = None
    tn_n1 = None
    if d.creances_clients.montant_n1 is not None:
        clients_n1   = d.creances_clients.montant_n1
        stocks_n1    = d.stocks.montant_n1 or 0
        fourn_n1     = d.dettes_fournisseurs.montant_n1 or 0
        cp_n1        = d.capitaux_propres.montant_n1 or 0
        dettes_fin_n1 = d.dettes_financieres.montant_n1 or 0
        immo_n1      = d.immobilisations_nettes.montant_n1 or 0
        bfr_n1  = clients_n1 + stocks_n1 - fourn_n1
        frng_n1 = (cp_n1 + dettes_fin_n1) - immo_n1
        tn_n1   = frng_n1 - bfr_n1
```

Then add the 8 new fields to the `return Ratios(...)` call:

```python
        bfr                      = bfr,
        frng                     = frng,
        tresorerie_nette         = tn,
        cycle_conversion_jours   = round(ratios_delai_clients + ratios_rotation_stocks - ratios_delai_fourn, 1),
        tresorerie_nette_jours_ca = tn_jours,
        bfr_n1                   = bfr_n1,
        frng_n1                  = frng_n1,
        tresorerie_nette_n1      = tn_n1,
```

Note: `ratios_delai_clients`, `ratios_rotation_stocks`, `ratios_delai_fourn` refer to the intermediate values used to compute `delai_clients_jours`, `delai_fournisseurs_jours`, `rotation_stocks_jours`. You will need to store them in local variables before the return statement so they can be reused. The existing code computes them inline in the return — extract them to local vars.

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_ratios.py -v`
Expected: ALL PASS (existing + new)

- [ ] **Step 6: Commit**

```bash
git add analysis/ratios.py tests/test_ratios.py
git commit -m "feat(ratios): add BFR, FRNG, tresorerie nette, cycle conversion"
```

---

### Task 2: Create treasury chart components

**Files:**
- Create: `app/components/treasury.py`

- [ ] **Step 1: Create `app/components/treasury.py`**

```python
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
```

- [ ] **Step 2: Commit**

```bash
git add app/components/treasury.py
git commit -m "feat(ui): add treasury chart components (waterfall, cycle, gauge)"
```

---

### Task 3: Add Tresorerie tab to Streamlit dashboard

**Files:**
- Modify: `app/main.py:244-250` (add import)
- Modify: `app/main.py:311-330` (tab labels and unpacking)
- Modify: after the Analyse sectorielle tab content (insert new tab content)

- [ ] **Step 1: Add import**

At the top of `render_dashboard()` (around line 245), add import:

```python
    from app.components.treasury import render_bfr_waterfall, render_cycle_bars, render_treasury_gauge
```

- [ ] **Step 2: Update tab labels**

Replace the tab_labels list to insert the treasury tab after "Analyse sectorielle":

```python
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
```

- [ ] **Step 3: Add Tresorerie tab content**

Insert after the `with t_secteur:` block and before the `if t_evol is not None:` block:

```python
    # ── Trésorerie ───────────────────────────────────────────────────────────
    with t_treso:
        # KPI cards
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
                 (bfr_var or 0) <= 0)  # BFR lower is better
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

        # Charts row
        col_wf, col_cy = st.columns([1, 1], gap="large")
        with col_wf:
            st.markdown('<div class="section-title">Décomposition du BFR</div>', unsafe_allow_html=True)
            render_bfr_waterfall(ratios, donnees)
        with col_cy:
            st.markdown('<div class="section-title">Cycle de conversion (jours)</div>', unsafe_allow_html=True)
            render_cycle_bars(ratios, benchmark)

        # Gauge
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
```

- [ ] **Step 4: Run all tests**

Run: `pytest -x -q`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat(ui): add Tresorerie tab with KPIs, waterfall, cycle, gauge"
```
