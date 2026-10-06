"""Partagé par les trois serveurs MCP de l'assistant.

Chaque serveur est un petit programme lancé par l'agent, avec qui il parle en JSON-RPC sur stdin/stdout.
Règle à respecter dans un serveur stdio : ne jamais écrire sur stdout (print), c'est le canal du protocole.

Chaque outil se décrit lui-même, et c'est l'agent qui décide quoi en faire :
  - annotations MCP standard : lecture seule ? action à confirmer ? contenu venu de l'extérieur ?
  - meta "va/label"  : nom court affiché pendant l'appel (« météo ») ;
  - meta "va/action" : phrase lue à l'utilisateur quand une confirmation est demandée (« ouvrir {name} »).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # pour importer actions.py, system.py, config.py

from mcp.server.mcpserver import MCPServer  # noqa: E402
from mcp.types import ToolAnnotations  # noqa: E402

# Lit une information, ne change rien sur la machine : jamais de confirmation.
LECTURE = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
# Lit du contenu écrit par des inconnus (pages web) : le résultat est traité comme non fiable par l'agent.
LECTURE_WEB = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=True)
# Agit sur la machine, sans rien casser : confirmation seulement si du contenu non fiable est entré dans la demande.
ACTION = ToolAnnotations(read_only_hint=False, destructive_hint=False, open_world_hint=False)
# Action gênante ou irréversible : confirmation orale systématique.
A_CONFIRMER = ToolAnnotations(read_only_hint=False, destructive_hint=True, open_world_hint=False)


def meta(label: str, action: str = "") -> dict:
    return {"va/label": label, **({"va/action": action} if action else {})}


__all__ = ["MCPServer", "LECTURE", "LECTURE_WEB", "ACTION", "A_CONFIRMER", "meta"]
