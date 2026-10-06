"""Le graphe LangGraph de l'assistant.

                 ┌──────────────────────────────────────────┐
                 ▼                                          │
    START ──► agent ──(appels d'outils ?)──► review ──► tools
                 │                             │
                 └──(réponse finale)──► END    └─ interrupt() : attend le « oui » de l'utilisateur

  agent   le modèle lit la conversation et choisit : répondre, ou appeler un ou plusieurs outils ;
  review  le garde-fou (policy.py) décide si ces appels exigent une confirmation orale ; si oui le graphe
          se met en pause, et reprendra ici même quand l'utilisateur aura répondu ;
  tools   exécute les appels acceptés (via MCP ou en local) et rend les résultats au modèle.

La boucle agent → review → tools recommence tant que le modèle demande des outils : c'est ce qui permet
« donne-moi la météo à Sousse puis mets un minuteur de dix minutes » en une seule phrase.
L'état est sauvegardé après chaque nœud par le checkpointer, sous un identifiant de conversation (thread_id) :
c'est à la fois la mémoire des échanges précédents et ce qui rend la pause possible.
"""
import asyncio
import contextvars
import time
from dataclasses import dataclass, field
from typing import Annotated, Any, Awaitable, Callable

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.types import Command, interrupt
from typing_extensions import TypedDict

try:
    from langgraph.checkpoint.memory import InMemorySaver
except ImportError:  # anciennes versions de langgraph
    from langgraph.checkpoint.memory import MemorySaver as InMemorySaver

from . import policy
from .prompts import build_system_prompt, clean_for_speech
from .toolbox import Toolbox

REDACTED = "[contenu web d'une demande précédente, retiré du contexte]"
INTERRUPTED = "Action interrompue avant d'avoir été exécutée."
TOO_MANY_STEPS = "Je n'ai pas réussi à terminer en un nombre raisonnable d'étapes. Peux-tu reformuler plus simplement ?"
LLM_DOWN = "Je n'arrive pas à joindre le modèle de langage pour le moment."


class State(TypedDict, total=False):
    messages: Annotated[list, add_messages]   # toute la conversation ; add_messages ajoute au lieu de remplacer
    tainted: bool                             # du contenu non fiable est entré dans la demande en cours
    decision: dict                            # id d'appel refusé -> explication donnée au modèle


@dataclass
class Turn:
    """Ce qui est mesuré et diffusé pendant une demande (transmis aux nœuds par contextvar, hors de l'état)."""
    emit: Callable[[dict], Awaitable[None]] | None = None
    llm_ms: float = 0.0
    llm_calls: int = 0
    tool_ms: float = 0.0

    async def send(self, event: dict) -> None:
        if self.emit:
            try:
                await self.emit(event)
            except Exception:
                pass                           # un navigateur déconnecté ne doit pas faire échouer l'action


_TURN: contextvars.ContextVar[Turn | None] = contextvars.ContextVar("va_turn", default=None)


@dataclass
class TurnResult:
    kind: str                                  # "result" : réponse finale ; "confirm" : question en attente d'un oui/non
    reply: str
    tools: list[str] = field(default_factory=list)      # noms courts des outils exécutés pendant la demande
    timings: dict = field(default_factory=dict)
    error: str = ""


