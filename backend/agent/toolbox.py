"""Le catalogue d'outils de l'agent.

Deux origines, une seule interface :
  - les outils MCP, découverts au démarrage auprès des serveurs listés dans mcp.json ;
  - quelques outils locaux qui ont besoin du processus du serveur web (minuteurs, mémoire).
Le graphe ne voit que des ToolSpec et `await toolbox.call(nom, arguments)`.
"""
import asyncio
import inspect
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

MAX_RESULT_CHARS = 4000


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    schema: dict
    source: str = "local"            # "local" ou le nom du serveur MCP
    read_only: bool = False          # ne change rien : jamais de confirmation
    destructive: bool = True         # action à confirmer à chaque fois
    open_world: bool = True          # renvoie du contenu écrit par des tiers : résultat non fiable
    label: str = ""                  # nom court affiché pendant l'appel
    action: str = ""                 # « ouvrir {name} » : phrase de la demande de confirmation


@dataclass
class ToolResult:
    text: str
    is_error: bool = False


@dataclass
class Toolbox:
    timeout: float = 20.0
    _specs: dict[str, ToolSpec] = field(default_factory=dict)
    _runners: dict[str, Callable[[dict], Awaitable[ToolResult]]] = field(default_factory=dict)

    # ---------- enregistrement ----------
    def register(self, spec: ToolSpec, runner: Callable[[dict], Any]) -> ToolSpec:
        """`runner(arguments)` peut être synchrone ou asynchrone, et retourner un texte ou un ToolResult."""
        if spec.name in self._specs:                      # deux serveurs exposent le même nom : on préfixe le second
            spec = ToolSpec(**{**spec.__dict__, "name": f"{spec.source}__{spec.name}"})
        self._specs[spec.name] = spec
        self._runners[spec.name] = runner
        return spec

    # ---------- lecture ----------
    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def specs(self) -> list[ToolSpec]:
        return list(self._specs.values())

    def label(self, name: str) -> str:
        spec = self.get(name)
        return (spec.label if spec and spec.label else name)

    def as_llm_tools(self) -> list[dict]:
        """Format « function calling » d'OpenAI, que tous les modèles de chat LangChain acceptent dans bind_tools."""
        return [{"type": "function",
                 "function": {"name": s.name, "description": s.description,
                              "parameters": s.schema or {"type": "object", "properties": {}}}}
                for s in self._specs.values()]

    # ---------- exécution ----------
    async def call(self, name: str, args: dict | None) -> ToolResult:
        runner = self._runners.get(name)
        if runner is None:
            return ToolResult(f"L'outil {name} n'existe pas.", is_error=True)
        try:
            out = runner(dict(args or {}))
            if inspect.isawaitable(out):
                out = await asyncio.wait_for(out, self.timeout)
        except asyncio.TimeoutError:
            return ToolResult(f"L'outil {name} n'a pas répondu à temps.", is_error=True)
        except Exception as e:  # un outil qui plante ne doit jamais faire tomber la conversation
            return ToolResult(f"L'outil {name} a échoué : {e}", is_error=True)
        result = out if isinstance(out, ToolResult) else ToolResult(str(out))
        if len(result.text) > MAX_RESULT_CHARS:
            result.text = result.text[:MAX_RESULT_CHARS] + "…"
        return result

    def simulated(self, canned: dict[str, str] | None = None) -> tuple["Toolbox", list[tuple[str, dict]]]:
        """Copie du catalogue où aucun outil n'agit vraiment : chaque appel est noté puis reçoit une réponse fixe.
        Sert à l'évaluation (eval/run_eval.py) : on mesure les décisions de l'agent sans verrouiller l'écran."""
        canned = canned or {}
        calls: list[tuple[str, dict]] = []
        box = Toolbox(timeout=self.timeout)
        for spec in self.specs():
            def runner(args, _name=spec.name):
                calls.append((_name, args))
                return canned.get(_name, "C'est fait.")
            box._specs[spec.name] = spec
            box._runners[spec.name] = runner
        return box, calls


def local_tool(fn: Callable, *, description: str, properties: dict | None = None, required: list[str] | None = None,
               read_only: bool = False, destructive: bool = False, label: str = "", action: str = "") -> tuple[ToolSpec, Callable]:
    """Déclare une fonction Python comme outil local. Le schéma JSON est écrit à la main : il y en a très peu."""
    spec = ToolSpec(name=fn.__name__, description=description,
                    schema={"type": "object", "properties": properties or {}, "required": required or []},
                    source="local", read_only=read_only, destructive=destructive, open_world=False,
                    label=label or fn.__name__, action=action)
    return spec, (lambda args: fn(**args))
