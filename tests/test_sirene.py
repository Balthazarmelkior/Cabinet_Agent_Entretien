from services.sirene import extraire_siren


def test_extraire_siren_fec_standard():
    assert extraire_siren("443021456FEC20240831.txt") == "443021456"


def test_extraire_siren_fec_sans_date():
    assert extraire_siren("443021456FEC.txt") == "443021456"


def test_extraire_siren_pdf():
    assert extraire_siren("bilan_2024.pdf") is None


def test_extraire_siren_nom_vide():
    assert extraire_siren("") is None


def test_extraire_siren_chiffres_insuffisants():
    assert extraire_siren("12345FEC20240831.txt") is None
