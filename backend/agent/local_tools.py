"""Outils locaux : ceux qui doivent tourner dans le processus du serveur web.

Un minuteur doit pouvoir prévenir le navigateur quand il sonne (notifier.push), et seul ce processus
tient la connexion WebSocket. Un serveur MCP séparé ne le pourrait pas sans canal de retour."""
import actions
import planner

from .memory import Memory
from .toolbox import Toolbox, local_tool


def register_local_tools(toolbox: Toolbox, memory: Memory) -> None:
    def start_timer(seconds: int, label: str = "") -> str:
        return actions.start_timer(seconds, label)

    def list_timers() -> str:
        return actions.list_timers()

    def cancel_timers() -> str:
        return actions.cancel_timers()

    def set_reminder(at: str, text: str) -> str:
        return planner.set_reminder(at, text)

    def list_reminders() -> str:
        return planner.list_reminders()

    def cancel_reminders() -> str:
        return planner.cancel_reminders()

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
        set_reminder, label="rappel", action="te rappeler « {text} » à {at}",
        description="Programme un rappel à une heure précise (« rappelle-moi d'appeler maman à 18 h »). "
                    "`at` : heure locale « HH:MM » (aujourd'hui, ou demain si l'heure est passée), ou « AAAA-MM-JJ HH:MM » "
                    "pour un autre jour ; calcule-la toi-même à partir de la date et de l'heure actuelles. `text` : de quoi "
                    "rappeler, court. Pour une durée (« dans dix minutes »), utilise plutôt le minuteur.",
        properties={"at": {"type": "string"}, "text": {"type": "string"}},
        required=["at", "text"]))
    toolbox.register(*local_tool(
        list_reminders, label="rappels", read_only=True,
        description="Liste les rappels programmés, avec leur jour et leur heure."))
    toolbox.register(*local_tool(
        cancel_reminders, label="annulation des rappels", action="annuler tous les rappels",
        description="Annule tous les rappels programmés."))
    toolbox.register(*local_tool(
        remember, label="mémoire", action="retenir « {fact} »",
        description="Retient durablement une information sur l'utilisateur (prénom, ville, goûts, habitudes), "
                    "seulement quand il te le demande ou te la donne pour plus tard. Une phrase courte et complète.",
        properties={"fact": {"type": "string"}}, required=["fact"]))
    toolbox.register(*local_tool(
        forget_memory, label="oubli", destructive=True, action="oublier tout ce que j'ai retenu sur toi",
        description="Efface toutes les informations retenues durablement sur l'utilisateur."))
