"""Routeur de commandes : un décorateur @skill(regex) enregistre une action."""
import re


class QuitAssistant(Exception):
    pass


_SKILLS = []


def skill(*patterns):
    compiled = [re.compile(p) for p in patterns]

    def deco(fn):
        _SKILLS.append((compiled, fn))
        return fn
    return deco


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'")
    return re.sub(r"[^\w\s'-]", " ", text).strip()


def dispatch(text: str) -> str:
    text = normalize(text)
    for patterns, fn in _SKILLS:
        for p in patterns:
            m = p.search(text)
            if m:
                return fn(m)
    return "Je n'ai pas compris. Dis « aide » pour voir ce que je sais faire."