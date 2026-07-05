# Moteur FEC — Extraction + détection famille A (Phase 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Émettre 45 signaux « famille A » du référentiel `seuils_signaux.json` (seuils sur comptes fins du FEC : seuils EUR, présence/absence, ratios, composites même-année, variations N/N-1), consommés par le matcher déterministe existant sans le modifier.

**Architecture:** Une couche d'extraction `IndicateursFEC` agrège débit/crédit par compte (N et N-1) depuis le df FEC brut. Un module de détection hybride combine un moteur générique piloté par le référentiel (opérateurs `seuil_eur`/`presence`/`absence`) et des détecteurs explicites (ratios/composites/variations). Les seuils `parametrable:true` ont pour défaut la valeur du référentiel, surchargeable depuis l'UI Streamlit via `BillanState["seuils_overrides"]`.

**Tech Stack:** Python 3.11+, pandas, Pydantic v2, LangGraph, Streamlit, pytest.

**Référence spec :** `docs/superpowers/specs/2026-07-05-moteur-fec-famille-a-design.md`

---

## Convention de signe (fondamentale — lire avant de coder)

`compute_fec_features` calcule pour chaque compte `ΣDebit` et `ΣCredit` bruts (jamais la colonne `Montant` de `_load_df`, dont la normalisation crédit `^(1|40|7)` est partielle). Les accesseurs dérivent la magnitude métier :
- `solde(prefixes, 'D')` = ΣDebit − ΣCredit → **positif pour charges (classe 6) et actifs (2,3, clients 41, dispo 5)**.
- `solde(prefixes, 'C')` = ΣCredit − ΣDebit → **positif pour produits (classe 7), capitaux (1), provisions (14,15,49,29), dettes/comptes créditeurs (40,455,457)**.
- `mouvement(prefixes)` = ΣDebit + ΣCredit → sert à `absence` (== 0 ⇔ aucune écriture sur le compte, insensible au signe).

Chaque signal porte son `sens` attendu. Exemples : `REMUNERATION_DIRIGEANT_ELEVEE` (6411) → `'D'` ; `COMPTE_COURANT_CREDITEUR_ELEVE` (455) → `'C'` ; `REVENUS_LOCATIFS_ELEVES` (706,708) → `'C'` ; `DEPRECIATION_CREANCES` (491, provision) → `'C'`.

---

## File Structure

| Fichier | Responsabilité |
|---|---|
| `analysis/fec_features.py` (créer) | `IndicateursFEC` (modèle Pydantic) + `compute_fec_features(df, df_n1) -> IndicateursFEC` |
| `analysis/fec_signals.py` (créer) | `GENERIC_SIGNALS` (table), moteur générique, détecteurs explicites, `seuils_parametrables()`, `detect_signals_from_fec(features, seuils_overrides)` |
| `models.py` (modifier) | ajouter `IndicateursFEC`… non — le modèle vit dans `fec_features.py` pour cohésion ; `models.py` inchangé |
| `graph.py` (modifier) | `BillanState` + `indicateurs_fec` + `seuils_overrides` ; `prepare_entretien_bilan` accepte `seuils_overrides` |
| `nodes/extract_financial_data.py` (modifier) | calcule `indicateurs_fec` |
| `nodes/detect_signals.py` (modifier) | appelle `detect_signals_from_fec` |
| `app/main.py` (modifier) | expander « Seuils de détection » → `seuils_overrides` dans le stream |
| `tests/test_fec_features.py` (créer) | extraction + signes |
| `tests/test_fec_signals.py` (créer) | moteur générique + explicites + surcharge |
| `tests/test_pipeline_e2e.py` (modifier) | e2e FEC synthétique riche |

> Décision : `IndicateursFEC` vit dans `analysis/fec_features.py` (avec sa fonction de calcul) plutôt que dans `models.py`, pour garder `models.py` centré sur les modèles métier partagés et co-localiser extraction + structure. Le state le référence via import.

---

## Task 1: `IndicateursFEC` + extraction avec gestion des signes

**Files:**
- Create: `analysis/fec_features.py`
- Test: `tests/test_fec_features.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_fec_features.py` :

```python
import pandas as pd
import pytest
from analysis.fec_features import IndicateursFEC, compute_fec_features


def _df(rows):
    # rows: list de (CompteNum, Debit, Credit, EcritureDate)
    return pd.DataFrame(
        [{"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt} for c, d, cr, dt in rows]
    )


def test_solde_debiteur_charge():
    # 6411 rémunération dirigeant : 60 000 au débit
    f = compute_fec_features(_df([("641100", 60000, 0, "20240131")]))
    assert f.solde(["6411"], "D") == 60000
    assert f.solde(["6411"], "C") == -60000


def test_solde_crediteur_compte_courant_associe():
    # 455 créditeur : l'associé a prêté 80 000 (crédit)
    f = compute_fec_features(_df([("4551", 0, 80000, "20240131")]))
    assert f.solde(["455"], "C") == 80000   # magnitude créditrice positive
    assert f.solde(["455"], "D") == -80000


def test_solde_crediteur_produit():
    f = compute_fec_features(_df([("706000", 0, 30000, "20240630")]))
    assert f.solde(["706", "708"], "C") == 30000


def test_prefixes_agregation():
    f = compute_fec_features(_df([
        ("213100", 100000, 0, "20240101"),
        ("214000", 50000, 0, "20240101"),
    ]))
    assert f.solde(["213", "214"], "D") == 150000
    assert f.solde(["213"], "D") == 100000  # 214 exclu


def test_absence_mouvement():
    f = compute_fec_features(_df([("606000", 1000, 0, "20240101")]))
    assert f.mouvement(["616"]) == 0    # aucun compte 616 → absence
    assert f.mouvement(["606"]) == 1000


def test_variation_pct_et_none_sans_n1():
    df_n = _df([("661000", 12000, 0, "20240101")])
    df_n1 = _df([("661000", 10000, 0, "20230101")])
    f = compute_fec_features(df_n, df_n1)
    assert f.variation_pct(["661"], "D") == 20.0
    f_sans = compute_fec_features(df_n)
    assert f_sans.variation_pct(["661"], "D") is None


def test_ratio_pct_et_none_si_denominateur_nul():
    f = compute_fec_features(_df([
        ("645000", 45000, 0, "20240101"),
        ("641100", 100000, 0, "20240101"),
    ]))
    assert f.ratio_pct(["645"], ["641"], "D", "D") == 45.0
    f0 = compute_fec_features(_df([("645000", 45000, 0, "20240101")]))
    assert f0.ratio_pct(["645"], ["641"], "D", "D") is None


def test_ca_memorise():
    f = compute_fec_features(_df([("706000", 0, 200000, "20240101")]))
    assert f.ca_n == 200000
```

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_features.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.fec_features'`.

