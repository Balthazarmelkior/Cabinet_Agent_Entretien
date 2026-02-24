# benchmark/sources/bdf.py
import json
import logging
import httpx
from pathlib import Path
from benchmark.base import BenchmarkSource, RatiosBruts

logger = logging.getLogger(__name__)


class BanqueDeFranceSource(BenchmarkSource):

    def __init__(self, cache_dir: str = "data/bdf_cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch(self, code_naf: str, annee: int, tranche_ca: str) -> RatiosBruts | None:
        naf = code_naf.replace(".", "").upper()

        cached = self._load_cache(naf, annee, tranche_ca)
        if cached:
            return cached

        try:
            data = self._call_api(naf, annee - 1, tranche_ca)
            if data:
                self._save_cache(data, naf, annee, tranche_ca)
            return data
        except Exception as exc:
            logger.warning("BdF API call failed for NAF %s: %s", naf, exc)
            return None

    def _call_api(self, naf: str, annee: int, tranche_ca: str) -> RatiosBruts | None:
        """
        API Webstat BdF — endpoint ratios sectoriels.
        Doc : https://www.banque-france.fr/statistiques/telecharger-les-series-temporelles
        """
        url = "https://www.banque-france.fr/webstat-backend/api/v1/data/RATIO_ENT"
        params = {
            "startPeriod": str(annee),
            "endPeriod":   str(annee),
            "dimensionAtObservation": "AllDimensions",
        }
        resp = httpx.get(url, params=params, headers={"Accept": "application/json"}, timeout=15.0)
        resp.raise_for_status()
        return self._parse(resp.json(), naf, tranche_ca, annee)

    def _parse(self, data: dict, naf: str, tranche: str, annee: int) -> RatiosBruts | None:
        """Parse format SDMX-JSON BdF — extrait médiane/Q1/Q3 par indicateur."""
        INDICATEURS = {
            "taux_ebe":                "B12",
            "taux_resultat_net":       "B22",
            "autonomie_financiere":    "B31",
            "couverture_dettes":       "B41",
            "delai_clients_jours":     "B51",
            "delai_fournisseurs_jours":"B52",
            "ratio_liquidite_generale":"B61",
        }
        try:
            series = data["data"]["dataSets"][0]["series"]
        except (KeyError, IndexError):
            return None

        ratios = {}
        for key, code in INDICATEURS.items():
            for _, serie in series.items():
                meta = str(serie.get("attributes", []))
                if naf in meta and tranche in meta and code in meta:
                    obs_vals = [v[0] for v in serie.get("observations", {}).values()
                                if v and v[0] is not None]
                    if len(obs_vals) >= 3:
                        s = sorted(obs_vals)
                        n = len(s)
                        ratios[key] = {"mediane": s[n//2], "q1": s[n//4], "q3": s[3*n//4]}
                    break

        if not ratios:
            return None

        return RatiosBruts(
            source="Banque de France",
            annee_reference=annee,
            libelle_secteur=f"Secteur NAF {naf}",
            fiabilite=1,
            **{k: ratios.get(k) for k in INDICATEURS.keys()},
        )

    def _cache_path(self, naf, annee, tranche) -> Path:
        return self.cache_dir / f"bdf_{naf}_{annee}_{tranche}.json"

    def _load_cache(self, naf, annee, tranche) -> RatiosBruts | None:
        p = self._cache_path(naf, annee, tranche)
        if p.exists():
            from dataclasses import fields
            d = json.loads(p.read_text())
            return RatiosBruts(**d)
        return None

    def _save_cache(self, data: RatiosBruts, naf, annee, tranche):
        from dataclasses import asdict
        self._cache_path(naf, annee, tranche).write_text(
            json.dumps(asdict(data), ensure_ascii=False)
        )
