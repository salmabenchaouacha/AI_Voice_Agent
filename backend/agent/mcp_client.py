"""Client MCP : lance les serveurs listés dans mcp.json, garde les connexions ouvertes et expose leurs outils.

Pourquoi des connexions gardées ouvertes : démarrer un serveur stdio coûte plusieurs centaines de millisecondes,
un appel sur une connexion déjà ouverte quelques millisecondes. Pour un assistant vocal, la différence s'entend.

Le fichier mcp.json a le même format que celui de Claude Desktop ou de Cursor : on peut y brancher
n'importe quel serveur MCP existant (fichiers, agenda, GitHub…) sans toucher au code de l'agent.
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters

from .toolbox import Toolbox, ToolResult, ToolSpec

CONNECT_TIMEOUT = 20.0


def load_config(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        servers = json.load(f).get("mcpServers", {})
    return {name: cfg for name, cfg in servers.items() if cfg.get("enabled", True)}


def _target(cfg: dict, base_dir: Path):
    """Ce qu'on passe à mcp.Client : une URL (serveur HTTP distant) ou la commande d'un serveur local."""
    if cfg.get("url"):
        return cfg["url"]
    command = cfg["command"]
    if command in ("python", "python3"):          # le même Python que l'assistant (donc le même environnement virtuel)
        command = sys.executable
    return StdioServerParameters(command=command, args=list(cfg.get("args", [])),
                                 env={**os.environ, **cfg.get("env", {})},
                                 cwd=str(base_dir / cfg["cwd"]) if cfg.get("cwd") else str(base_dir))


def spec_from_mcp(server: str, tool) -> ToolSpec:
    """Traduit la description MCP d'un outil. Un outil sans annotations est traité comme le veut la
    spécification : supposé modifier le système, destructif et ouvert sur l'extérieur, donc à confirmer."""
    a = tool.annotations
    meta = tool.meta or {}
    read_only = bool(a.read_only_hint) if a and a.read_only_hint is not None else False
    return ToolSpec(
        name=tool.name,
        description=(tool.description or tool.title or tool.name).strip(),
        schema=tool.input_schema or {"type": "object", "properties": {}},
        source=server,
        read_only=read_only,
        destructive=False if read_only else (a.destructive_hint if a and a.destructive_hint is not None else True),
        open_world=a.open_world_hint if a and a.open_world_hint is not None else True,
        label=str(meta.get("va/label") or tool.title or tool.name),
        action=str(meta.get("va/action") or ""),
    )


class MCPManager:
    def __init__(self, servers: dict, base_dir: str | Path = "."):
        self.servers = servers
        self.base_dir = Path(base_dir)
        self.errors: dict[str, str] = {}          # serveur -> raison de l'échec de connexion
        self.tools: dict[str, list] = {}          # serveur -> outils MCP découverts
        self._clients: dict[str, Client] = {}
        self._tasks: list[asyncio.Task] = []
        self._stop: asyncio.Event | None = None

    @classmethod
    def from_file(cls, path: str) -> "MCPManager":
        return cls(load_config(path), base_dir=Path(path).resolve().parent)

    async def _serve(self, name: str, cfg: dict, ready: asyncio.Future) -> None:
        """Une tâche par serveur : elle ouvre la connexion, la garde, et la referme elle-même à l'arrêt.
        (Une connexion MCP doit être ouverte et fermée par la même tâche asyncio.)"""
        try:
            async with Client(_target(cfg, self.base_dir)) as client:
                tools = (await client.list_tools()).tools
                self._clients[name] = client
                ready.set_result(tools)
                await self._stop.wait()
        except Exception as e:
            if not ready.done():
                ready.set_exception(e)
        finally:
            self._clients.pop(name, None)

    async def start(self) -> None:
        self._stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        pending = {}
        for name, cfg in self.servers.items():
            pending[name] = loop.create_future()
            self._tasks.append(asyncio.create_task(self._serve(name, cfg, pending[name]), name=f"mcp:{name}"))
        for name, ready in pending.items():       # un serveur en panne n'empêche pas les autres de démarrer
            try:
                self.tools[name] = await asyncio.wait_for(ready, CONNECT_TIMEOUT)
            except Exception as e:
                while getattr(e, "exceptions", None):          # anyio regroupe les erreurs : on garde la cause réelle
                    e = e.exceptions[0]
                self.errors[name] = f"{type(e).__name__}: {e}".rstrip(": ")

    async def stop(self) -> None:
        if self._stop:
            self._stop.set()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()

    async def __aenter__(self) -> "MCPManager":
        await self.start()
        return self

    async def __aexit__(self, *exc) -> None:
        await self.stop()

    async def call(self, server: str, tool: str, args: dict) -> ToolResult:
        client = self._clients.get(server)
        if client is None:
            return ToolResult(f"Le serveur {server} n'est plus connecté.", is_error=True)
        result = await client.call_tool(tool, args)
        text = "\n".join(c.text for c in (getattr(result, "content", None) or []) if getattr(c, "type", "") == "text")
        return ToolResult(text.strip() or "C'est fait.", is_error=bool(getattr(result, "is_error", False)))

    def register_into(self, toolbox: Toolbox) -> None:
        for server, tools in self.tools.items():
            for tool in tools:
                def runner(args, _server=server, _tool=tool.name):
                    return self.call(_server, _tool, args)
                toolbox.register(spec_from_mcp(server, tool), runner)
