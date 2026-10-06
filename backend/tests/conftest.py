import os
import sys
from pathlib import Path

os.environ.setdefault("VA_PRELOAD", "0")  # pas de chargement de Whisper pendant les tests
os.environ["VA_AGENT"] = "off"            # les tests d'API utilisent le mode hors-ligne : aucun appel à un vrai LLM
os.environ["VA_METRICS"] = ""             # pas de fichier de mesures écrit par les tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
