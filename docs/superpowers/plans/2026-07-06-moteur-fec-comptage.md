# Moteur FEC — Comptage / distinct (Phase 2b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Émettre 7 signaux « comptage/distinct » (`EMPRUNTS_MULTIPLES`, `MULTI_BIENS_IMMOBILIERS`, `PARC_VEHICULES_IMPORTANT`, `NOMBREUX_FOURNISSEURS`, `ACOMPTES_FREQUENTS`, `COMPLEXITE_COMPTABLE`, `VOLUME_FACTURATION_ELEVE`) en étendant `IndicateursFEC` avec des capacités de comptage, consommés par le matcher déterministe sans le modifier.

**Architecture:** `compute_fec_features` calcule, depuis le même `df` FEC, des features de comptage (sous-comptes distincts, tiers CompAuxNum, écritures, journaux, mois). Un nouveau table `COUNT_SIGNALS` + `_eval_count` gère les 6 signaux « métrique ≥ seuil » ; `VOLUME_FACTURATION_ELEVE` est un détecteur explicite (double seuil mensuel). Les seuils de comptage paramétrables apparaissent dans l'expander Streamlit existant via `seuils_parametrables` étendu.

**Tech Stack:** Python 3.11+, pandas, Pydantic v2, Streamlit, pytest.

**Référence spec :** `docs/superpowers/specs/2026-07-06-moteur-fec-comptage-design.md`

---

## Convention de comptage (rappel)
- **sous-comptes distincts** sous un préfixe (`nb_comptes`) → emprunts (164), biens (213), véhicules (2182).
- **tiers distincts** = CompAuxNum si présent, sinon CompteNum (`nb_tiers`) → fournisseurs (401). Validé sur le FEC réel : 401 a 1 sous-compte mais 26 CompAuxNum.
- **écritures** = lignes sous un préfixe (`nb_ecritures`) → acomptes (4191), volume (70/60).
- **journaux distincts** (JournalCode) (`nb_journaux`) → complexité.
- Comparaison **inclusive** (`≥`) pour tous les seuils de comptage.

## File Structure

| Fichier | Modification |
|---|---|
| `analysis/fec_features.py` | ajout des champs de comptage à `IndicateursFEC` + `_count_features(df)` + 5 accesseurs |
| `analysis/fec_signals.py` | `CountSpec`/`COUNT_SIGNALS`/`_eval_count`/`_volume_facturation`, wiring dans `detect_signals_from_fec`, `seuils_parametrables` étendu, helper `titre_signal` |
| `app/main.py` | l'expander seuils utilise `titre_signal(code)` au lieu de `GENERIC_SIGNALS[code].titre` |
| `tests/test_fec_features.py` | tests extraction comptage |
| `tests/test_fec_signals.py` | tests des 7 signaux + surcharge |
| `tests/test_pipeline_e2e.py` | e2e fournisseurs → mission |

Aucun changement de `graph.py`, `nodes/*`, ni du state (les features sont sur le même objet, calculées au même endroit).

---

## Task 1: Extraction des features de comptage

**Files:**
- Modify: `analysis/fec_features.py`
- Test: `tests/test_fec_features.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_fec_features.py` :

