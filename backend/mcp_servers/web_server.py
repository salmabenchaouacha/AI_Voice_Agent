"""Serveur MCP « web » : météo, carte d'un lieu, recherche web lue par l'agent, lecture de page, YouTube, lien.

Météo, carte et recherche accrochent une carte visuelle à leur texte (voir cards.py) : l'interface l'affiche
sous la réponse, le modèle ne la voit pas."""
from _common import ACTION, LECTURE, LECTURE_WEB, MCPServer, meta

import actions
import cards

mcp = MCPServer("web", instructions="Accès à Internet : météo, recherche, lecture de pages, ouverture de liens.")


@mcp.tool(annotations=LECTURE, meta=meta("météo"))
def get_weather(city: str = "") -> str:
    """Météo actuelle d'une ville (température, ciel, vent) et prévisions des trois prochains jours (mini, maxi, ciel).
    Sans ville, utilise celle de l'utilisateur. Sert aussi pour « et demain ? » ou « ce week-end »."""
    text, card = actions.weather_report(city)
    return cards.attach(text + actions.forecast_text(card), card)


@mcp.tool(annotations=LECTURE, meta=meta("carte"))
def show_map(place: str) -> str:
    """Affiche à l'écran une carte centrée sur un lieu (ville, quartier, monument, pays) et dit où il se trouve.
    À utiliser quand l'utilisateur demande où se trouve un endroit ou veut le voir sur une carte."""
    return cards.attach(*actions.locate_report(place))


@mcp.tool(annotations=LECTURE_WEB, meta=meta("recherche web"))
def web_search(query: str, max_results: int = 4) -> str:
    """Cherche sur le web et retourne les titres, extraits et adresses des premiers résultats.
    À utiliser pour toute question d'actualité ou tout fait que tu ne connais pas avec certitude."""
    return cards.attach(*actions.web_search_report(query, max_results))


@mcp.tool(annotations=LECTURE_WEB, meta=meta("lecture de page"))
def read_page(url: str) -> str:
    """Lit le texte d'une page web publique (par exemple un résultat de web_search) pour en savoir plus."""
    return actions.read_page(url)


@mcp.tool(annotations=ACTION, meta=meta("YouTube", "lancer {query} sur YouTube"))
def play_youtube(query: str) -> str:
    """Ouvre YouTube dans le navigateur sur une recherche : musique, artiste, vidéo."""
    return actions.play_youtube(query)


@mcp.tool(annotations=ACTION, meta=meta("ouverture d'un lien", "ouvrir {url}"))
def open_in_browser(url: str) -> str:
    """Ouvre une adresse http(s) dans le navigateur de l'utilisateur."""
    return actions.open_url(url)


if __name__ == "__main__":
    mcp.run()
