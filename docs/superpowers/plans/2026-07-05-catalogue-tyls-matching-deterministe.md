# Catalogue TYLS — Matching déterministe (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remplacer le matching missions LLM par le matcher déterministe TYLS (catalogue 79 missions + référentiel 90 signaux), branché sur les signaux calculables depuis les données financières agrégées actuelles.

**Architecture:** `detect_signals` produit une liste de `Signal` (codes alignés sur le référentiel `seuils_signaux.json`). `match_missions` extrait les codes actifs, les passe à `MissionMatcher` (déterministe, explicable, sans LLM), et convertit les `MissionMatch` en `MissionRecommandee` consommés en aval par `generate_interview_plan` et le générateur Word. Les missions priorité 1 restent toujours proposées. Phase 1 couvre ~22 des 90 codes (ceux dérivables des montants agrégés N/N-1) ; les ~68 restants (mensuel, N-2, comptages, libellés, comptes fins) relèvent d'une Phase 2 (moteur FEC ligne-à-ligne) hors périmètre de ce plan.

**Tech Stack:** Python 3.11+, LangGraph (StateGraph), Pydantic v2, pytest.

---

## Périmètre & décisions actées

- **Matcher déterministe pur** : `matching/mission_matcher.py` devient LE moteur. `matching/llm_matcher.py` et `matching/rag_matcher.py` ne sont plus appelés par le node (fichiers conservés sur disque, non supprimés — YAGNI, aucune régression).
- **Une seule source de vérité** : le matcher lit directement `data/seuils_signaux.json` (dict indexé par code). Aucun fichier `referentiel_signaux_fec.json` n'est créé.
- **Argumentaire = `benefice_client`** du catalogue (déjà du copywriting orienté client). La prose sur-mesure est produite en aval par `generate_interview_plan` (inchangé).
- **Cohérence vérifiée** : les 90 codes référencés par les missions existent tous dans le référentiel → `MissionMatcher._verifier_coherence` ne lève pas. 19 missions ont `codes_signaux=[]` (jamais déclenchées par signal ; proposées via la règle priorité 1).

### Inventaire couverture Phase 1 (codes émis, tous présents au référentiel)

Déjà émis par `analysis/rules.py` (inchangé) : `EBE_NEGATIF`, `EBE_FAIBLE`, `ENDETTEMENT_EXCESSIF`, `LIQUIDITE_CRITIQUE`, `DELAI_CLIENTS_ELEVE`, `BAISSE_CA_SIGNIFICATIVE`, `DESEQUILIBRE_BFR`, `FORTE_RENTABILITE`, `FORTE_CROISSANCE`, `CAPACITE_INVESTISSEMENT`, `OPTIMISATION_FISCALE` (11).
> Note : `rules.py` émet aussi `LIQUIDITE_TENDUE` et `AUTONOMIE_FAIBLE`, absents du référentiel. Ils restent affichés dans la fiche mais ne déclenchent aucune mission — comportement voulu, sans effet de bord (le matcher ignore les codes inconnus).

Ajoutés par `detect_signals_from_donnees` (Task 2) : `PRESENCE_SALARIES`, `MASSE_SALARIALE_ELEVEE`, `TRESORERIE_EXCEDENTAIRE`, `HAUSSE_TRESORERIE`, `MARGE_BRUTE_FAIBLE`, `MARGE_NETTE_FAIBLE`, `HAUSSE_ACHATS_SANS_CA`, `RESULTAT_EN_CROISSANCE`, `RESULTAT_NET_ELEVE_RECURRENT`, `CAPITAUX_PROPRES_ELEVES_SANS_HOLDING`, `EROSION_PORTEFEUILLE_CLIENTS` (11).

---

## File Structure