```python
def _dfx(rows):
    # rows: (CompteNum, Debit, Credit, EcritureDate, CompAuxNum, JournalCode)
    return pd.DataFrame([
        {"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt,
         "CompAuxNum": aux, "JournalCode": jc}
        for c, d, cr, dt, aux, jc in rows
    ])


def test_nb_comptes_sous_comptes_distincts():
    f = compute_fec_features(_dfx([
        ("164100", 0, 10000, "20240101", "", "OD"),
        ("164200", 0, 20000, "20240101", "", "OD"),
        ("164200", 0, 5000, "20240201", "", "OD"),   # même sous-compte → 1
        ("512000", 100, 0, "20240101", "", "BQ"),
    ]))
    assert f.nb_comptes(["164"]) == 2
    assert f.nb_comptes(["213"]) == 0


def test_nb_tiers_via_compauxnum():
    # 1 seul sous-compte 401 mais 3 CompAuxNum distincts → 3 fournisseurs
    f = compute_fec_features(_dfx([
        ("401000", 0, 100, "20240101", "F001", "AC"),
        ("401000", 0, 200, "20240102", "F002", "AC"),
        ("401000", 0, 300, "20240103", "F003", "AC"),
        ("401000", 0, 300, "20240104", "F003", "AC"),  # doublon tiers
    ]))
    assert f.nb_tiers(["401"]) == 3


def test_nb_tiers_repli_sous_compte_si_aux_vide():
    # pas de CompAuxNum → on retombe sur les sous-comptes distincts
    f = compute_fec_features(_dfx([
        ("401100", 0, 100, "20240101", "", "AC"),
        ("401200", 0, 200, "20240102", "", "AC"),
    ]))
    assert f.nb_tiers(["401"]) == 2


def test_nb_ecritures_et_journaux_et_mois():
    f = compute_fec_features(_dfx([
        ("419100", 500, 0, "20240115", "", "VE"),
        ("419100", 300, 0, "20240210", "", "VE"),
        ("700000", 0, 1000, "20240115", "", "VE"),
        ("600000", 800, 0, "20240310", "", "AC"),
    ]))
    assert f.nb_ecritures(["4191"]) == 2
    assert f.nb_journaux() == 2       # VE, AC
    assert f.nb_mois() == 3           # 2024-01, 02, 03


def test_comptage_colonnes_absentes_renvoie_zero():
    # df sans CompAuxNum ni JournalCode (format Debit/Credit minimal)
    f = compute_fec_features(pd.DataFrame([
        {"CompteNum": "401100", "Debit": 0, "Credit": 100, "EcritureDate": "20240101"},
    ]))
    assert f.nb_tiers(["401"]) == 1   # repli sous-compte
    assert f.nb_journaux() == 0
    assert f.nb_mois() == 1           # minimum 1


def test_nb_mois_minimum_un_sur_df_vide_de_dates():
    f = compute_fec_features(pd.DataFrame([
        {"CompteNum": "700000", "Debit": 0, "Credit": 1000, "EcritureDate": ""},
    ]))
    assert f.nb_mois() == 1
```

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_features.py -k "nb_comptes or nb_tiers or nb_ecritures or comptage or nb_mois" -v`
Expected: FAIL — `AttributeError: 'IndicateursFEC' object has no attribute 'nb_comptes'`.

- [ ] **Step 3: Étendre `IndicateursFEC` + `compute_fec_features`**

Dans `analysis/fec_features.py`, ajouter les champs au modèle (après `ca_n`) :

```python
    comptes: list[str] = Field(default_factory=list)
    paires_tiers: list[list[str]] = Field(default_factory=list)
    nb_ecritures_par_compte: dict[str, int] = Field(default_factory=dict)
    journaux: list[str] = Field(default_factory=list)
    mois: list[str] = Field(default_factory=list)
```

Ajouter les accesseurs dans la classe :

```python
    def nb_comptes(self, prefixes: list[str]) -> int:
        pref = tuple(prefixes)
        return sum(1 for c in self.comptes if c.startswith(pref))

    def nb_tiers(self, prefixes: list[str]) -> int:
        pref = tuple(prefixes)
        keys = set()
        for compte, aux in self.paires_tiers:
            if compte.startswith(pref):
                keys.add(aux if aux else compte)
        return len(keys)

    def nb_ecritures(self, prefixes: list[str]) -> int:
        pref = tuple(prefixes)
        return sum(v for k, v in self.nb_ecritures_par_compte.items() if k.startswith(pref))

    def nb_journaux(self) -> int:
        return len(self.journaux)

    def nb_mois(self) -> int:
        return max(1, len(self.mois))
