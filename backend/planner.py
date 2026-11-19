"""Tâches à faire et rappels à heure fixe.

Tâches  : un fichier JSON dans le dossier personnel. Elles sont lues et écrites par le serveur MCP « notes »
          (l'agent) et par le serveur web (le panneau, où l'on peut cocher une tâche) : le fichier fait le lien.
Rappels : « rappelle-moi d'appeler maman à 18 h ». Comme les minuteurs, ils doivent prévenir le navigateur
          (notifier.push), donc ils vivent dans le processus du serveur web. Ils sont aussi écrits sur disque :
          après un redémarrage du serveur, restore_reminders() les reprogramme.
"""
import json
import os
import re
import threading
import time
import unicodedata
from datetime import datetime, timedelta

import config
import notifier

_lock = threading.Lock()


# ---------- fichiers JSON ----------
def _load(path: str) -> list[dict]:
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, ValueError):
        return []


def _save(path: str, items: list[dict]) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    os.replace(tmp, path)                       # écriture atomique : jamais de fichier à moitié écrit


def _fold(text: str) -> str:
    """« Réviser le RAG » -> « reviser le rag » : pour retrouver une tâche dite à l'oral."""
    text = unicodedata.normalize("NFD", text or "").casefold()
    return re.sub(r"\s+", " ", "".join(c for c in text if unicodedata.category(c) != "Mn")).strip()


# ---------- tâches ----------
def add_task(text: str, path: str | None = None) -> str:
    text = (text or "").strip().rstrip(".")
    if not text:
        return "La tâche est vide, je n'ai rien ajouté."
    path = path or config.TASKS_FILE
    with _lock:
        items = _load(path)
        if any(not t["done"] and _fold(t["text"]) == _fold(text) for t in items):
            return f"La tâche « {text} » est déjà dans ta liste."
        items.append({"id": max((t["id"] for t in items), default=0) + 1, "text": text, "done": False,
                      "created": round(time.time() * 1000), "done_at": None})
        _save(path, items)
    return f"Tâche ajoutée : {text}."


def list_tasks(path: str | None = None) -> str:
    todo = [t for t in _load(path or config.TASKS_FILE) if not t["done"]]
    if not todo:
        return "Ta liste de tâches est vide."
    return (f"{len(todo)} tâche{'s' if len(todo) > 1 else ''} à faire : "
            + " ; ".join(f"{t['id']}. {t['text']}" for t in todo) + ".")


def _find(items: list[dict], query: str) -> list[dict]:
    query = (query or "").strip()
    todo = [t for t in items if not t["done"]]
    if query.isdigit():
        return [t for t in todo if t["id"] == int(query)]
    q = _fold(query)
    exact = [t for t in todo if _fold(t["text"]) == q]
    return exact or [t for t in todo if q and (q in _fold(t["text"]) or _fold(t["text"]) in q)]


def complete_task(query: str, path: str | None = None) -> str:
    """`query` : le numéro de la tâche ou quelques mots de son texte."""
    path = path or config.TASKS_FILE
    with _lock:
        items = _load(path)
        found = _find(items, query)
        if not found:
            return f"Je ne trouve pas de tâche à faire qui corresponde à « {query} »."
        if len(found) > 1:
            return "Plusieurs tâches correspondent : " + " ; ".join(f"{t['id']}. {t['text']}" for t in found) + \
                   ". Laquelle ?"
        found[0].update(done=True, done_at=round(time.time() * 1000))
        _save(path, items)
    return f"Tâche terminée : {found[0]['text']}."


def toggle_task(task_id: int, path: str | None = None) -> bool:
    """Coche ou décoche une tâche depuis le panneau. Retourne False si elle n'existe pas."""
    path = path or config.TASKS_FILE
    with _lock:
        items = _load(path)
        for t in items:
            if t["id"] == task_id:
                t["done"] = not t["done"]
                t["done_at"] = round(time.time() * 1000) if t["done"] else None
                _save(path, items)
                return True
    return False


def clear_done_tasks(path: str | None = None) -> str:
    path = path or config.TASKS_FILE
    with _lock:
        items = _load(path)
        kept = [t for t in items if not t["done"]]
        _save(path, kept)
    n = len(items) - len(kept)
    return f"{n} tâche{'s' if n > 1 else ''} terminée{'s' if n > 1 else ''} retirée{'s' if n > 1 else ''}." if n \
        else "Aucune tâche terminée à retirer."


