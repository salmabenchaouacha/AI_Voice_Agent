"""Mémoire durable : quelques faits sur l'utilisateur, gardés d'une session à l'autre dans un fichier JSON.

À ne pas confondre avec la mémoire de conversation (les derniers échanges), gérée par le checkpointer de LangGraph.
Les faits sont réinjectés dans le prompt système à chaque appel du modèle."""
import json
import os
import threading

MAX_FACTS = 30


class Memory:
    def __init__(self, path: str):
        self.path = path
        self._lock = threading.Lock()

    def facts(self) -> list[str]:
        try:
            with open(self.path, encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, ValueError):
            return []
        return [str(x) for x in data if str(x).strip()] if isinstance(data, list) else []

    def remember(self, fact: str) -> str:
        fact = " ".join((fact or "").split())[:200]
        if not fact:
            return "Il n'y a rien à retenir."
        with self._lock:
            facts = self.facts()
            if fact.lower() in (f.lower() for f in facts):
                return "Je le savais déjà."
            facts = (facts + [fact])[-MAX_FACTS:]
            tmp = self.path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(facts, f, ensure_ascii=False, indent=1)
            os.replace(tmp, self.path)
        return "C'est retenu."

    def forget_all(self) -> str:
        with self._lock:
            try:
                os.remove(self.path)
            except FileNotFoundError:
                return "Je n'avais rien retenu."
        return "J'ai tout oublié."
