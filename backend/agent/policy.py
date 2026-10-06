"""Garde-fou entre ce que le modèle veut faire et ce qui est réellement exécuté.

Trois règles, appliquées dans cet ordre à chaque appel d'outil demandé par le modèle :
  1. un outil en lecture seule passe toujours ;
  2. un outil marqué « à confirmer » par son serveur demande toujours un oui oral ;
  3. tout autre outil qui agit sur la machine demande un oui si du contenu non fiable (une page web,
     un résultat de recherche) est entré dans le contexte pendant la demande en cours.

La règle 3 est la défense contre l'injection de prompt : une page piégée peut convaincre le modèle
d'appeler un outil, mais elle ne peut pas répondre « oui » à la place de l'utilisateur.
Tout ce fichier est du Python pur, sans LLM : il se teste et se mesure indépendamment.
"""
import re

from .toolbox import ToolSpec

_OUI = (r"oui|ouais|ouep|yes|yep|ok|okay|d'accord|dac|vas[- ]y|allez|go|confirme|je confirme|c'est bon|bien s[uû]r|"
        r"absolument|exactement|fais[- ]le|ey|ih|aywa|na3am|نعم|اي|إي|ايه|أيوه|باهي")
_NON = (r"non|nan|no|nope|annule|annuler|arr[eê]te|stop|laisse tomber|surtout pas|pas maintenant|ne fais pas|"
        r"n'en fais rien|لا|ما تعملش")
_RE_OUI = re.compile(rf"^(?:{_OUI})\b", re.IGNORECASE)
_RE_NON = re.compile(rf"^(?:{_NON})\b", re.IGNORECASE)
_RE_RETRACTATION = re.compile(r"\b(?:ne|non|attends|pas (?:maintenant|encore|ça|tout de suite))\b|n'", re.IGNORECASE)


def parse_confirmation(text: str) -> bool | None:
    """True = oui, False = non, None = ni l'un ni l'autre (l'utilisateur a dit autre chose).

    Volontairement strict : la réponse doit COMMENCER par un oui ou un non. Dans le doute on n'agit pas."""
    t = re.sub(r"[^\w\s'-]", " ", (text or "").lower().replace("’", "'")).strip()
    if not t:
        return None
    if _RE_NON.match(t):
        # « non » = refus. « non, mets plutôt un minuteur » = une nouvelle demande : on la laisse au modèle (None).
        return False if len(t.split()) <= 3 else None
    if _RE_OUI.match(t):
        return None if _RE_RETRACTATION.search(t) else True      # « oui mais pas maintenant » n'est pas un oui
    return None


def needs_confirmation(spec: ToolSpec | None, tainted: bool) -> bool:
    if spec is None:                 # outil inconnu : il ne sera pas exécuté, rien à confirmer
        return False
    if spec.read_only:
        return False
    if spec.destructive:
        return True
    return tainted


def describe(spec: ToolSpec, args: dict) -> str:
    """« ouvrir chrome » : l'action reformulée avec ses arguments, pour que l'utilisateur entende ce qui a été compris."""
    if spec.action:
        try:
            return spec.action.format(**{k: str(v) for k, v in (args or {}).items()})
        except (KeyError, IndexError, ValueError):
            pass
    detail = ", ".join(f"{k} {v}" for k, v in (args or {}).items())
    return f"utiliser {spec.label or spec.name}" + (f" avec {detail}" if detail else "")


def confirmation_question(actions: list[str]) -> str:
    if len(actions) == 1:
        todo = actions[0]
    else:
        todo = ", ".join(actions[:-1]) + " et " + actions[-1]
    return f"Je vais {todo}. Tu confirmes ?"


def refusal_note(verdict: bool | None, said: str) -> str:
    """Ce que le modèle lit à la place du résultat de l'outil quand l'action n'a pas été confirmée."""
    if verdict is False:
        return "Action annulée : l'utilisateur a refusé. Ne la relance pas, confirme simplement l'annulation."
    return ("Action non exécutée : au lieu de confirmer, l'utilisateur a dit « " + (said or "").strip()[:300] +
            " ». Réponds à ce qu'il vient de dire.")


def wrap_untrusted(text: str) -> str:
    """Encadre un contenu venu de l'extérieur. Le prompt système dit au modèle de n'y voir que des données."""
    return f"<contenu_externe>\n{text.replace('</contenu_externe>', '')}\n</contenu_externe>"
