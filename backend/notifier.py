"""Notifications serveur -> navigateur (ex. fin d'un minuteur)."""
_subscribers = set()


def subscribe(loop, queue):
    """Enregistre une file asyncio ; retourne la fonction de désinscription."""
    entry = (loop, queue)
    _subscribers.add(entry)
    return lambda: _subscribers.discard(entry)


def push(text: str) -> None:
    """Appelable depuis n'importe quel thread."""
    print(f"🔔 {text}")
    for loop, queue in list(_subscribers):
        loop.call_soon_threadsafe(queue.put_nowait, text)