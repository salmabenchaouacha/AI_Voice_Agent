"""API + WebSocket de l'assistant vocal.

Le navigateur envoie de l'audio (ou du texte) sur /ws ; le serveur transcrit avec Whisper,
exécute la commande sur CETTE machine et renvoie la réponse en JSON."""
import asyncio
import io
import json
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
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
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_TEXT_CHARS = 500


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
    yield


app = FastAPI(title="Assistant vocal", lifespan=lifespan)
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


def transcribe_bytes(data: bytes) -> str:
    try:
        from stt import transcribe
        return transcribe(io.BytesIO(data))
    except Exception as e:
        print(f"Erreur de transcription : {e}")
        return ""


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

            if msg.get("bytes") is not None:                       # audio du micro
                source, data = "voice", msg["bytes"]
                if len(data) > MAX_AUDIO_BYTES:
                    heard = ""
                else:
                    heard = await asyncio.to_thread(transcribe_bytes, data)
            elif msg.get("text"):                                  # commande tapée
                source = "text"
                try:
                    heard = str(json.loads(msg["text"]).get("text", "")).strip()[:MAX_TEXT_CHARS]
                except (ValueError, AttributeError):
                    heard = ""
            else:
                continue

            reply = await asyncio.to_thread(run_command, heard) if heard else "Je n'ai rien compris. Réessaie."
            await ws.send_json({"type": "result", "source": source, "heard": heard, "reply": reply})
    except WebSocketDisconnect:
        pass


# Version « production » : après `npm run build`, FastAPI sert aussi le front sur le port 8000
DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if DIST.exists():
    app.mount("/", StaticFiles(directory=DIST, html=True), name="front")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=int(os.getenv("VA_PORT", "8000")))