- [ ] **Step 3: Implémenter `analysis/fec_features.py`**

```python
# analysis/fec_features.py
"""Extraction d'indicateurs fins depuis le FEC (débit/crédit par compte)."""
from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, Field


def _sums_by_account(df: pd.DataFrame) -> tuple[dict[str, float], dict[str, float]]:
    """Retourne (debit_par_compte, credit_par_compte) agrégés par CompteNum."""
    debit = pd.to_numeric(df.get("Debit"), errors="coerce").fillna(0)
    credit = pd.to_numeric(df.get("Credit"), errors="coerce").fillna(0)
    comptes = df["CompteNum"].astype(str)
    d = debit.groupby(comptes).sum().to_dict()
    c = credit.groupby(comptes).sum().to_dict()
    return {k: float(v) for k, v in d.items()}, {k: float(v) for k, v in c.items()}


class IndicateursFEC(BaseModel):
    debit_n: dict[str, float] = Field(default_factory=dict)
    credit_n: dict[str, float] = Field(default_factory=dict)
    debit_n1: dict[str, float] = Field(default_factory=dict)
    credit_n1: dict[str, float] = Field(default_factory=dict)
    ca_n: float = 0.0

    def _agg(self, prefixes: list[str], *, n1: bool) -> tuple[float, float]:
        debit = self.debit_n1 if n1 else self.debit_n
        credit = self.credit_n1 if n1 else self.credit_n
        pref = tuple(prefixes)
        d = sum(v for k, v in debit.items() if k.startswith(pref))
        c = sum(v for k, v in credit.items() if k.startswith(pref))
        return d, c

    def solde(self, prefixes: list[str], sens: str = "D", *, n1: bool = False) -> float:
        d, c = self._agg(prefixes, n1=n1)
        return (d - c) if sens == "D" else (c - d)

    def mouvement(self, prefixes: list[str], *, n1: bool = False) -> float:
        d, c = self._agg(prefixes, n1=n1)
        return d + c

    def variation_pct(self, prefixes: list[str], sens: str = "D") -> float | None:
        n1 = self.solde(prefixes, sens, n1=True)
        if not n1:
            return None
        n = self.solde(prefixes, sens)
        return round((n - n1) / abs(n1) * 100, 1)

    def ratio_pct(self, num: list[str], den: list[str], sens_num: str = "D", sens_den: str = "D") -> float | None:
        d = self.solde(den, sens_den)
        if not d:
            return None
        return round(self.solde(num, sens_num) / d * 100, 1)


def compute_fec_features(df: pd.DataFrame, df_n1: pd.DataFrame | None = None) -> IndicateursFEC:
    debit_n, credit_n = _sums_by_account(df)
    debit_n1, credit_n1 = ({}, {})
    if df_n1 is not None:
        debit_n1, credit_n1 = _sums_by_account(df_n1)

    feat = IndicateursFEC(
        debit_n=debit_n, credit_n=credit_n,
        debit_n1=debit_n1, credit_n1=credit_n1,
    )
    feat.ca_n = feat.solde(["70"], "C")
    return feat
```

- [ ] **Step 4: Lancer — passe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_features.py -v`
Expected: PASS (8 tests).

- [ ] **Step 5: Commit**

```bash
git add analysis/fec_features.py tests/test_fec_features.py
git commit -m "feat(fec): IndicateursFEC extraction with debit/credit sign handling"
```

---

## Task 2: Moteur générique piloté par le référentiel

**Files:**
- Create: `analysis/fec_signals.py`
- Test: `tests/test_fec_signals.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Créer `tests/test_fec_signals.py` :