- `data/catalogue_missions_tyls.json` — **déplacé** depuis la racine du repo principal. 79 missions TYLS. Schéma Pydantic `Mission` inchangé.
- `data/seuils_signaux.json` — **déplacé**. Référentiel 90 signaux, dict indexé par code.
- `matching/mission_matcher.py` — **déplacé** depuis `data/mission_matcher.py` + adapté pour lire le dict `seuils_signaux.json`.
- `analysis/rules.py` — **ajout** de `detect_signals_from_donnees(donnees, ratios)` (signature de `detect_signals_from_rules` inchangée).
- `nodes/detect_signals.py` — combine les deux fonctions de détection.
- `nodes/match_missions.py` — **réécrit** : matcher déterministe + bridge `MissionMatch → MissionRecommandee`.
- `graph.py`, `app/main.py`, `tests/conftest.py`, `README.md`, `CLAUDE.md` — bascule du défaut catalogue vers `catalogue_missions_tyls.json`.
- Tests : `tests/test_mission_matcher.py` (nouveau), `tests/test_rules.py` (ajout), `tests/test_nodes.py` (réécriture bloc match), `tests/test_pipeline_e2e.py` (ajustement).

---

## Task 1: Déplacer les fichiers et adapter le matcher au référentiel `seuils_signaux.json`

**Files:**
- Create (move): `data/catalogue_missions_tyls.json`, `data/seuils_signaux.json`, `matching/mission_matcher.py`
- Test: `tests/test_mission_matcher.py`

- [ ] **Step 1: Déplacer les 3 fichiers depuis le repo principal vers le worktree**

Depuis la racine du worktree :

```bash
cp ../../../data/catalogue_missions_tyls.json data/catalogue_missions_tyls.json
cp ../../../data/seuils_signaux.json          data/seuils_signaux.json
cp ../../../data/mission_matcher.py           matching/mission_matcher.py
```

- [ ] **Step 2: Écrire le test qui échoue**

Créer `tests/test_mission_matcher.py` :

```python
from pathlib import Path
import pytest
from matching.mission_matcher import MissionMatcher

ROOT = Path(__file__).resolve().parent.parent
CATALOGUE = ROOT / "data" / "catalogue_missions_tyls.json"
SEUILS = ROOT / "data" / "seuils_signaux.json"


@pytest.fixture
def matcher():
    return MissionMatcher.from_files(CATALOGUE, SEUILS)


def test_from_files_loads_and_coherence_ok(matcher):
    # 79 missions, 90 signaux, cohérence catalogue/référentiel valide (pas de ValueError)
    assert len(matcher.missions) == 79
    assert len(matcher.signaux) == 90


def test_signal_reads_dict_referential(matcher):
    sig = matcher.signaux["TRESORERIE_EXCEDENTAIRE"]
    assert sig.categorie == "TRESORERIE"
    assert "512" in sig.comptes_fec
    assert sig.seuil_texte  # champ non vide
    assert sig.libelle  # libellé synthétisé, jamais vide


def test_match_deterministe_par_signaux(matcher):
    matches = matcher.match({"TRESORERIE_EXCEDENTAIRE", "HAUSSE_TRESORERIE"})
    ids = {m.mission.id for m in matches}
    # Placement de trésorerie est déclenché par ces deux signaux
    assert "MISSION_PATRIMOINE_TRESORERIE" in ids
    treso = next(m for m in matches if m.mission.id == "MISSION_PATRIMOINE_TRESORERIE")
    assert treso.score >= 2
    assert {s.code for s in treso.signaux_declencheurs} >= {"TRESORERIE_EXCEDENTAIRE", "HAUSSE_TRESORERIE"}


def test_missions_sans_signal_jamais_declenchees(matcher):
    # MISSION_COMPTA_EXPERTISE a codes_signaux=[] → jamais dans un match par signal
    matches = matcher.match({"TRESORERIE_EXCEDENTAIRE"})
    assert "MISSION_COMPTA_EXPERTISE" not in {m.mission.id for m in matches}


def test_tri_priorite_puis_score(matcher):
    matches = matcher.match({"LIQUIDITE_CRITIQUE", "DELAI_CLIENTS_ELEVE", "DECOUVERT_RECURRENT"})
    priorites = [m.mission.priorite_proposition for m in matches]
    assert priorites == sorted(priorites)
```

- [ ] **Step 3: Lancer le test — il échoue**