def tasks_snapshot(done_limit: int = 3, path: str | None = None) -> list[dict]:
    """Pour le panneau : les tâches à faire, puis les dernières terminées (barrées)."""
    items = _load(path or config.TASKS_FILE)
    todo = [t for t in items if not t["done"]]
    done = sorted((t for t in items if t["done"]), key=lambda t: t.get("done_at") or 0, reverse=True)[:done_limit]
    return [{"id": t["id"], "text": t["text"], "done": t["done"]} for t in todo + done]


# ---------- rappels ----------
_timers: dict[int, threading.Timer] = {}
_TIME = re.compile(r"^(\d{1,2})\s*(?:h|:)\s*(\d{2})?$")


def parse_when(at: str, now: datetime | None = None) -> datetime | None:
    """« 18:30 », « 18h », « 2026-11-20 09:00 » -> date et heure du rappel (aujourd'hui, ou demain si c'est passé)."""
    now = now or datetime.now()
    at = re.sub(r"^(\d{4}-\d{2}-\d{2})t", r"\1 ", (at or "").strip().lower())   # format ISO accepté aussi
    m = _TIME.match(at)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        if hour > 23 or minute > 59:
            return None
        when = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        return when + timedelta(days=1) if when <= now else when
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %Hh%M", "%Y-%m-%d %Hh"):
        try:
            return datetime.strptime(at, fmt)
        except ValueError:
            pass
    return None


def spoken_when(when: datetime, now: datetime | None = None) -> str:
    now = now or datetime.now()
    hour = f"{when.hour} heure{'s' if when.hour > 1 else ''}" + (f" {when.minute:02d}" if when.minute else "")
    if when.date() == now.date():
        return f"aujourd'hui à {hour}"
    if when.date() == (now + timedelta(days=1)).date():
        return f"demain à {hour}"
    return f"le {when.day}/{when.month:02d} à {hour}"


def _schedule(item: dict, path: str) -> None:
    delay = max(1.0, item["at"] / 1000 - time.time())

    def fire():
        with _lock:
            _timers.pop(item["id"], None)
            _save(path, [r for r in _load(path) if r["id"] != item["id"]])
        notifier.push(f"Rappel : {item['text']}")

    t = threading.Timer(delay, fire)
    t.daemon = True
    _timers[item["id"]] = t
    t.start()


def set_reminder(at: str, text: str, path: str | None = None, now: datetime | None = None) -> str:
    text = (text or "").strip().rstrip(".")
    if not text:
        return "De quoi dois-je te rappeler ?"
    now = now or datetime.now()
    when = parse_when(at, now)
    if when is None:
        return f"Je n'ai pas compris l'heure « {at} ». Donne-la sous la forme 18:30."
    if when <= now:
        return "Cette heure est déjà passée."
    if when - now > timedelta(days=31):
        return "Je ne programme pas de rappel à plus d'un mois."
    path = path or config.REMINDERS_FILE
    with _lock:
        items = _load(path)
        item = {"id": max((r["id"] for r in items), default=0) + 1, "text": text, "at": round(when.timestamp() * 1000)}
        items.append(item)
        _save(path, items)
        _schedule(item, path)
    return f"C'est noté, je te rappellerai {spoken_when(when, now)} : {text}."


def list_reminders(path: str | None = None) -> str:
    items = sorted(_load(path or config.REMINDERS_FILE), key=lambda r: r["at"])
    if not items:
        return "Aucun rappel programmé."
    return "Rappels programmés : " + " ; ".join(
        f"{spoken_when(datetime.fromtimestamp(r['at'] / 1000))}, {r['text']}" for r in items) + "."


def cancel_reminders(path: str | None = None) -> str:
    path = path or config.REMINDERS_FILE
    with _lock:
        items = _load(path)
        for t in _timers.values():
            t.cancel()
        _timers.clear()
        _save(path, [])
    n = len(items)
    return f"{n} rappel{'s' if n > 1 else ''} annulé{'s' if n > 1 else ''}." if n else "Aucun rappel à annuler."


def reminders_snapshot(path: str | None = None) -> list[dict]:
    """Pour le panneau : `at` en millisecondes (horloge du serveur)."""
    return sorted(({"id": r["id"], "text": r["text"], "at": r["at"]} for r in _load(path or config.REMINDERS_FILE)),
                  key=lambda r: r["at"])


def restore_reminders(path: str | None = None) -> int:
    """Au démarrage du serveur : reprogramme les rappels enregistrés. Un rappel manqué pendant que le serveur
    était arrêté sonne quelques secondes après le démarrage, le temps que le navigateur se reconnecte."""
    path = path or config.REMINDERS_FILE
    with _lock:
        items = [r for r in _load(path) if r["id"] not in _timers]
        for r in items:
            if r["at"] / 1000 < time.time():
                r = {**r, "at": round((time.time() + 8) * 1000)}
            _schedule(r, path)
    return len(items)
