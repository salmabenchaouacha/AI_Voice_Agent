"""Toutes les commandes vocales. Pour en ajouter une : @skill(regex) + une fonction qui retourne un texte."""
import random
import re
import threading
import webbrowser
from datetime import datetime
from urllib.parse import quote_plus

import requests

import notifier
import system
from config import DEFAULT_CITY, NOTES_FILE
from router import QuitAssistant, skill

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
NUMS = {"un": 1, "une": 1, "deux": 2, "trois": 3, "quatre": 4, "cinq": 5, "six": 6, "sept": 7,
        "huit": 8, "neuf": 9, "dix": 10, "quinze": 15, "vingt": 20, "trente": 30, "quarante": 40,
        "cinquante": 50, "soixante": 60}
BLAGUES = [
    "Pourquoi les développeurs confondent Halloween et Noël ? Parce que 31 octobre égale 25 décembre.",
    "Un SQL entre dans un bar, s'approche de deux tables et demande : je peux vous joindre ?",
    "Il y a 10 types de personnes : celles qui comprennent le binaire et les autres.",
]


def _to_int(s: str):
    return int(s) if s.isdigit() else NUMS.get(s)


@skill(r"\b(au revoir|arrête[- ]toi|quitte|éteins[- ]toi|goodbye|exit)\b")
def quit_(m):
    raise QuitAssistant("À bientôt !")


@skill(r"(?:minuteur|timer|compte à rebours).*?(\w+)\s*(seconde|minute|heure)")
def timer(m):
    n = _to_int(m.group(1))
    if not n:
        return "Je n'ai pas compris la durée."
    unit = m.group(2)
    secs = n * {"seconde": 1, "minute": 60, "heure": 3600}[unit]
    t = threading.Timer(secs, lambda: notifier.push("Ton minuteur est terminé !"))
    t.daemon = True
    t.start()
    return f"Minuteur de {n} {unit}{'s' if n > 1 else ''} lancé."


@skill(r"(?:monte|augmente|plus fort).*(?:volume|son)|volume (?:plus fort|up)")
def vol_up(m):
    system.volume(+1)
    return "Volume augmenté."


@skill(r"(?:baisse|diminue).*(?:volume|son)|volume (?:moins fort|down)")
def vol_down(m):
    system.volume(-1)
    return "Volume baissé."


@skill(r"\b(?:coupe|mute|muet|rétablis)\b.*(?:son|volume)?")
def mute(m):
    system.volume(0)
    return "C'est fait."


@skill(r"capture d'écran|screenshot")
def shot(m):
    return f"Capture enregistrée : {system.screenshot()}"


@skill(r"verrouille|lock (?:the )?screen")
def lock(m):
    system.lock_screen()
    return "Écran verrouillé."


@skill(r"météo(?:\s+(?:à|a|de|pour|en))?\s*(.*)", r"quel temps (?:fait-il|il fait)(?:\s+(?:à|a|de|en))?\s*(.*)",
       r"weather(?:\s+in)?\s*(.*)")
def weather(m):
    city = (m.group(1) or "").strip() or DEFAULT_CITY
    try:
        g = requests.get("https://geocoding-api.open-meteo.com/v1/search",
                         params={"name": city, "count": 1, "language": "fr"}, timeout=8).json()
        if not g.get("results"):
            return f"Je ne trouve pas la ville {city}."
        r = g["results"][0]
        w = requests.get("https://api.open-meteo.com/v1/forecast",
                         params={"latitude": r["latitude"], "longitude": r["longitude"],
                                 "current": "temperature_2m,wind_speed_10m"}, timeout=8).json()["current"]
        return (f"À {r['name']}, il fait {round(w['temperature_2m'])} degrés "
                f"avec un vent de {round(w['wind_speed_10m'])} kilomètres par heure.")
    except requests.RequestException:
        return "Impossible de récupérer la météo, vérifie ta connexion."


@skill(r"\b(?:prends? (?:une )?note|note[- ]moi|take a note)\b\s*(?:que|:)?\s*(.+)")
def note(m):
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {m.group(1)}\n")
    return "Note enregistrée."


@skill(r"(?:joue|mets|play|cherche|recherche)\s+(.+?)\s+sur youtube", r"(?:joue|mets|play)\s+(.+)")
def youtube(m):
    webbrowser.open(f"https://www.youtube.com/results?search_query={quote_plus(m.group(1))}")
    return f"Je cherche {m.group(1)} sur YouTube."


@skill(r"(?:ouvre|ouvrir|lance|démarre|open)\s+(.+)")
def open_app(m):
    return system.open_target(m.group(1))


@skill(r"(?:cherche|recherche|search|google)\s+(.+)")
def search(m):
    q = re.sub(r"\s+sur google$", "", m.group(1))
    webbrowser.open(f"https://www.google.com/search?q={quote_plus(q)}")
    return f"Voici les résultats pour {q}."


@skill(r"quelle heure|l'heure|what time")
def time_(m):
    return datetime.now().strftime("Il est %H heures %M.")


@skill(r"quel jour|quelle date|la date|what day")
def date_(m):
    d = datetime.now()
    return f"Nous sommes le {JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}."


@skill(r"batterie|battery")
def battery(m):
    import psutil
    b = psutil.sensors_battery()
    if not b:
        return "Je ne détecte pas de batterie."
    return f"La batterie est à {round(b.percent)} pourcent{', en charge' if b.power_plugged else ''}."


@skill(r"blague|joke|fais[- ]moi rire")
def joke(m):
    return random.choice(BLAGUES)


@skill(r"\baide\b|\bhelp\b|que peux[- ]tu faire")
def help_(m):
    return ("Je peux donner l'heure et la date, la météo, ouvrir une application ou un site, "
            "chercher sur Google ou YouTube, régler le volume, lancer un minuteur, prendre une note, "
            "faire une capture d'écran, verrouiller l'écran, ou te raconter une blague.")