```

Ajouter la fonction de calcul (avant `compute_fec_features`) :

```python
def _count_features(df: pd.DataFrame):
    cn = df["CompteNum"].astype(str)
    comptes = sorted(cn.unique().tolist())
    nb_ecritures_par_compte = {k: int(v) for k, v in cn.value_counts().to_dict().items()}

    if "CompAuxNum" in df.columns:
        aux = df["CompAuxNum"].astype(str).str.strip()
        aux = aux.where(~aux.str.lower().isin(["nan", "none"]), "")
    else:
        aux = pd.Series([""] * len(df), index=df.index)
    paires_tiers = sorted({(c, a) for c, a in zip(cn, aux)})
    paires_tiers = [[c, a] for c, a in paires_tiers]

    if "JournalCode" in df.columns:
        journaux = sorted(
            j for j in df["JournalCode"].astype(str).str.strip().unique()
            if j and j.lower() not in ("nan", "none")
        )
    else:
        journaux = []

    if "EcritureDate" in df.columns:
        mois = sorted({str(d)[:6] for d in df["EcritureDate"].astype(str) if str(d)[:6].strip()})
    else:
        mois = []

    return comptes, paires_tiers, nb_ecritures_par_compte, journaux, mois
```

Modifier `compute_fec_features` pour renseigner ces champs (juste avant `feat.ca_n = ...`) :

```python
def compute_fec_features(df: pd.DataFrame, df_n1: pd.DataFrame | None = None) -> IndicateursFEC:
    debit_n, credit_n = _sums_by_account(df)
    debit_n1, credit_n1 = ({}, {})
    if df_n1 is not None:
        debit_n1, credit_n1 = _sums_by_account(df_n1)

    comptes, paires_tiers, nb_ecr, journaux, mois = _count_features(df)

    feat = IndicateursFEC(
        debit_n=debit_n, credit_n=credit_n,
        debit_n1=debit_n1, credit_n1=credit_n1,
        comptes=comptes, paires_tiers=paires_tiers,
        nb_ecritures_par_compte=nb_ecr, journaux=journaux, mois=mois,
    )
    feat.ca_n = feat.solde(["70"], "C")
    return feat
```

- [ ] **Step 4: Lancer — passe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_features.py -v`
Expected: PASS (tests existants + 6 nouveaux).

- [ ] **Step 5: Commit**

```bash
git add analysis/fec_features.py tests/test_fec_features.py
git commit -m "feat(fec): counting features (distinct accounts, tiers, journals, entries)"
```

---

## Task 2: Détecteurs de comptage (`COUNT_SIGNALS` + volume)

**Files:**
- Modify: `analysis/fec_signals.py`
- Test: `tests/test_fec_signals.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à la fin de `tests/test_fec_signals.py` (le helper `_df` existant n'a pas CompAuxNum/JournalCode ; ajouter un helper local `_dfx`) :

```python
def _dfx(rows):
    return pd.DataFrame([
        {"CompteNum": c, "Debit": d, "Credit": cr, "EcritureDate": dt,
         "CompAuxNum": aux, "JournalCode": jc}
        for c, d, cr, dt, aux, jc in rows
    ])


def _codesx(df, overrides=None):
    feat = compute_fec_features(df)
    return {s.code for s in detect_signals_from_fec(feat, overrides or {})}


def test_emprunts_multiples():
    df = _dfx([("164100", 0, 1, "20240101", "", "OD"),
               ("164200", 0, 1, "20240101", "", "OD"),
               ("164300", 0, 1, "20240101", "", "OD")])
    assert "EMPRUNTS_MULTIPLES" in _codesx(df)
    df2 = _dfx([("164100", 0, 1, "20240101", "", "OD"),
                ("164200", 0, 1, "20240101", "", "OD")])
    assert "EMPRUNTS_MULTIPLES" not in _codesx(df2)  # 2 < 3


