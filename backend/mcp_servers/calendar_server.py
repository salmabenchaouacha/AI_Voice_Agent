"""Serveur MCP « agenda » : Google Agenda de l'utilisateur (lecture d'un jour, ajout d'un événement).

Désactivé par défaut dans mcp.json : il faut d'abord connecter le compte Google (voir agenda.py ou le README).
    python mcp_servers/calendar_server.py --login     autorise l'accès, une seule fois
"""
import sys

from _common import ACTION, LECTURE, MCPServer, meta

import agenda
import cards

mcp = MCPServer("agenda", instructions="Google Agenda de l'utilisateur : ses rendez-vous, cours, réunions.")


@mcp.tool(annotations=LECTURE, meta=meta("agenda"))
def list_events(day: str = "aujourd'hui") -> str:
    """Liste les événements de l'agenda pour un jour. `day` : « aujourd'hui », « demain », « après-demain »,
    un jour de la semaine (« vendredi ») ou une date « AAAA-MM-JJ »."""
    return cards.attach(*agenda.list_events(day))


@mcp.tool(annotations=ACTION, meta=meta("ajout à l'agenda", "ajouter « {title} » à ton agenda le {start}"))
def create_event(title: str, start: str, duration_minutes: int = 60) -> str:
    """Ajoute un événement à l'agenda. `start` : « AAAA-MM-JJ HH:MM » en heure locale, calculé à partir de la date
    actuelle (« jeudi à 10 h » -> la date de jeudi prochain). `duration_minutes` : 60 si l'utilisateur ne dit rien."""
    return cards.attach(*agenda.create_event(title, start, duration_minutes))


if __name__ == "__main__":
    if "--login" in sys.argv:
        try:
            print(f"Agenda connecté. Jeton enregistré dans {agenda.login()}")
            print('Passe maintenant "enabled" du serveur « agenda » à true dans mcp.json, puis relance le serveur.')
        except agenda.NotConnected as e:
            print(e)
    else:
        mcp.run()
