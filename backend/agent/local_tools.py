"""Outils locaux : ceux qui doivent tourner dans le processus du serveur web.

Un minuteur doit pouvoir prévenir le navigateur quand il sonne (notifier.push), et seul ce processus
tient la connexion WebSocket. Un serveur MCP séparé ne le pourrait pas sans canal de retour."""
import actions

from .memory import Memory
from .toolbox import Toolbox, local_tool


def register_local_tools(toolbox: Toolbox, memory: Memory) -> None:
    def start_timer(seconds: int, label: str = "") -> str:
        return actions.start_timer(seconds, label)

    def list_timers() -> str:
        return actions.list_timers()

    def cancel_timers() -> str:
        return actions.cancel_timers()

    def remember(fact: str) -> str:
        return memory.remember(fact)

    def forget_memory() -> str:
        return memory.forget_all()

    toolbox.register(*local_tool(
        start_timer, label="minuteur", action="lancer un minuteur de {seconds} secondes",
        description="Lance un minuteur qui préviendra l'utilisateur à la fin. Convertis toi-même la durée en secondes "
                    "(« un quart d'heure » = 900). `label` : à quoi sert le minuteur, s'il l'a dit (« pâtes »).",
        properties={"seconds": {"type": "integer", "minimum": 1, "maximum": 86400},
                    "label": {"type": "string"}},
        required=["seconds"]))
    toolbox.register(*local_tool(
        list_timers, label="minuteurs", read_only=True,
        description="Liste les minuteurs en cours et le temps qu'il leur reste."))
    toolbox.register(*local_tool(
        cancel_timers, label="annulation des minuteurs", action="annuler tous les minuteurs",
        description="Annule tous les minuteurs en cours."))
    toolbox.register(*local_tool(
        remember, label="mémoire", action="retenir « {fact} »",
        description="Retient durablement une information sur l'utilisateur (prénom, ville, goûts, habitudes), "
                    "seulement quand il te le demande ou te la donne pour plus tard. Une phrase courte et complète.",
        properties={"fact": {"type": "string"}}, required=["fact"]))
    toolbox.register(*local_tool(
        forget_memory, label="oubli", destructive=True, action="oublier tout ce que j'ai retenu sur toi",
        description="Efface toutes les informations retenues durablement sur l'utilisateur."))
