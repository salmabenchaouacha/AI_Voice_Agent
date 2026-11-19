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

# Les tests lancent toujours les mêmes serveurs MCP, quel que soit ton mcp.json : le serveur « agenda » y est
# désactivé (il demande un compte Google), et les chemins sont absolus pour marcher depuis n'importe quel dossier.
import json as _json  # noqa: E402

_backend = Path(__file__).resolve().parent.parent
with open(_backend / "mcp.json", encoding="utf-8") as _f:
    _servers = _json.load(_f)["mcpServers"]
for _name, _cfg in _servers.items():
    _cfg["args"] = [str(_backend / a) if a.endswith(".py") else a for a in _cfg.get("args", [])]
    _cfg["cwd"] = str(_backend)
    if _name == "agenda":
        _cfg["enabled"] = False
_test_mcp = os.path.join(_tmp, "mcp.json")
with open(_test_mcp, "w", encoding="utf-8") as _f:
    _json.dump({"mcpServers": _servers}, _f)
os.environ["VA_MCP_CONFIG"] = _test_mcp