# ---------- fonctions pures sur la liste de messages ----------
def text_of(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        return content.strip()
    parts = []
    for block in content or []:                # certains fournisseurs renvoient une liste de blocs
        if isinstance(block, str):
            parts.append(block)
        elif isinstance(block, dict) and block.get("type") == "text":
            parts.append(block.get("text", ""))
    return " ".join(parts).strip()


def rounds_since_human(messages: list) -> int:
    """Nombre d'allers-retours modèle → outils déjà faits pour la demande en cours."""
    n = 0
    for m in reversed(messages):
        if m.type == "human":
            break
        if m.type == "ai" and getattr(m, "tool_calls", None):
            n += 1
    return n


def executed_tools(messages: list) -> list[str]:
    names = []
    for m in reversed(messages):
        if m.type == "human":
            break
        if m.type == "tool" and (m.additional_kwargs or {}).get("va_executed"):
            names.append(m.name)
    return names[::-1]


def window(messages: list, toolbox: Toolbox, history_turns: int) -> list:
    """Les messages réellement envoyés au modèle.

    1. On garde les `history_turns` dernières demandes (coût et latence bornés), en coupant toujours au début
       d'une demande pour ne jamais séparer un appel d'outil de son résultat.
    2. Le contenu web des demandes précédentes est retiré : il n'est dans le contexte que pendant la demande
       où il a été lu, celle où le garde-fou surveille les actions (voir policy.py).
    3. Un appel d'outil resté sans résultat (coupure réseau en pleine demande) reçoit un résultat neutre,
       sinon l'API du modèle refuserait toute la conversation."""
    humans = [i for i, m in enumerate(messages) if m.type == "human"]
    if not humans:
        return list(messages)
    start = humans[-history_turns] if len(humans) > history_turns else humans[0]
    last_human = humans[-1]

    def kept(index: int, m: Any) -> Any:
        if m.type == "tool" and index < last_human:
            spec = toolbox.get(m.name or "")
            if spec is None or spec.open_world:
                return ToolMessage(content=REDACTED, tool_call_id=m.tool_call_id, name=m.name)
        return m

    out, i = [], start
    while i < len(messages):
        m = messages[i]
        out.append(kept(i, m))
        i += 1
        if m.type == "ai" and getattr(m, "tool_calls", None):
            answered = set()
            while i < len(messages) and messages[i].type == "tool":
                answered.add(messages[i].tool_call_id)
                out.append(kept(i, messages[i]))
                i += 1
            for call in m.tool_calls:
                if call["id"] not in answered:
                    out.append(ToolMessage(content=INTERRUPTED, tool_call_id=call["id"], name=call["name"]))
    return out


# ---------- le graphe ----------
def build_graph(model: Any, toolbox: Toolbox, *, facts: Callable[[], list[str]] = lambda: [],
                checkpointer: Any = None, max_steps: int = 6, history_turns: int = 8,
                language: str = "fr", city: str = "", llm_timeout: float = 30.0):
    """`model` : n'importe quel modèle de chat LangChain (ou un faux modèle dans les tests)."""
    llm = model.bind_tools(toolbox.as_llm_tools()) if toolbox.specs() else model

    async def agent(state: State) -> dict:
        turn = _TURN.get() or Turn()
        messages = state["messages"]
        rounds = rounds_since_human(messages)
        prompt = [SystemMessage(content=build_system_prompt(language=language, city=city, facts=facts()))]
        prompt += window(messages, toolbox, history_turns)
        started = time.perf_counter()
        try:
            reply = await asyncio.wait_for(llm.ainvoke(prompt), llm_timeout)
        except Exception as e:      # clé invalide, quota, réseau, délai dépassé : on termine proprement, sans planter le graphe
            reply = AIMessage(content=LLM_DOWN, additional_kwargs={"va_error": f"{type(e).__name__}: {e}"[:300]})
        turn.llm_ms += (time.perf_counter() - started) * 1000
        turn.llm_calls += 1
        if rounds >= max_steps and getattr(reply, "tool_calls", None):
            reply = AIMessage(content=TOO_MANY_STEPS)       # garde-fou contre une boucle d'outils sans fin
        return {"messages": [reply]}

    def after_agent(state: State) -> str:
        return "review" if getattr(state["messages"][-1], "tool_calls", None) else END

    def review(state: State) -> dict:
        """Nœud synchrone et sans effet de bord avant interrupt() : à la reprise, LangGraph le rejoue depuis le début."""
        tainted = bool(state.get("tainted"))
        flagged = []
        for call in state["messages"][-1].tool_calls:
            spec = toolbox.get(call["name"])
            if policy.needs_confirmation(spec, tainted):
                flagged.append((call, spec))
        if not flagged:
            return {"decision": {}}
        question = policy.confirmation_question([policy.describe(spec, call.get("args") or {}) for call, spec in flagged])
        answer = interrupt({"question": question, "tools": [call["name"] for call, _ in flagged]})
        said = answer.get("text", "") if isinstance(answer, dict) else str(answer)
        verdict = policy.parse_confirmation(said)
        if verdict is True:
            return {"decision": {}}
        note = policy.refusal_note(verdict, said)
        return {"decision": {call["id"]: note for call, _ in flagged}}

    async def tools(state: State) -> dict:
        turn = _TURN.get() or Turn()
        calls = state["messages"][-1].tool_calls
        refused = state.get("decision") or {}

        async def run(call: dict) -> tuple[ToolMessage, bool]:
            name, args, call_id = call["name"], call.get("args") or {}, call["id"]
            spec = toolbox.get(name)
            if call_id in refused or spec is None:
                content = refused.get(call_id) or f"L'outil {name} n'existe pas."
                return ToolMessage(content=content, tool_call_id=call_id, name=name,
                                   additional_kwargs={"va_executed": False}), False
            await turn.send({"type": "step", "tool": name, "label": spec.label})
            result = await toolbox.call(name, args)
            content = policy.wrap_untrusted(result.text) if spec.open_world else result.text
            return ToolMessage(content=content, tool_call_id=call_id, name=name,
                               additional_kwargs={"va_executed": True}), spec.open_world

        started = time.perf_counter()
        specs = [toolbox.get(c["name"]) for c in calls]
        if len(calls) > 1 and all(s is not None and s.read_only for s in specs):
            done = await asyncio.gather(*(run(c) for c in calls))      # des lectures : en parallèle, on gagne du temps
        else:
            done = [await run(c) for c in calls]                       # des actions : une par une, dans l'ordre demandé
        turn.tool_ms += (time.perf_counter() - started) * 1000
        return {"messages": [m for m, _ in done],
                "tainted": bool(state.get("tainted")) or any(untrusted for _, untrusted in done),
                "decision": {}}

    builder = StateGraph(State)
    builder.add_node("agent", agent)
    builder.add_node("review", review)
    builder.add_node("tools", tools)
    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", after_agent, {"review": "review", END: END})
    builder.add_edge("review", "tools")
    builder.add_edge("tools", "agent")
    return builder.compile(checkpointer=checkpointer or InMemorySaver())


class VoiceAgent:
    """Enveloppe le graphe : une méthode `run_turn(conversation, texte)` par phrase entendue."""

    def __init__(self, model: Any, toolbox: Toolbox, *, facts: Callable[[], list[str]] = lambda: [],
                 checkpointer: Any = None, max_steps: int = 6, history_turns: int = 8,
                 language: str = "fr", city: str = ""):
        self.toolbox = toolbox
        self.max_steps = max_steps
        self.graph = build_graph(model, toolbox, facts=facts, checkpointer=checkpointer, max_steps=max_steps,
                                 history_turns=history_turns, language=language, city=city)
        self._awaiting: set[str] = set()

    async def _pending_interrupts(self, config: dict) -> list | None:
        """Les questions en attente pour cette conversation, ou None si on n'a pas pu lire l'état."""
        try:
            snapshot = await self.graph.aget_state(config)
            found = list(getattr(snapshot, "interrupts", None) or [])
            for task in getattr(snapshot, "tasks", None) or []:
                found.extend(i for i in (getattr(task, "interrupts", None) or []) if i not in found)
            return found
        except Exception:
            return None

    async def run_turn(self, thread_id: str, text: str,
                       emit: Callable[[dict], Awaitable[None]] | None = None) -> TurnResult:
        config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 4 * self.max_steps + 12}
        pending = await self._pending_interrupts(config)
        waiting = bool(pending) if pending is not None else thread_id in self._awaiting
        if waiting:
            payload: Any = Command(resume={"text": text})       # la phrase est la réponse à la question posée
        else:
            payload = {"messages": [HumanMessage(content=text)], "tainted": False, "decision": {}}

        turn = Turn(emit=emit)
        token = _TURN.set(turn)
        started = time.perf_counter()
        try:
            result = await self.graph.ainvoke(payload, config)
        finally:
            _TURN.reset(token)
        self._awaiting.discard(thread_id)

        messages = result.get("messages") or []
        timings = {"llm_ms": round(turn.llm_ms), "llm_calls": turn.llm_calls, "tool_ms": round(turn.tool_ms),
                   "agent_ms": round((time.perf_counter() - started) * 1000)}
        tools_used = [self.toolbox.label(n) for n in executed_tools(messages)]

        interrupts = list(result.get("__interrupt__") or []) or (await self._pending_interrupts(config) or [])
        if interrupts:
            self._awaiting.add(thread_id)
            value = getattr(interrupts[0], "value", interrupts[0])
            question = value.get("question", "") if isinstance(value, dict) else str(value)
            return TurnResult("confirm", question or "Tu confirmes ?", tools_used, timings)

        last = messages[-1] if messages else None
        error = (getattr(last, "additional_kwargs", None) or {}).get("va_error", "")
        reply = clean_for_speech(text_of(last)) or "C'est fait."
        return TurnResult("result", reply, tools_used, timings, error)
