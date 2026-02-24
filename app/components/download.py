# app/components/download.py
import io
from models import FicheEntretien
from output.word_generator import generate_word_doc


def get_word_bytes(fiche: FicheEntretien) -> bytes:
    buf = io.BytesIO()
    generate_word_doc(fiche, buf)
    buf.seek(0)
    return buf.read()
