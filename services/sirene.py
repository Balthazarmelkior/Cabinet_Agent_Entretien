import re
import logging

logger = logging.getLogger(__name__)


def extraire_siren(nom_fichier: str) -> str | None:
    """Extrait le SIREN (9 chiffres) depuis un nom de fichier FEC."""
    m = re.match(r"^(\d{9})FEC", nom_fichier)
    return m.group(1) if m else None
