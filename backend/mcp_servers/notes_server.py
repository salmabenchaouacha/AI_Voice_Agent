"""Serveur MCP « notes » : le carnet de notes de l'utilisateur (un fichier texte dans son dossier personnel)."""
from _common import A_CONFIRMER, ACTION, LECTURE, MCPServer, meta

import actions

mcp = MCPServer("notes", instructions="Carnet de notes personnel de l'utilisateur.")


@mcp.tool(annotations=ACTION, meta=meta("note", "noter « {text} »"))
def add_note(text: str) -> str:
    """Ajoute une note datée au carnet. `text` est le contenu à retenir, reformulé proprement."""
    return actions.add_note(text)


@mcp.tool(annotations=LECTURE, meta=meta("notes"))
def list_notes(limit: int = 5) -> str:
    """Relit les dernières notes du carnet (les `limit` plus récentes)."""
    return actions.read_notes(limit)


@mcp.tool(annotations=A_CONFIRMER, meta=meta("effacement des notes", "effacer toutes tes notes"))
def clear_notes() -> str:
    """Efface définitivement toutes les notes du carnet."""
    return actions.clear_notes()


if __name__ == "__main__":
    mcp.run()