Run: `pytest tests/test_mission_matcher.py -v`
Expected: FAIL — `MissionMatcher.from_files` lève `KeyError`/`TypeError` car il lit encore une **liste** d'objets avec `libelle`/`regle_calcul`/`seuil`, alors que `seuils_signaux.json` est un **dict** indexé par code sans ces champs.

- [ ] **Step 4: Adapter `matching/mission_matcher.py`**

Remplacer la dataclass `Signal` et sa fabrique par (le reste du fichier — `Mission`, `MissionMatch`, `MissionMatcher.match`, `build_matcher_node` — reste inchangé) :

```python
@dataclass(frozen=True)
class Signal:
    """Un signal FEC tel que défini dans seuils_signaux.json (dict indexé par code)."""

    code: str
    categorie: str
    comptes_fec: list[str]
    seuil_texte: str
    periode_reference: str
    libelle: str

    @classmethod
    def from_dict(cls, code: str, d: dict) -> "Signal":
        return cls(
            code=code,
            categorie=d["categorie"],
            comptes_fec=list(d.get("comptes_fec", [])),
            seuil_texte=d.get("seuil_texte", ""),
            periode_reference=d.get("periode_reference", ""),
            libelle=d.get("libelle") or code.replace("_", " ").capitalize(),
        )
```

Puis dans `MissionMatcher.from_files`, remplacer la construction du dict `signaux` (le référentiel est un dict `{code: {...}}`, plus une liste) :

```python
        missions_raw = json.loads(Path(catalogue_path).read_text(encoding="utf-8"))
        signaux_raw = json.loads(Path(referentiel_path).read_text(encoding="utf-8"))

        missions = [Mission.from_dict(m) for m in missions_raw]
        signaux = {code: Signal.from_dict(code, d) for code, d in signaux_raw.items()}

        cls._verifier_coherence(missions, signaux)
        return cls(missions, signaux)
```

Enfin, mettre à jour le bloc `if __name__ == "__main__":` pour pointer sur le référentiel réel :

```python
    matcher = MissionMatcher.from_files(
        base.parent / "data" / "catalogue_missions_tyls.json",
        base.parent / "data" / "seuils_signaux.json",
    )
```

- [ ] **Step 5: Lancer le test — il passe**

Run: `pytest tests/test_mission_matcher.py -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add data/catalogue_missions_tyls.json data/seuils_signaux.json matching/mission_matcher.py tests/test_mission_matcher.py
git commit -m "feat(matching): add TYLS deterministic matcher reading seuils_signaux.json"
```

---

## Task 2: Étendre la détection de signaux aux montants absolus

