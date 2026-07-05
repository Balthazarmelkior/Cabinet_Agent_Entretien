"""Moteur de matching missions ↔ signaux FEC.

Prend en entrée l'ensemble des codes signaux calculés depuis le FEC (par une couche
amont) et ressort les missions TYLS à proposer, triées par priorité puis pertinence,
avec pour chacune les signaux qui l'ont déclenchée (explicabilité).

Conçu pour être utilisé aussi bien en direct qu'en nœud d'un StateGraph LangGraph
(voir `build_matcher_node` en bas de fichier).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Optional

# --------------------------------------------------------------------------- #
# Modèles
# --------------------------------------------------------------------------- #


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


@dataclass(frozen=True)
class Mission:
    """Une mission telle que définie dans catalogue_missions_tyls.json."""

    id: str
    titre: str
    description: str
    benefice_client: str
    codes_signaux: list[str]
    honoraires_indicatifs: str
    priorite_proposition: int

    @classmethod
    def from_dict(cls, d: dict) -> "Mission":
        return cls(
            id=d["id"],
            titre=d["titre"],
            description=d["description"],
            benefice_client=d["benefice_client"],
            codes_signaux=list(d.get("codes_signaux", [])),
            honoraires_indicatifs=d["honoraires_indicatifs"],
            priorite_proposition=int(d["priorite_proposition"]),
        )

    @property
    def marque(self) -> str:
        """Marque déduite du préfixe de l'id (MISSION_IMMO_* -> IMMO)."""
        parts = self.id.split("_")
        return parts[1] if len(parts) > 1 else ""


@dataclass
class MissionMatch:
    """Une mission retenue + les signaux actifs qui l'ont déclenchée."""

    mission: Mission
    signaux_declencheurs: list[Signal] = field(default_factory=list)

    @property
    def score(self) -> int:
        """Nombre de signaux actifs ayant déclenché la mission (proxy de pertinence)."""
        return len(self.signaux_declencheurs)

    def to_dict(self) -> dict:
        """Sérialisation légère, pratique dans un state LangGraph ou une API."""
        return {
            "id": self.mission.id,
            "titre": self.mission.titre,
            "marque": self.mission.marque,
            "priorite": self.mission.priorite_proposition,
            "score": self.score,
            "benefice_client": self.mission.benefice_client,
            "honoraires_indicatifs": self.mission.honoraires_indicatifs,
            "signaux_declencheurs": [
                {"code": s.code, "libelle": s.libelle, "categorie": s.categorie}
                for s in self.signaux_declencheurs
            ],
        }


# --------------------------------------------------------------------------- #
# Matcher
# --------------------------------------------------------------------------- #


class MissionMatcher:
    """Charge le catalogue + le référentiel une fois, puis matche à la demande.

    Instancier une fois (ex. au démarrage de l'agent) et réutiliser : le chargement
    des JSON n'a lieu qu'à la construction.
    """

    def __init__(self, missions: list[Mission], signaux: dict[str, Signal]) -> None:
        self.missions = missions
        self.signaux = signaux  # code -> Signal

    # -- Fabriques ---------------------------------------------------------- #

    @classmethod
    def from_files(
        cls,
        catalogue_path: str | Path,
        referentiel_path: str | Path,
    ) -> "MissionMatcher":
        missions_raw = json.loads(Path(catalogue_path).read_text(encoding="utf-8"))
        signaux_raw = json.loads(Path(referentiel_path).read_text(encoding="utf-8"))

        missions = [Mission.from_dict(m) for m in missions_raw]
        signaux = {code: Signal.from_dict(code, d) for code, d in signaux_raw.items()}

        cls._verifier_coherence(missions, signaux)
        return cls(missions, signaux)

    @staticmethod
    def _verifier_coherence(
        missions: list[Mission], signaux: dict[str, Signal]
    ) -> None:
        """Garde-fou : tout code référencé dans une mission doit exister au référentiel."""
        codes_definis = set(signaux)
        inconnus: set[str] = set()
        for m in missions:
            inconnus |= set(m.codes_signaux) - codes_definis
        if inconnus:
            raise ValueError(
                f"Codes signaux référencés dans le catalogue mais absents du "
                f"référentiel : {sorted(inconnus)}"
            )

    # -- Matching ----------------------------------------------------------- #

    def match(
        self,
        signaux_actifs: Iterable[str],
        *,
        priorite_max: Optional[int] = None,
        marques: Optional[Iterable[str]] = None,
        limite: Optional[int] = None,
    ) -> list[MissionMatch]:
        """Retourne les missions déclenchées, triées par (priorité, -score, titre).

        Args:
            signaux_actifs: codes signaux calculés depuis le FEC pour ce dossier.
            priorite_max: ne garder que les missions de priorité <= à cette valeur
                (ex. 1 pour ne remonter que les propositions systématiques).
            marques: filtrer sur certaines marques (ex. {"IMMO", "PATRIMOINE"}).
            limite: nombre maximum de missions à retourner.

        Les missions sans signal FEC (codes_signaux == []) ne sont jamais déclenchées
        automatiquement — c'est le comportement voulu.
        """
        actifs = set(signaux_actifs)
        marques_set = {m.upper() for m in marques} if marques is not None else None

        resultats: list[MissionMatch] = []
        for mission in self.missions:
            if not mission.codes_signaux:
                continue  # jamais déclenchée automatiquement
            if priorite_max is not None and mission.priorite_proposition > priorite_max:
                continue
            if marques_set is not None and mission.marque not in marques_set:
                continue

            declencheurs = [c for c in mission.codes_signaux if c in actifs]
            if declencheurs:
                resultats.append(
                    MissionMatch(
                        mission=mission,
                        signaux_declencheurs=[self.signaux[c] for c in declencheurs],
                    )
                )

        resultats.sort(
            key=lambda r: (
                r.mission.priorite_proposition,  # priorité 1 d'abord
                -r.score,                          # puis le plus de signaux
                r.mission.titre,                   # tri stable
            )
        )
        return resultats[:limite] if limite is not None else resultats

    # -- Confort ------------------------------------------------------------ #

    def signaux_orphelins(self, signaux_actifs: Iterable[str]) -> list[str]:
        """Signaux actifs qui ne déclenchent aucune mission (diagnostic/couverture)."""
        actifs = set(signaux_actifs)
        couverts = {c for m in self.missions for c in m.codes_signaux}
        return sorted(actifs - couverts)


