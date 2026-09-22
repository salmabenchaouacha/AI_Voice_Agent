import os

LANGUAGE = os.getenv("VA_LANG", "fr")               # "fr", "en", "ar" : langue reconnue par Whisper et parlée par le navigateur
WHISPER_MODEL = os.getenv("VA_MODEL", "small")      # tiny (rapide) / base / small (conseillé) / medium
DEFAULT_CITY = os.getenv("VA_CITY", "Tunis")        # ville par défaut pour la météo
NOTES_FILE = os.path.expanduser("~/assistant_notes.txt")