```python
import json
from pathlib import Path
import pandas as pd
import pytest
from analysis.fec_features import compute_fec_features
from analysis.fec_signals import (
    detect_signals_from_fec, seuils_parametrables, GENERIC_SIGNALS,
)

ROOT = Path(__file__).resolve().parent.parent
SEUILS = json.loads((ROOT / "data" / "seuils_signaux.json").read_text(encoding="utf-8"))


def _df(rows):
    return pd.DataFrame(
        [{"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt} for c, d, cr, dt in rows]
    )


def _codes(df, df_n1=None, overrides=None):
    feat = compute_fec_features(df, df_n1)
    return {s.code for s in detect_signals_from_fec(feat, overrides or {})}


# --- Moteur générique : opérateurs ---

def test_seuil_eur_declenche():
    # REMUNERATION_DIRIGEANT_ELEVEE : 6411 > 48000
    assert "REMUNERATION_DIRIGEANT_ELEVEE" in _codes(_df([("641100", 60000, 0, "20240131")]))


def test_seuil_eur_borne_non_declenchee():
    assert "REMUNERATION_DIRIGEANT_ELEVEE" not in _codes(_df([("641100", 40000, 0, "20240131")]))


def test_presence_declenche():
    # PENALITES_FISCALES : 6712 > 0
    assert "PENALITES_FISCALES" in _codes(_df([("671200", 500, 0, "20240131")]))


def test_absence_declenche_si_compte_absent():
    # ABSENCE_ASSURANCE_RC : 616 == 0 (aucune écriture 616)
    assert "ABSENCE_ASSURANCE_RC" in _codes(_df([("606000", 1000, 0, "20240101")]))


def test_absence_non_declenchee_si_compte_present():
    assert "ABSENCE_ASSURANCE_RC" not in _codes(_df([("616000", 1200, 0, "20240101")]))


def test_crediteur_produit_locatif():
    # REVENUS_LOCATIFS_ELEVES : 706/708 > 30000 (sens C)
    assert "REVENUS_LOCATIFS_ELEVES" in _codes(_df([("706000", 0, 35000, "20240630")]))


# --- Seuils paramétrables + surcharge UI ---

def test_seuils_parametrables_couvre_referentiel():
    params = seuils_parametrables(SEUILS)
    # tous les codes parametrable:true du référentiel présents dans GENERIC_SIGNALS y figurent
    attendus = {c for c, v in SEUILS.items()
                if v.get("parametrable") and c in GENERIC_SIGNALS}
    assert attendus.issubset(set(params))
    assert params["REMUNERATION_DIRIGEANT_ELEVEE"] == 48000


def test_override_abaisse_le_seuil():
    df = _df([("641100", 30000, 0, "20240131")])  # 30k < défaut 48k → non déclenché
    assert "REMUNERATION_DIRIGEANT_ELEVEE" not in _codes(df)
    # override à 25k → déclenché
    assert "REMUNERATION_DIRIGEANT_ELEVEE" in _codes(df, overrides={"REMUNERATION_DIRIGEANT_ELEVEE": 25000})


def test_signaux_sont_des_models_signal():
    from models import Signal
    feat = compute_fec_features(_df([("641100", 60000, 0, "20240131")]))
    sigs = detect_signals_from_fec(feat, {})
    assert all(isinstance(s, Signal) for s in sigs)
```

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.fec_signals'`.

- [ ] **Step 3: Implémenter le socle + moteur générique dans `analysis/fec_signals.py`**

Créer le fichier avec le socle, la table générique, et un `detect_signals_from_fec` qui ne traite QUE le générique pour l'instant (les explicites arrivent en Task 3) :