# --------------------------------------------------------------------------- #
# Intégration LangGraph
# --------------------------------------------------------------------------- #


def build_matcher_node(
    matcher: MissionMatcher,
    *,
    input_key: str = "signaux_actifs",
    output_key: str = "missions_proposees",
    priorite_max: Optional[int] = None,
    limite: Optional[int] = None,
):
    """Fabrique un nœud LangGraph à partir d'un matcher déjà chargé.

    Le nœud lit `state[input_key]` (itérable de codes signaux) et écrit
    `state[output_key]` (liste de dicts sérialisés, prêts pour le state / la génération
    du document Word).

    Exemple :
        from langgraph.graph import StateGraph

        matcher = MissionMatcher.from_files(
            "catalogue_missions_tyls.json", "referentiel_signaux_fec.json"
        )
        graph = StateGraph(MonState)
        graph.add_node("matching_missions", build_matcher_node(matcher))
        graph.add_edge("detection_signaux", "matching_missions")
    """

    def _node(state: dict) -> dict:
        signaux_actifs = state.get(input_key, []) or []
        matches = matcher.match(
            signaux_actifs, priorite_max=priorite_max, limite=limite
        )
        return {output_key: [m.to_dict() for m in matches]}

    return _node


# --------------------------------------------------------------------------- #
# Démo / test rapide
# --------------------------------------------------------------------------- #

if __name__ == "__main__":
    import sys

    base = Path(__file__).parent
    matcher = MissionMatcher.from_files(
        base.parent / "data" / "catalogue_missions_tyls.json",
        base.parent / "data" / "seuils_signaux.json",
    )

    # Dossier fictif : PME avec tension de trésorerie, retards clients et
    # trésorerie d'associé dormante.
    signaux_demo = {
        "DELAI_CLIENTS_ELEVE",
        "BALANCE_AGEE_DEGRADEE",
        "CLIENTS_DOUTEUX",
        "TRESORERIE_EXCEDENTAIRE",
        "COMPTE_COURANT_CREDITEUR_ELEVE",
        "REMUNERATION_DIRIGEANT_ELEVEE",
        "ABSENCE_PREVOYANCE_MADELIN",
    }

    print(f"Signaux actifs : {sorted(signaux_demo)}\n")
    for match in matcher.match(signaux_demo):
        codes = ", ".join(s.code for s in match.signaux_declencheurs)
        print(
            f"[P{match.mission.priorite_proposition}] "
            f"{match.mission.titre}  (score {match.score})\n"
            f"    déclencheurs : {codes}"
        )

    orphelins = matcher.signaux_orphelins(signaux_demo)
    if orphelins:
        print(f"\nSignaux sans mission associée : {orphelins}", file=sys.stderr)
