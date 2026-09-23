"""API + WebSocket de l'assistant vocal.

Le navigateur envoie de l'audio (ou du texte) sur /ws ; le serveur transcrit avec Whisper,
exécute la commande sur CETTE machine et renvoie la réponse en JSON."""
import asyncio
import json
import os

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import skills  # noqa: F401  (enregistre les commandes)
from config import LANGUAGE
from router import QuitAssistant, dispatch

# Sécurité : ce serveur pilote ton ordinateur. Seules ces origines peuvent l'appeler
# (les WebSockets ne sont PAS protégés par CORS, on vérifie donc l'en-tête Origin nous-mêmes).
ALLOWED_ORIGINS = set(os.getenv(
    "VA_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173,http://localhost:8000,http://127.0.0.1:8000",
).split(","))
MAX_TEXT_CHARS = 500


def origin_ok(origin) -> bool:
    return origin is None or origin in ALLOWED_ORIGINS   # None : client non-navigateur (curl, tests)


def require_origin(request: Request) -> None:
    if not origin_ok(request.headers.get("origin")):
        raise HTTPException(status_code=403, detail="Origine non autorisée")


app = FastAPI(title="Assistant vocal")
app.add_middleware(
    CORSMiddleware,
    allow_origins=sorted(ALLOWED_ORIGINS),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


def run_command(text: str) -> str:
    try:
        return dispatch(text)
    except QuitAssistant as e:
        return str(e)
    except Exception as e:  # une commande qui plante ne doit pas tuer le serveur
        return f"Une erreur est survenue : {e}"


class Command(BaseModel):
    text: str


@app.get("/api/config", dependencies=[Depends(require_origin)])
def get_config():
    return {"language": LANGUAGE}


@app.post("/api/command", dependencies=[Depends(require_origin)])
async def post_command(cmd: Command):
    text = cmd.text.strip()[:MAX_TEXT_CHARS]
    if not text:
        raise HTTPException(status_code=400, detail="Commande vide")
    return {"heard": text, "reply": await asyncio.to_thread(run_command, text)}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    if not origin_ok(ws.headers.get("origin")):
        await ws.close(code=1008)
        return
    await ws.accept()
    try:
        while True:
            msg = await ws.receive()
            if msg["type"] == "websocket.disconnect":
                break
            if not msg.get("text"):
                continue
            try:
                heard = str(json.loads(msg["text"]).get("text", "")).strip()[:MAX_TEXT_CHARS]
            except (ValueError, AttributeError):
                heard = ""
            reply = await asyncio.to_thread(run_command, heard) if heard else "Je n'ai rien compris. Réessaie."
            await ws.send_json({"type": "result", "source": "text", "heard": heard, "reply": reply})
    except WebSocketDisconnect:
        pass