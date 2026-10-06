"""Ce que l'assistant sait faire, en fonctions simples : des arguments typés, un texte à dire en retour.

Ces fonctions ne savent pas qui les appelle. Elles servent à la fois :
  - au mode hors-ligne (skills.py : une regex extrait les arguments) ;
  - à l'agent (serveurs MCP et outils locaux : c'est le modèle qui choisit les arguments).
"""
import ipaddress
import os
import re
import socket
import threading
import time
import webbrowser
from datetime import datetime
from html.parser import HTMLParser
from urllib.parse import quote_plus, urljoin, urlparse

import requests

import config
import notifier

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]

# Codes météo WMO renvoyés par open-meteo, regroupés en quelques mots faciles à dire
_CIEL = [
    ((0,), "ciel dégagé"), ((1, 2), "quelques nuages"), ((3,), "ciel couvert"),
    ((45, 48), "du brouillard"), ((51, 53, 55, 56, 57), "de la bruine"),
    ((61, 63, 65, 66, 67, 80, 81, 82), "de la pluie"), ((71, 73, 75, 77, 85, 86), "de la neige"),
    ((95, 96, 99), "de l'orage"),
]


# ---------- Heure et date ----------
def now_time() -> str:
    return datetime.now().strftime("Il est %H heures %M.")


def today_date() -> str:
    d = datetime.now()
    return f"Nous sommes le {JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}."


# ---------- Météo ----------
def weather(city: str = "") -> str:
    city = (city or "").strip() or config.DEFAULT_CITY
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "fr"}, timeout=8).json()
        if not g.get("results"):
            return f"Je ne trouve pas la ville {city}."
        r = g["results"][0]
        w = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": r["latitude"], "longitude": r["longitude"],
                                 "current": "temperature_2m,wind_speed_10m,weather_code"}, timeout=8).json()["current"]
    except requests.RequestException:
        return "Impossible de récupérer la météo, vérifie ta connexion."
    ciel = next((mot for codes, mot in _CIEL if w.get("weather_code") in codes), "")
    return (f"À {r['name']}, il fait {round(w['temperature_2m'])} degrés{', ' + ciel + ',' if ciel else ''} "
            f"avec un vent de {round(w['wind_speed_10m'])} kilomètres par heure.")