```python
# analysis/fec_signals.py
"""Détection des signaux famille A depuis IndicateursFEC (moteur hybride)."""
from __future__ import annotations

from models import Signal, TypeSignal, Gravite
from analysis.fec_features import IndicateursFEC

R, O, C, X = TypeSignal.RISQUE, TypeSignal.OPPORTUNITE, TypeSignal.CONFORMITE, TypeSignal.OPTIMISATION
F, M, E = Gravite.FAIBLE, Gravite.MOYENNE, Gravite.ELEVEE

# code -> (op, comptes, sens, seuil_defaut, type, gravite, titre, levier)
#   op ∈ {"seuil_eur", "presence", "absence"}
GENERIC_SIGNALS: dict[str, tuple] = {
    # --- seuil_eur ---
    "PORTEFEUILLE_FINANCIER_IMPORTANT": ("seuil_eur", ["26", "27", "50", "51"], "D", 500000, O, F,
        "Portefeuille financier important", "Diagnostic patrimonial, placements sur mesure"),
    "CESSION_ACTIFS_RECENTE": ("seuil_eur", ["775", "757"], "C", 50000, O, F,
        "Cession d'actifs récente", "Réemploi, placement du produit de cession, valorisation"),
    "REMUNERATION_DIRIGEANT_ELEVEE": ("seuil_eur", ["6411"], "D", 48000, X, M,
        "Rémunération dirigeant élevée", "Optimisation du statut social, arbitrage salaire/dividendes"),
    "FRAIS_CONTENTIEUX_ELEVES": ("seuil_eur", ["6227"], "D", 1000, R, M,
        "Frais de contentieux élevés", "Sécurisation juridique, recouvrement, prévention"),
    "HONORAIRES_JURIDIQUES_ELEVES": ("seuil_eur", ["6226", "6228"], "D", 2000, X, F,
        "Honoraires juridiques élevés", "SIRH, sécurisation juridique RH"),
    "FRAIS_ADMINISTRATIFS_ELEVES": ("seuil_eur", ["626"], "D", 3000, X, F,
        "Frais administratifs élevés", "Assistanat administratif externalisé"),
    "REVENUS_LOCATIFS_ELEVES": ("seuil_eur", ["706", "708"], "C", 30000, O, F,
        "Revenus locatifs élevés", "Comptabilité LMNP, structuration SCI, assurance PNO"),
    "PATRIMOINE_IMMO_IMPORTANT": ("seuil_eur", ["213", "214"], "D", 300000, O, F,
        "Patrimoine immobilier important", "Gestion de portefeuille investisseurs, transmission"),
    "CA_LOCATIF_CONSOLIDE_ELEVE": ("seuil_eur", ["706", "708"], "C", 80000, O, F,
        "CA locatif consolidé élevé", "Gestion de portefeuille investisseurs"),
    "IMMO_PRO_ELEVEE": ("seuil_eur", ["213"], "D", 400000, O, F,
        "Immobilier professionnel élevé", "Structuration immobilier professionnel (SCI, holding)"),
    "LOYERS_VERSES_ELEVES": ("seuil_eur", ["613"], "D", 60000, X, F,
        "Loyers versés élevés", "Structuration immobilier professionnel, acquisition des murs"),
    "PARC_MACHINES_IMPORTANT": ("seuil_eur", ["215"], "D", 50000, C, F,
        "Parc de machines important", "Assurance bris de machine"),
    "ACTIFS_A_ASSURER": ("seuil_eur", ["21", "3"], "D", 50000, C, F,
        "Actifs à assurer", "Multirisque entreprise"),
    # --- presence (> 0) ---
    "CLIENTS_DOUTEUX": ("presence", ["416"], "D", 0, R, M,
        "Clients douteux détectés", "Recouvrement de créances"),
    "CREANCES_PASSEES_EN_PERTE": ("presence", ["654"], "D", 0, R, M,
        "Créances passées en perte", "Recouvrement, prévention des impayés"),
    "DEPRECIATION_CREANCES": ("presence", ["491"], "C", 0, R, F,
        "Dépréciation de créances", "Recouvrement, assainissement du poste clients"),
    "PENALITES_FISCALES": ("presence", ["6712"], "D", 0, R, E,
        "Pénalités fiscales", "Pack Sérénité (ECF + Zen Fiscal), sécurisation"),
    "PENALITES_SOCIALES": ("presence", ["6714"], "D", 0, R, E,
        "Pénalités sociales", "Sécurisation juridique RH, audit social"),
    "PROVISION_RISQUE_SOCIAL": ("presence", ["158", "1511"], "C", 0, R, M,
        "Provision pour risque social", "Sécurisation juridique RH"),
    "FONDS_COMMERCIAL_RECENT": ("presence", ["207"], "D", 0, O, F,
        "Fonds commercial récent", "Étude de zone de chalandise, financement"),
    "CONSTRUCTION_EN_COURS": ("presence", ["231"], "D", 0, O, F,
        "Construction en cours", "Assurance dommage ouvrage, recherche de financement"),
    "NOUVEL_ASSOCIE": ("presence", ["4561", "108"], "C", 0, C, F,
        "Nouvel associé détecté", "Modification de société, pacte d'associés"),
    "TITRES_PARTICIPATION_DETECTES": ("presence", ["261", "271"], "D", 0, O, F,
        "Titres de participation détectés", "Croissance externe, cession/acquisition"),
    "NOUVEAU_BAIL": ("presence", ["275"], "D", 0, O, F,
        "Nouveau bail détecté", "Recherche de financement, garantie"),
    # --- absence (== 0) ---
    "ABSENCE_ASSURANCE_RC": ("absence", ["616"], "D", 0, R, E,
        "Absence d'assurance responsabilité civile", "RC professionnelle, RC dirigeants"),
    "ABSENCE_PER_RETRAITE": ("absence", ["646", "6467", "6468"], "D", 0, X, F,
        "Absence de PER retraite", "Retraite du dirigeant (PER), optimisation fiscale"),
}


def _desc_generic(op: str, comptes: list[str], seuil: float, valeur: float) -> str:
    j = "/".join(comptes)
    if op == "seuil_eur":
        return f"Comptes {j} : {valeur:,.0f} € (seuil {seuil:,.0f} €)."
    if op == "presence":
        return f"Comptes {j} : présence détectée ({valeur:,.0f} €)."
    return f"Comptes {j} : aucune écriture (compte absent)."


def _eval_generic(code: str, feat: IndicateursFEC, seuils_overrides: dict[str, float]) -> Signal | None:
    op, comptes, sens, defaut, typ, grav, titre, levier = GENERIC_SIGNALS[code]
    seuil = float(seuils_overrides.get(code, defaut))
    if op == "absence":
        if feat.mouvement(comptes) != 0:
            return None
        valeur = 0.0
    else:
        valeur = feat.solde(comptes, sens)
        seuil_test = seuil if op == "seuil_eur" else 0
        if not (valeur > seuil_test):
            return None
    return Signal(type=typ, gravite=grav, code=code, titre=titre,
                  description=_desc_generic(op, comptes, seuil, valeur), levier=levier)


def seuils_parametrables(referentiel: dict) -> dict[str, float]:
    """code -> seuil défaut, pour les signaux GENERIC parametrable:true (source unique UI + moteur)."""
    out: dict[str, float] = {}
    for code, spec in GENERIC_SIGNALS.items():
        ref = referentiel.get(code, {})
        if ref.get("parametrable") and ref.get("seuil_valeur") is not None:
            out[code] = float(ref["seuil_valeur"])
    return out


def detect_signals_from_fec(feat: IndicateursFEC, seuils_overrides: dict[str, float] | None = None) -> list[Signal]:
    overrides = seuils_overrides or {}
    signals: list[Signal] = []
    for code in GENERIC_SIGNALS:
        sig = _eval_generic(code, feat, overrides)
        if sig is not None:
            signals.append(sig)
    # (détecteurs explicites ajoutés en Task 3)
    return signals
```

> Note sur `seuils_parametrables` : le défaut renvoyé provient du **référentiel** (`seuil_valeur`), pas de la colonne `defaut` de `GENERIC_SIGNALS`. La colonne `defaut` de la table est le repli si le code n'est pas surchargé ET absent du référentiel ; en pratique les deux coïncident. Le test `test_seuils_parametrables_couvre_referentiel` vérifie l'alignement.

- [ ] **Step 4: Lancer — passe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add analysis/fec_signals.py tests/test_fec_signals.py
git commit -m "feat(fec): generic signal engine driven by seuils_signaux.json"
```

---

## Task 3: Détecteurs explicites (ratios, composites, variations)

**Files:**
- Modify: `analysis/fec_signals.py`
- Test: `tests/test_fec_signals.py`

- [ ] **Step 1: Ajouter les tests qui échouent**

Ajouter à la fin de `tests/test_fec_signals.py` :

```python
# --- Détecteurs explicites ---

def test_ratio_charges_sociales_elevees():
    df = _df([("645000", 50000, 0, "20240101"), ("641100", 100000, 0, "20240101")])  # 50% > 45%
    assert "CHARGES_SOCIALES_ELEVEES" in _codes(df)
    df2 = _df([("645000", 40000, 0, "20240101"), ("641100", 100000, 0, "20240101")])  # 40% < 45%
    assert "CHARGES_SOCIALES_ELEVEES" not in _codes(df2)


def test_composite_compte_courant_crediteur():
    # 455 créditeur 80k > 50k
    assert "COMPTE_COURANT_CREDITEUR_ELEVE" in _codes(_df([("4551", 0, 80000, "20240101")]))
    # 455 créditeur 30k < 50k
    assert "COMPTE_COURANT_CREDITEUR_ELEVE" not in _codes(_df([("4551", 0, 30000, "20240101")]))


