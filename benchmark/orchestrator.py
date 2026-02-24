# benchmark/orchestrator.py
from benchmark.base import RatiosBruts
from benchmark.sources.bdf import BanqueDeFranceSource
from benchmark.sources.insee import InseeSource
from benchmark.sources.llm_source import LLMSource
from models import BenchmarkSectoriel, RatioSectoriel
from analysis.ratios import Ratios

RATIO_KEYS = [
    "taux_ebe", "taux_resultat_net", "autonomie_financiere", "couverture_dettes",
    "delai_clients_jours", "delai_fournisseurs_jours", "ratio_liquidite_generale",
]

LIBELLES = {
    "taux_ebe":                "Taux d'EBE (%)",
    "taux_resultat_net":       "Taux de résultat net (%)",
    "autonomie_financiere":    "Autonomie financière (%)",
    "couverture_dettes":       "Couverture des dettes (années)",
    "delai_clients_jours":     "Délai clients (jours)",
    "delai_fournisseurs_jours":"Délai fournisseurs (jours)",
    "ratio_liquidite_generale":"Ratio de liquidité générale",
}

SENS = {
    "taux_ebe":                "plus",
    "taux_resultat_net":       "plus",
    "autonomie_financiere":    "plus",
    "ratio_liquidite_generale":"plus",
    "couverture_dettes":       "moins",
    "delai_clients_jours":     "moins",
    "delai_fournisseurs_jours":"moins",
}


def _interpretation(val: float, med: float, q1: float, q3: float, sens: str) -> str:
    if sens == "plus":
        if val >= q3:      return "favorable"
        if val >= med:     return "dans la norme"
        if val >= q1:      return "en dessous de la médiane"
        return "défavorable"
    else:
        if val <= q1:      return "favorable"
        if val <= med:     return "dans la norme"
        if val <= q3:      return "en dessous de la médiane"
        return "défavorable"


class BenchmarkOrchestrator:

    def __init__(self, bdf: BanqueDeFranceSource, insee: InseeSource, llm: LLMSource):
        self.sources = [bdf, insee, llm]  # ordre de fiabilité décroissante

    def build(
        self,
        ratios_client: Ratios,
        code_naf: str,
        secteur_activite: str,
        ca: float,
        annee: int,
    ) -> BenchmarkSectoriel:

        tranche   = self._tranche(ca)
        resultats = [s for s in (src.fetch(code_naf, annee, tranche) for src in self.sources) if s]
        merged    = self._merge(resultats)

        vals_client = {
            "taux_ebe":                ratios_client.taux_ebe,
            "taux_resultat_net":       ratios_client.taux_resultat_net,
            "autonomie_financiere":    ratios_client.autonomie_financiere,
            "couverture_dettes":       ratios_client.couverture_dettes,
            "delai_clients_jours":     ratios_client.delai_clients_jours,
            "delai_fournisseurs_jours":ratios_client.delai_fournisseurs_jours,
            "ratio_liquidite_generale":ratios_client.ratio_liquidite_generale,
        }

        ratios_sectoriels = []
        for cle, ref in merged.items():
            vc  = vals_client.get(cle)
            med = ref.get("mediane")
            q1  = ref.get("q1")
            q3  = ref.get("q3")
            src = ref.get("_source", "—")

            if vc is None:
                continue

            ecart = round((vc - med) / abs(med) * 100, 1) if med and med != 0 else None
            interp = _interpretation(vc, med, q1, q3, SENS[cle]) \
                     if all([med, q1, q3]) else "données insuffisantes"

            ratios_sectoriels.append(RatioSectoriel(
                libelle=LIBELLES[cle],
                valeur_client=vc,
                mediane_secteur=med,
                quartile_q1=q1,
                quartile_q3=q3,
                source=src,
                interpretation=interp,
                ecart_mediane_pct=ecart,
            ))

        libelle  = resultats[0].libelle_secteur if resultats else secteur_activite
        annee_ref= resultats[0].annee_reference if resultats else annee - 1

        return BenchmarkSectoriel(
            code_naf=code_naf,
            libelle_secteur=libelle,
            annee_reference=annee_ref,
            taille_entreprise=tranche,
            ratios=ratios_sectoriels,
            commentaire_global=self._commentaire(ratios_sectoriels, libelle),
        )

    def _merge(self, resultats: list[RatiosBruts]) -> dict:
        merged = {}
        for data in sorted(resultats, key=lambda d: d.fiabilite, reverse=True):
            for cle in RATIO_KEYS:
                val = getattr(data, cle, None)
                if val is not None:
                    merged[cle] = {**val, "_source": data.source}
        return merged

    def _tranche(self, ca: float) -> str:
        if ca < 2_000_000:  return "TPE"
        if ca < 50_000_000: return "PME"
        return "ETI"

    def _commentaire(self, ratios: list[RatioSectoriel], secteur: str) -> str:
        fav = [r.libelle for r in ratios if r.interpretation == "favorable"]
        def_ = [r.libelle for r in ratios if r.interpretation == "défavorable"]
        parties = []
        if fav:
            parties.append(f"Points forts vs secteur ({secteur}) : {', '.join(fav)}.")
        if def_:
            parties.append(f"Points de vigilance vs secteur : {', '.join(def_)}.")
        if not parties:
            parties.append(f"Positionnement globalement dans la norme du secteur {secteur}.")
        return " ".join(parties)