def test_nombreux_fournisseurs_via_aux():
    rows = [("401000", 0, 1, "20240101", f"F{i:03}", "AC") for i in range(50)]
    assert "NOMBREUX_FOURNISSEURS" in _codesx(_dfx(rows))
    rows2 = [("401000", 0, 1, "20240101", f"F{i:03}", "AC") for i in range(49)]
    assert "NOMBREUX_FOURNISSEURS" not in _codesx(_dfx(rows2))  # 49 < 50


def test_complexite_comptable():
    rows = [("600000", 1, 0, "20240101", "", jc) for jc in
            ["AC", "VE", "BQ", "OD", "OI", "SA", "AN", "CA"]]  # 8 journaux
    assert "COMPLEXITE_COMPTABLE" in _codesx(_dfx(rows))


def test_acomptes_frequents():
    rows = [("419100", 100, 0, f"202401{d:02}", "", "VE") for d in range(1, 6)]  # 5 lignes
    assert "ACOMPTES_FREQUENTS" in _codesx(_dfx(rows))


def test_count_override_abaisse_seuil():
    df = _dfx([("164100", 0, 1, "20240101", "", "OD"),
               ("164200", 0, 1, "20240101", "", "OD")])  # 2 emprunts
    assert "EMPRUNTS_MULTIPLES" not in _codesx(df)                       # défaut 3
    assert "EMPRUNTS_MULTIPLES" in _codesx(df, overrides={"EMPRUNTS_MULTIPLES": 2})


def test_volume_facturation_emises():
    # 30 écritures compte 70 sur 1 mois → émises >= 30
    rows = [("700000", 0, 100, "20240115", "", "VE") for _ in range(30)]
    assert "VOLUME_FACTURATION_ELEVE" in _codesx(_dfx(rows))


def test_volume_facturation_recues():
    rows = [("600000", 100, 0, "20240115", "", "AC") for _ in range(50)]
    assert "VOLUME_FACTURATION_ELEVE" in _codesx(_dfx(rows))


def test_volume_facturation_non_declenche():
    rows = [("700000", 0, 100, "20240115", "", "VE") for _ in range(10)]
    assert "VOLUME_FACTURATION_ELEVE" not in _codesx(_dfx(rows))
```

Ajouter en tête de `tests/test_fec_signals.py` l'import manquant s'il n'y est pas déjà : `from analysis.fec_features import compute_fec_features` (probablement déjà présent).

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -k "emprunts or fournisseurs or complexite or acomptes or count_override or volume" -v`
Expected: FAIL — les codes de comptage ne sont pas émis.

- [ ] **Step 3: Ajouter la table + le moteur de comptage dans `analysis/fec_signals.py`**

Ajouter `NamedTuple` en haut du fichier (le `from typing import NamedTuple` existe déjà via `GenericSpec`). Après la définition de `GENERIC_SIGNALS`, ajouter :

