"""Toutes les commandes vocales. Pour en ajouter une : @skill(regex) + une fonction qui retourne un texte."""
import random
from datetime import datetime

from config import NOTES_FILE
from router import QuitAssistant, skill

JOURS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]
BLAGUES = [
    "Pourquoi les développeurs confondent Halloween et Noël ? Parce que 31 octobre égale 25 décembre.",
    "Un SQL entre dans un bar, s'approche de deux tables et demande : je peux vous joindre ?",
    "Il y a 10 types de personnes : celles qui comprennent le binaire et les autres.",
]


@skill(r"\b(au revoir|arrête[- ]toi|quitte|éteins[- ]toi|goodbye|exit)\b")
def quit_(m):
    raise QuitAssistant("À bientôt !")


@skill(r"\b(?:prends? (?:une )?note|note[- ]moi|take a note)\b\s*(?:que|:)?\s*(.+)")
def note(m):
    with open(NOTES_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M}] {m.group(1)}\n")
    return "Note enregistrée."


@skill(r"quelle heure|l'heure|what time")
def time_(m):
    return datetime.now().strftime("Il est %H heures %M.")


@skill(r"quel jour|quelle date|la date|what day")
def date_(m):
    d = datetime.now()
    return f"Nous sommes le {JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}."


@skill(r"blague|joke|fais[- ]moi rire")
def joke(m):
    return random.choice(BLAGUES)