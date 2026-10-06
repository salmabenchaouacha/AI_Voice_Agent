"""Les nouvelles capacités d'actions.py : notes relues et effacées, minuteurs nommés, recherche web lue, lecture de page."""
import requests

import actions
import notifier


# ---------- notes ----------
def test_notes_relire_et_effacer(tmp_path):
    fichier = str(tmp_path / "notes.txt")
    assert actions.read_notes(path=fichier) == "Tu n'as aucune note."
    for texte in ("un", "deux", "trois"):
        actions.add_note(texte, path=fichier)
    relu = actions.read_notes(limit=2, path=fichier)
    assert relu.startswith("3 notes au total") and "deux" in relu and "trois" in relu and "] un" not in relu
    assert actions.clear_notes(path=fichier) == "Toutes les notes sont effacées."
    assert actions.clear_notes(path=fichier) == "Il n'y avait aucune note à effacer."
    assert actions.add_note("   ", path=fichier) == "La note est vide, je n'ai rien enregistré."


# ---------- minuteurs ----------
class FauxTimer:
    crees = []

    def __init__(self, secondes, fonction):
        self.secondes, self.fonction, self.daemon, self.annule = secondes, fonction, False, False
        FauxTimer.crees.append(self)

    def start(self):
        pass

    def cancel(self):
        self.annule = True


def test_duree_dite_naturellement():
    assert actions.spoken_duration(300) == "5 minutes"
    assert actions.spoken_duration(1) == "1 seconde"
    assert actions.spoken_duration(5400) == "1 heure 30 minutes"


def test_minuteur_nomme_liste_et_annulation(monkeypatch):
    FauxTimer.crees = []
    annonces = []
    monkeypatch.setattr(actions.threading, "Timer", FauxTimer)
    monkeypatch.setattr(notifier, "push", annonces.append)
    actions.cancel_timers()

    assert actions.start_timer(600, "pâtes") == "Minuteur de 10 minutes lancé."
    assert actions.start_timer(60) == "Minuteur de 1 minute lancé."
    assert "pâtes" in actions.list_timers() and "sans nom" in actions.list_timers()

    FauxTimer.crees[0].fonction()                       # le premier minuteur sonne
    assert annonces == ["Ton minuteur « pâtes » est terminé !"]
    assert "pâtes" not in actions.list_timers()

    assert actions.cancel_timers() == "1 minuteur annulé."
    assert FauxTimer.crees[1].annule and actions.list_timers() == "Aucun minuteur en cours."


def test_minuteur_duree_refusee():
    assert "entre une seconde" in actions.start_timer(0)
    assert "entre une seconde" in actions.start_timer(10 ** 7)


# ---------- recherche web ----------
def test_recherche_web_retourne_des_extraits(monkeypatch):
    demandes = []

    def moteur(requete, n):
        demandes.append((requete, n))
        return [{"title": "LangGraph", "body": "Bibliothèque d'agents.", "href": "https://exemple.tn/lg"}]

    monkeypatch.setattr(actions, "_search_backend", moteur)
    assert actions.web_search("langgraph", 3) == "1. LangGraph : Bibliothèque d'agents. (source : https://exemple.tn/lg)"
    assert demandes == [("langgraph", 3)]


def test_recherche_web_sans_resultat_ou_en_panne(monkeypatch):
    monkeypatch.setattr(actions, "_search_backend", lambda q, n: [])
    assert actions.web_search("zzz") == "Aucun résultat pour zzz."

    def panne(q, n):
        raise RuntimeError("quota")
    monkeypatch.setattr(actions, "_search_backend", panne)
    assert "a échoué" in actions.web_search("zzz")
    assert actions.web_search("  ") == "Il me faut des mots à chercher."


# ---------- lecture de page ----------
def test_html_vers_texte_ignore_scripts_et_menus():
    html = "<html><head><style>p{}</style><script>alert(1)</script></head><body><nav>Menu</nav><p>Bonjour  <b>Salma</b></p></body></html>"
    assert actions.html_to_text(html) == "Bonjour Salma"


def test_adresses_locales_refusees():
    for url in ("http://127.0.0.1:8000/api/config", "http://localhost/", "http://192.168.1.1/", "http://10.0.0.5/x",
                "http://[::1]/", "file:///etc/passwd", "ftp://exemple.tn/", "pas une adresse"):
        assert actions.is_public_url(url) is False, url
    assert actions.read_page("http://127.0.0.1:8000/api/config") == "Je ne peux lire que des pages web publiques."


class Page:
    def __init__(self, status=200, html="", headers=None, encoding="utf-8"):
        self.status_code, self._html, self.encoding = status, html, encoding
        self.headers = {"content-type": "text/html; charset=utf-8", **(headers or {})}

    def iter_content(self, taille):
        yield self._html.encode("utf-8")

    def close(self):
        pass


def test_lecture_de_page_et_redirection_vers_une_adresse_locale(monkeypatch):
    monkeypatch.setattr(actions, "is_public_url", lambda url: "127.0.0.1" not in url)
    pages = {
        "https://exemple.tn/a": Page(html="<p>" + "mot " * 2000 + "</p>"),
        "https://exemple.tn/vers-local": Page(status=302, headers={"location": "http://127.0.0.1:8000/"}),
        "https://exemple.tn/pdf": Page(headers={"content-type": "application/pdf"}),
        "https://exemple.tn/404": Page(status=404),
    }
    monkeypatch.setattr(requests, "get", lambda url, **options: pages[url])

    texte = actions.read_page("https://exemple.tn/a", max_chars=100)
    assert texte.startswith("mot mot") and len(texte) == 101 and texte.endswith("…")
    assert actions.read_page("https://exemple.tn/vers-local") == "Je ne peux lire que des pages web publiques."
    assert actions.read_page("https://exemple.tn/pdf") == "Ce lien ne mène pas à une page de texte."
    assert "404" in actions.read_page("https://exemple.tn/404")


def test_ouverture_de_lien_http_seulement(monkeypatch):
    ouverts = []
    monkeypatch.setattr(actions.webbrowser, "open", ouverts.append)
    assert actions.open_url("https://github.com/x") == "J'ouvre github.com."
    assert "http" in actions.open_url("file:///etc/passwd") and ouverts == ["https://github.com/x"]


def test_meteo_avec_etat_du_ciel(monkeypatch):
    class R:
        def __init__(self, d): self.d = d
        def json(self): return self.d

    def faux_get(url, params=None, timeout=None):
        if "geocoding" in url:
            return R({"results": [{"name": "Sousse", "latitude": 35.8, "longitude": 10.6}]})
        return R({"current": {"temperature_2m": 27.4, "wind_speed_10m": 12.2, "weather_code": 0}})

    monkeypatch.setattr(requests, "get", faux_get)
    assert actions.weather("sousse") == "À Sousse, il fait 27 degrés, ciel dégagé, avec un vent de 12 kilomètres par heure."