```python
class CountSpec(NamedTuple):
    metric: str            # "nb_comptes" | "nb_tiers" | "nb_ecritures" | "nb_journaux"
    comptes: list[str]
    seuil_defaut: int
    type: TypeSignal
    gravite: Gravite
    titre: str
    levier: str


COUNT_SIGNALS: dict[str, CountSpec] = {
    "EMPRUNTS_MULTIPLES": CountSpec("nb_comptes", ["164"], 3, O, F,
        "Emprunts multiples", "Recherche de financement, restructuration de dette"),
    "MULTI_BIENS_IMMOBILIERS": CountSpec("nb_comptes", ["213"], 2, O, F,
        "Multi-biens immobiliers", "Gestion de SCI, gestion de portefeuille investisseurs"),
    "PARC_VEHICULES_IMPORTANT": CountSpec("nb_comptes", ["2182"], 5, C, F,
        "Parc de véhicules important", "Flotte automobile (assurance)"),
    "NOMBREUX_FOURNISSEURS": CountSpec("nb_tiers", ["401"], 50, C, F,
        "Nombreux fournisseurs", "Mise en place facture électronique"),
    "ACOMPTES_FREQUENTS": CountSpec("nb_ecritures", ["4191"], 5, C, F,
        "Acomptes fréquents", "Mise en place facture électronique"),
    "COMPLEXITE_COMPTABLE": CountSpec("nb_journaux", [], 8, O, M,
        "Comptabilité complexe", "DAF externalisée, contrôle de gestion"),
}


def _count_metric(feat: IndicateursFEC, spec: CountSpec) -> int:
    if spec.metric == "nb_comptes":
        return feat.nb_comptes(spec.comptes)
    if spec.metric == "nb_tiers":
        return feat.nb_tiers(spec.comptes)
    if spec.metric == "nb_ecritures":
        return feat.nb_ecritures(spec.comptes)
    return feat.nb_journaux()


def _eval_count(code: str, feat: IndicateursFEC, seuils_overrides: dict[str, float]) -> Signal | None:
    spec = COUNT_SIGNALS[code]
    seuil = float(seuils_overrides.get(code, spec.seuil_defaut))
    valeur = _count_metric(feat, spec)
    if valeur < seuil:
        return None
    return Signal(type=spec.type, gravite=spec.gravite, code=code, titre=spec.titre,
                  description=f"{spec.titre} : {int(valeur)} détecté(s) (seuil {int(seuil)}).",
                  levier=spec.levier)
```

Ajouter le détecteur explicite `_volume_facturation` près des autres détecteurs explicites (avant `_EXPLICIT_DETECTORS`) :

```python
def _volume_facturation(f: IndicateursFEC) -> Signal | None:
    mois = f.nb_mois()
    emises = f.nb_ecritures(["70"]) / mois
    recues = f.nb_ecritures(["60"]) / mois
    if emises < 30 and recues < 50:
        return None
    return _sig("VOLUME_FACTURATION_ELEVE", C, M, "Volume de facturation élevé",
                f"Facturation : {emises:.0f} émises/mois, {recues:.0f} reçues/mois "
                f"(seuils 30 émises / 50 reçues).",
                "Externalisation de la facturation électronique, formation facture électronique")
```

Ajouter `_volume_facturation` à la liste `_EXPLICIT_DETECTORS` (à la fin de la liste).

Enfin, dans `detect_signals_from_fec`, ajouter la boucle de comptage APRÈS la boucle générique et AVANT/autour de la boucle des détecteurs explicites :

```python
    for code in COUNT_SIGNALS:
        sig = _eval_count(code, feat, overrides)
        if sig is not None:
            signals.append(sig)
```

(La boucle `_EXPLICIT_DETECTORS` existante inclura désormais `_volume_facturation`.)

- [ ] **Step 4: Lancer — passe**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -v`
Expected: PASS (tests Phase 2a + nouveaux comptage).

- [ ] **Step 5: Vérifier la cohérence référentiel**

Run:
`.venv/Scripts/python.exe -c "import json; ref=set(json.load(open('data/seuils_signaux.json',encoding='utf-8'))); from analysis.fec_signals import COUNT_SIGNALS; miss=[c for c in COUNT_SIGNALS if c not in ref]; print('COUNT absents du référentiel:', miss); print('VOLUME_FACTURATION_ELEVE présent:', 'VOLUME_FACTURATION_ELEVE' in ref)"`
Expected: `COUNT absents du référentiel: []` et `VOLUME_FACTURATION_ELEVE présent: True`.

- [ ] **Step 6: Commit**

```bash
git add analysis/fec_signals.py tests/test_fec_signals.py
git commit -m "feat(fec): counting detectors (COUNT_SIGNALS + volume facturation)"
```

---

## Task 3: Seuils de comptage paramétrables dans l'UI

**Files:**
- Modify: `analysis/fec_signals.py`
- Modify: `app/main.py`
- Test: `tests/test_fec_signals.py`

- [ ] **Step 1: Écrire les tests qui échouent**

Ajouter à `tests/test_fec_signals.py` :

```python
def test_seuils_parametrables_inclut_comptage():
    params = seuils_parametrables(SEUILS)
    # les codes de comptage parametrable:true du référentiel sont exposés
    for code in ["EMPRUNTS_MULTIPLES", "NOMBREUX_FOURNISSEURS", "COMPLEXITE_COMPTABLE"]:
        if SEUILS.get(code, {}).get("parametrable"):
            assert code in params
    # VOLUME_FACTURATION_ELEVE n'est pas paramétrable → absent
    assert "VOLUME_FACTURATION_ELEVE" not in params


