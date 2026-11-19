import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("VA_PRELOAD", "0")  # pas de chargement de Whisper pendant les tests
os.environ["VA_AGENT"] = "off"            # les tests d'API utilisent le mode hors-ligne : aucun appel à un vrai LLM
os.environ["VA_METRICS"] = ""             # pas de fichier de mesures écrit par les tests
os.environ["VA_AUDIT"] = ""               # pas de journal des actions sensibles écrit par les tests
_tmp = tempfile.mkdtemp(prefix="va-tests-")  # tâches et rappels des tests : jamais dans le vrai dossier personnel
os.environ["VA_TASKS"] = os.path.join(_tmp, "tasks.json")
os.environ["VA_REMINDERS"] = os.path.join(_tmp, "reminders.json")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
