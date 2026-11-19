"""Serveur MCP « notes » : le carnet de notes et la liste de tâches de l'utilisateur (fichiers dans son dossier personnel)."""
from _common import A_CONFIRMER, ACTION, LECTURE, MCPServer, meta

import actions
import planner

mcp = MCPServer("notes", instructions="Carnet de notes et liste de tâches de l'utilisateur.")


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


@mcp.tool(annotations=ACTION, meta=meta("tâche", "ajouter « {text} » à tes tâches"))
def add_task(text: str) -> str:
    """Ajoute une tâche à faire à la liste de l'utilisateur (« ajoute réviser le RAG à mes tâches »).
    `text` : la tâche, courte, à l'infinitif. Une tâche à faire n'est pas une note : une note est une information à garder."""
    return planner.add_task(text)


@mcp.tool(annotations=LECTURE, meta=meta("tâches"))
def list_tasks() -> str:
    """Liste les tâches qui restent à faire, avec leur numéro."""
    return planner.list_tasks()


@mcp.tool(annotations=ACTION, meta=meta("tâche terminée", "marquer « {query} » comme faite"))
def complete_task(query: str) -> str:
    """Marque une tâche comme faite. `query` : son numéro, ou quelques mots de son texte (« le RAG »)."""
    return planner.complete_task(query)


@mcp.tool(annotations=ACTION, meta=meta("nettoyage des tâches", "retirer les tâches terminées"))
def clear_done_tasks() -> str:
    """Retire de la liste les tâches déjà terminées. Les tâches à faire restent."""
    return planner.clear_done_tasks()


if __name__ == "__main__":
    mcp.run()