def test_titre_signal_resout_les_deux_tables():
    from analysis.fec_signals import titre_signal
    assert titre_signal("REMUNERATION_DIRIGEANT_ELEVEE")  # GENERIC
    assert titre_signal("EMPRUNTS_MULTIPLES") == "Emprunts multiples"  # COUNT
    assert titre_signal("CODE_INCONNU") == "CODE_INCONNU"  # repli
```

- [ ] **Step 2: Lancer — échoue**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -k "parametrables_inclut or titre_signal" -v`
Expected: FAIL — `titre_signal` n'existe pas ; `seuils_parametrables` n'inclut pas encore le comptage.

- [ ] **Step 3: Étendre `seuils_parametrables` + ajouter `titre_signal`**

Dans `analysis/fec_signals.py`, remplacer `seuils_parametrables` par :

```python
def seuils_parametrables(referentiel: dict) -> dict[str, float]:
    """code -> seuil défaut, pour les signaux GENERIC + COUNT parametrable:true."""
    out: dict[str, float] = {}
    for table in (GENERIC_SIGNALS, COUNT_SIGNALS):
        for code in table:
            ref = referentiel.get(code, {})
            if ref.get("parametrable") and ref.get("seuil_valeur") is not None:
                out[code] = float(ref["seuil_valeur"])
    return out


def titre_signal(code: str) -> str:
    """Titre lisible d'un code, cherché dans GENERIC puis COUNT (repli = code)."""
    if code in GENERIC_SIGNALS:
        return GENERIC_SIGNALS[code].titre
    if code in COUNT_SIGNALS:
        return COUNT_SIGNALS[code].titre
    return code
```

- [ ] **Step 4: Utiliser `titre_signal` dans l'UI**

Dans `app/main.py`, dans l'expander « ⚙️ Seuils de détection », remplacer l'import et l'accès au titre. L'import actuel est `from analysis.fec_signals import seuils_parametrables, GENERIC_SIGNALS` et la ligne `_titre = GENERIC_SIGNALS[_code].titre`. Remplacer par :

```python
        from analysis.fec_signals import seuils_parametrables, titre_signal
```
et
```python
            _titre = titre_signal(_code)
```
(Supprimer l'usage de `GENERIC_SIGNALS` dans l'expander s'il n'est plus référencé ailleurs dans le bloc.)

- [ ] **Step 5: Lancer + vérifier syntaxe UI**

Run: `.venv/Scripts/python.exe -m pytest tests/test_fec_signals.py -v` → PASS
Run: `.venv/Scripts/python.exe -c "import ast; ast.parse(open('app/main.py', encoding='utf-8').read()); print('syntaxe OK')"` → `syntaxe OK`

- [ ] **Step 6: Commit**

```bash
git add analysis/fec_signals.py app/main.py tests/test_fec_signals.py
git commit -m "feat(fec): expose counting thresholds in UI via seuils_parametrables + titre_signal"
```

---

## Task 4: E2E + vérification finale

**Files:**
- Modify: `tests/test_pipeline_e2e.py`

- [ ] **Step 1: Écrire le test e2e**

Ajouter à `tests/test_pipeline_e2e.py` :