# ---------- Notes ----------
def add_note(text: str, path: str | None = None) -> str:
    text = (text or "").strip()
    if not text:
        return "La note est vide, je n'ai rien enregistré."
    with open(path or config.NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {text}\n")
    return "Note enregistrée."


def read_notes(limit: int = 5, path: str | None = None) -> str:
    try:
        with open(path or config.NOTES_FILE, encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        lines = []
    if not lines:
        return "Tu n'as aucune note."
    last = lines[-max(1, limit):]
    return f"{len(lines)} note{'s' if len(lines) > 1 else ''} au total. Les dernières : " + " ; ".join(last)


def clear_notes(path: str | None = None) -> str:
    try:
        os.remove(path or config.NOTES_FILE)
    except FileNotFoundError:
        return "Il n'y avait aucune note à effacer."
    return "Toutes les notes sont effacées."


# ---------- Minuteurs ----------
# Ils vivent dans le processus du serveur web : c'est lui qui tient la connexion au navigateur (notifier.push).
_timers: dict[int, dict] = {}
_timers_lock = threading.Lock()
_timer_seq = 0


def spoken_duration(seconds: int) -> str:
    """300 -> « 5 minutes », 5400 -> « 1 heure 30 minutes »."""
    parts = []
    for size, name in ((3600, "heure"), (60, "minute"), (1, "seconde")):
        n, seconds = divmod(seconds, size)
        if n:
            parts.append(f"{n} {name}{'s' if n > 1 else ''}")
    return " ".join(parts) or "0 seconde"


def start_timer(seconds: int, label: str = "") -> str:
    global _timer_seq
    seconds = int(seconds)
    if not 1 <= seconds <= 24 * 3600:
        return "Je ne peux lancer un minuteur que pour une durée entre une seconde et vingt-quatre heures."
    label = (label or "").strip()
    with _timers_lock:
        _timer_seq += 1
        tid = _timer_seq

    def done():
        with _timers_lock:
            _timers.pop(tid, None)
        notifier.push(f"Ton minuteur « {label} » est terminé !" if label else "Ton minuteur est terminé !")

    t = threading.Timer(seconds, done)
    t.daemon = True
    with _timers_lock:
        _timers[tid] = {"timer": t, "label": label, "end": time.time() + seconds}
    t.start()
    return f"Minuteur de {spoken_duration(seconds)} lancé."


def list_timers() -> str:
    with _timers_lock:
        items = sorted(_timers.values(), key=lambda x: x["end"])
    if not items:
        return "Aucun minuteur en cours."
    now = time.time()
    return "Minuteurs en cours : " + " ; ".join(
        f"{x['label'] or 'sans nom'}, reste {spoken_duration(max(1, round(x['end'] - now)))}" for x in items)


def cancel_timers() -> str:
    with _timers_lock:
        items = list(_timers.values())
        _timers.clear()
    for x in items:
        x["timer"].cancel()
    if not items:
        return "Aucun minuteur à annuler."
    return f"{len(items)} minuteur{'s' if len(items) > 1 else ''} annulé{'s' if len(items) > 1 else ''}."


# ---------- Système ----------
def battery() -> str:
    import psutil
    b = psutil.sensors_battery()
    if not b:
        return "Je ne détecte pas de batterie."
    return f"La batterie est à {round(b.percent)} pourcent{', en charge' if b.power_plugged else ''}."


# ---------- Navigateur ----------
def play_youtube(query: str) -> str:
    webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(query)}")
    return f"Je cherche {query} sur YouTube."


def open_google(query: str) -> str:
    webbrowser.open(f"https://www.google.com/search?q={quote_plus(query)}")
    return f"Voici les résultats pour {query}."


def open_url(url: str) -> str:
    url = (url or "").strip()
    if urlparse(url).scheme not in ("http", "https"):
        return "Je n'ouvre que des adresses qui commencent par http ou https."
    webbrowser.open(url)
    return f"J'ouvre {urlparse(url).netloc}."


# ---------- Recherche web : l'agent LIT les résultats (au lieu d'ouvrir un onglet) ----------
def _search_backend(query: str, max_results: int) -> list[dict]:
    """Renvoie [{title, href, body}, …]. Isolé ici pour pouvoir changer de moteur ou le simuler dans les tests."""
    from ddgs import DDGS
    return list(DDGS().text(query, region="fr-fr", max_results=max_results))


def web_search(query: str, max_results: int = 4) -> str:
    query = (query or "").strip()
    if not query:
        return "Il me faut des mots à chercher."
    try:
        results = _search_backend(query, max(1, min(int(max_results), 8)))
    except ImportError:
        return "La recherche web n'est pas installée. Lance : pip install ddgs"
    except Exception as e:  # moteur indisponible, quota, réseau…
        return f"La recherche web a échoué ({type(e).__name__}). Réessaie dans un instant."
    if not results:
        return f"Aucun résultat pour {query}."
    return "\n".join(
        f"{i}. {r.get('title', '').strip()} : {r.get('body', '').strip()} (source : {r.get('href', '')})"
        for i, r in enumerate(results, 1))


class _TextOnly(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form", "aside"}

    def __init__(self):
        super().__init__()
        self.parts, self._skip = [], 0

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip and data.strip():
            self.parts.append(data.strip())


def html_to_text(html: str) -> str:
    parser = _TextOnly()
    parser.feed(html)
    return re.sub(r"\s+", " ", " ".join(parser.parts)).strip()


def is_public_url(url: str) -> bool:
    """Vrai si l'adresse est en http(s) et pointe vers Internet, pas vers cette machine ni le réseau local.

    Sans ce contrôle, une page web piégée pourrait faire lire à l'agent http://127.0.0.1:8000 ou la box du réseau."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, parsed.port or 80, proto=socket.IPPROTO_TCP)
        return bool(infos) and all(ipaddress.ip_address(info[4][0].split("%")[0]).is_global for info in infos)
    except (socket.gaierror, UnicodeError, ValueError):
        return False


def read_page(url: str, max_chars: int = 3000) -> str:
    url = (url or "").strip()
    try:
        for _ in range(4):                                   # redirections suivies à la main pour re-vérifier chaque saut
            if not is_public_url(url):
                return "Je ne peux lire que des pages web publiques."
            r = requests.get(url, timeout=8, allow_redirects=False, stream=True,
                             headers={"User-Agent": "Mozilla/5.0 (assistant-vocal)"})
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                url = urljoin(url, r.headers["location"])
                continue
            break
        else:
            return "Cette page redirige trop de fois."
        if r.status_code != 200:
            return f"La page a répondu avec le code {r.status_code}."
        ctype = r.headers.get("content-type", "text/html").lower()
        if "html" not in ctype and not ctype.startswith("text/"):
            return "Ce lien ne mène pas à une page de texte."
        raw = b""
        for chunk in r.iter_content(65536):                  # on ne télécharge pas plus de 600 Ko
            raw += chunk
            if len(raw) >= 600_000:
                break
        r.close()
        text = html_to_text(raw.decode(r.encoding or "utf-8", errors="replace"))
    except requests.RequestException:
        return "Impossible de lire cette page, vérifie l'adresse ou ta connexion."
    if not text:
        return "Je n'ai trouvé aucun texte lisible sur cette page."
    return text[:max_chars] + ("…" if len(text) > max_chars else "")
