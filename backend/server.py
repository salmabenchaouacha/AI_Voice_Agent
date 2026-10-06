"""API + WebSocket de l'assistant vocal.

Le navigateur envoie de l'audio (ou du texte) sur /ws ; le serveur transcrit avec Whisper, confie la phrase
à l'assistant (agent LangGraph + outils MCP, ou regex en mode hors-ligne) et renvoie la réponse en JSON.

Messages envoyés au navigateur :
  {"type": "step", "tool", "label"}                    un outil est en cours d'appel (affiché pendant l'attente)
  {"type": "confirm", "heard", "reply"}                l'assistant demande un oui / non avant d'agir
  {"type": "result", "heard", "reply", "tools", …}     réponse finale
  {"type": "notification", "text"}                     événement spontané (fin d'un minuteur)"""
import asyncio
import io
import json
import os
import re
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

import metrics
import notifier
import skills  # noqa: F401  (enregistre les commandes du mode hors-ligne)
from agent.runtime import Assistant, run_offline
from config import LANGUAGE

# Sécurité : ce serveur pilote ton ordinateur. Seules ces origines peuvent l'appeler
# (les WebSockets ne sont PAS protégés par CORS, on vérifie donc l'en-tête Origin nous-mêmes).
ALLOWED_ORIGINS = set(os.getenv(
    "VA_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
).split(","))
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 500
SESSION_RE = re.compile(r"[\w-]{6,64}")     # identifiant de conversation choisi par le navigateur

assistant = Assistant()


def origin_ok(origin) -> bool:
    return origin is None or origin in ALLOWED_ORIGINS   # None : client non-navigateur (curl, tests)


def require_origin(request: Request) -> None:
    if not origin_ok(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origine non autorisée")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if os.getenv("VA_PRELOAD", "1") == "1":
        print("Chargement du modèle Whisper (au premier lancement, il est téléchargé)…")
        from stt import load
        await asyncio.to_thread(load)
        print("Modèle prêt.")
    await assistant.start()                  # lance les serveurs MCP et compile le graphe, si un LLM est configuré
    if assistant.mode == "agent":
        print(f"Mode agent : {len(assistant.agent.toolbox.specs())} outils disponibles.")
    else:
        print(f"Mode hors-ligne (regex) : {assistant.reason}.")
    try:
        yield
    finally:
        await assistant.stop()


app = FastAPI(title="Assistant vocal", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


run_command = run_offline   # ancien nom, gardé pour compatibilité


async def answer(heard: str, session: str, source: str, emit=None, stt_ms: int = 0) -> dict:
    """Fait traiter une phrase par l'assistant, enregistre les mesures, et prépare le message pour le navigateur."""
    started = time.perf_counter()
    out = await assistant.handle(heard, session, emit)
    timings = {**out.get("timings", {}), "stt_ms": stt_ms,
               "total_ms": stt_ms + round((time.perf_counter() - started) * 1000)}
    metrics.record({"mode": out["mode"], "type": out["type"], "source": source, "tools": out["tools"], **timings})
    return {"type": out["type"], "source": source, "heard": heard, "reply": out["reply"],
            "tools": out["tools"], "mode": out["mode"], "timings": timings}


def transcribe_bytes(data: bytes) -> str:
    try:
        from stt import transcribe
        return transcribe(io.BytesIO(data))
    except Exception as e:
        print(f"Erreur de transcription : {e}")
        return ""


class Command(BaseModel):
    text: str
    session: str = "rest"


@app.get("/api/config", dependencies=[Depends(require_origin)])
def get_config():
    return {"language": LANGUAGE}


@app.post("/api/command", dependencies=[Depends(require_origin)])
async def post_command(cmd: Command):
    text = cmd.text.strip()[:MAX_TEXT_CHARS]
    if not text:
        raise HTTPException(status_code=400, detail="Commande vide")
    session = cmd.session if SESSION_RE.fullmatch(cmd.session) else "rest"
    out = await answer(text, session, "text")
    return {"heard": text, "reply": out["reply"], "type": out["type"], "tools": out["tools"], "mode": out["mode"]}


@app.get("/api/status", dependencies=[Depends(require_origin)])
def get_status():
    """Mode actif, modèle, outils découverts (et auprès de quel serveur MCP), règle de confirmation de chacun."""
    return assistant.status()


@app.get("/api/metrics", dependencies=[Depends(require_origin)])
def get_metrics():
    return metrics.summary()


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if not origin_ok(ws.headers.get("origin")):
        await ws.close(code=1008)
        return
    await ws.accept()
    # Une conversation par navigateur : l'identifiant sert de thread_id au checkpointer de LangGraph.
    session = ws.query_params.get("session", "")
    if not SESSION_RE.fullmatch(session):
        session = uuid.uuid4().hex

    queue: asyncio.Queue = asyncio.Queue()
    unsubscribe = notifier.subscribe(asyncio.get_running_loop(), queue)

    async def forward_notifications():
        while True:
            await ws.send_json({"type": "notification", "text": await queue.get()})

    pump = asyncio.create_task(forward_notifications())
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break

            stt_ms = 0
            if msg.get("bytes") is not None:                       # audio du micro
                source, data = "voice", msg["bytes"]
                if len(data) > MAX_AUDIO_BYTES:
                    heard = ""
                else:
                    started = time.perf_counter()
                    heard = await asyncio.to_thread(transcribe_bytes, data)
                    stt_ms = round((time.perf_counter() - started) * 1000)
            elif msg.get("text"):                                  # commande tapée
                source = "text"
                try:
                    heard = str(json.loads(msg["text"]).get("text", "")).strip()[:MAX_TEXT_CHARS]
                except (ValueError, AttributeError):
                    heard = ""
            else:
                continue

            if not heard:
                await ws.send_json({"type": "result", "source": source, "heard": heard,
                                    "reply": "Je n'ai rien compris. Réessaie."})
                continue
            await ws.send_json(await answer(heard, session, source, emit=ws.send_json, stt_ms=stt_ms))
    except WebSocketDisconnect:
        pass
    finally:
        pump.cancel()
        unsubscribe()


# Version « production » : après `npm run build`, FastAPI sert aussi le front sur le port 8000
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="front")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("VA_PORT", "8000")))