```python
def test_fournisseurs_drive_facture_electronique(catalogue_path, donnees_saine):
    import pandas as pd
    from unittest.mock import patch, MagicMock
    from analysis.fec_features import compute_fec_features
    from nodes.detect_signals import detect_signals
    from nodes.match_missions import match_missions

    # 55 fournisseurs distincts (CompAuxNum) sous un seul sous-compte 401
    rows = [{"CompteNum": "401000", "Debit": 0, "Credit": 100,
             "EcritureDate": "20240115", "CompAuxNum": f"F{i:03}", "JournalCode": "AC"}
            for i in range(55)]
    feat = compute_fec_features(pd.DataFrame(rows))

    with patch("nodes.detect_signals.ChatOpenAI") as mock_cls:
        inst = MagicMock(); resp = MagicMock(); resp.content = "[]"
        inst.invoke.return_value = resp; mock_cls.return_value = inst
        s = detect_signals({"donnees_financieres": donnees_saine, "indicateurs_fec": feat, "seuils_overrides": {}})

    assert "NOMBREUX_FOURNISSEURS" in {sig.code for sig in s["signaux_detectes"]}

    m = match_missions({**s, "catalogue_path": catalogue_path})
    ids = {r.mission.id for r in m["missions_recommandees"]}
    assert "MISSION_COMPTA_FX_MISE_EN_PLACE" in ids
```

- [ ] **Step 2: Lancer le test**

Run: `.venv/Scripts/python.exe -m pytest tests/test_pipeline_e2e.py::test_fournisseurs_drive_facture_electronique -v`
Expected: PASS. Si l'assertion mission échoue, vérifier dans `data/catalogue_missions_tyls.json` que `MISSION_COMPTA_FX_MISE_EN_PLACE.codes_signaux` contient `NOMBREUX_FOURNISSEURS` ; si le code réel diffère, ajuster l'assertion pour cibler une mission réellement déclenchée (ne modifier ni le catalogue ni le code métier). Reporter tout ajustement.

- [ ] **Step 3: Vérification globale**

Run: `.venv/Scripts/python.exe -m pytest -q`
Expected: tout vert, aucune régression.

Run (démo sur le vrai FEC) :
`.venv/Scripts/python.exe -c "from parsers.fec_parser import _load_df; from analysis.fec_features import compute_fec_features; f=compute_fec_features(_load_df('input/443021456FEC20250831.txt')); print('fournisseurs:', f.nb_tiers(['401']), '| journaux:', f.nb_journaux(), '| ecr70:', f.nb_ecritures(['70']), '| mois:', f.nb_mois())"`
Expected: `fournisseurs: 26 | journaux: 7 | ecr70: 53 | mois: 12` (ou proches). Reporter la sortie.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pipeline_e2e.py
git commit -m "test(fec): e2e counting signals drive missions"
```

---

## Self-Review (plan vs spec)

- **Couverture spec** : extraction comptage (Task 1) ✓ ; 6 signaux COUNT_SIGNALS + volume explicite (Task 2) ✓ ; seuils paramétrables UI + titre_signal (Task 3) ✓ ; e2e (Task 4) ✓. 7 codes couverts.
- **Cohérence des types** : `IndicateursFEC.nb_comptes/nb_tiers/nb_ecritures(prefixes)`, `nb_journaux()`, `nb_mois()` définis Task 1, utilisés Task 2. `CountSpec(metric, comptes, seuil_defaut, type, gravite, titre, levier)` + `COUNT_SIGNALS` défini Task 2, `.titre` utilisé Task 3 (`titre_signal`). `_count_metric`/`_eval_count` cohérents. `seuils_parametrables` étendu Task 3 parcourt GENERIC + COUNT. ✓
- **Comparaisons** : comptage inclusif `valeur < seuil → skip` (donc `≥ seuil` déclenche), conforme au « ≥ N » du référentiel. ✓
- **Dégradation** : colonnes CompAuxNum/JournalCode absentes → 0 (Task 1 testé) ; `nb_mois() ≥ 1` évite la division par 0 dans `_volume_facturation`. ✓
- **Placeholders** : aucun — code complet à chaque étape.
- **Pas de changement de pipeline/state** : conforme à la décision spec (features sur le même objet, même nœud). ✓
