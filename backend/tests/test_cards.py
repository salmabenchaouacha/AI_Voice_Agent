"""Lot 2 : cartes visuelles (météo et prévisions, sources d'une recherche, carte d'un lieu, capture)."""
import asyncio

import requests

import actions
import cards
from agent.toolbox import Toolbox, ToolSpec


class R:
    def __init__(self, d): self.d = d
    def json(self): return self.d


GEO = {"results": [{"name": "Sousse", "latitude": 35.83, "longitude": 10.64, "admin1": "Sousse", "country": "Tunisie"}]}
METEO = {
    "current": {"temperature_2m": 27.4, "wind_speed_10m": 12.2, "weather_code": 2},
    "daily": {"time": ["2026-11-19", "2026-11-20", "2026-11-21"], "weather_code": [2, 61, 0],
              "temperature_2m_max": [24.6, 21.2, 23.0], "temperature_2m_min": [15.1, 14.4, 13.8]},
}


def faux_get(url, params=None, timeout=None):
    return R(GEO if "geocoding" in url else METEO)


# ---------- le marqueur ----------
def test_carte_accrochee_puis_detachee():
    texte = cards.attach("Il fait beau.", {"kind": "weather", "city": "Sousse"})
    assert texte.startswith("Il fait beau.") and cards.MARK in texte
    assert cards.split(texte) == ("Il fait beau.", {"kind": "weather", "city": "Sousse"})
    assert cards.split("Sans carte.") == ("Sans carte.", None)
    assert cards.attach("Rien.", None) == "Rien."
    assert cards.split("Cassé." + cards.MARK + "{pas du json") == ("Cassé.", None)


def test_la_boite_a_outils_cache_la_carte_au_modele():
    box = Toolbox()
    box.register(ToolSpec(name="meteo", description="", schema={}), lambda a: cards.attach("27 degrés.", {"kind": "weather"}))
    r = asyncio.run(box.call("meteo", {}))
    assert r.text == "27 degrés." and r.card == {"kind": "weather"}


# ---------- météo ----------
def test_meteo_avec_previsions(monkeypatch):
    monkeypatch.setattr(requests, "get", faux_get)
    texte, carte = actions.weather_report("sousse")
    assert texte == "À Sousse, il fait 27 degrés, quelques nuages, avec un vent de 12 kilomètres par heure."
    assert carte["kind"] == "weather" and carte["temp"] == 27 and carte["country"] == "Tunisie"
    assert carte["days"][1] == {"date": "2026-11-20", "code": 61, "sky": "de la pluie", "max": 21, "min": 14}
    prev = actions.forecast_text(carte)
    assert prev == " Prévisions : demain, de 14 à 21 degrés, de la pluie ; samedi, de 14 à 23 degrés, ciel dégagé."
    assert actions.weather("sousse") == texte                     # le mode hors-ligne dit toujours la même phrase


def test_meteo_ville_inconnue_ou_reseau_coupe(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda url, **o: R({}))
    assert actions.weather_report("zzz") == ("Je ne trouve pas la ville zzz.", None)

    def coupe(url, **o):
        raise requests.ConnectionError()
    monkeypatch.setattr(requests, "get", coupe)
    assert actions.weather_report("Sousse")[1] is None


# ---------- carte d'un lieu ----------
def test_carte_d_un_lieu(monkeypatch):
    monkeypatch.setattr(requests, "get", faux_get)
    texte, carte = actions.locate_report("Sousse")
    assert texte.startswith("Lieu trouvé : Sousse, Tunisie.")       # la région du même nom n'est pas répétée
    assert carte == {"kind": "map", "name": "Sousse", "place": "Tunisie", "lat": 35.83, "lon": 10.64}
    assert actions.locate_report("  ") == ("Quel lieu veux-tu voir sur la carte ?", None)


# ---------- sources ----------
def test_sources_de_la_recherche(monkeypatch):
    monkeypatch.setattr(actions, "_search_backend", lambda q, n: [
        {"title": "LangGraph", "body": "Bibliothèque d'agents.", "href": "https://www.langchain.com/langgraph"},
        {"title": "Piège", "body": "x", "href": "javascript:alert(1)"},
    ])
    texte, carte = actions.web_search_report("langgraph")
    assert "LangGraph" in texte
    assert carte == {"kind": "sources", "query": "langgraph", "items": [
        {"title": "LangGraph", "url": "https://www.langchain.com/langgraph", "site": "langchain.com",
         "snippet": "Bibliothèque d'agents."}]}                    # un lien non http n'est jamais affiché


def test_recherche_reessayee_une_fois(monkeypatch):
    monkeypatch.setattr(actions, "SEARCH_RETRY_DELAY", 0)
    essais = []

    def capricieux(q, n):
        essais.append(q)
        if len(essais) == 1:
            raise RuntimeError("ratelimit")
        return [{"title": "T", "body": "B", "href": "https://exemple.tn"}]
    monkeypatch.setattr(actions, "_search_backend", capricieux)
    assert actions.web_search("x") == "1. T : B (source : https://exemple.tn)" and len(essais) == 2
