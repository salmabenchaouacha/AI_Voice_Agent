"""Serveur MCP « bureau » : applications, volume, capture d'écran, verrouillage, batterie."""
import re
from typing import Literal

from _common import A_CONFIRMER, ACTION, LECTURE, MCPServer, meta

import actions
import system

mcp = MCPServer("bureau", instructions="Pilote l'ordinateur de l'utilisateur : applications, volume, écran, batterie.")


@mcp.tool(annotations=ACTION, meta=meta("ouverture", "ouvrir {name}"))
def open_app(name: str) -> str:
    """Ouvre une application installée (chrome, calculatrice, bloc-notes, vscode, terminal, spotify, explorateur)
    ou un site connu par son nom (youtube, gmail, github, linkedin, google). `name` est le nom dit par l'utilisateur."""
    name = name.lower().strip()
    connu = any(site in name for site in system.SITES) or any(k in name for keys in system.APPS for k in keys)
    if not connu and not re.fullmatch(r"[\w.+-]+", name):
        # Un nom inconnu est lancé tel quel par le système : on refuse tout ce qui ressemble à une commande avec arguments.
        return f"Je ne connais pas l'application {name}."
    return system.open_target(name)


@mcp.tool(annotations=ACTION, meta=meta("volume", "changer le volume"))
def set_volume(action: Literal["up", "down", "mute"]) -> str:
    """Règle le volume de l'ordinateur : "up" monte, "down" baisse, "mute" coupe ou rétablit le son."""
    system.volume({"up": 1, "down": -1, "mute": 0}[action])
    return {"up": "Volume augmenté.", "down": "Volume baissé.", "mute": "Son coupé ou rétabli."}[action]


@mcp.tool(annotations=ACTION, meta=meta("capture d'écran", "faire une capture d'écran"))
def take_screenshot() -> str:
    """Fait une capture d'écran et l'enregistre dans le dossier personnel. Retourne le chemin du fichier."""
    return f"Capture enregistrée : {system.screenshot()}"


@mcp.tool(annotations=A_CONFIRMER, meta=meta("verrouillage", "verrouiller l'écran"))
def lock_screen() -> str:
    """Verrouille la session de l'ordinateur. L'utilisateur devra retaper son mot de passe."""
    system.lock_screen()
    return "Écran verrouillé."


@mcp.tool(annotations=LECTURE, meta=meta("batterie"))
def battery_status() -> str:
    """Donne le niveau de batterie de l'ordinateur et indique s'il est en charge."""
    return actions.battery()


if __name__ == "__main__":
    mcp.run()
