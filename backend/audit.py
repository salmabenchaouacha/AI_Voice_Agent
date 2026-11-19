"""Journal des actions sensibles : chaque demande de confirmation et la réponse obtenue.

Une ligne JSON par action, dans un fichier du dossier personnel. On y voit ce qui a été confirmé, refusé,
ou remplacé par une autre demande, et pourquoi la confirmation a été exigée (action sensible par nature,
ou action demandée après la lecture de contenu web : la défense contre l'injection de prompt)."""
import json
import os
import threading
import time

# Fichier du journal (VA_AUDIT vide = pas de journal, comme pendant les tests)
PATH = os.path.expanduser(os.getenv("VA_AUDIT", "~/assistant_audit.jsonl"))
_lock = threading.Lock()


def record(entries: list[dict]) -> None:
    if not PATH:
        return
    stamp = round(time.time() * 1000)
    try:
        with _lock, open(PATH, "a", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps({"t": stamp, **e}, ensure_ascii=False) + "\n")
    except OSError:
        pass


def recent(limit: int = 8) -> list[dict]:
    """Les dernières entrées, la plus récente d'abord."""
    if not PATH:
        return []
    try:
        with open(PATH, encoding="utf-8") as f:
            lines = f.readlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in reversed(lines):
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out