def test_composite_absence_prevoyance_madelin():
    # 6467 == 0 ET 6411 > 36000 → déclenché
    assert "ABSENCE_PREVOYANCE_MADELIN" in _codes(_df([("641100", 40000, 0, "20240101")]))
    # 6467 présent → non déclenché
    df = _df([("641100", 40000, 0, "20240101"), ("646700", 2000, 0, "20240101")])
    assert "ABSENCE_PREVOYANCE_MADELIN" not in _codes(df)


def test_composite_sous_remuneration_dirigeant():
    # RN(12) > 80k ET 6411 < 40k
    df = _df([("120000", 0, 100000, "20241231"), ("641100", 30000, 0, "20240101")])
    assert "SOUS_REMUNERATION_DIRIGEANT" in _codes(df)


def test_variation_frais_financiers_en_hausse():
    df_n = _df([("661000", 12000, 0, "20240101")])
    df_n1 = _df([("661000", 10000, 0, "20230101")])  # +20%
    assert "FRAIS_FINANCIERS_EN_HAUSSE" in _codes(df_n, df_n1)


def test_variation_absente_sans_n1():
    # pas de N-1 → aucun signal de variation
    df_n = _df([("661000", 99999, 0, "20240101")])
    assert "FRAIS_FINANCIERS_EN_HAUSSE" not in _codes(df_n)


def test_resultat_bnc_eleve():
    assert "RESULTAT_BNC_ELEVE" in _codes(_df([("120000", 0, 120000, "20241231")]))  # RN 120k > 100k
```

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -k "ratio or composite or variation or bnc" -v`
Expected: FAIL — les détecteurs explicites ne sont pas encore branchés.

- [ ] **Step 3: Ajouter les détecteurs explicites dans `analysis/fec_signals.py`**

Ajouter ces fonctions AVANT `detect_signals_from_fec`, puis les appeler dans la boucle finale. Chaque détecteur renvoie `Signal | None` :

