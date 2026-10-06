import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:                                    # backend/.env : pratique pour la clé d'API (voir .env.example)
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

LANGUAGE = os.getenv("VA_LANG", "fr")               # "fr", "en", "ar" : langue reconnue par Whisper et parlée par le navigateur
WHISPER_MODEL = os.getenv("VA_MODEL", "small")      # tiny (rapide) / base / small (conseillé) / medium
DEFAULT_CITY = os.getenv("VA_CITY", "Tunis")        # ville par défaut pour la météo
NOTES_FILE = os.path.expanduser(os.getenv("VA_NOTES", "~/assistant_notes.txt"))

# ---------- Agent (LangGraph + MCP) ----------
# VA_AGENT : "auto" (agent si un LLM est configuré, sinon regex) ou "off" (regex seulement)
AGENT_MODE = os.getenv("VA_AGENT", "auto").lower()
# Format "fournisseur:modèle" compris par LangChain : anthropic:…, openai:…, google_genai:…, ollama:…
LLM = os.getenv("VA_LLM", "anthropic:claude-haiku-4-5-20251001")
MCP_CONFIG = os.getenv("VA_MCP_CONFIG", str(BASE_DIR / "mcp.json"))
MEMORY_FILE = os.path.expanduser(os.getenv("VA_MEMORY", "~/assistant_memory.json"))
METRICS_FILE = os.path.expanduser(os.getenv("VA_METRICS", str(BASE_DIR / "metrics.jsonl")))   # vide = pas de mesures
MAX_STEPS = int(os.getenv("VA_MAX_STEPS", "6"))             # allers-retours modèle ↔ outils par demande
HISTORY_TURNS = int(os.getenv("VA_HISTORY_TURNS", "8"))     # demandes gardées dans le contexte du modèle
TOOL_TIMEOUT = float(os.getenv("VA_TOOL_TIMEOUT", "20"))    # secondes par appel d'outil
