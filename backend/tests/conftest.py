import os
import sys
from pathlib import Path

os.environ.setdefault("VA_PRELOAD", "0")  # pas de chargement de Whisper pendant les tests
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))