```python
def _sig(code, typ, grav, titre, desc, levier) -> Signal:
    return Signal(type=typ, gravite=grav, code=code, titre=titre, description=desc, levier=levier)


# --- Ratios ---
def _charges_sociales_elevees(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["645"], ["641"], "D", "D")
    if r is None or r <= 45:
        return None
    return _sig("CHARGES_SOCIALES_ELEVEES", X, M, "Charges sociales élevées",
                f"Charges sociales / salaires bruts = {r:.0f}% (seuil 45%).",
                "Audit et optimisation sociale, intéressement/PEE")


def _ratio_dividendes_eleve(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["457"], ["6411"], "C", "D")
    if r is None or r <= 60:
        return None
    return _sig("RATIO_DIVIDENDES_ELEVE", X, M, "Ratio dividendes/salaire élevé",
                f"Dividendes / rémunération = {r:.0f}% (seuil 60%).",
                "Rémunération optimisée du dirigeant, statut social")


def _charges_sociales_perso_elevees(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["646"], ["12"], "D", "C")
    if r is None or r <= 30:
        return None
    return _sig("CHARGES_SOCIALES_PERSO_ELEVEES", X, F, "Charges sociales personnelles élevées",
                f"Cotisations perso dirigeant / résultat = {r:.0f}% (seuil 30%).",
                "Optimisation du statut social du dirigeant")


def _amortissements_avances(f: IndicateursFEC) -> Signal | None:
    r = f.ratio_pct(["2813"], ["213"], "C", "D")
    if r is None or r <= 80:
        return None
    return _sig("AMORTISSEMENTS_AVANCES", O, F, "Amortissements avancés",
                f"Amortissements / valeur brute immeubles = {r:.0f}% (seuil 80%).",
                "Arbitrage patrimonial, réinvestissement, cession")


# --- Composites même-année ---
def _compte_courant_crediteur_eleve(f: IndicateursFEC) -> Signal | None:
    v = f.solde(["455"], "C")
    if v <= 50000:
        return None
    grav = E if v > 150000 else (M if v > 100000 else F)
    return _sig("COMPTE_COURANT_CREDITEUR_ELEVE", O, grav, "Compte courant d'associé créditeur élevé",
                f"Compte courant d'associé créditeur : {v:,.0f} € (seuil 50 000 €).",
                "Diagnostic patrimonial, placement, succession & transmission")


def _absence_interessement(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["6414"]) != 0 or f.solde(["12"], "C") <= 80000:
        return None
    return _sig("ABSENCE_INTERESSEMENT", X, F, "Absence d'intéressement",
                "Aucune prime d'intéressement (6414 = 0) alors que le résultat dépasse 80 000 €.",
                "Intéressement des salariés, PEE")


def _absence_provision_ifc(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["153"]) != 0 or f.solde(["641"], "D") <= 100000:
        return None
    return _sig("ABSENCE_PROVISION_IFC", R, M, "Absence de provision IFC",
                "Aucune provision pour indemnités de fin de carrière (153 = 0) avec une masse salariale > 100 000 €.",
                "Indemnités de fin de carrière (IFC)")


def _absence_prevoyance_madelin(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["6467"]) != 0 or f.solde(["6411"], "D") <= 36000:
        return None
    return _sig("ABSENCE_PREVOYANCE_MADELIN", R, M, "Absence de prévoyance Madelin",
                "Aucune cotisation prévoyance (6467 = 0) alors que la rémunération dépasse 36 000 €.",
                "Prévoyance dirigeant (Madelin)")


def _sous_remuneration_dirigeant(f: IndicateursFEC) -> Signal | None:
    if f.solde(["12"], "C") <= 80000 or not (0 < f.solde(["6411"], "D") < 40000):
        return None
    return _sig("SOUS_REMUNERATION_DIRIGEANT", X, M, "Sous-rémunération du dirigeant",
                "Résultat > 80 000 € mais rémunération dirigeant < 40 000 € : arbitrage à étudier.",
                "Rémunération optimisée du dirigeant, statut social")


def _absence_force_commerciale(f: IndicateursFEC) -> Signal | None:
    if f.mouvement(["6221"]) != 0 or f.ca_n <= 200000:
        return None
    return _sig("ABSENCE_FORCE_COMMERCIALE", O, M, "Absence de force commerciale",
                "Aucune commission commerciale (6221 = 0) avec un CA > 200 000 €.",
                "Assistanat commercial, développement commercial")


def _depenses_pub_sans_effet(f: IndicateursFEC) -> Signal | None:
    var_ca = f.variation_pct(["70"], "C")
    if f.solde(["6231"], "D") <= 5000 or var_ca is None or var_ca > 0:
        return None
    return _sig("DEPENSES_PUB_SANS_EFFET", R, F, "Dépenses publicitaires sans effet",
                "Dépenses de publicité > 5 000 € sans progression du CA.",
                "Assistanat commercial, étude de zone de chalandise")


def _immo_locatif_non_amorti(f: IndicateursFEC) -> Signal | None:
    if f.solde(["213", "214"], "D") <= 0 or f.mouvement(["2813", "2814"]) != 0:
        return None
    return _sig("IMMO_LOCATIF_NON_AMORTI", O, M, "Immobilier locatif non amorti",
                "Biens immobiliers présents (213/214) sans amortissement constaté (2813/2814 = 0).",
                "Comptabilité LMNP au réel (amortissement)")


# --- Variations N/N-1 ---
def _variation_haus(code, comptes, sens, seuil, typ, grav, titre, levier):
    def _f(f: IndicateursFEC) -> Signal | None:
        v = f.variation_pct(comptes, sens)
        if v is None or v <= seuil:
            return None
        return _sig(code, typ, grav, titre, f"{titre} : {v:+.0f}% vs N-1 (seuil +{seuil:.0f}%).", levier)
    return _f


_frais_financiers_en_hausse = _variation_haus(
    "FRAIS_FINANCIERS_EN_HAUSSE", ["661"], "D", 20, R, M,
    "Frais financiers en hausse", "Prévisionnel de trésorerie, restructuration de dette")
_frais_bancaires_en_hausse = _variation_haus(
    "FRAIS_BANCAIRES_EN_HAUSSE", ["627"], "D", 20, X, F,
    "Frais bancaires en hausse", "Assistanat administratif, renégociation bancaire")
_hausse_immobilisations = _variation_haus(
    "HAUSSE_IMMOBILISATIONS", ["21"], "D", 20, C, F,
    "Hausse des immobilisations", "Multirisque entreprise, garantie emprunteur")
_honoraires_exceptionnels_en_hausse = _variation_haus(
    "HONORAIRES_EXCEPTIONNELS_EN_HAUSSE", ["6226"], "D", 50, C, F,
    "Honoraires exceptionnels en hausse", "Cession & acquisition, accompagnement")


def _variation_remuneration_dirigeant(f: IndicateursFEC) -> Signal | None:
    v = f.variation_pct(["6411"], "D")
    if v is None or abs(v) < 15:
        return None
    return _sig("VARIATION_REMUNERATION_DIRIGEANT", C, F, "Variation de rémunération du dirigeant",
                f"Rémunération dirigeant : {v:+.0f}% vs N-1 (seuil ±15%).",
                "Prévoyance dirigeant, conseil RH")


def _augmentation_capital(f: IndicateursFEC) -> Signal | None:
    n1 = f.solde(["101"], "C", n1=True)
    if not n1 or f.solde(["101"], "C") - n1 <= 0:
        return None
    return _sig("AUGMENTATION_CAPITAL", C, F, "Augmentation de capital",
                "Le capital social (101) a augmenté vs N-1.",
                "Modification de société, secrétariat juridique")


# --- Divers ---
def _resultat_bnc_eleve(f: IndicateursFEC) -> Signal | None:
    if f.solde(["12"], "C") <= 100000:
        return None
    return _sig("RESULTAT_BNC_ELEVE", X, M, "Résultat élevé (BNC)",
                f"Résultat de l'exercice : {f.solde(['12'], 'C'):,.0f} € (seuil 100 000 €).",
                "Structuration des professions libérales (SEL, SPFPL)")


_EXPLICIT_DETECTORS = [
    _charges_sociales_elevees, _ratio_dividendes_eleve, _charges_sociales_perso_elevees,
    _amortissements_avances, _compte_courant_crediteur_eleve, _absence_interessement,
    _absence_provision_ifc, _absence_prevoyance_madelin, _sous_remuneration_dirigeant,
    _absence_force_commerciale, _depenses_pub_sans_effet, _immo_locatif_non_amorti,
    _frais_financiers_en_hausse, _frais_bancaires_en_hausse, _hausse_immobilisations,
    _honoraires_exceptionnels_en_hausse, _variation_remuneration_dirigeant,
    _augmentation_capital, _resultat_bnc_eleve,
]
```

Puis remplacer le corps de `detect_signals_from_fec` (la ligne-commentaire `# (détecteurs explicites ajoutés en Task 3)`) par l'appel des détecteurs explicites :

```python
    for detector in _EXPLICIT_DETECTORS:
        sig = detector(feat)
        if sig is not None:
            signals.append(sig)
    return signals
```

- [ ] **Step 4: Lancer — passe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -v`
Expected: PASS (tous : génériques + explicites).

- [ ] **Step 5: Commit**

```bash
git add analysis/fec_signals.py tests/test_fec_signals.py
git commit -m "feat(fec): explicit detectors (ratios, composites, variations)"
```

---

## Task 4: Branchement dans le pipeline (extraction, détection, state)

**Files:**
- Modify: `graph.py`, `nodes/extract_financial_data.py`, `nodes/detect_signals.py`
- Test: `tests/test_nodes.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter dans `tests/test_nodes.py` cette classe. Elle vérifie le nœud `detect_signals` complet avec un `indicateurs_fec` injecté et le LLM mocké (la fixture `donnees_saine` vient de `conftest.py`) :

