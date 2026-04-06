import re
import logging

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class InfoEntreprise(BaseModel):
    siren: str
    denomination: str
    code_naf: str
    libelle_naf: str | None = None
    forme_juridique: str | None = None


API_URL = "https://recherche-entreprises.api.gouv.fr/search"


def rechercher_entreprise(siren: str) -> InfoEntreprise | None:
    """Interroge l'API Recherche d'entreprises pour un SIREN donné."""
    try:
        resp = httpx.get(API_URL, params={"q": siren}, timeout=10.0)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        r = results[0]
        return InfoEntreprise(
            siren=siren,
            denomination=r.get("nom_complet", ""),
            code_naf=r.get("activite_principale", ""),
            libelle_naf=r.get("libelle_activite_principale"),
            forme_juridique=r.get("nature_juridique"),
        )
    except Exception as exc:
        logger.warning("Recherche entreprise SIREN %s échouée : %s", siren, exc)
        return None


def extraire_siren(nom_fichier: str) -> str | None:
    """Extrait le SIREN (9 chiffres) depuis un nom de fichier FEC."""
    m = re.match(r"^(\d{9})FEC", nom_fichier)
    return m.group(1) if m else None
