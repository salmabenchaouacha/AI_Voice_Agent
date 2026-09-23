import pytest
import requests

import skills
from router import dispatch


class Reponse:
    def __init__(self, data):
        self.data = data

    def json(self):
        return self.data


@pytest.fixture
def api_meteo(monkeypatch):
    appels = []

    def faux_get(url, params=None, timeout=None):
        appels.append((url, params))
        if "geocoding" in url:
            if params["name"] == "inconnue":
                return Reponse({})
            return Reponse({"results": [{"name": params["name"].capitalize(), "latitude": 35.8, "longitude": 10.6}]})
        return Reponse({"current": {"temperature_2m": 27.4, "wind_speed_10m": 12.2}})

    monkeypatch.setattr(skills.requests, "get", faux_get)
    return appels


def test_meteo_ville_dite(api_meteo):
    assert dispatch("quel temps fait-il à Sousse") == "À Sousse, il fait 27 degrés avec un vent de 12 kilomètres par heure."


def test_meteo_ville_par_defaut(api_meteo):
    dispatch("météo")
    assert api_meteo[0][1]["name"] == skills.DEFAULT_CITY


def test_meteo_ville_inconnue(api_meteo):
    assert dispatch("météo à inconnue") == "Je ne trouve pas la ville inconnue."


def test_meteo_sans_reseau(monkeypatch):
    def panne(*a, **k):
        raise requests.ConnectionError()
    monkeypatch.setattr(skills.requests, "get", panne)
    assert "connexion" in dispatch("météo à tunis")


@pytest.fixture
def navigateur(monkeypatch):
    ouverts = []
    monkeypatch.setattr(skills.webbrowser, "open", ouverts.append)
    return ouverts


def test_youtube(navigateur):
    assert dispatch("mets du jazz sur youtube") == "Je cherche du jazz sur YouTube."
    assert dispatch("joue du rock") == "Je cherche du rock sur YouTube."
    assert navigateur == [
        "https://www.youtube.com/results?search_query=du+jazz",
        "https://www.youtube.com/results?search_query=du+rock",
    ]


def test_recherche_google(navigateur):
    assert dispatch("cherche python fastapi sur google") == "Voici les résultats pour python fastapi."
    assert navigateur == ["https://www.google.com/search?q=python+fastapi"]