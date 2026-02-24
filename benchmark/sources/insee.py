# benchmark/sources/insee.py
import logging
import httpx
from benchmark.base import BenchmarkSource, RatiosBruts

logger = logging.getLogger(__name__)


class InseeSource(BenchmarkSource):

    def __init__(self, api_key: str = ""):
        self.api_key = api_key

    def fetch(self, code_naf: str, annee: int, tranche_ca: str) -> RatiosBruts | None:
        if not self.api_key:
            return None
        try:
            naf_2 = code_naf[:2]
            data = self._fetch_esane(naf_2, annee - 1)
            if not data:
                return None

            return RatiosBruts(
                source="INSEE Esane",
                annee_reference=annee - 1,
                libelle_secteur=data.get("libelle", f"Secteur NAF {naf_2}"),
                fiabilite=2,
                # INSEE Esane ne fournit pas tous les ratios financiers
                taux_ebe=None,
                taux_resultat_net=None,
                autonomie_financiere=None,
                couverture_dettes=None,
                ratio_liquidite_generale=None,
                delai_clients_jours=data.get("delai_clients"),
                delai_fournisseurs_jours=data.get("delai_fournisseurs"),
            )
        except Exception as exc:
            logger.warning("INSEE fetch failed for NAF %s: %s", code_naf, exc)
            return None

    def _fetch_esane(self, naf_2: str, annee: int) -> dict | None:
        url = f"https://api.insee.fr/series/BDM/V1/data/ESANE-COMPTES/{annee}-A{naf_2}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            resp = httpx.get(url, headers=headers, timeout=10.0)
            resp.raise_for_status()
            return self._parse_esane(resp.json())
        except httpx.HTTPError:
            return None

    def _parse_esane(self, data: dict) -> dict:
        result = {}
        try:
            series = data["message:StructureSpecificData"]["message:DataSet"]["Series"]
            for serie in (series if isinstance(series, list) else [series]):
                code  = serie.get("@INDICATEUR", "")
                obs   = serie.get("Obs", {})
                valeur = float(obs.get("@OBS_VALUE", 0))
                if "DELAI_CLI" in code:
                    result["delai_clients"]     = {"mediane": valeur, "q1": None, "q3": None}
                elif "DELAI_FRN" in code:
                    result["delai_fournisseurs"] = {"mediane": valeur, "q1": None, "q3": None}
        except (KeyError, TypeError, ValueError):
            pass
        return result
