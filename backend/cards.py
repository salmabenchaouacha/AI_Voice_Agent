"""Cartes visuelles : ce qu'un outil veut MONTRER à l'écran, en plus de ce que l'assistant DIT.

Un outil renvoie toujours un texte (lu par le modèle, puis résumé à voix haute). Il peut y accrocher une carte
(météo, sources d'une recherche, carte d'un lieu, capture d'écran) : des données JSON que l'interface dessine
sous la réponse. La carte voyage à la fin du texte, derrière un marqueur, pour passer telle quelle par MCP ;
la boîte à outils (agent/toolbox.py) la détache avant que le modèle ne lise le résultat.
"""
import json

MARK = "\n[[va-card]]"


def attach(text: str, card: dict | None) -> str:
    """Le texte de l'outil, avec la carte accrochée à la fin (ou le texte seul s'il n'y a pas de carte)."""
    if not card:
        return text
    return text + MARK + json.dumps(card, ensure_ascii=False, separators=(",", ":"))


def split(text: str) -> tuple[str, dict | None]:
    """L'inverse de attach : (texte pour le modèle, carte pour l'écran ou None)."""
    if MARK not in (text or ""):
        return text, None
    body, _, raw = text.rpartition(MARK)
    try:
        card = json.loads(raw)
    except ValueError:
        return body, None
    return body, card if isinstance(card, dict) and card.get("kind") else None
