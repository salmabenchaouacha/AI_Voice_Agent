"""Mode hors-ligne : des regex reconnaissent la commande et extraient ses arguments.

La logique elle-même est dans actions.py, partagée avec l'agent. Ce fichier sert quand aucun LLM
n'est configuré (ou injoignable). Pour ajouter une commande : @skill(regex) + une fonction qui retourne un texte."""
import random
import re
import threading  # noqa: F401  (les tests remplacent skills.threading.Timer)
import webbrowser  # noqa: F401  (les tests remplacent skills.webbrowser.open)

import requests  # noqa: F401  (les tests remplacent skills.requests.get)

import actions
import system
from config import DEFAULT_CITY, NOTES_FILE  # noqa: F401
from router import QuitAssistant, skill

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
    return actions.start_timer(n * {"seconde": 1, "minute": 60, "heure": 3600}[m.group(2)])


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
    return actions.weather(m.group(1) or "")


@skill(r"\b(?:prends? (?:une )?note|note[- ]moi|take a note)\b\s*(?:que|:)?\s*(.+)")
def note(m):
    return actions.add_note(m.group(1), path=NOTES_FILE)


@skill(r"(?:joue|mets|play|cherche|recherche)\s+(.+?)\s+sur youtube", r"(?:joue|mets|play)\s+(.+)")
def youtube(m):
    return actions.play_youtube(m.group(1))


@skill(r"(?:ouvre|ouvrir|lance|démarre|open)\s+(.+)")
def open_app(m):
    return system.open_target(m.group(1))


@skill(r"(?:cherche|recherche|search|google)\s+(.+)")
def search(m):
    return actions.open_google(re.sub(r"\s+sur google$", "", m.group(1)))


@skill(r"quelle heure|l'heure|what time")
def time_(m):
    return actions.now_time()


@skill(r"quel jour|quelle date|la date|what day")
def date_(m):
    return actions.today_date()


@skill(r"batterie|battery")
def battery(m):
    return actions.battery()


@skill(r"blague|joke|fais[- ]moi rire")
def joke(m):
    return random.choice(BLAGUES)


@skill(r"\baide\b|\bhelp\b|que peux[- ]tu faire")
def help_(m):
    return ("Je peux donner l'heure et la date, la météo, ouvrir une application ou un site, "
            "chercher sur Google ou YouTube, régler le volume, lancer un minuteur, prendre une note, "
            "faire une capture d'écran, verrouiller l'écran, ou te raconter une blague.")
