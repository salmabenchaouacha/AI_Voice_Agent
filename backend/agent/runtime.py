"""Assemble l'assistant au démarrage du serveur et traite chaque phrase.

Deux modes, choisis une fois au démarrage :
  - "agent"   : LangGraph + outils MCP, si les bibliothèques sont installées et qu'un LLM est configuré ;
  - "offline" : le routeur à regex d'origine. C'est aussi le repli si le modèle devient injoignable en cours de route.
"""
import asyncio

import config
import llm
from router import QuitAssistant, dispatch


def run_offline(text: str) -> str:
    try:
        return dispatch(text)
    except QuitAssistant as e:
        return str(e)
    except Exception as e:  # une commande qui plante ne doit pas tuer le serveur
        return f"Une erreur est survenue : {e}"


class Assistant:
    def __init__(self):
        self.agent = None
        self.mcp = None
        self.mode = "offline"
        self.reason = "agent désactivé (VA_AGENT=off)"

    # ---------- cycle de vie ----------
    async def start(self) -> None:
        if config.AGENT_MODE == "off":
            return
        key = llm.missing_key()
        if key:
            self.reason = f"variable {key} absente : pas de modèle de langage"
            return
        try:
            from .graph import VoiceAgent
            from .local_tools import register_local_tools
            from .mcp_client import MCPManager
            from .memory import Memory
            from .toolbox import Toolbox

            model = llm.get_chat_model()
            toolbox = Toolbox(timeout=config.TOOL_TIMEOUT)
            memory = Memory(config.MEMORY_FILE)
            register_local_tools(toolbox, memory)
            self.mcp = MCPManager.from_file(config.MCP_CONFIG)
            await self.mcp.start()
            self.mcp.register_into(toolbox)
            self.agent = VoiceAgent(model, toolbox, facts=memory.facts, max_steps=config.MAX_STEPS,
                                    history_turns=config.HISTORY_TURNS, language=config.LANGUAGE,
                                    city=config.DEFAULT_CITY)
            self.mode, self.reason = "agent", ""
        except Exception as e:      # bibliothèque absente, mcp.json invalide… : l'assistant reste utilisable
            await self.stop()
            self.agent = None
            self.reason = f"agent indisponible ({type(e).__name__}: {e})"

    async def stop(self) -> None:
        if self.mcp:
            await self.mcp.stop()
            self.mcp = None

    def status(self) -> dict:
        info = {"mode": self.mode, "reason": self.reason}
        if self.agent:
            info["model"] = config.LLM
            info["tools"] = [{"name": s.name, "source": s.source, "label": s.label,
                              "confirmation": "toujours" if s.destructive else "jamais" if s.read_only else "après contenu web"}
                             for s in self.agent.toolbox.specs()]
            info["mcp_errors"] = dict(self.mcp.errors) if self.mcp else {}
        return info

    # ---------- une phrase ----------
    async def handle(self, text: str, session: str = "default", emit=None) -> dict:
        """Retourne {"type": "result" | "confirm", "reply", "tools", "mode", "timings"}."""
        if self.agent:
            try:
                turn = await self.agent.run_turn(session, text, emit)
            except Exception as e:
                turn = None
                error = f"{type(e).__name__}: {e}"
            else:
                error = turn.error
                if not (error and not turn.tools):
                    return {"type": turn.kind, "reply": turn.reply, "tools": turn.tools, "mode": "agent",
                            "timings": turn.timings, **({"error": error} if error else {})}
            # Le modèle n'a pas répondu et rien n'a été exécuté : la même phrase passe par les regex.
            reply = await asyncio.to_thread(run_offline, text)
            return {"type": "result", "reply": reply, "tools": [], "mode": "offline", "timings": {}, "error": error}
        reply = await asyncio.to_thread(run_offline, text)
        return {"type": "result", "reply": reply, "tools": [], "mode": "offline", "timings": {}}