```python
class TestFecSignalsWiring:
    def test_detect_signals_includes_fec_codes(self, donnees_saine):
        import pandas as pd
        from unittest.mock import patch, MagicMock
        from analysis.fec_features import compute_fec_features

        df = pd.DataFrame([{"CompteNum": "641100", "Debit": 60000, "Credit": 0, "EcritureDate": "20240131"}])
        feat = compute_fec_features(df)  # REMUNERATION_DIRIGEANT_ELEVEE

        with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
            inst = MagicMock()
            resp = MagicMock(); resp.content = "[]"
            inst.invoke.return_value = resp
            mock_cls.return_value = inst
            from nodes.detect_signals import detect_signals
            result = detect_signals({
                "donnees_financieres": donnees_saine,
                "indicateurs_fec": feat,
                "seuils_overrides": {},
            })

        codes = {s.code for s in result["signaux_detectes"]}
        assert "REMUNERATION_DIRIGEANT_ELEVEE" in codes
```

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_nodes.py::TestFecSignalsWiring -v`
Expected: FAIL — `detect_signals` n'utilise pas encore `indicateurs_fec`.

- [ ] **Step 3: Modifier `graph.py`**

Dans `class BillanState`, ajouter après `ratios: Optional[Ratios]` :

```python
    indicateurs_fec: Optional["IndicateursFEC"]
    seuils_overrides: dict
```

Ajouter l'import en tête (après les imports `models`) :

```python
from analysis.fec_features import IndicateursFEC
```

Dans `prepare_entretien_bilan`, ajouter le paramètre et le passer dans `graph.invoke` :

```python
def prepare_entretien_bilan(
    fichier_path: str,
    catalogue_path: str,
    code_naf: str,
    fichier_path_n1: Optional[str] = None,
    anonymize: bool = False,
    seuils_overrides: Optional[dict] = None,
) -> BillanState:
    graph = build_graph()
    return graph.invoke({
        "fichier_path":    fichier_path,
        "fichier_path_n1": fichier_path_n1,
        "catalogue_path":  catalogue_path,
        "code_naf":        code_naf.upper().strip(),
        "anonymize":       anonymize,
        "seuils_overrides": seuils_overrides or {},
    })
```

- [ ] **Step 4: Modifier `nodes/extract_financial_data.py`**

Dans la branche FEC (après le calcul de `ca_mensuel_n1`), calculer les features et les ajouter au retour. Charger le df N-1 une seule fois :

```python
        from analysis.fec_features import compute_fec_features
        df_n1 = _load_df(str(file_path_n1)) if file_path_n1 else None
        indicateurs_fec = compute_fec_features(df_n, df_n1)
```

Dans la branche PDF, `indicateurs_fec = None`. Ajouter au dict de retour :

```python
        "indicateurs_fec": indicateurs_fec,
```

(déclarer `indicateurs_fec = None` dans la branche PDF pour que la variable existe dans les deux cas).

- [ ] **Step 5: Modifier `nodes/detect_signals.py`**

Après la ligne `signaux = detect_signals_from_rules(ratios) + detect_signals_from_donnees(donnees, ratios)`, ajouter :

```python
    features = state.get("indicateurs_fec")
    if features is not None:
        from analysis.fec_signals import detect_signals_from_fec
        signaux += detect_signals_from_fec(features, state.get("seuils_overrides") or {})
```

(garder le tri par gravité existant en fin de fonction).

- [ ] **Step 6: Lancer — passe + non-régression**

Run: `.venv/Scripts/python.exe -m pytest tests/test_nodes.py -v`
Then: `.venv/Scripts/python.exe -m pytest -q`
Expected: PASS partout, aucune régression sur les 151 tests + les nouveaux.

- [ ] **Step 7: Commit**

```bash
git add graph.py nodes/extract_financial_data.py nodes/detect_signals.py tests/test_nodes.py
git commit -m "feat(fec): wire FEC signal engine into extract/detect pipeline"
```

---

## Task 5: Édition des seuils paramétrables dans l'UI Streamlit

**Files:**
- Modify: `app/main.py`

- [ ] **Step 1: Vérifier la signature d'appel actuelle**

Dans `app/main.py`, la fonction `run_analysis(fichier, nom_client, code_naf, catalogue_path, fichier_n1=None, anonymize=False)` construit le dict passé à `graph.stream(...)`. Le formulaire appelle `run_analysis(...)` à la ligne du bouton « Lancer l'analyse ».

- [ ] **Step 2: Ajouter l'expander des seuils dans le formulaire**

Dans le bloc du formulaire (après le champ `catalogue` et avant le bouton), ajouter :

```python
    with st.expander("⚙️ Seuils de détection (avancé)"):
        import json as _json
        from pathlib import Path as _Path
        from analysis.fec_signals import seuils_parametrables, GENERIC_SIGNALS
        _ref = _json.loads(_Path("data/seuils_signaux.json").read_text(encoding="utf-8"))
        _defauts = seuils_parametrables(_ref)
        seuils_overrides = {}
        st.caption("Ajustez les seuils des signaux paramétrables. Vide = valeur par défaut.")
        for _code, _def in sorted(_defauts.items()):
            _titre = GENERIC_SIGNALS[_code][6]  # champ titre de la table
            _val = st.number_input(f"{_titre} ({_code})", min_value=0.0, value=float(_def), step=1000.0, key=f"seuil_{_code}")
            if _val != _def:
                seuils_overrides[_code] = _val
```

- [ ] **Step 3: Passer `seuils_overrides` à `run_analysis` puis au stream**

Modifier l'appel du bouton :

```python
    if lancer:
        run_analysis(fichier, nom_client, code_naf, catalogue, fichier_n1, anonymiser, seuils_overrides)
