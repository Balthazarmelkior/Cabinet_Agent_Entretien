from unittest.mock import patch, MagicMock
from services.sirene import extraire_siren, rechercher_entreprise, InfoEntreprise
import httpx


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


def test_rechercher_entreprise_success():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {
        "results": [
            {
                "nom_complet": "ABC TRANSPORT",
                "activite_principale": "49.41A",
                "libelle_activite_principale": "Transports routiers de fret interurbains",
                "nature_juridique": "5710",
            }
        ]
    }
    fake_response.raise_for_status = MagicMock()

    with patch("services.sirene.httpx.get", return_value=fake_response) as mock_get:
        result = rechercher_entreprise("443021456")

    mock_get.assert_called_once()
    assert result is not None
    assert result.siren == "443021456"
    assert result.denomination == "ABC TRANSPORT"
    assert result.code_naf == "49.41A"
    assert result.libelle_naf == "Transports routiers de fret interurbains"


def test_rechercher_entreprise_not_found():
    fake_response = MagicMock()
    fake_response.status_code = 200
    fake_response.json.return_value = {"results": []}
    fake_response.raise_for_status = MagicMock()

    with patch("services.sirene.httpx.get", return_value=fake_response):
        result = rechercher_entreprise("000000000")

    assert result is None


def test_rechercher_entreprise_api_error():
    with patch("services.sirene.httpx.get", side_effect=httpx.HTTPError("timeout")):
        result = rechercher_entreprise("443021456")

    assert result is None