**Files:**
- Modify: `analysis/rules.py` (ajout d'une fonction, signatures existantes inchangées)
- Modify: `nodes/detect_signals.py:31-32`
- Test: `tests/test_rules.py`

- [ ] **Step 1: Écrire le test qui échoue**

Ajouter à la fin de `tests/test_rules.py` :

```python
from analysis.rules import detect_signals_from_donnees
from analysis.ratios import compute_ratios


def _codes(donnees):
    return {s.code for s in detect_signals_from_donnees(donnees, compute_ratios(donnees))}


def test_donnees_saine_emits_absolute_signals(donnees_saine):
    codes = _codes(donnees_saine)
    # CA 1M, tréso 200k>80k, CP 500k, salariés présents
    assert "TRESORERIE_EXCEDENTAIRE" in codes
    assert "PRESENCE_SALARIES" in codes
    assert "RESULTAT_NET_ELEVE_RECURRENT" in codes  # RN 160k > 150k


def test_masse_salariale_elevee():
    from models import DonneesFinancieres, PosteComptable
    d = DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=100_000),
        achats_consommes=PosteComptable(libelle="A", montant_n=10_000),
        charges_externes=PosteComptable(libelle="CE", montant_n=5_000),
        charges_personnel=PosteComptable(libelle="CP", montant_n=70_000),  # 70% > 60%
        ebe=PosteComptable(libelle="EBE", montant_n=15_000),
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=10_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=8_000),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=20_000),
        stocks=PosteComptable(libelle="S", montant_n=5_000),
        creances_clients=PosteComptable(libelle="Cl", montant_n=10_000),
        tresorerie_actif=PosteComptable(libelle="T", montant_n=5_000),
        capitaux_propres=PosteComptable(libelle="CP", montant_n=30_000),
        dettes_financieres=PosteComptable(libelle="DF", montant_n=10_000),
        dettes_fournisseurs=PosteComptable(libelle="Fo", montant_n=5_000),
    )
    codes = {s.code for s in detect_signals_from_donnees(d, compute_ratios(d))}
    assert "MASSE_SALARIALE_ELEVEE" in codes
    assert "PRESENCE_SALARIES" in codes


def test_hausse_tresorerie_variation():
    from models import DonneesFinancieres, PosteComptable
    d = DonneesFinancieres(
        exercice_n=2024,
        chiffre_affaires=PosteComptable(libelle="CA", montant_n=500_000),
        achats_consommes=PosteComptable(libelle="A", montant_n=200_000),
        charges_externes=PosteComptable(libelle="CE", montant_n=50_000),
        charges_personnel=PosteComptable(libelle="CP", montant_n=100_000),
        ebe=PosteComptable(libelle="EBE", montant_n=100_000),
        resultat_exploitation=PosteComptable(libelle="Rex", montant_n=80_000),
        resultat_net=PosteComptable(libelle="RN", montant_n=60_000),
        immobilisations_nettes=PosteComptable(libelle="Immo", montant_n=100_000),
        stocks=PosteComptable(libelle="S", montant_n=20_000),
        creances_clients=PosteComptable(libelle="Cl", montant_n=40_000),
        tresorerie_actif=PosteComptable(libelle="T", montant_n=150_000, montant_n1=100_000),  # +50%
        capitaux_propres=PosteComptable(libelle="CP", montant_n=200_000),
        dettes_financieres=PosteComptable(libelle="DF", montant_n=50_000),
        dettes_fournisseurs=PosteComptable(libelle="Fo", montant_n=30_000),
    )
    assert "HAUSSE_TRESORERIE" in {s.code for s in detect_signals_from_donnees(d, compute_ratios(d))}
```

- [ ] **Step 2: Lancer le test — il échoue**

Run: `pytest tests/test_rules.py -k "absolute or masse or hausse_tresorerie" -v`
Expected: FAIL — `ImportError: cannot import name 'detect_signals_from_donnees'`.

- [ ] **Step 3: Ajouter la fonction dans `analysis/rules.py`**

Ajouter en tête l'import du modèle de données, puis la nouvelle fonction après `detect_signals_from_rules` :

```python
from models import Signal, TypeSignal, Gravite, DonneesFinancieres
from analysis.ratios import Ratios


def detect_signals_from_donnees(d: DonneesFinancieres, ratios: Ratios) -> list[Signal]:
    """Signaux nécessitant des montants absolus (non portés par Ratios).

    Complète detect_signals_from_rules. Les codes émis sont alignés sur
    data/seuils_signaux.json. Certains seuils sont des proxys sur l'exercice N
    faute d'historique N-2 (Phase 1) — précisé dans la description.
    """
    signals: list[Signal] = []
    ca = d.chiffre_affaires.montant_n

    if d.charges_personnel.montant_n > 0:
        signals.append(Signal(
            type=TypeSignal.CONFORMITE, gravite=Gravite.FAIBLE,
            code="PRESENCE_SALARIES",
            titre="Présence de salariés",
            description="La société emploie du personnel (charges de personnel > 0).",
            levier="Prévoyance salariés, mutuelle collective, paie, épargne salariale",
        ))

    if ca and d.charges_personnel.montant_n / ca * 100 > 60:
        pct = d.charges_personnel.montant_n / ca * 100
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="MASSE_SALARIALE_ELEVEE",
            titre=f"Masse salariale élevée ({pct:.0f}% du CA)",
            description=f"Les charges de personnel représentent {pct:.0f}% du CA (seuil 60%).",
            levier="Audit social, intéressement/PEE, structuration des rémunérations",
        ))

    if d.tresorerie_actif.montant_n > 80_000:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="TRESORERIE_EXCEDENTAIRE",
            titre=f"Trésorerie excédentaire ({d.tresorerie_actif.montant_n:,.0f} €)",
            description="La trésorerie dépasse 80 000 € : capital potentiellement dormant.",
            levier="Placement de trésorerie, contrats de capitalisation, SCPI",
        ))

    tn1 = d.tresorerie_actif.montant_n1
    if tn1 and tn1 > 0 and (d.tresorerie_actif.montant_n - tn1) / tn1 * 100 > 20:
        var = (d.tresorerie_actif.montant_n - tn1) / tn1 * 100
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="HAUSSE_TRESORERIE",
            titre=f"Hausse de trésorerie ({var:+.0f}% vs N-1)",
            description="La trésorerie progresse fortement : marge de manœuvre nouvelle.",
            levier="Placement, investissement, distribution optimisée",
        ))

    if ratios.taux_marge_brute < 25:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="MARGE_BRUTE_FAIBLE",
            titre=f"Marge brute faible ({ratios.taux_marge_brute:.1f}%)",
            description="La marge brute est sous le seuil de vigilance (25%).",
            levier="Contrôle de gestion, calcul du prix de revient, politique tarifaire",
        ))

    if ratios.taux_resultat_net < 3:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="MARGE_NETTE_FAIBLE",
            titre=f"Marge nette faible ({ratios.taux_resultat_net:.1f}%)",
            description="Le résultat net représente moins de 3% du CA.",
            levier="DAF externalisée, optimisation des charges, pilotage des marges",
        ))

    va = d.achats_consommes.variation_pct
    vca = d.chiffre_affaires.variation_pct
    if va is not None and vca is not None and va > 10 and vca <= 0:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
            code="HAUSSE_ACHATS_SANS_CA",
            titre=f"Achats en hausse ({va:+.0f}%) sans effet sur le CA ({vca:+.0f}%)",
            description="Les achats progressent alors que le CA stagne ou baisse : dérapage de marge.",
            levier="Analyse des consommations, renégociation fournisseurs, contrôle de gestion",
        ))

    if ratios.variation_resultat_pct is not None and ratios.variation_resultat_pct > 15:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="RESULTAT_EN_CROISSANCE",
            titre=f"Résultat en croissance ({ratios.variation_resultat_pct:+.0f}%)",
            description="Le résultat net progresse nettement vs N-1.",
            levier="Intéressement, optimisation fiscale, transmission anticipée",
        ))

    if d.resultat_net.montant_n > 150_000:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="RESULTAT_NET_ELEVE_RECURRENT",
            titre=f"Résultat net élevé ({d.resultat_net.montant_n:,.0f} €)",
            description="Résultat net supérieur à 150 000 € (proxy exercice N ; récurrence à confirmer sur 3 ans).",
            levier="Diagnostic patrimonial, holding, PER, placements",
        ))

    if d.capitaux_propres.montant_n > 500_000:
        signals.append(Signal(
            type=TypeSignal.OPPORTUNITE, gravite=Gravite.FAIBLE,
            code="CAPITAUX_PROPRES_ELEVES_SANS_HOLDING",
            titre=f"Capitaux propres élevés ({d.capitaux_propres.montant_n:,.0f} €)",
            description="Capitaux propres > 500 000 € : enjeu de structuration et de transmission (détention holding à vérifier).",
            levier="Création de holding, pacte Dutreil, restructuration patrimoniale",
        ))

    vcl = d.creances_clients.variation_pct
    if vcl is not None and vcl < -15:
        signals.append(Signal(
            type=TypeSignal.RISQUE, gravite=Gravite.FAIBLE,
            code="EROSION_PORTEFEUILLE_CLIENTS",
            titre=f"Baisse des créances clients ({vcl:+.0f}%)",
            description="Les créances clients reculent de plus de 15% vs N-1 : érosion possible du portefeuille.",
            levier="Assistanat commercial, diagnostic commercial, relance de la prospection",
        ))

    return signals
```

- [ ] **Step 4: Brancher la fonction dans `nodes/detect_signals.py`**

Remplacer les lignes 31-32 :

```python
    ratios = compute_ratios(donnees)
    signaux = detect_signals_from_rules(ratios)
```

par :

```python
    ratios = compute_ratios(donnees)
    signaux = detect_signals_from_rules(ratios) + detect_signals_from_donnees(donnees, ratios)
```

et compléter l'import ligne 11 :

```python
from analysis.rules import detect_signals_from_rules, detect_signals_from_donnees
```

- [ ] **Step 5: Lancer les tests — ils passent**

Run: `pytest tests/test_rules.py -v`
Expected: PASS (tests existants + 3 nouveaux).

- [ ] **Step 6: Commit**

```bash
git add analysis/rules.py nodes/detect_signals.py tests/test_rules.py
git commit -m "feat(signals): detect absolute-amount signals aligned on TYLS referential"
```

---

## Task 3: Réécrire `match_missions` en matcher déterministe

**Files:**
- Modify: `nodes/match_missions.py` (réécriture complète)
- Test: `tests/test_nodes.py:174-236` (réécriture du bloc `TestMatchMissionsNode`)

- [ ] **Step 1: Réécrire le test qui échoue**

Remplacer entièrement la classe `TestMatchMissionsNode` (lignes 174-236) de `tests/test_nodes.py` par :

```python
# ── Node match_missions (déterministe) ─────────────────────────────────────────

class TestMatchMissionsNode:

    def _signal(self, code):
        from models import Signal, TypeSignal, Gravite
        return Signal(type=TypeSignal.RISQUE, gravite=Gravite.MOYENNE,
                      code=code, titre=code, description="", levier="")

    def test_priority_1_missions_always_included(self):
        """Les missions priorité 1 sont toujours proposées, même sans signal."""
        from nodes.match_missions import match_missions
        result = match_missions({"signaux_detectes": []})
        recos = result["missions_recommandees"]
        assert any(r.mission.priorite_proposition == 1 for r in recos)
        assert len(recos) > 0

    def test_signal_declenche_mission(self):
        """Un signal actif déclenche les missions qui le référencent, avec explicabilité."""
        from nodes.match_missions import match_missions
        result = match_missions({
            "signaux_detectes": [self._signal("TRESORERIE_EXCEDENTAIRE"),
                                 self._signal("HAUSSE_TRESORERIE")],
        })
        recos = {r.mission.id: r for r in result["missions_recommandees"]}
        assert "MISSION_PATRIMOINE_TRESORERIE" in recos
        assert "TRESORERIE_EXCEDENTAIRE" in recos["MISSION_PATRIMOINE_TRESORERIE"].signaux_declencheurs
        assert recos["MISSION_PATRIMOINE_TRESORERIE"].argumentaire  # = benefice_client, non vide

    def test_sorted_by_score_descending(self):
        """Les recommandations sont triées par score_pertinence décroissant."""
        from nodes.match_missions import match_missions
        result = match_missions({
            "signaux_detectes": [self._signal("LIQUIDITE_CRITIQUE"),
                                 self._signal("DELAI_CLIENTS_ELEVE")],
        })
        scores = [r.score_pertinence for r in result["missions_recommandees"]]
        assert scores == sorted(scores, reverse=True)

    def test_unknown_signal_code_ignored(self):
        """Un code signal inconnu du référentiel ne fait pas planter le matching."""
        from nodes.match_missions import match_missions
        result = match_missions({"signaux_detectes": [self._signal("CODE_BIDON_XYZ")]})
        assert "missions_recommandees" in result

    def test_security_rejects_path_traversal(self):
        """Le chargement du catalogue refuse les chemins traversaux."""
        import pytest
        from nodes.match_missions import match_missions
        with pytest.raises(ValueError, match="outside the allowed"):
            match_missions({"signaux_detectes": [], "catalogue_path": "../../../etc/passwd"})
```

- [ ] **Step 2: Lancer le test — il échoue**

Run: `pytest tests/test_nodes.py::TestMatchMissionsNode -v`
Expected: FAIL — l'ancien `match_missions` charge encore `data/catalogue_missions.json` et appelle le LLM ; `MISSION_PATRIMOINE_TRESORERIE` n'existe pas dans l'ancien catalogue.

- [ ] **Step 3: Réécrire `nodes/match_missions.py`**

Remplacer tout le fichier par :

```python
# nodes/match_missions.py
import os
from pathlib import Path
from models import Mission, MissionRecommandee
from matching.mission_matcher import MissionMatcher, Mission as MissionDC

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_URGENCE = {1: "immédiate", 2: "court terme", 3: "moyen terme"}


def _resolve(path: str) -> Path:
    resolved = (Path(path) if Path(path).is_absolute() else (_DATA_DIR.parent / path)).resolve()
    if not resolved.is_relative_to(_DATA_DIR):
        raise ValueError(f"Path '{path}' is outside the allowed data directory.")
    return resolved


def _to_model(m: MissionDC) -> Mission:
    return Mission(
        id=m.id, titre=m.titre, description=m.description,
        benefice_client=m.benefice_client, codes_signaux=m.codes_signaux,
        honoraires_indicatifs=m.honoraires_indicatifs,
        priorite_proposition=m.priorite_proposition,
    )


def match_missions(state: dict) -> dict:
    signaux = state.get("signaux_detectes", []) or []
    codes_actifs = [s.code for s in signaux]

    catalogue_path = _resolve(state.get("catalogue_path", "data/catalogue_missions_tyls.json"))
    seuils_path = _resolve(state.get("seuils_path", os.getenv("SEUILS_PATH", "data/seuils_signaux.json")))

    matcher = MissionMatcher.from_files(catalogue_path, seuils_path)
    matches = matcher.match(codes_actifs)

    recommandations: list[MissionRecommandee] = []
    ids_retenus: set[str] = set()

    for m in matches:
        mission = _to_model(m.mission)
        ids_retenus.add(mission.id)
        score = 1.0 if mission.priorite_proposition == 1 else min(1.0, round(0.5 + 0.1 * m.score, 2))
        recommandations.append(MissionRecommandee(
            mission=mission,
            score_pertinence=score,
            signaux_declencheurs=[s.code for s in m.signaux_declencheurs],
            argumentaire=mission.benefice_client,
            urgence=_URGENCE.get(mission.priorite_proposition, "moyen terme"),
        ))

    # Toujours inclure les missions priorité 1, même sans signal déclencheur
    for m in matcher.missions:
        if m.priorite_proposition == 1 and m.id not in ids_retenus:
            mission = _to_model(m)
            recommandations.append(MissionRecommandee(
                mission=mission,
                score_pertinence=1.0,
                signaux_declencheurs=[],
                argumentaire=mission.benefice_client,
                urgence="immédiate",
            ))

    recommandations.sort(key=lambda r: r.score_pertinence, reverse=True)
    return {"missions_recommandees": recommandations}
```

- [ ] **Step 4: Lancer le test — il passe**

Run: `pytest tests/test_nodes.py::TestMatchMissionsNode -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add nodes/match_missions.py tests/test_nodes.py
git commit -m "refactor(matching): deterministic match_missions node, drop LLM matcher"
```

---

## Task 4: Basculer le catalogue par défaut vers TYLS

**Files:**
- Modify: `tests/conftest.py:19`
- Modify: `app/main.py:206`
- Modify: `tests/test_pipeline_e2e.py` (fixture `catalogue_path` héritée de conftest ; ajuster l'assertion du test de traversal si besoin)
- Modify: `CLAUDE.md:32,90,119`, `README.md:262`

- [ ] **Step 1: Mettre à jour la fixture de tests**

Dans `tests/conftest.py`, ligne 19 :

```python
CATALOGUE_PATH = str(ROOT / "data" / "catalogue_missions_tyls.json")
```

- [ ] **Step 2: Mettre à jour l'UI Streamlit**

Dans `app/main.py`, ligne 206 :

```python
            catalogue = st.text_input("Catalogue missions", value="data/catalogue_missions_tyls.json")
```

- [ ] **Step 3: Lancer la suite de tests complète**

Run: `pytest -v`
Expected: PASS. Le test `test_full_pipeline_match_missions` et `test_end_to_end_all_nodes_sequential` utilisent la fixture `catalogue_path` (désormais TYLS) et le mock LLM `_mock_llm("[]")` sur `nodes.match_missions.ChatOpenAI` : ce patch devient un no-op inoffensif (le node n'importe plus `ChatOpenAI`), les assertions `len(...) > 0` restent vraies grâce aux missions priorité 1.

> Si un test échoue sur `patch("nodes.match_missions.ChatOpenAI")` (AttributeError car le symbole n'existe plus dans le module), retirer ce `patch(...)` du `with` dans `tests/test_pipeline_e2e.py` (lignes ~166 et ~203) — il n'a plus d'objet à patcher.

- [ ] **Step 4: Mettre à jour la documentation**

Dans `CLAUDE.md` : ligne 32 (défaut `CATALOGUE_PATH` → `data/catalogue_missions_tyls.json`), ligne 90 et ligne 119 (référence au catalogue). Ajouter une ligne dans le tableau des variables d'environnement :

```
| `SEUILS_PATH` | No | `data/seuils_signaux.json` | Référentiel des signaux FEC (matcher déterministe) |
```

Dans `README.md`, ligne 262 : remplacer `data/catalogue_missions.json` par `data/catalogue_missions_tyls.json`.

- [ ] **Step 5: Commit**

```bash
git add tests/conftest.py app/main.py tests/test_pipeline_e2e.py CLAUDE.md README.md
git commit -m "chore: switch default mission catalog to TYLS + document SEUILS_PATH"
```

---

## Task 5: Vérification end-to-end

**Files:** aucun changement — vérification seule.

- [ ] **Step 1: Suite complète**

Run: `pytest -v`
Expected: PASS sur l'ensemble.

- [ ] **Step 2: Démo du matcher en isolation**

Run: `python matching/mission_matcher.py`
Expected: affiche des missions triées `[P1]/[P2]...` avec leurs signaux déclencheurs, sans exception (cohérence catalogue/référentiel OK).

- [ ] **Step 3: Fumée pipeline (si une clé OpenAI de test est configurée, sinon ignorer)**

Vérifier que `match_missions` s'insère sans erreur d'import dans le graphe :

```bash
python -c "from graph import build_graph; build_graph(); print('graph OK')"
```
Expected: `graph OK`.

- [ ] **Step 4: Commit final éventuel**

Si des ajustements ont été nécessaires :

```bash
git add -A
git commit -m "test: verify TYLS deterministic matching pipeline end-to-end"
```

---

## Self-Review

- **Couverture spec** : catalogue TYLS branché (Task 1, 4) ✓ ; référentiel `seuils_signaux.json` unique source (Task 1) ✓ ; `mission_matcher.py` intégré comme node (Task 3) ✓ ; signaux calculés depuis les indicateurs (Task 2) ✓ ; missions priorité 1 conservées (Task 3) ✓ ; sécurité path traversal conservée (Task 3) ✓.
- **Placeholders** : aucun — chaque étape porte le code complet.
- **Cohérence des types** : `MissionMatcher.from_files(catalogue, referentiel)`, `Signal.from_dict(code, d)`, `match(codes) -> list[MissionMatch]`, `MissionMatch.mission: Mission(dataclass)` / `.signaux_declencheurs: list[Signal]` / `.score: int` ; bridge `_to_model(MissionDC) -> models.Mission` ; `MissionRecommandee(mission, score_pertinence, signaux_declencheurs, argumentaire, urgence)` — signatures alignées entre tâches.
- **Hors périmètre (Phase 2)** : les ~68 signaux exigeant mensuel / N-2 / comptages / libellés / comptes fins (ex. `DECOUVERT_RECURRENT`, `MULTI_BIENS_IMMOBILIERS`, `REMUNERATION_DIRIGEANT_ELEVEE`, tous les `IMMO_*`, `PARC_*`) restent non émis ; leurs missions ne se déclenchent que si un futur moteur FEC produit ces codes.
```