```

Modifier la signature et le dict de `run_analysis` :

```python
def run_analysis(fichier, nom_client, code_naf, catalogue_path, fichier_n1=None, anonymize=False, seuils_overrides=None):
    ...
        for event in graph.stream({
            "fichier_path":    tmp_path,
            "fichier_path_n1": tmp_path_n1,
            "catalogue_path":  catalogue_path,
            "code_naf":        code_naf.upper().strip(),
            "anonymize":       anonymize,
            "seuils_overrides": seuils_overrides or {},
        }):
```

- [ ] **Step 4: Vérifier l'import de l'app (pas de crash au chargement)**

Run: `.venv/Scripts/python.exe -c "import ast; ast.parse(open('app/main.py', encoding='utf-8').read()); print('app/main.py syntaxe OK')"`
Expected: `app/main.py syntaxe OK`

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "feat(ui): editable detection thresholds in Streamlit form"
```

---

## Task 6: Test e2e FEC synthétique riche + vérification finale

**Files:**
- Modify: `tests/test_pipeline_e2e.py`

- [ ] **Step 1: Écrire le test e2e qui échoue**

Ajouter à `tests/test_pipeline_e2e.py` ce test. Il injecte un `indicateurs_fec` calculé depuis un FEC synthétique (dirigeant sur-rémunéré, 455 créditeur, pénalités fiscales) et vérifie que les signaux remontent jusqu'aux missions. `catalogue_path` et `donnees_saine` sont des fixtures existantes (conftest) :

```python
def test_fec_signals_drive_missions(catalogue_path, donnees_saine):
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from analysis.fec_features import compute_fec_features
    from nodes.detect_signals import detect_signals
    from nodes.match_missions import match_missions

    df = pd.DataFrame([
        {"CompteNum": "641100", "Debit": 60000, "Credit": 0, "EcritureDate": "20240131"},
        {"CompteNum": "4551",   "Debit": 0, "Credit": 90000, "EcritureDate": "20240131"},
        {"CompteNum": "671200", "Debit": 800, "Credit": 0, "EcritureDate": "20240201"},
    ])
    feat = compute_fec_features(df)

    with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
        inst = MagicMock(); resp = MagicMock(); resp.content = "[]"
        inst.invoke.return_value = resp; mock_cls.return_value = inst
        s = detect_signals({"donnees_financieres": donnees_saine, "indicateurs_fec": feat, "seuils_overrides": {}})

    codes = {sig.code for sig in s["signaux_detectes"]}
    assert {"REMUNERATION_DIRIGEANT_ELEVEE", "COMPTE_COURANT_CREDITEUR_ELEVE", "PENALITES_FISCALES"} <= codes

    m = match_missions({**s, "catalogue_path": catalogue_path})
    ids = {r.mission.id for r in m["missions_recommandees"]}
    assert "MISSION_PROTECTION_STATUT_SOCIAL" in ids           # rémunération dirigeant
    assert "MISSION_COMPTA_PACK_SERENITE" in ids               # pénalités fiscales
```

- [ ] **Step 2: Lancer — échoue puis passe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline_e2e.py::test_fec_signals_drive_missions -v`
Expected: après Tasks 1-4 déjà en place, ce test PASSE directement (il valide l'intégration). S'il échoue, lire les codes émis et corriger le mapping compte→mission (vérifier que `MISSION_PROTECTION_STATUT_SOCIAL.codes_signaux` contient bien `REMUNERATION_DIRIGEANT_ELEVEE` dans `data/catalogue_missions_tyls.json`).

- [ ] **Step 3: Vérification globale**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: tout vert, aucune régression.

Run: `.venv/Scripts/python.exe -c "from graph import build_graph; build_graph(); print('graph OK')"`
Expected: `graph OK`.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline_e2e.py
git commit -m "test(fec): e2e synthetic FEC drives family-A signals to missions"
```

---

## Self-Review (relecture plan vs spec)

- **Couverture spec** : `IndicateursFEC` + signes (Task 1) ✓ ; moteur générique 26 codes + `seuils_parametrables` (Task 2) ✓ ; 19 détecteurs explicites — ratios/composites/variations/divers (Task 3) ✓ ; branchement extraction/détection/state (Task 4) ✓ ; seuils UI Streamlit (Task 5) ✓ ; e2e (Task 6) ✓. Total 26 + 19 = 45 codes.
- **Décompte** : GENERIC_SIGNALS = 13 seuil_eur + 11 presence + 2 absence = 26 entrées. `_EXPLICIT_DETECTORS` = 4 ratios + 8 composites (dont COMPTE_COURANT_CREDITEUR_ELEVE) + 6 variations + 1 divers = 19. ✓
- **Cohérence des types** : `compute_fec_features(df, df_n1=None) -> IndicateursFEC` ; `feat.solde(prefixes, sens, n1=)`, `feat.mouvement(prefixes)`, `feat.variation_pct(prefixes, sens)`, `feat.ratio_pct(num, den, sens_num, sens_den)`, `feat.ca_n` — signatures identiques entre Task 1 (définition) et Tasks 2/3 (usage). `detect_signals_from_fec(feat, seuils_overrides)` cohérent Tasks 2→4. `seuils_parametrables(referentiel)` cohérent Tasks 2/5. `GENERIC_SIGNALS[code][6]` = champ titre (index : op0, comptes1, sens2, defaut3, type4, gravite5, titre6, levier7) — utilisé en Task 5. ✓
- **Signes vérifiés** : charges classe 6 → 'D' ; produits 7 et créditeurs (455/457) → 'C' ; provisions (491/158/1511/2813) → 'C' ; capital 101 → 'C' ; résultat 12 → 'C'. ✓
- **Dégradation** : variations → `None` sans N-1 (non émises) ; PDF → `indicateurs_fec = None` → moteur non appelé. ✓
- **Placeholders** : les blocs « fragiles » du Task 6 Step 1 sont explicitement remplacés par la forme finale à utiliser (fixture pytest en paramètre) — la version retenue est complète. Aucune section « TODO/à compléter » dans le code livré.
